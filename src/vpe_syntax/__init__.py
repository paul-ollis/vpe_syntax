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
from vpe.user_commands import (
    CommandHandler, Namespace, TopLevelSubcommandHandler)

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

    syn_path = Path(vpe.dot_vim_dir()) / f'plugin/vpe_syntax/{filetype}.syn'
    if syn_path.is_file():
        traversables.append(syn_path)

    return traversables


def _user_config_dirpath() -> Path:
    return Path(vpe.dot_vim_dir()) / 'plugin/vpe_syntax'


def _std_config_dirpath() -> Path:
    syn_trav: Traversable = files('vpe_syntax.resources')
    text = str(syn_trav)
    path_name = text.split("'")[1]
    return Path(path_name)


class ConfDirCommand(CommandHandler):
    """The 'Synsit confdir' command implementation."""

    def add_arguments(self) -> None:
        """Add the arguments for this command."""
        self.parser.add_argument(
            '--user', action='store_true',
            help="Show the user (rather than installation) directory.")

    def handle_command(self, args: Namespace):
        """Handle the 'Synsit confdir' command."""
        if args.user:
            vpe.echo_msg(str(_user_config_dirpath()))
        else:
            vpe.echo_msg(str(_std_config_dirpath()))


class OpenConfigCommand(CommandHandler):
    """The 'Synsit openconfig ...' command implementation."""

    def add_arguments(self) -> None:
        """Add the arguments for this command."""
        self.parser.add_argument(
            '--std', action='store_true',
            help="Open the standard file from the installation.")
        self.parser.add_argument(
            'conf_file_name',
            help="The name of the language.")

    def handle_command(self, args: Namespace):
        """Handle the 'Synsit confdir' command."""
        config_dir = Path(vpe.dot_vim_dir()) / 'plugin/vpe_syntax'
        if not config_dir.is_dir():
            try:
                config_dir.mkdir(parents=True)
            except OSError:
                vpe.log(
                    f'{config_dir} is not a directory and could not be'
                    ' created!')

        if args.std:
            conf_path = _std_config_dirpath() / args.conf_file_name
            if not conf_path.is_file():
                vpe.error_msg(
                    f'There is no {args.conf_file_name} installed.')
                return

            vpe.commands.view(f'{conf_path}')
            vim.current.buffer.options.modifiable = False
        else:
            conf_path = config_dir / args.conf_file_name
            vpe.commands.edit(f'{conf_path}')
            if not conf_path.is_file():
                text = '# Tree structure                   Property name'
                vim.current.buffer[:] = [text]


class Plugin(TopLevelSubcommandHandler):
    """The plug-in."""

    initalised: ClassVar[bool] = False
    highlights: ClassVar[dict[str, hl_groups.Highlight]] = {}
    subcommands = {
        'on': (
            ':simple', 'Turn on syntax highlighting for the current buffer.'),
        'openconfig':
            (OpenConfigCommand, 'Open the user configuration file.'),
        'tweak': (
            ':simple', 'Open highlight tweaker.'),
        'rebuild': (
            ':simple', 'Rebuild syntax tables and highlighing.'),
        'confdir': (ConfDirCommand, 'Display a configuration directory name.'),
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
            store.highlighter.ensure_minimal_syntax()
            return

        if msg := vpe_sitter.treesit_current_buffer():
            vpe.error_msg(msg)
            return

        # Check that the current buffer is using a supported language.
        filetype = buf.options.filetype
        traversables: list[Traversable] = find_language_syntax_files(filetype)
        if not traversables:
            s = [f'No {filetype}.syn file found in:']
            s.append(f'    {_std_config_dirpath()}')
            s.append(f'    {_user_config_dirpath()}')
            vpe.log('\n'.join(s))
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
        self._lazy_init()

        # Create a Highlighter connected to the buffer's `Listener` and add to
        # the buffer store.
        buf = vim.current.buffer
        listener: Listener = buf.store('tree-sitter').listener
        store = buf.store('syntax-sitter')
        store.highlighter = core.Highlighter(buf, listener)
        store.highlighter.ensure_minimal_syntax()

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
