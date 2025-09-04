"""A simple interactive syntax scheme tweaker."""
from __future__ import annotations

import re
from collections.abc import Sequence
from functools import partial
from itertools import chain
from typing import ClassVar, Final
from weakref import proxy

import vpe
from vpe import vim
from vpe.mapping import KeyHandler

from vpe_syntax import hl_groups, web_colours
from vpe_syntax.hl_groups import (
    Colour, ColourTermSettings, GUISettings, Highlight, NamedColour,
    TermSettings)

APP_NAME = 'VPE_sysntax_tweaker'

nmapped = partial(KeyHandler.mapped, mode='normal')

if vim.options.background == 'dark':
    alt_bg_colour = '#ffffff'
else:
    alt_bg_colour = '#000000'
TWEAKER_GROUPS: dict[str, dict] = {
    'CloseFGColour':      {'priority': 50, 'fg':  'White',},
    'CloseBGColour':      {'priority': 50, 'fg':  'White',},
    'CloseSPColour':      {'priority': 50, 'fg':  'White',},
    'Hotkey':             {'priority': 50, 'fg':  'SeaGreen',
                                           'gui': 'Bold'},
    'Label':              {'priority': 50, 'fg':  'DarkGoldenrod',},
    'Template':           {'priority': 50, 'fg':  'DarkGoldenrod',},
    'LightBG':            {'priority': 50, 'bg':  'White',},
    'DarkBG':             {'priority': 50, 'bg':  'Black',},
}

command_to_highlight_flag = {
    'tb': 'bold',
    'tc': 'undercurl',
    'ti': 'italic',
    'to': 'standout',
    'tr': 'reverse',
    'ts': 'strikethrough',
    'tu': 'underline',
}


class ColourPopup(vpe.Popup):
    """A popup window used to select a colour."""

    def __init__(
            self, *, parent: Tweaker, **kwargs):
        super().__init__('', name='Colour Palette', **kwargs)
        self.parent = parent

    def on_key(self, key: str, byte_seq: bytes) -> bool:
        """Process a key or mouse event for the popup window."""
        if key in ('<ScrollWheelUp>', '<ScrollWheelDown>'):
            return False
        elif key == '<Esc>':
            self.hide()
            return True
        elif key != '<LeftMouse>':
            return True

        mouse_info = vim.getmousepos()
        if mouse_info['winid'] != self.id:
            return True

        lidx = mouse_info['line'] - 1
        colour_name = self.buffer[lidx].split()[0]

        self.hide()
        self.parent.complete_handle_choose_colour(colour_name)
        return True


class TweakerBuffer(vpe.ScratchBuffer):
    """A display buffer for the syntax tweaker."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.create_properties()

    def create_properties(self):
        """Create the property (types) used within this buffer."""
        kw = {
            'priority': 50,
            'combine': False,       # Over-ride normal syntax highlighting.
            'start_incl': False,    # Do not extend for inserts at the start.
            'end_incl': False,      # Do not extend for inserts at the end.
            'bufnr': self.number,
        }
        for name, data in TWEAKER_GROUPS.items():
            kw['priority'] = data.get('priority', 50)
            name = f'Tweaker_{name}'
            kw['highlight'] = name
            known_prop_info = vim.prop_type_get(name)
            if not known_prop_info:
                vim.prop_type_add(name, kw)

    def highlight(self, prop_name: str, pattern: str) -> None:
        """Highlight text within this buffer using the given property."""
        cp = re.compile(pattern)
        for i, line in enumerate(self):
            for m in cp.finditer(line):
                a, b = m.span()
                kw = {
                    'bufnr': self.number,
                    'end_col': b + 1,
                    'type': prop_name,
                }
                vim.prop_add(i + 1, a + 1, kw)

    def highlight_line(
            self, lidx, props: Sequence[tuple[str, int, int]],
        ) -> None:
        """Set the propery highlights for a line."""
        vim.prop_clear(lidx + 1)
        for prop_name, start_col, end_col in props:
            kw = {
                'bufnr': self.number,
                'end_col': end_col + 1,
                'type': prop_name,
            }
            vim.prop_add(lidx + 1, start_col + 1, kw)


class Tweaker(vpe.CommandHandler, KeyHandler):
    """The tweaker contol object."""

    def __init__(self):
        self.buf: vpe.ScratchBuffer = vpe.get_display_buffer(
            APP_NAME, buf_class=TweakerBuffer)
        self.cursor = 'fg'
        self.backups: dict[str, Highlight] = {}
        self.widgets = {}
        self.highlight: Highlight = hl_groups.highlights['Comment']
        self._create_widgets()
        with self.buf.modifiable():
            self.buf[:] = [''] * 20
        self.layout_buffer()
        with vpe.temp_active_buffer(self.buf):
            self.auto_map_keys(pass_info=True)
        self.draw_widgets()
        self.colour_popup: ColourPopup | None = None

    def _create_widgets(self) -> None:
        """Create the widgets."""
        lidx = 2
        self.widgets['highlight'] = EditHighlightWidget(lidx, self)

        lidx = 4
        self.widgets['fg'] = RgbTweakerWidget(
            parent=self, attr='gui.fg', lidx=lidx, highlight=self.highlight,
            label='fg',
            closest_highlighter=tweaker_highlights['CloseFGColour'],
        )
        self.widgets['bg'] = RgbTweakerWidget(
            parent=self, attr='gui.bg', lidx=lidx + 1,
            highlight=self.highlight, label='bg',
            closest_highlighter=tweaker_highlights['CloseBGColour']
        )
        self.widgets['sp'] = RgbTweakerWidget(
            parent=self, attr='gui.sp', lidx=lidx + 2,
            highlight=self.highlight, label='sp',
            closest_highlighter=tweaker_highlights['CloseSPColour']
        )
        lidx += 4
        self.widgets['menu'] = self._create_menu_widget(lidx)
        lidx += self.widgets['menu'].height + 1

        w = None
        for name, highlight in sorted(hl_groups.highlights.items()):
            w = HighlightWidget(lidx, self, highlight, before=w)
            self.widgets[name] = w

    def _create_menu_widget(self, lidx) -> MenuWidget:
        menu = MenuWidget(lidx, self)
        menu.add_entry('d', 'Darken')
        menu.add_entry('l', 'Lighten')
        menu.add_entry('tb', 'Toggle bold')
        menu.add_entry('tb', 'Toggle bold')
        menu.add_entry('tc', 'Toggle undercurl')
        menu.add_entry('ti', 'Toggle italic')
        menu.add_entry('to', 'Toggle standout')
        menu.add_entry('tr', 'Toggle reverse')
        menu.add_entry('ts', 'Toggle strike through')
        menu.add_entry('tu', 'Toggle underline')
        menu.add_entry('ch', 'Copy highlight')
        menu.add_entry('cc', 'Choose colour')
        return menu

    def layout_buffer(self) -> None:
        """Set the basic buffer layout."""
        with self.buf.modifiable():
            self.buf[0] = 'Syntax Tweaker'.center(79).rstrip()
        self.buf.highlight('Label', 'Syntax Tweaker')

    def is_selected_widget(self, widget: Widget) -> bool:
        """Test if a widget is the selected one."""
        return self.widgets[self.cursor] is widget

    def show(self):
        """Show the TweakerBuffer in a split window."""
        if not self.buf.goto_active_window():
            self.buf.show(splitlines=-40)

    def copy_highlight(self, name: str) -> None:
        """Copy the seetings from highlight group."""
        self.highlight.copy_from_named_highlight(name)
        self.highlight.apply()
        self.draw_widgets()

    def switch_highlight_group(self, name: str) -> None:
        """Switch which highlight group is being tweaked."""
        self.highlight = hl_groups.highlights[name]
        self.widgets['fg'].highlight = self.highlight
        self.widgets['bg'].highlight = self.highlight
        self.widgets['sp'].highlight = self.highlight
        self.highlight.apply()
        self.draw_widgets()

    def draw_widgets(self) -> None:
        """Draw all the widgets."""
        with self.buf.modifiable():
            for widget in self.widgets.values():
                widget.draw(self.buf)
        widget = self.widgets[self.cursor]
        try:
            vim.current.window.cursor = widget.dyn_lidx + 1, 0
        except vim.error:
            pass  # Happens during load.

    def draw_rgb(self, label: str, highlight: Highlight) -> None:
        """Draw an RGB control."""
        def build_widget(
                label: str, colour: Colour) -> tuple[str, int, Colour | None]:
            s = [f'{label}:']
            s.append(f'r↓ [{colour.r:3d}] ↑R')
            s.append(f'g↓ [{colour.g:3d}] ↑G')
            s.append(f'b↓ [{colour.b:3d}] ↑B')
            offset = len(' '.join(s)) + 7 + 6 * 2
            if colour.is_valid():
                c_colour = colour.closest_colour()
                s.append(f' ({c_colour.name}:{c_colour.as_decimal()})')
            else:
                c_colour = None
            return ' '.join(s), offset, c_colour

        lidx = 4 if label == 'fg' else 5
        selected = label == self.cursor
        colour = getattr(highlight, label)
        text, offset, c_colour = build_widget(label, colour)
        parts = ['    ', text, '    ']
        if selected:
            parts[0] = ' << '
            parts[2] = ' >>'

        self.buf[lidx] = ''.join(parts)
        props = [
            ('Tweaker_Hotkey', c, c + 1) for c in (8, 22, 24, 38, 40, 54)]
        props.append(('Tweaker_Label', 4, 6))
        if c_colour is not None:
            if label =='fg':
                key = 'CloseFGColour'
            elif label =='bg':
                key = 'CloseBGColour'
            else:
                key = 'CloseSPColour'
            hl = tweaker_highlights[key]
            props.append(
                (f'{hl.name}', offset, offset + len(c_colour.name)))
            hl.fg = c_colour
            hl.apply()

        self.buf.highlight_line(lidx, props)

    def adjust_rgb(self, key: str) -> None:
        """Adjust an RGB value for the selected colour."""
        if self.cursor in ('fg', 'bg', 'sp'):
            attr_name = f'gui.{self.cursor}'
            self.highlight.break_link()
            self.highlight.adjust_rgb(attr_name, key, 10)
        self.highlight.apply()
        self.draw_widgets()

    def adjust_brightness(self, key: str) -> None:
        """Adjust the brighness value for the selected colour."""
        inc = 5.0 if key == 'l' else -5.0
        if self.cursor in ('fg', 'bg'):
            attr_name = f'gui.{self.cursor}'
            self.highlight.break_link()
            self.highlight.adjust_brightness(attr_name, inc)
        self.highlight.apply()
        self.draw_widgets()

    @nmapped(keyseq=(
        'n', 'd', 'l',
        'r', 'R', 'g', 'G', 'b', 'B', '<c-R>', '<c-G>', '<c-B>',
        ))
    def handle_hotkey(self, info:vpe.MappingInfo) -> None:
        """Handle one of the tweak hot keys."""
        key = info.keys
        if key == 'n':
            self.switch_highlight_group('Keyword')
        elif key in 'rRgGbB' or info.keys in ('<c-R>', '<c-G>', '<c-B>'):
            self.adjust_rgb(info.keys)
        elif key in 'dl':
            self.adjust_brightness(info.keys)

    @nmapped(keyseq=('<tab>',))
    def handle_navkey(self, info:vpe.MappingInfo) -> None:
        """Handle one of the tweak navigation keys."""
        labels = chain(self.widgets, self.widgets)
        for label in labels:
            if label == self.cursor:
                while True:
                    self.cursor = next(labels)
                    widget = self.widgets[self.cursor]
                    if widget.is_selectable:
                        break
                self.draw_widgets()
                return

    @nmapped(keyseq=('cc'))
    def handle_choose_colour(self, info:vpe.MappingInfo) -> None:
        """Allow colour selection from a popup."""
        if self.cursor not in ('fg', 'bg', 'sp'):
            return

        if self.colour_popup is None:
            colours = web_colours.name_to_hexstr
            nl = max(len(name) for name in colours)
            self.colour_popup = ColourPopup(
                parent=self,
                maxheight=50,
                minwidth=nl + 2,
                border=[1, 1, 1, 1],
                highlight='Tweaker_DarkBG')
            buf = self.colour_popup.buffer

            prop_type_kw = {
                'priority': 50,
                'bufnr': buf.number,
            }
            lines = []
            for name, hexstr in colours.items():
                colour = hl_groups.EditableColour.parse(hexstr)
                props = []

                for mode in ('dbg', 'lbg'):
                    prop_name = f'Tweaker_colour_{name}_{mode}'
                    if mode == 'lbg':
                        highlight = Highlight.from_name('Tweaker_LightBG')
                    else:
                        highlight = Highlight.from_name('Tweaker_Template')
                    highlight.set_colour('gui.fg', colour)
                    highlight.name = prop_name
                    highlight.apply()

                    prop_type_kw['highlight'] = prop_name
                    vim.prop_type_add(prop_name, prop_type_kw)

                    if mode == 'dbg':
                        props.append(
                            {'col': 1, 'length': nl + 2, 'type': prop_name})
                    else:
                        props.append({
                            'col': nl + 2, 'length': nl + 2, 'type': prop_name
                        })

                lines.append({
                    'text': f' {name:{nl}} {name:{nl}} ',
                    'props': props,
                })
            self.colour_popup.settext(lines)

        self.colour_popup.show()

    def complete_handle_choose_colour(self, name: str) -> None:
        """Finish the process of choosing a colour by name."""
        colour = hl_groups.EditableColour.parse(name)
        attr_name = f'gui.{self.cursor}'
        self.highlight.set_colour(attr_name, colour)
        self.highlight.apply()
        self.draw_widgets()

    @nmapped(keyseq=('<cr>', 'ch'))
    def handle_select(self, info:vpe.MappingInfo) -> None:
        """Select highlight for the current line, if any."""
        row, _ = vim.current.window.cursor
        if info.keys in ('<cr>', 'ch'):
            self._select_by_line(row - 1, info.keys)

    @nmapped(keyseq=('tb', 'tc', 'ti', 'to', 'tr', 'ts', 'tu'))
    def handle_command_sequence(self, info:vpe.MappingInfo) -> None:
        """Handle one of the command sequence mappings."""
        cmd = info.keys
        if cmd in ('tb', 'tc', 'ti', 'to', 'tr', 'ts', 'tu'):
            flag = command_to_highlight_flag[cmd]
            self.highlight.break_link()
            self.highlight.toggle_flag('gui', flag)
            self.highlight.apply()
        self.draw_widgets()

    @nmapped(keyseq=('<C-LeftMouse>',))
    def handle_mouse(self, info:vpe.MappingInfo) -> None:
        """Select highlight for the current line, if any."""
        mouse_info = vim.getmousepos()
        self._select_by_line(mouse_info['line'] - 1, info.keys)

    def _select_by_line(self, lidx: int, keys: str) -> None:
        for name, widget in self.widgets.items():
            if lidx in widget.line_range:
                break
        else:
            return

        if keys in ('<cr>', '<C-LeftMouse>', 'ch'):
            if isinstance(widget, HighlightWidget):
                if keys == 'ch':
                    self.copy_highlight(name)
                else:
                    self.switch_highlight_group(name)
                self.cursor = 'fg'
                return

        if widget.is_selectable:
            self.cursor = name
            self.draw_widgets()


class Widget:
    """Base for various widgets."""

    is_selectable: Final[ClassVar] = True

    def __init__(self, parent: Tweaker, lidx: int):
        self.parent = proxy(parent)
        self.lidx = lidx

    @property
    def dyn_lidx(self) -> int:
        """The dynamically calculated line index."""
        return self.lidx

    @property
    def height(self) -> int:
        """The number of lines this widget occupies."""
        return 1

    @property
    def is_selected(self) -> bool:
        """A flag indicating if this is the selected widget."""
        return self.parent.is_selected_widget(self)

    @property
    def line_range(self) -> range:
        """The range of line indices used by this widget."""
        return range(self.dyn_lidx, self.dyn_lidx + self.height)

    def draw(self, buf: vpe.Buffer) -> None:
        """Draw this widget."""

    def draw_line(self, lidx: int, text: str, props: list) -> None:
        """Draw a line and add its properties."""
        buf = self.parent.buf
        prefix = '    '
        if self.is_selected and lidx == self.dyn_lidx:
            prefix = '==> '
        offset = len(prefix)
        if lidx + 1 > len(buf):
            buf.append('')
        buf[lidx] = f'{prefix}{text}'
        buf.highlight_line(
            lidx, [(n, s + offset, e + offset) for n, s, e in props])


class ColourComponentTweakerGadget:
    """An RGB colour component tweaker gadget."""

    def __init__(self, parent: RgbTweakerWidget, name: str):
        self.parent = proxy(parent)
        self.name = name

    @property
    def value(self) -> int:
        """The current value for this component."""
        return getattr(self.parent.colour, self.name)

    def format(self) -> str:
        """Format this gadget as a plain string."""
        lc = self.name.lower()
        uc = self.name.upper()
        return f'{lc}↓ [{self.value:3d}] ↑{uc}'

    def props(self, offset: int) -> list[tuple[str, int, int]]:
        """The properties to highlight this gadget."""
        return [
            ('Tweaker_Hotkey', offset + c, offset + c + 1) for c in (0, 13)]

    def byte_length(self) -> int:
        """The length of this gadget in bytes."""
        return len(self.format().encode('utf-8'))


class RgbTweakerWidget(Widget):
    """An RGB colour tweaker widget."""
    # pylint: disable=too-many-instance-attributes

    def __init__(
            self,
            parent: Tweaker,
            attr: str,
            lidx: int,
            highlight: Highlight,
            label: str,
            closest_highlighter: Highlight,
        ):
        # pylint: disable=too-many-positional-arguments,too-many-arguments
        super().__init__(parent=parent, lidx=lidx)
        self.attr = attr
        self.label = label
        self.highlight = highlight
        self.components = {
            'r': ColourComponentTweakerGadget(self, 'r'),
            'g': ColourComponentTweakerGadget(self, 'g'),
            'b': ColourComponentTweakerGadget(self, 'b'),
        }
        self.closest_highlighter = closest_highlighter

    @property
    def colour(self) -> Colour:
        """The colour for this tweaker widget."""
        return self.highlight.get_colour(self.attr)

    def draw(self, buf: vpe.Buffer) -> None:
        """Draw and style this widget."""
        prefix = '==> ' if self.is_selected else '    '
        parts = [f'{self.label}:']
        props = []
        offset = len(parts[0]) + 1 + len(prefix)
        for component in self.components.values():
            parts.append(component.format())
            props.extend(component.props(offset))
            offset += component.byte_length() + 1

        closest_colour = self.colour.closest_colour
        if closest_colour is not None:
            parts.append(
                f' ({closest_colour.name}:'
                f'{closest_colour.as_decimal()})')
            hl = self.closest_highlighter
            hl.set_colour('gui.fg', closest_colour)
            hl.set_colour('cterm.fg', closest_colour)
            hl.apply()
            offset += 2
            props.append((
                f'{hl.name}', offset, offset + len(closest_colour.name)
            ))

        buf[self.lidx] = prefix + ' '.join(parts)
        buf.highlight_line(self.lidx, props)


class EditHighlightWidget(Widget):
    """A widget that displays details of the edited highlight group."""

    is_selectable: Final[ClassVar] = False

    def __init__(
            self,
            lidx: int,
            parent: Tweaker,
        ):
        super().__init__(parent=parent, lidx=lidx)
        self.number_of_lines: int = 0

    @property
    def highlight(self) -> Highlight:
        """The currently displayed highlight."""
        return self.parent.highlight

    def draw(self, buf: vpe.Buffer) -> None:
        """Draw and style this widget."""
        name = self.highlight.name
        self.draw_line(
            self.dyn_lidx, f'Highlight/Property: {name}',
            [(name, 20, 20 + len(name))])


class HighlightWidget(Widget):
    """A widget that displays details of a highlight group."""

    def __init__(
            self,
            lidx: int,
            parent: Tweaker,
            highlight: Highlight,
            before: HighlightWidget | None,
        ):
        if before is not None:
            lidx = before.lidx + before.height
        super().__init__(parent=parent, lidx=lidx)
        self.highlight = highlight
        self.number_of_lines: int = 0
        self.before = before

    @property
    def dyn_lidx(self) -> int:
        """The dynamically calculated line index."""
        if self.before:
            return self.before.dyn_lidx + self.before.height
        else:
            return self.lidx

    @property
    def height(self) -> int:
        return self.number_of_lines

    def draw(self, buf: vpe.Buffer) -> None:
        """Draw and style this widget."""
        if self.before is None:
            buf[self.lidx:] = []

        highlight = self.highlight
        name = highlight.name
        if highlight.is_linked:
            self.draw_line(
                self.dyn_lidx, f'highlight link {name} {highlight.link}',
                [(name, 15, 15 + len(name))])
            self.number_of_lines = 1
        else:
            def flush():
                nonlocal length
                self.draw_line(
                    self.dyn_lidx + self.number_of_lines,
                    ' '.join(parts),
                    props)
                self.number_of_lines += 1
                parts[:] = ['        \\']
                props[:] = []
                length = len(parts[0]) + 1

            self.number_of_lines = 0
            parts = [f'highlight {name}']
            props = [(name, 10, 10 + len(name))]
            length = len(parts[0]) + 1
            for attr_name in ('term', 'cterm', 'gui'):
                settings = getattr(highlight, attr_name)
                if settings is not None:
                    args_dict = settings.format_args()
                    args = [f'{n}={v}' for n, v in args_dict.items()]
                    for arg in args:
                        if len(arg) + 1 + length > 79:
                            flush()
                        parts.append(arg)
                        length += len(arg) + 1
            flush()


class MenuEntryGadget:
    """A single entry in the command menu."""

    def __init__(self, parent: MenuWidget, key_seq: str, name: str):
        self.parent = proxy(parent)
        self.key_seq = key_seq
        self.name = name

    def format(self) -> str:
        """Format this gadget as a plain string."""
        return f'{self.key_seq:<2s}: {self.name}'

    def props(self, offset: int) -> list[tuple[str, int, int]]:
        """The properties to highlight this gadget."""
        return [('Tweaker_Hotkey', offset, offset + 2)]


class MenuWidget(Widget):
    """A widget that displays the command menu."""

    is_selectable: Final[ClassVar] = False

    def __init__(
            self,
            lidx: int,
            parent: Tweaker,
        ):
        super().__init__(parent=parent, lidx=lidx)
        self.entries: list[MenuEntryGadget] = []
        self.number_of_lines: int = 0
        self.grid: list[list] = []
        self.gadget_width = 0

    @property
    def height(self) -> int:
        return len(self.grid)

    def add_entry(self, key_seq: str, name: str) -> None:
        """An entry to the menu."""
        self.entries.append(MenuEntryGadget(self, key_seq, name))
        self.grid = self._form_grid()

    def draw(self, buf: vpe.Buffer) -> None:
        """Draw and stye this widget."""
        for lidx, line in enumerate(self.grid, self.lidx):
            buf[lidx] = ''
            parts = ['  ']
            line_props = []
            for text, props in line:
                parts.append(f'{text:{self.gadget_width}}')
                line_props.extend(props)
            buf[lidx] = '  '.join(parts)
            buf.highlight_line(lidx, line_props)

    def _form_grid(self) -> list[list]:
        """Form the grid layout for the menu display."""
        strings = [entry.format() for entry in self.entries]
        entry_length = max(len(s) for s in strings)
        per_line = 77 // entry_length
        line_length = entry_length + (per_line - 1) * (entry_length + 2)
        if line_length > 77:
            per_line -= 1

        grid = [[]]
        line = grid[-1]
        offset = 4
        for entry in self.entries:
            text = entry.format()
            line.append((text, entry.props(offset)))
            if len(line) == per_line:
                grid.append([])
                line = grid[-1]
                offset = 4
            else:
                offset += entry_length + 2
        if not line:
            grid.pop()
        self.gadget_width = entry_length
        return grid


def load_standard_colors():
    """Load the 'standard' named colours.

    The 'standard' is taken to be the set in::

        $VIMRUNTIME/colors/lists/csscolors.vim'

    which is basically the 'standard' Web/CSS set of named colours.
    """

    saved_colours = {}
    saved_colours.update(vim.vvars.colornames)
    while vim.vvars.colornames:
        vim.vvars.colornames.popitem()
    vim.command('source $VIMRUNTIME/colors/lists/csscolors.vim')
    for name in vim.vvars.colornames:
        std_colours[name[4:]] = NamedColour.parse(name)

    while vim.vvars.colornames:
        vim.vvars.colornames.popitem()
    vim.vvars.colornames.update(saved_colours)


def create_tweaker_groups():
    """Create highlight groups specific to tweaker."""
    for name, data in TWEAKER_GROUPS.items():
        unused = Colour(-1, -1, -1)
        kw = {'fg': unused, 'bg': unused}
        hl_name = f'Tweaker_{name}'
        if 'fg' in data:
            kw['fg'] = Colour.parse(data['fg'])
        if 'bg' in data:
            kw['bg'] = Colour.parse(data['bg'])

        term = TermSettings()
        cterm = ColourTermSettings(**kw)
        gui = GUISettings(**kw)
        tweaker_highlights[name] = Highlight(hl_name, term, cterm, gui)
        tweaker_highlights[name].apply()


def show():
    """Show the tweaker in a split window."""
    global tweaker                           # pylint: disable=global-statement

    if tweaker is None:
        load_standard_colors()
        create_tweaker_groups()
        tweaker = Tweaker()
    tweaker.show()


tweaker: Tweaker | None = None
std_colours: dict[str, Colour] = {}
tweaker_highlights: dict[str, Highlight] = {}
