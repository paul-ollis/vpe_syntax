"""A simple interactive syntax scheme tweaker."""
# pylint: disable=too-many-lines
from __future__ import annotations

import inspect
import re
from collections import defaultdict
from contextlib import contextmanager
from functools import partial
from itertools import count
from typing import Callable, ClassVar, Iterator, TypeAlias, cast
from weakref import proxy

import vpe
from vpe import vim
from vpe.mapping import KeyHandler, MappingInfo

from vpe_syntax import hl_groups, web_colours
from vpe_syntax.hl_groups import (
    Colour, ColourTermSettings, GUISettings, Highlight, TermSettings,
    default_white, none_colour, unused_colour)

UndoGroup: TypeAlias = list[Callable[[], None]]
APP_NAME = 'VPE_highlight_tweaker'

nmapped = partial(KeyHandler.mapped, mode='normal')

if vim.options.background == 'dark':
    alt_bg_colour = '#ffffff'
else:
    alt_bg_colour = '#000000'

prop_id_source = count(1)

TWEAKER_GROUPS: dict[str, dict] = {
    'HotKey':             {'priority': 50, 'fg':  'Greed',},
    'SelBracket':         {'priority': 50, 'fg':  'Blue',
                                           'bg':  'SlateGrey',
                                           'gui': 'Bold'},
    'ClosestColour':      {'priority': 50, 'fg':  'White',},
    'ClosestColour2':     {'priority': 50, 'fg':  'White',},
    'GreyedOut':          {'priority': 50, 'fg':  'Grey',},
    'Hotkey':             {'priority': 50, 'fg':  'SeaGreen',
                                           'gui': 'Bold'},
    'CTermEmul':          {'priority': 50, 'fg':  'Grey',},
    'TermEmul':           {'priority': 50, 'fg':  'White',},
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

#: The template for the colour editing part of the UI.
colour_editor_layout = '''
  ╭═════════════════════════════════════════════════════════════════════════╮
  ║ ┌─ Foreground ────────────────────────────────────────────────────────┐ ║
  ║ │              red    green  blue   closest color                     │ ║
  ║ │⦃ GUI:        255/ff 255/ff 255/ff cadet blue                       ⦄│ ║
  ║ │  Color term:   "      "      "    green                             │ ║
  ║ └─────────────────────────────────────────────────────────────────────┘ ║
  ║   GUI text sample          Color term sample         Mono term sample   ║
  ║                                                                         ║
  ║   Increase/decrease color: R/r  G/g  B/b   Inc/dec step (s):  10        ║
  ║   ⁻ ⁻ ⁻ ⁻ ⁻ ⁻ ⁻ ⁻ ⁻ ⁻ ⁻ ⁻ ⁻ ⁻ ⁻ ⁻ ⁻ ⁻ ⁻ ⁻ ⁻ ⁻ ⁻ ⁻ ⁻ ⁻ ⁻ ⁻ ⁻ ⁻ ⁻ ⁻ ⁻ ⁻   ║
  ║   C: Use closest color   N: Toggle NONE             P: Palette chooser  ║
  ║   D: Darken:             L: Lighten                 K: Break link       ║
  ║   u: Undo:               c: Toggle copy GUI     <Tab>: Move selection   ║
  ╰═════════════════════════════════════════════════════════════════════════╯
    ╓─────────────────────────────────────────────────────────────────────╖
    ║ F1: fg   F2: bg   F3: sp/ul   F4: attrs                             ║
    ║ a: Toggle active highlight groups                                   ║
    ╙─────────────────────────────────────────────────────────────────────╜



  ⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻
  When the cursor is on a highlight group below:

  <Enter>: Select as the group being edited.
        g: Update current edit group to match this one.
        J: Make the current group link to this one.
  ⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻
'''

#: The template for the attribute editing part of the UI.
attribute_editor_layout = '''
  ╭═════════════════════════════════════════════════════════════════════════╮
  ║ ┌─ Text attributes ───────────────────────────────────────────────────┐ ║
  ║ │⦃ GUI:         bold underline                                       ⦄│ ║
  ║ │  Color term:  <close copy of gui>                                   │ ║
  ║ │  Mono term:   italic                                                │ ║
  ║ └─────────────────────────────────────────────────────────────────────┘ ║
  ║   GUI text sample          Color term sample         Mono term sample   ║
  ║                                                                         ║
  ║                                                                         ║
  ║   B: Bold                                           K: Break link       ║
  ║   S: Strikethrough     I: Italic                    U: Underline        ║
  ║   u: Undo:                                      <Tab>: Move selection   ║
  ║                                                                         ║
  ╰═════════════════════════════════════════════════════════════════════════╯
    ╓─────────────────────────────────────────────────────────────────────╖
    ║ F1: fg   F2: bg   F3: sp/ul   F4: attrs                             ║
    ║ a: Toggle active highlight groups                                   ║
    ╙─────────────────────────────────────────────────────────────────────╜



  ⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻
  When the cursor is on a highlight group below:

  <Enter>: Select as the group being edited.
        g: Update current edit group to match this one.
        J: Make the current group link to this one.
  ⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻⁻
'''

alt_menu = '''
    ╔═════════════════════════════════════════════════════════════════════╗
    ║ F1: fg   F2: bg   F3: sp/ul   F4: attrs   F5: edit/select           ║
    ╚═════════════════════════════════════════════════════════════════════╝
'''


def load_layout(template: str) -> list[str]:
    """Load and clean a layout template."""
    lines = inspect.cleandoc(template).splitlines()
    return lines


def create_editor_widgets(
        parent: Tweaker,
    ) -> tuple[dict[str, Widget], dict[str, Widget], dict[str, Widget]]:
    """Parse a layout to create the contained widgets."""
    common_widgets: dict[str, Widget] = {}
    colour_widgets: dict[str, Widget] = {}
    attr_widgets: dict[str, Widget] = {}

    hot_key_patterns = (
        ' ([BISUNDLKuca]): ',  ' (<Tab>): ',  ' ([RGB])/[rgb] ',
        ' [RGB]/([rgb]) ',     r'\((s)\): ',  ' (F[1234]): ',
    )
    colour_widgets['hot-keys'] = HotKeyWidget(parent)
    attr_widgets['hot-keys'] = HotKeyWidget(parent)

    layout = load_layout(colour_editor_layout)
    for lidx, line in enumerate(layout):
        # Selection marker for colours/arrtibutes.
        if '⦃' in line:
            a = line.index('⦃')
            b = line.index('⦄')
            common_widgets['selection'] = SelWidget(parent, lidx - 1, a, b)

        # The RGB widgets.
        if '255/ff' in line:
            offset = 0
            right = line
            for colour in ('red', 'green', 'blue'):
                left, middle, right = right.partition('255/ff')
                offset += len(left)
                colour_widgets[colour] = RGB_Widget(
                    parent, lidx, colour, offset)
                colour_widgets[f'{colour}2'] = RGB_Widget(
                    parent, lidx + 1, colour, offset, term=True)
                offset += len(middle)

        # The increment/decrement step widget.
        if 'Inc/dec step' in line:
            offset = line.index('10')
            colour_widgets['step'] = StepWidget(parent, lidx, offset)

        # The nearest colour name widget.
        if 'cadet blue' in line:
            offset = line.index('cadet blue')
            right_offset = line.rindex('│') - 1
            colour_widgets['closest-colour'] = CloseColourWidget(
                parent, lidx, offset, right_offset)
            colour_widgets['closest-colour2'] = CloseColourWidget(
                parent, lidx + 1, offset, right_offset, term=True)

        # The sample text widget.
        if 'GUI text sample' in line:
            idx_1 = line.index('GUI')
            idx_2 = line.rindex('Color')
            idx_3 = line.rindex('Mono')
            common_widgets['sample'] = SampleWidget(
                parent, lidx, idx_1, idx_2, idx_3)

        # The colour mode widget.
        if 'Foreground' in line:
            offset = line.index('Foreground')
            common_widgets['colour-mode'] = ColourModeWidget(
                parent, lidx, offset)

        # The hot key widget.
        widget = cast(HotKeyWidget, colour_widgets['hot-keys'])
        for pat in hot_key_patterns:
            for m in re.finditer(pat, line):
                widget.add_key(m.group(1), lidx, m.start(1), m.end(1))

    layout = load_layout(attribute_editor_layout)
    for lidx, line in enumerate(layout):
        # GUI attributes widget.
        if 'bold underline' in line:
            offset = line.index('bold underline')
            attr_widgets['gui_attrs'] = AttrWidget(
                parent, lidx, offset, mode='gui')

        # Colour terminal attributes widget.
        if '<close copy of gui>' in line:
            offset = line.index('<close copy of gui>')
            attr_widgets['cterm_attrs'] = AttrWidget(
                parent, lidx, offset, mode='cterm')

        # Colour terminal attributes widget.
        if 'Mono term:' in line:
            offset = line.index('italic')
            attr_widgets['mono_attrs'] = AttrWidget(
                parent, lidx, offset, mode='term')

        # The hot key widget.
        widget = cast(HotKeyWidget, attr_widgets['hot-keys'])
        for pat in hot_key_patterns:
            for m in re.finditer(pat, line):
                widget.add_key(m.group(1), lidx, m.start(1), m.end(1))

    return common_widgets, colour_widgets, attr_widgets


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


class Tweaker(vpe.CommandHandler, KeyHandler):
    """The tweaker contol object.

    @mode:
        The current editing (sub)mode. One of fg, bg, sp and attrs.
    @hl_group:
        The `Highlight` group being edited.
    @show_inactive_highlights:
        When True then highlight groups that do no appear in the code buffer
        are hidden.
    @active_property_names:
        The names of the properties (highlight groups) that are used by
        the code buffer.
    """
    # pylint: disable=too-many-instance-attributes,too-many-public-methods

    def __init__(self):
        self.buf: TweakerBuffer = cast(
            TweakerBuffer, vpe.get_display_buffer(
                APP_NAME, buf_class=TweakerBuffer))
        self.mode = 'fg'      # Can also be 'bg', 'sp' and 'attrs'.
        self.hl_group: Highlight
        self.show_inactive_highlights: bool = True
        self.active_property_names = _get_used_prop_names()
        self.select_first_highlight_group()
        self.common_widgets: dict[str, Widget] = {}
        self.colour_widgets: dict[str, Widget] = {}
        self.attr_widgets: dict[str, Widget] = {}
        self.widgets: dict[str, Widget] = {}
        self.hl_widgets: dict[str, HighlightWidget] = {}
        self.create_widgets()
        self.render_editor()
        self.auto_map_keys(pass_info=True, buffer=self.buf)
        self.undo_buffer: list[UndoGroup] = []
        self.colour_popup: ColourPopup | None = None

    #< Properties
    @property
    def ui_type(self) -> str:
        """The current Vim user interface type - gui, term or cterm."""
        return cast(SelWidget, self.widgets['selection']).ui_type

    @property
    def hl_display_lidx(self) -> int:
        """The line index where the current highlight group should be displayed."""
        return len(load_layout(colour_editor_layout)) - 10

    @property
    def first_hl_lidx(self) -> int:
        """The line index where the first highlight group is displayed."""
        return len(load_layout(colour_editor_layout))

    @property
    def colour_attr_name(self) -> str:
        """The attribute name need to get the current colour."""
        return f'{self.ui_type}.{self.mode}'

    #< Key handling
    @nmapped(keyseq='<Tab>')
    def move_to_next_group(self, _info: MappingInfo) -> None:
        """Perform TAB move to next group."""
        cast(SelWidget, self.widgets['selection']).goto_next()
        self.refresh()

    @nmapped(keyseq=('<F1>', '<F2>', '<F3>', '<F4>'))
    def switch_mode(self, info: MappingInfo) -> None:
        """Perform TAB move to next group."""
        key = info.keys
        match key:
            case '<F1>':
                self.mode = 'fg'
            case '<F2>':
                self.mode = 'bg'
            case '<F3>':
                self.mode = 'sp'
            case '<F4>':
                self.mode = 'attrs'
        self.render_editor()

    @nmapped(keyseq=('r', 'R', 'g', 'G', 'b', 'B'))
    def handle_rgb_inc_or_dec(self, info: MappingInfo) -> None:
        """Handle a key used to increment or decrement and RGB value."""
        key = info.keys
        if self.mode == 'attrs':
            match key:
                case 'B':
                    self.handle_attribute_toggle(info)
            return

        suffix = '' if self.ui_type == 'gui' else '2'
        match key:
            case 'r' | 'R':
                colour = f'red{suffix}'
            case 'g' | 'G':
                colour = f'green{suffix}'
            case 'b' | 'B':
                colour = f'blue{suffix}'
        direction = 1 if key.upper() == key else -1
        step_widget = cast(StepWidget, self.widgets['step'])
        colour_widget = cast(RGB_Widget, self.widgets[colour])
        with self.undo_group() as undo:
            if colour_widget.modify_value(direction * step_widget.value, undo):
                self.refresh()

    @nmapped(keyseq=('D', 'L'))
    def adjust_brightness(self, info: MappingInfo) -> None:
        """Handle keys that adjust the brighness for the selected colour."""
        if self.mode == 'attrs':
            return

        colour = self.hl_group.get_colour(self.colour_attr_name)
        if colour is none_colour or colour is unused_colour:
            return

        key = info.keys
        direction = 1 if key == 'L' else -1
        step = cast(StepWidget, self.widgets['step']).value
        with self.undo_group() as undo:
            def do_undo():
                colour.r, colour.b, colour.g = prev

            prev = colour.r, colour.b, colour.g
            if colour.adjust_brightness(direction * step):
                undo.append(do_undo)

        self.refresh()

    @nmapped(keyseq='K')
    def handle_break_link(self, info: MappingInfo) -> None:
        """Handle key break the link for the highlight group."""
        link_name = self.hl_group.link
        if link_name:
            with self.undo_group() as undo:
                undo.append(partial(self.hl_group.set_link, link_name))
                self.hl_group.break_link()
            self.refresh()

    @nmapped(keyseq='<Enter>')
    def handle_select_highlight_group(self, info: MappingInfo) -> None:
        """Handle selecting a new highlight groupto edit."""
        lnum, _ = vim.current.window.cursor
        lidx = lnum - 1
        for widget in self.hl_widgets.values():
            if widget.matches_line_index(lidx):
                break
        else:
            return

        if widget.highlight is not self.hl_group:
            with self.undo_group() as undo:
                def do_undo():
                    self.hl_group = prev_hl_group

                prev_hl_group = self.hl_group
                undo.append(do_undo)
                self.hl_group = widget.highlight
                self.refresh()
            vim.current.window.cursor = 1, 0
            def move_cursor():
                vim.current.window.cursor = self.first_hl_lidx, 0
            vpe.call_soon(move_cursor)

    @nmapped(keyseq='s')
    def handle_step_cycle(self, info: MappingInfo) -> None:
        """Handle key used to step through increment values."""
        with self.undo_group() as undo:
            cast(StepWidget, self.widgets['step']).cycle_value(undo)

    @nmapped(keyseq='a')
    def handle_toggle_active(self, _info: MappingInfo) -> None:
        """Handle key toggle whether inactive highlights are shown."""
        self.show_inactive_highlights = not self.show_inactive_highlights
        if not self.show_inactive_highlights:
            if self.hl_group.name not in self.active_property_names:
                self.select_first_highlight_group()
        self.refresh()

    @nmapped(keyseq='c')
    def handle_toggle_copy_gui(self, _info: MappingInfo) -> None:
        """Handle the key to toggle the copy from the GUI setting."""
        if self.mode == 'attrs' or self.hl_group.is_linked:
            return

        hl_group = self.hl_group
        with self.undo_group() as undo:
            undo.append(
                partial(hl_group.set_copy_gui, hl_group.cterm_copies_gui))
            hl_group.set_copy_gui(not hl_group.cterm_copies_gui)
        self.refresh()

    @nmapped(keyseq=('S', 'I', 'U'))
    def handle_attribute_toggle(self, info: MappingInfo) -> None:
        """Handle the key to toggle an attribute."""
        if self.hl_group.is_linked:
            return

        key_to_attr = {
            'B': 'bold',
            'S': 'strikethrough',
            'I': 'italic',
            'U': 'underline',
        }
        attr_name = key_to_attr[info.keys]
        hl_group = self.hl_group
        settings = getattr(hl_group, self.ui_type)
        flag = getattr(settings, attr_name)
        with self.undo_group() as undo:
            undo.append(partial(setattr, settings, attr_name, flag))
        setattr(settings, attr_name, not flag)
        self.refresh()

    @nmapped(keyseq='N')
    def handle_toggle_none(self, _info: MappingInfo) -> None:
        """Handle the key to toggle NONE for a colour."""
        if self.hl_group.is_linked:
            return

        ui_type = self.ui_type
        if self.hl_group.cterm_copies_gui and ui_type != 'gui':
            return

        hl_group = self.hl_group
        attr_name = f'{ui_type}.{self.mode}'
        colour = hl_group.get_colour(attr_name)
        with self.undo_group() as undo:
            undo.append(partial(hl_group.set_colour, colour))
        if colour is none_colour:
            hl_group.set_colour(attr_name, default_white)
        else:
            hl_group.set_colour(attr_name, none_colour)
        self.refresh()

    @nmapped(keyseq='P')
    def handle_choose_from_palette(self, _info: MappingInfo) -> None:
        """Handle the key to choose a colour from a pelette."""
        if self.hl_group.is_linked:
            return

        ui_type = self.ui_type
        if self.hl_group.cterm_copies_gui and ui_type != 'gui':
            return

        if self.colour_popup is not None:
            self.colour_popup.show()
            return

        colours = web_colours.name_to_hexstr
        nl = max(len(name) for name in colours)
        self.colour_popup = ColourPopup(
            parent=proxy(self),
            maxheight=50,
            minwidth=nl + 2,
            border=[1, 1, 1, 1],
            highlight='Tweaker_DarkBG')
        buf = self.colour_popup.buf

        prop_type_kw = {
            'priority': 50,
            'bufnr': buf.number,
        }
        lines = []
        for name, hexstr in colours.items():
            colour = Colour.parse(hexstr)
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

    @nmapped(keyseq='C')
    def handle_use_closest_colour(self, _info: MappingInfo) -> None:
        """Handle the key to set colour to match the nearest named colour."""
        ui_type = self.ui_type
        hl_group = self.hl_group
        attr_name = f'{ui_type}.{self.mode}'
        colour = hl_group.get_colour(attr_name)
        match ui_type:
            case 'gui':
                closest_colour = colour.closest_colour
            case 'cterm':
                closest_colour = colour.closest_terminal_colour
            case _:
                return

        with self.undo_group() as undo:
            undo.append(
                partial(hl_group.set_colour, attr_name, colour))
            hl_group.set_colour(attr_name, closest_colour)
        self.refresh()

    @nmapped(keyseq='u')
    def handle_undo(self, _info: MappingInfo) -> None:
        """Handle key used to undo a change."""
        if self.undo_buffer:
            actions = self.undo_buffer.pop()
            for action in actions:
                action()
            self.refresh()

    #< Widgets and rendering
    def create_widgets(self):
        """Create the various widget sets."""
        layout = load_layout(colour_editor_layout)
        self.hl_widgets = self.create_hl_widgets(len(layout))
        widget_sets = create_editor_widgets(self)
        self.common_widgets = widget_sets[0]
        self.colour_widgets = widget_sets[1]
        self.attr_widgets = widget_sets[2]

    def render_editor(self) -> None:
        """Render the full contents of the editor buffer."""
        self.widgets = self.common_widgets.copy()
        match self.mode:
            case 'fg' | 'bg' | 'sp':
                layout = load_layout(colour_editor_layout)
                self.widgets.update(self.colour_widgets)
            case 'attrs':
                self.widgets.update(self.attr_widgets)
                layout = load_layout(attribute_editor_layout)

        self.buf.clear_props()
        with self.buf.modifiable():
            self.buf[:] = layout
        self._set_active_keys()
        self.draw_widgets()

    def refresh(self) -> None:
        """Refresh the UI buffer contents."""
        self._set_active_keys()
        self.hl_group.apply()
        self.draw_widgets()

    def _set_active_keys(self) -> None:
        widget = cast(HotKeyWidget, self.widgets['hot-keys'])
        inactive: set[str] = set()
        if self.mode != 'attrs':
            colour = self.hl_group.get_colour(self.colour_attr_name)
            if colour is unused_colour or colour is none_colour:
                inactive.update('rgbRGB')
            if self.hl_group.is_linked:
                inactive.update('DLCc')
            else:
                inactive.update('K')
            if self.hl_group.cterm_copies_gui and self.ui_type == 'cterm':
                inactive.update('rgbRGB')
        else:
            if self.hl_group.is_linked:
                inactive.update('BSIUN')
            else:
                inactive.update('K')

        match self.mode:
            case 'fg':
                inactive.add('F1')
            case 'bg':
                inactive.add('F2')
            case 'sp':
                inactive.add('F3')
            case 'attrs':
                inactive.add('F4')
        widget.set_inactive(inactive)

    def draw_widgets(self) -> None:
        """Draw all the widgets."""
        with self.buf.modifiable():
            for widget in self.widgets.values():
                widget.clean()
                widget.draw(self.buf)
            for widget in self.hl_widgets.values():
                widget.clean()
                widget.draw(self.buf)

    def create_hl_widgets(self, start_lidx: int) -> dict[str, HighlightWidget]:
        """Create the highlight widgets."""
        lidx = start_lidx
        widgets: dict[str, HighlightWidget] = {}
        w = None
        for name, highlight in sorted(hl_groups.highlights.items()):
            w = HighlightWidget(lidx, self, highlight, before=w)
            widgets[name] = w

        return widgets

    #< Undo support
    def show(self):
        """Show the TweakerBuffer in a split window."""
        if not self.buf.goto_active_window():
            self.buf.show(splitlines=-40)

    @contextmanager
    def undo_group(self) -> Iterator[UndoGroup]:
        """Provide a context to create an undo group."""
        undo_group: UndoGroup = []
        try:
            yield undo_group
        finally:
            if undo_group:
                self.undo_buffer.append(undo_group)

    #< Suport methods
    def complete_handle_choose_colour(self, name: str) -> None:
        """Finish the process of choosing a colour by name."""
        colour = Colour.parse(name)
        self.hl_group.set_colour(self.colour_attr_name, colour)
        self.hl_group.apply()
        self.refresh()

    def select_first_highlight_group(self) -> None:
        """Select the first groupas the active group."""
        for _, self.hl_group in sorted(hl_groups.highlights.items()):
            if self.show_inactive_highlights:
                break
            if self.hl_group.name in self.active_property_names:
                break


#< Widgets
class Widget:
    """Base for various widgets."""

    is_selectable: ClassVar = True

    def __init__(self, parent: Tweaker, lidx: int):
        self.parent = proxy(parent)
        self.lidx = lidx

    #< Properties
    @property
    def height(self) -> int:
        """The number of lines this widget occupies."""
        return 1

    @property
    def line_range(self) -> range:
        """The range of line indices used by this widget."""
        return range(self.lidx, self.lidx + 1)

    @property
    def buf(self) -> TweakerBuffer:
        """The buffer showing the UI."""
        return self.parent.buf

    @property
    def mode(self) -> str:
        """The current mode - fg, bg, sp, attrs."""
        return self.parent.mode

    #< Rendering
    def draw(self, buf: vpe.Buffer) -> None:
        """Draw this widget."""

    def clean(self) -> None:
        """Clean up the UI for this widget."""


class SelWidget(Widget):
    """The widget that selects the colour/attributes group."""

    prop_id = next(prop_id_source)
    prop_name: str = 'Tweaker_SelBracket'

    def __init__(
            self, parent: Tweaker, lidx: int, left: int, right: int,
        ):
        super().__init__(parent, lidx)
        self.cur_lidx = lidx
        if self.mode != 'attrs':
            self.cur_lidx = lidx + 1
        self.left = left
        self.right = right

    #< Properties
    @property
    def ui_type(self) -> str:
        """The current Vim user interface type - gui, term or cterm."""
        lidx = self.cur_lidx if self.mode == 'attrs' else self.cur_lidx - 1
        match lidx - self.lidx:
            case 0:
                return 'gui'
            case 1:
                return 'cterm'
            case 2:
                return 'term'
        return 'gui'

    #< Rendering
    def clean(self) -> None:
        """Clean up the UI for this widget."""
        buf = self.buf
        with buf.modifiable():
            for lidx in range(self.lidx, self.lidx + 3):
                chars = list(buf[lidx])
                chars[self.left] = ' '
                chars[self.right] = ' '
                buf[lidx] = ''.join(chars)

    def draw(self, buf: vpe.Buffer) -> None:
        """Draw this widget."""
        chars = list(buf[self.cur_lidx])
        chars[self.left] = '⦃'
        chars[self.right] = '⦄'
        with buf.modifiable():
            buf[self.cur_lidx] = ''.join(chars)
        props = [
            (self.left, self.left + 2, self.prop_name),
            (self.right - 1, self.right + 1, self.prop_name),
        ]
        buf.set_line_props(self.cur_lidx, props, id=self.prop_id)

    def undraw(self, buf: vpe.Buffer) -> None:
        """Undo effect of the last draw."""
        buf = self.parent.buf
        chars = list(buf[self.cur_lidx])
        chars[self.left] = ' '
        chars[self.right] = ' '
        buf.remove_line_props(self.cur_lidx, id=self.prop_id)
        with buf.modifiable():
            buf[self.cur_lidx] = ''.join(chars)

    def goto_next(self) -> None:
        """Select the next widget group."""
        max_lidx = self.lidx + 2
        self.undraw(self.parent.buf)
        self.cur_lidx += 1
        if self.cur_lidx > max_lidx:
            min_lidx = self.lidx + 1 if self.mode != 'attrs' else self.lidx
            self.cur_lidx = min_lidx
        self.draw(self.parent.buf)

    @property
    def colour_mode(self) -> str:
        """The current colour mode selected - gui, term, none."""
        if self.mode == 'attrs':
            return 'none'
        elif self.cur_lidx == self.lidx:
            return 'gui'
        else:
            return 'term'


class HighlightEditingWidgetBase(Widget):
    """Base for widgets that edit part of a `Highlight`."""
    # TODO: A bad name. Some widgets only use the value.

    @property
    def hl_group(self) -> Highlight:
        """The highlight group being edited."""
        return self.parent.hl_group

    @property
    def ui_type(self) -> str:
        """The current Vim user interface type - gui, term or cterm."""
        return self.parent.ui_type


class RGB_Widget(HighlightEditingWidgetBase):
    """The widget for an RGB component."""
    # pylint: disable=invalid-name

    prop_ids = {
        'red': next(prop_id_source),
        'green': next(prop_id_source),
        'blue': next(prop_id_source),
    }
    prop_name: str = 'Number'

    def __init__(
            self, parent: Tweaker, lidx: int, component: str, left: int,
            term: bool = False
        ):
        # pylint: disable=too-many-arguments,too-many-positional-arguments
        super().__init__(parent, lidx)
        self.component = component
        self.left = left
        self.term = term

    @property
    def hl_colour(self) -> Colour:
        """The highlight group being edited."""
        assert self.mode != 'attr'
        ui_type = 'cterm' if self.term else 'gui'
        if self.hl_group.cterm_copies_gui:
            ui_type = 'gui'
        return self.hl_group.get_colour(f'{ui_type}.{self.mode}')

    @property
    def value(self) -> int | str:
        """The current value for this widget."""
        colour = self.hl_colour
        if colour is none_colour:
            return '-n-'
        elif colour is unused_colour:
            return '---'
        return getattr(colour, self.component[0])

    def draw(self, buf: vpe.Buffer) -> None:
        """Draw this widget."""
        value = self.value
        lidx = self.lidx
        text = buf[lidx]
        a, b = text[:self.left], text[self.left + 6:]
        prop_name = self.prop_name
        match value:
            case '-n-':
                content = '-n-/--'
                prop_name = 'Tweaker_GreyedOut'
            case '---':
                content = '---/--'
                prop_name = 'Tweaker_GreyedOut'
            case _:
                content = f'{self.value:3}/{self.value:02x}'
        if self.hl_group.cterm_copies_gui and self.term:
            prop_name = 'Tweaker_GreyedOut'

        with buf.modifiable():
            buf[lidx] = f'{a}{content}{b}'
        prop_id = self.prop_ids[self.component]
        buf.remove_line_props(lidx, id=prop_id)
        buf.set_line_prop(
            lidx, self.left, self.left + 3, prop_name,
            id=prop_id)
        buf.set_line_prop(
            lidx, self.left + 4, self.left + 6, prop_name,
            id=prop_id)

    def modify_value(self, delta: int, undo: UndoGroup) -> bool:
        """Adjust value by a given delta."""
        hl_colour = self.hl_colour
        prev_value = self.value
        code = self.component[0]
        hl_colour.adjust_component(code, delta)
        if prev_value != self.value:
            undo.append(partial(setattr, hl_colour, code, prev_value))
            return True
        else:
            return False


class AttrWidget(HighlightEditingWidgetBase):
    """A widget that displays text attribute values."""

    prop_id = next(prop_id_source)

    attrs = {
        'bold': 'bold',
        'italic': 'italic',
        'underline': 'u/l',
        'undercurl': 'u/c',
        'strikethrough': 'strike',
        'reverse': 'rev',
        'standout': 'standout',
        'nocombine': 'nocombine',
    }

    def __init__(
            self, parent: Tweaker, lidx: int, left: int, mode: str,
        ):
        super().__init__(parent, lidx)
        self.left = left
        self.this_mode = mode

    def draw(self, buf: vpe.Buffer) -> None:
        """Draw this widget."""
        hl_group = self.hl_group.resolve_link()
        settings = getattr(hl_group, self.this_mode)
        active = []
        for attr_name, display_name in self.attrs.items():
            flag = getattr(settings, attr_name)
            if flag:
                active.append(display_name)
        content = ' '.join(active)

        lidx = self.lidx
        text = buf[lidx]
        left, right = text[:self.left], text[-4:]
        w = len(text) - len(left) - len(right)
        content = content[:w]
        buf.remove_line_props(lidx, id=self.prop_id)
        with buf.modifiable():
            buf[lidx] = f'{left}{content:{w}}{right}'

        if self.hl_group.is_linked:
            buf.set_line_prop(
                lidx, self.left, self.left + len(content),
                'Tweaker_GreyedOut', id=self.prop_id)


class StepWidget(Widget):
    """The widget for the increment/decrement step."""

    prop_id = next(prop_id_source)
    prop_name: str = 'Number'

    def __init__(
            self, parent: Tweaker, lidx: int, left: int
        ):
        super().__init__(parent, lidx)
        self.left = left
        self.value = 5

    def draw(self, buf: vpe.Buffer) -> None:
        """Draw this widget."""
        text = buf[self.lidx]
        a, b = text[:self.left], text[self.left + 2:]
        content = f'{self.value:2}'
        with buf.modifiable():
            buf[self.lidx] = f'{a}{content}{b}'
        if not buf.query_props(self.lidx, ids=self.prop_id):
            buf.set_line_prop(
                self.lidx, self.left, self.left + 2, self.prop_name,
                id=self.prop_id)

    def cycle_value(self, undo: UndoGroup) -> None:
        """Cycle to the next increment value."""
        undo.append(partial(self.undo, self.value))
        match self.value:
            case 10:
                self.value = 1
            case 5:
                self.value = 10
            case _:
                self.value = 5
        self.draw(self.parent.buf)

    def undo(self, value: int) -> None:
        """Undo a change back to a given value."""
        self.value = value
        self.draw(self.parent.buf)


class CloseColourWidget(HighlightEditingWidgetBase):
    """The widget closest colour display."""

    prop_id = next(prop_id_source)
    prop_name: str = 'Tweaker_ClosestColour'

    def __init__(
            self, parent: Tweaker, lidx: int, left: int, right: int,
            term: bool = False
        ):
        # pylint: disable=too-many-arguments,too-many-positional-arguments
        super().__init__(parent, lidx)
        self.left = left
        self.right = right
        self.term = term

    def draw(self, buf: vpe.Buffer) -> None:
        """Draw this widget."""
        # pylint: disable=too-many-locals
        lidx = self.lidx
        ui_type = 'cterm' if self.term else 'gui'
        hl_group = self.parent.hl_group
        colour = hl_group.get_colour(f'{ui_type}.{self.mode}')
        match ui_type:
            case 'gui':
                closest_colour = colour.closest_colour
            case 'cterm':
                closest_colour = colour.closest_terminal_colour
            case _:
                return

        text = buf[lidx]
        a, b = text[:self.left], text[self.right:]
        w = self.right - self.left - 6
        n = closest_colour.number
        d = colour.distance(closest_colour)
        col_text = closest_colour.name[:w -5]
        col_text = f'{col_text} d={d:4.2f}'
        if n >= 0:
            content = f'XXXX: {n:<3} {col_text:<{w-4}}'
        else:
            content = f'XXXX:     {col_text:<{w-4}}'
        with buf.modifiable():
            buf[lidx] = f'{a}{content}{b}'
        buf.remove_line_props(lidx, id=self.prop_id)
        suffix = '2' if self.term else ''
        buf.set_line_prop(
            lidx, self.left, self.left + 4, f'{self.prop_name}{suffix}',
            id=self.prop_id)
        highlight = tweaker_highlights[f'ClosestColour{suffix}']
        highlight.set_colour('gui.fg', closest_colour)
        highlight.apply()


class SampleWidget(HighlightEditingWidgetBase):
    """The widget showing sample text."""
    # TODO: Use base class for this and CloseColourWidget.

    prop_id = next(prop_id_source)

    def __init__(
            self, parent: Tweaker, lidx: int, idx_1: int, idx_2: int,
            idx_3: int,
        ):
        # pylint: disable=too-many-arguments,too-many-positional-arguments
        super().__init__(parent, lidx)
        self.idx_1 = idx_1
        self.idx_2 = idx_2
        self.idx_3 = idx_3

    def draw(self, buf: vpe.Buffer) -> None:
        """Draw this widget."""
        hl_group = self.hl_group.resolve_link()
        self.buf.remove_line_props(self.lidx, id=self.prop_id)
        self.buf.set_line_prop(
            self.lidx, self.idx_1, self.idx_1 + len('GUI text sample'),
            hl_group=self.hl_group.name, id=self.prop_id)

        hl = tweaker_highlights['CTermEmul']
        if self.hl_group.cterm_copies_gui:
            cterm = hl_group.gui
        else:
            cterm = hl_group.cterm
        t_cterm = hl_group.cterm
        if cterm is not None and hl.gui is not None:
            hl.gui.set_from_colour_term_settings(cterm)
            if t_cterm is not None:
                hl.gui.set_flags_from_colour_term_settings(t_cterm)
            else:
                hl.gui.clear_flags()
            hl.apply()
            self.buf.set_line_prop(
                self.lidx, self.idx_2, self.idx_2 + len('Color term sample'),
                hl_group='Tweaker_CTermEmul', id=self.prop_id)

        hl = tweaker_highlights['TermEmul']
        term = hl_group.term
        if term is not None and hl.gui is not None:
            hl.gui.set_from_mono_term_settings(term)
            hl.apply()
            self.buf.set_line_prop(
                self.lidx, self.idx_3, self.idx_3 + len('Mono term sample'),
                hl_group='Tweaker_TermEmul', id=self.prop_id)


class ColourModeWidget(Widget):
    """The widget showing which colour is being edited."""

    prop_id = next(prop_id_source)

    def __init__(
            self, parent: Tweaker, lidx: int, left: int,
        ):
        super().__init__(parent, lidx)
        self.left = left

    def draw(self, buf: vpe.Buffer) -> None:
        """Draw this widget."""
        match self.parent.mode:
            case 'fg':
                content = 'Foreground'
            case 'bg':
                content = 'Background'
            case 'sp':
                if self.parent.ui_type == 'gui':
                    content = 'Special'
                else:
                    content = 'Underline'
            case _:
                return

        lidx = self.lidx
        buf = self.parent.buf
        buf.clear_line_props(lidx)
        line_char = '─'
        text = buf[lidx]
        w = 40
        left, right = text[:self.left - 1], text[self.left + w + 1:]
        right = line_char * w + right
        right = right[len(content):]
        buf[lidx] = f'{left} {content} {right}'

class HotKeyWidget(Widget):
    """A widget that can grey-out inactive hot keys."""

    prop_id = next(prop_id_source)

    def __init__(self, parent: Tweaker):
        super().__init__(parent, lidx=0)
        self.hot_keys: dict[str, tuple[int, int, int]] = {}
        self.disabled: set[str] = set()

    def add_key(self, key: str, lidx: int, start: int, end: int) -> None:
        """Add a key to the set of managed hopt keys."""
        self.hot_keys[key] = lidx, start, end

    def set_inactive(self, keys: set[str]) -> None:
        """Set the inactive keys."""
        self.disabled.clear()
        self.disabled.update(keys)

    def draw(self, buf: vpe.Buffer) -> None:
        """Draw this widget."""

        by_line: dict[int, list[tuple]] = defaultdict(list)
        for key, (lidx, start, end) in self.hot_keys.items():
            if key in self.disabled:
                prop = 'Tweaker_GreyedOut'
            else:
                prop = 'Tweaker_Hotkey'
            by_line[lidx].append((key, start, end, prop))
        buf = self.buf
        for lidx, entries in by_line.items():
            text = buf[lidx]
            buf.remove_line_props(lidx, id=self.prop_id)
            for key, start, end, prop in entries:
                left, right = text[:start], text[end:]
                text = f'{left}{key}{right}'
            buf[lidx] = text
            for key, start, end, prop in entries:
                buf.set_line_prop(lidx, start, end, prop, id=self.prop_id)


class HighlightWidget(Widget):
    """A widget that displays details of a highlight group.

    A list of these appears under the main editing area. Each shows the command
    that create the highlight. The highlight being edited is also shown at the
    bottom of the editing area.
    """
    _draw_lidx: ClassVar[int] = -1

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
        self.cur_lidx: int = -1
        self.highlight: Highlight = highlight
        self.number_of_lines: int = 0
        self.before: HighlightWidget | None = before

    @property
    def enabled(self) -> bool:
        """Test if this widget is enabled (should be displayed."""
        parent = self.parent
        if not parent.show_inactive_highlights:
            if self.highlight.name not in parent.active_property_names:
                return False
        return True

    @property
    def draw_lidx(self) -> int:
        """The line where drawing should start for the widget bing drawn."""
        return self._draw_lidx

    @draw_lidx.setter
    def draw_lidx(self, value) -> None:
        self.__class__._draw_lidx = value    # pylint: disable=protected-access

    @property
    def height(self) -> int:
        return self.number_of_lines

    def draw(self, buf: vpe.Buffer) -> None:
        """Draw and style this widget."""
        if self.before is None:
            buf[self.lidx:] = []
            self.draw_lidx = self.lidx

        self.cur_lidx = -1
        if not self.enabled:
            return

        self.cur_lidx = self.draw_lidx
        parent = self.parent
        if not parent.show_inactive_highlights:
            if self.highlight.name not in parent.active_property_names:
                return

        self.draw_at_line(self.cur_lidx)
        self.draw_lidx = self.cur_lidx + self.number_of_lines
        if self.highlight is self.parent.hl_group:
            self.draw_at_line(self.parent.hl_display_lidx, height=3)

    def draw_at_line(self, lidx: int, height: int = 0) -> None:
        """Draw this starting at the give line index."""
        # pylint: disable=too-many-locals
        for i in range(lidx, lidx + height):
            self.buf.clear_line_props(i)
            self.buf[i] = ''

        prefix = '    '
        highlight = self.highlight
        if highlight.name in self.parent.active_property_names:
            prefix = ' A  '
        name = highlight.name
        length = 0
        if highlight.is_linked:
            self.draw_line(
                lidx,
                f'highlight link [{name}]{name}[]'
                f' [{highlight.link}]{highlight.link}',
                rich=True, prefix=prefix)
            self.number_of_lines = 1
        else:
            def flush():
                nonlocal length, prefix
                self.draw_line(
                    lidx + self.number_of_lines, ' '.join(parts), props,
                    prefix=prefix)
                prefix = '    '
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

    def draw_line(
            self, lidx: int, text: str, props: list | None = None,
            rich: bool = False, prefix: str = '    '
        ) -> None:
        """Draw a line and add its properties."""
        # pylint: disable=too-many-arguments,too-many-positional-arguments
        props = props or []
        buf = self.parent.buf
        offset = len(prefix)
        if lidx + 1 > len(buf):
            buf.append('')
        if rich:
            buf.set_rich_like_line(lidx, f'{prefix}{text}')
        else:
            buf[lidx] = f'{prefix}{text}'
            buf.set_line_props(
                lidx, [(s + offset, e + offset, n) for n, s, e in props])

    def matches_line_index(self, lidx: int) -> bool:
        """Test if a line index maps on to this widget."""
        if self.cur_lidx < 0:
            return False
        else:
            return self.cur_lidx <= lidx < self.cur_lidx + self.number_of_lines


#< Support functions
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
        std_colours[name[4:]] = Colour.parse(name)

    while vim.vvars.colornames:
        vim.vvars.colornames.popitem()
    vim.vvars.colornames.update(saved_colours)


def create_tweaker_groups():
    """Create highlight groups specific to tweaker."""
    kw: dict['str', Colour]
    for name, data in TWEAKER_GROUPS.items():
        kw = {'fg': unused_colour, 'bg': unused_colour}
        hl_name = f'Tweaker_{name}'
        if 'fg' in data:
            kw['fg'] = Colour.parse(data['fg'])
        if 'bg' in data:
            kw['bg'] = Colour.parse(data['bg'])

        term = TermSettings()
        cterm = ColourTermSettings(**kw)               # type: ignore[arg-type]
        gui = GUISettings(**kw)                        # type: ignore[arg-type]
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


def _get_used_prop_names() -> set[str]:
    """Get a list of all the property name used in the current buffer."""
    names: set[str] = set()
    for i in range(len(vim.current.buffer)):
        for prop in vim.prop_list(i + 1):
            name = prop.get('type', '')
            if name:
                names.add(name)
    return names


tweaker: Tweaker | None = None
std_colours: dict[str, Colour] = {}
tweaker_highlights: dict[str, Highlight] = {}


#< Older widgets

class ColourPopup(vpe.Popup):
    """A popup window used to select a colour."""

    def __init__(
            self, *, parent: Tweaker, **kwargs):
        super().__init__('', name='Colour Palette', **kwargs)
        self.parent = parent
        assert self.buffer is not None
        self.buf: vpe.Buffer = self.buffer

    def on_key(self, key: str | bytes, byte_seq: bytes) -> bool:
        """Process a key or mouse event for the popup window."""
        if isinstance(key, bytes):
            key = key.decode('utf-8', errors='ignore')
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
        colour_name = self.buf[lidx].split()[0]

        self.hide()
        self.parent.complete_handle_choose_colour(colour_name)
        return True
