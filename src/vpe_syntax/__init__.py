"""Provide syntax highlighting using Tree-sitter.

This uses the vps_sitter
This plugin maintains a Tree-sitter parse tree for each buffer that
has a supported language.

Dependencies:
    vpe_sitter - attaches and maintains the parse tree for each buffer.
"""
from __future__ import annotations

from typing import ClassVar

import vpe
from vpe import EventHandler, vim

import vpe_sitter
from vpe_sitter.listen import Listener
from vpe_syntax import core, hl_groups, scheme_tweaker


class Plugin(vpe.CommandHandler, EventHandler):
    """The plug-in."""

    initalised: ClassVar[bool] = False
    highlights: ClassVar[dict[str, hl_groups.Highlight]] = {}

    def __init__(self, *args, **kwargs):
        # create_text_prop_types()
        super().__init__(*args, **kwargs)
        self.highlighters: dict[int, core.Highlighter] = {}
        self.auto_define_commands()
        self.auto_define_event_handlers('VPE_SyntaxEventGroup')

    @vpe.CommandHandler.command('Syntaxsit')
    def run(self):
        """Execute the Syntaxsit command.

        Starts running Tree-sitter syntax highlighting on the current buffer.
        """
        if not vpe_sitter.treesit_current_buffer():
            print('Tree-sitter base syntax highlighting is not possible.')
            return

        # Make sure that syntax highlighting is activated, but clear any syntax
        # for the current buffer.
        vim.command('syntax clear')
        if not vim.exists('g:syntax_on'):
            vim.command('syntax enable')
        self._lazy_init()

        # Create a Highlighter connected to the buffer's `Listener` and add to
        # the buffer store.
        buf = vim.current.buffer
        listener: Listener = buf.store('tree-sitter').listener
        store = buf.store('syntax-sitter')
        store.highlighter = core.Highlighter(buf, listener)

    @vpe.CommandHandler.command('Syntweak')
    def show_scheme(self):
        """"Show scheme tweaker in a split window."""
        scheme_tweaker.show()

    @EventHandler.handle('WinResized')
    @EventHandler.handle('WinScrolled')
    def handle_window_change(self, *args, **kwargs) -> None:
        """Take action when some windows have scrolled or resized."""
        event = vim.vvars.event
        win_id: str
        for win_id in event:
            if win_id == 'all':
                continue
            window = vpe.Window.win_id_to_window(win_id)
            if window is None:
                continue
            buffer = window.buffer
            if buffer.name.startswith('/[['):
                continue

            # print(f'WinScrolled: {buffer.name}')
            store = buffer.store('syntax-sitter')
            highlighter = getattr(store, 'highlighter', None)
            if highlighter is not None:
                highlighter.handle_window_scrolled(vim.getwininfo(win_id)[0])

    @classmethod
    def _lazy_init(cls) -> None:
        """Perform lazy initialisation.

        This exists to allow other Vim plugin and initalisation code to run
        first.
        """
        if cls.initalised:
            return
        cls.initalised = True
        cls.highlights = hl_groups.highlights


app = Plugin()
