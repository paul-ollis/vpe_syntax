"""Provide syntax highlighting using Tree-sitter.

This uses the vps_sitter
This plugin maintains a Tree-sitter parse tree for each buffer that
has a supported language.

Dependencies:
    vim-vpe    - The Vim Python Extensions.
    vpe_sitter - Attaches and maintains the parse tree for each buffer.
"""
from __future__ import annotations

# TODO:
#   Probably need to do recreate tree after a buffer load (e.g. after external
#   changes).

from importlib.resources import files
from importlib.resources.abc import Traversable
from pathlib import Path
from typing import ClassVar

import vpe
from vpe import vim
from vpe.user_commands import Namespace, TopLevelSubcommandHandler

import vpe_sitter
from vpe_sitter.listen import Listener
from vpe_syntax import core, hl_groups, scheme_tweaker
from vpe_syntax.core import EmbeddedHighlighter, NestedCodeBlockSpec


def register_embedded_language(
        filetype: str,
        embedded_type: str,
        highlighter: EmbeddedHighlighter,
    ) -> None:
    """Register an `EmbeddedHighlighter` object.

    :filetype:
        The language name of the parent file.
    :embedded_type:
        The language name of embdedded code.
    :highlighter:
        A `EmbeddedHighlighter` that finds embedded code.
    """
    core.embedded_syntax_handlers[(filetype, embedded_type)] = highlighter


def find_language_syntax_files(filetype: str) -> list[Traversable]:
    """Find built-in and user defined syntax files for a given filetype.

    :return:
        A list of `Traversable` objects for the given language in priority
        order, lowest to highest. An empty list indicates that the langhuag is
        not supported.
    """

    traversables = []
    syn_trav: Traversable = files(
        'vpe_syntax.resources').joinpath(f'{filetype}.syn')
    if syn_trav.is_file():
        traversables.append(syn_trav)

    syn_path = Path.home() / f'.vim/plugin/vpe_syntax/{filetype}.syn'
    if syn_path.is_file():
        traversables.append(syn_path)

    return traversables


class Plugin(TopLevelSubcommandHandler):
    """The plug-in."""

    initalised: ClassVar[bool] = False
    highlights: ClassVar[dict[str, hl_groups.Highlight]] = {}
    subcommands = {
        'on': (
            ':simple', 'Turn on syntax highlighting for the current buffer.'),
        'tweak': (
            ':simple', 'Open highlight tweaker.'),
        'rebuild': (
            ':simple', 'Rebuild syntax tables and highlighing.'),
    }

    def __init__(self, *args, **kwargs):
        # create_text_prop_types()
        super().__init__(*args, **kwargs)
        self.highlighters: dict[int, core.Highlighter] = {}

    def handle_on(self, _args: Namespace) -> None:
        """Execute the 'Synsit on' command.

        Starts running Tree-sitter syntax highlighting on the current buffer.
        """
        buf = vim.current.buffer
        store = buf.retrieve_store('syntax-sitter')
        if store is not None:
            # Syntax highlighting is already active.
            return

        if msg := vpe_sitter.treesit_current_buffer():
            vpe.error_msg(msg)
            return

        # Check that the current buffer is using a supported language.
        filetype = buf.options.filetype
        traversables: list[Traversable] = find_language_syntax_files(filetype)
        if not traversables:
            vpe.error_msg(
                f'Tree-sitter syntax not defined for {filetype}.')
            return

        # pylint: disable=import-outside-toplevel
        # from vpe_syntax.language_nesting import MyEmbeddedHighlighter
        # TODO:
        #   This needs to be performed in a lazy manner, under a user's
        #   control (e.g. in .vim/after/ftplugin/<lang>.vim).
        #register_embedded_language(
        #    'python', 'python', MyEmbeddedHighlighter('python'))

        # Build the supporting tables.
        core.build_tables(filetype, traversables)

        # Make sure that syntax highlighting is activated, but clear any syntax
        # for the current buffer. Then add a 'dummy' Spell cluster so that Vim
        # will do limited spell checking.
        vim.command('syntax clear')
        vim.command('syntax cluster Spell contains=NothingToSeeHere')
        if not vim.exists('g:syntax_on'):
            vim.command('syntax enable')
        self._lazy_init()

        # Create a Highlighter connected to the buffer's `Listener` and add to
        # the buffer store.
        buf = vim.current.buffer
        listener: Listener = buf.store('tree-sitter').listener
        store = buf.store('syntax-sitter')
        store.highlighter = core.Highlighter(buf, listener)

    def handle_tweak(self, _args: Namespace):
        """Execute the 'Synsit tweak' command.

        Show scheme tweaker in a split window."""
        scheme_tweaker.show()

    def handle_rebuild(self, _args: Namespace):
        """Execute the 'Synsit rebuild' command."""
        buf = vim.current.buffer
        store = buf.retrieve_store('syntax-sitter')
        if store is None:
            vpe.error_msg(
                'Current buffer is not using vpe_syntax highlighting.')
            return

        # Rebuild the highlighting tables.
        filetype = buf.options.filetype
        traversables: list[Traversable] = find_language_syntax_files(filetype)
        core.build_tables(filetype, traversables, rebuild=True)

    @classmethod
    def _lazy_init(cls) -> None:
        """Perform lazy initialisation.

        This exists to allow other Vim/plugin initalisation code to run first.
        """
        if cls.initalised:
            return
        cls.initalised = True
        cls.highlights = hl_groups.highlights


app = Plugin('Synsit')

_CUR_PROP = """
def! Vpe_syntax_cursor_prop(): string
    var props = prop_list(line('.'))
    var col = col('.')
    var found = []
    for prop in props
        var pcol = prop['col']
        var plen = prop['length']
        if pcol <= col && (pcol + plen) > col
            call add(found, get(prop, 'type', '-'))
        endif
    endfor
    return string(found)
enddef
"""

vim.command(_CUR_PROP)
