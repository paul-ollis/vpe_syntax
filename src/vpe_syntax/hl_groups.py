"""Highlight groups/properties used for syntax highlighting."""
from __future__ import annotations

from collections import defaultdict
from colorsys import hls_to_rgb, rgb_to_hls
from dataclasses import dataclass, field, fields
from functools import lru_cache, partial
from math import sqrt
from typing import Callable, ClassVar, TypeAlias

import vpe
from vpe import vim

#: The standard code highlight groups and default property priorities.
#:
#: These groups are created as a result of 'syntax on' being executed. They are
#: the recommended generic group names that are applicable for a range of
#: programming languages.
#:
#: Each has a priority value, which is used by Vim to handle overlapping
#: propeties. The property with the highest priority is used to colour the
#: text. In order to handle syntax items that nest within other syntax items
#: and also embedded syntax, a priorty scheme is required. The current scheme
#: is, roughly:
#:
#: - The default priorty for a group is 50 and values in the range 1 to 99 are
#:   allowed. This should be enought to handle normal syntax item nesting.
#: - For each group, additional property types are created to handle embedded
#:   syntax. These have multiple of 100 added to their priority values. For
#:   example, the "Comment" group gives rise to property types "Comment" and
#:   "Comment1", with priority values of 50 and 150.
STANDARD_GROUPS = (
    # The groupings match those in Vim's help. The first entry in a group is
    # the 'preferred' group and the others are considered 'sub-groups'. This
    # set of names and the groupings thereof are somewhat C-centric.
    ('Comment', 50),

    ('Constant', 50),
    ('String', 30),
    ('Character', 50),
    ('Number', 50),
    ('Boolean', 50),
    ('Float', 50),

    ('Identifier', 50),
    ('Function', 50),

    ('Statement', 50),
    ('Conditional', 50),
    ('Repeat', 50),
    ('Label', 50),
    ('Operator', 50),
    ('Keyword', 50),
    ('Exception', 50),

    ('PreProc', 50),
    ('Include', 50),
    ('Define', 50),
    ('Macro', 50),
    ('PreCondit', 50),

    ('Type', 50),
    ('StorageClass', 50),
    ('Structure', 50),
    ('Typedef', 50),

    ('Special', 50),
    ('SpecialChar', 50),
    ('Tag', 50),
    ('Delimiter', 50),
    ('SpecialComment', 50),
    ('Debug', 50),

    ('Underlined', 50),

    ('Error', 50),

    ('Todo', 50),

    ('Added', 50),

    ('Changed', 50),

    ('Removed', 50),
)

#: Some additional syntax highlighting groups for more nuanced highlighting.
#:
#: Tree-sitter parsing make it relatively easy to identify more fine grained
#: syntactic and semantic content from code. Hence this set of extended
#: 'standard' groups.
#:
#: In this table, each is group is linked to one of the 'standard' groups or
#: `None` as a starting point. The intention is that users or colour schemes
#: may over-ride these group definitions as required.
EXT_STANDARD_GROUPS: list[tuple[str, str | None, int]] = [
    ('Argument',            'Identifier',  55),
    ('Attribute',           'Identifier',  55),
    ('CalledFunction',      'Identifier',  55),
    ('CalledMethod',        'Identifier',  58),
    ('Class',               'Keyword',     55),
    ('ClassName',           'Identifier',  55),
    ('Constructor',         'Normal',      65),
    ('DefinitionStarter',   'Identifier',  55),
    ('Decorator',           'Identifier',  55),
    ('DocString',           'Comment',     55),
    ('FormatIdentifier',    'Normal',      45),
    ('FormatSpecifier',     'Normal',      40),
    ('FunctionDef',         'Keyword',     55),
    ('FunctionName',        'Identifier',  55),
    ('GenericType',         'Type',        55),
    ('ImportedAliasedName', 'Normal',      55),
    ('ImportedName',        'Normal',      55),
    ('Import',              'Import',      55),
    ('Interpolation',       'String',      40),
    ('MethodCall',          'Normal',      55),
    ('MethodDef',           'Keyword',     55),
    ('MethodName',          'Identifier',  55),
    ('None',                'Special',     55),
    ('NonStandardSelf',     'Normal',      55),
    ('Parameter',           'Normal',      55),
    ('Return',              'Keyword',     55),
    ('Self',                'Normal',      55),
    ('SpecialPunctuation',  'Normal',      55),
    ('StandardConst',       'Identifier',  55),
    ('SyntaxError',         'WarningMsg',  10),
    ('TypeBracket',         'Normal',      60),
]


class Colour:
    """The RGB representation of a colour.

    If any component is -1 then the instance represents a non-colour.
    """
    def __init__(self, r: int = -1, g: int = -1, b: int = -1):
        self._r = r
        self._g = g
        self._b = b

    @classmethod
    def _from_colour_name(cls, name: str) -> Colour:
        """Create an instance from a colour name."""
        return cls._from_hex_rgb(
            vim.vvars.colornames.get(f'{name.lower()}', '#ffffff'))

    @classmethod
    def _from_hex_rgb(cls, rgb_str: str) -> Colour:
        """Create an instance from a Vim RGB colour string."""
        hex_strings = rgb_str[1:3], rgb_str[3:5], rgb_str[5:7]
        r, g, b = [int(s, 16) for s in hex_strings]
        return cls(r, g, b)

    @classmethod
    def parse(cls, name_or_hex: str) -> Colour:
        """Create an instance from a colour name or hexadecimal."""
        if name_or_hex.startswith('#'):
            return cls._from_hex_rgb(name_or_hex)
        else:
            return cls._from_colour_name(name_or_hex)

    @property
    def r(self) -> int:
        """The red component value in the range -1 (non-colour) to 255."""
        return self._r

    @property
    def g(self) -> int:
        """The green component value in the range -1 (non-colour) to 255."""
        return self._g

    @property
    def b(self) -> int:
        """The blue component value in the range -1 (non-colour) to 255."""
        return self._b

    def is_valid(self) -> bool:
        """Test if all RGB values are valid."""
        positive = self.r >= 0 and self.g >= 0 and self.b >= 0
        inrange = self.r <= 255 and self.g <= 255 and self.b <= 255
        return positive and inrange

    def as_hex(self) -> bool:
        """Provide Vim style hex representation."""
        return f'#{self.r:02x}{self.g:02x}{self.b:02x}'

    def as_decimal(self) -> bool:
        """Provide decimal values."""
        return f'({self.r},{self.g},{self.b})'

    def __eq__(self, other: NamedColour) -> bool:
        ra, ga, ba = self.r, self.g, self.b
        rb, gb, bb = other.r, other.g, other.b
        return (ra, ga, ba) == (rb, gb, bb)


class NamedColour(Colour):
    """The RGB representation of a named colour.

    Instances of this class *must* have a valid name.
    """
    def __init__(self, name: str, r: int = -1, g: int = -1, b: int = -1):
        super().__init__(r, g, b)
        self._name = name

    @property
    def name(self) -> str:
        """The name defined for this colour's RGB values."""
        return self._name

    @classmethod
    def parse(cls, name_or_hex: str) -> Colour:
        """Create an instance from a colour name."""
        assert name_or_hex and not name_or_hex.startswith('#')
        colour = Colour.parse(name_or_hex)
        return cls(name_or_hex, colour.r, colour.g, colour.b)


class TerminalColour(Colour):
    """The RGB representation of a terminal colour.

    Instances of this class jhave a corresponding terminal colour code 0-256.
    """
    def __init__(self, hex_val: str, number: int):
        colour = Colour.parse(hex_val)
        super().__init__(colour.r, colour.g, colour.b)
        self.number = number


class EditableColour(NamedColour):
    """The RGB representation of a colour.

    This over-rides `NamedColour` as follows:

    - The RGB components can be modified.
    - This can be unnamed and, when it has a name, that name becomes invalid
      when any of the RGB values difffer from those used at construction time.

    @name_is_valid:
        Set false the `name` does match the current RGB values.
    @close_colour:
        The closest, named `NamedColour` that matches the current RGB values.
    """
    # pylint: disable=too-many-instance-attributes

    _v_colournames: ClassVar[dict] = {}

    def __init__(self, name: str = '', r: int = -1, g: int = -1, b: int = -1):
        super().__init__('--unused-name--', r, g, b)
        self._name = name
        self.name_is_valid = bool(name)
        self.closest_colour: NamedColour | None = None
        self.closest_terminal_color: TerminalColour | None = None
        self._update_closest_colours()

    @Colour.r.setter
    def r(self, value) -> int:
        self._r = value
        self._match_validity(self._r)

    @Colour.g.setter
    def g(self, value) -> int:
        self._g = value
        self._match_validity(self._g)

    @Colour.b.setter
    def b(self, value) -> int:
        self._b = value
        self._match_validity(self._b)

    @classmethod
    def from_colour(cls, colour: Colour) -> EditableColour:
        """Create an instance from another colour."""
        return cls('', colour.r, colour.g, colour.b)

    @classmethod
    def parse(cls, name_or_hex: str) -> EditableColour:
        """Create an instance from a colour name."""
        if not name_or_hex:
            return cls('', -1, -1, -1)
        else:
            colour = Colour.parse(name_or_hex)
            name = '' if name_or_hex.startswith('#') else name_or_hex
            return cls(name, colour.r, colour.g, colour.b)

    def adjust_component(self, name: str, inc: int):
        """Adjust one of the RGB values by defined amount."""
        if name == 'r':
            self.r = min(255, max(0, self.r + inc))
        elif name == 'g':
            self.g = min(255, max(0, self.g + inc))
        elif name == 'b':
            self.b = min(255, max(0, self.b + inc))
        self._update_closest_colours()

    def adjust_brightness(self, inc: float) -> Colour:
        """Adjust the brightness of this colour.

        :inc:
            Change in brighness. -255.0 or less will completely darken and
            255.0 or above will completely lighten.
        """
        h, l, s = rgb_to_hls(self.r, self.g, self.b)
        l = min(255.0, max(0.0, l + inc))
        rf, gf, bf = hls_to_rgb(h, l, s)
        self.r = min(255, max(0, round(rf)))
        self.g = min(255, max(0, round(gf)))
        self.b = min(255, max(0, round(bf)))
        self._update_closest_colours()

    @property
    def lightness(self) -> float:
        """The lightness of this colour - black=0.0, white=255.0."""
        _h, l, _s = rgb_to_hls(self.r, self.g, self.b)
        return l

    def distance(self, other: Colour) -> float:
        """Calculate the distance between 2 colours."""
        ra, ga, ba = self.r, self.g, self.b
        rb, gb, bb = other.r, other.g, other.b
        return sqrt((ra - rb)**2 + (ga - gb)**2  + (ba - bb)**2)

    def _update_closest_colours(self) -> None:
        """Update the closest colour match."""
        if not self.is_valid():
            self.closest_colour = None
            self.closest_terminal_color = None
            return

        if len(self._v_colournames) == 0:
            for name in vim.vvars.colornames:
                self._v_colournames[name] = NamedColour.parse(name)

        self.closest_colour = self._find_closest(self.r, self.g, self.b)
        self.closest_terminal_color = self._find_closest_terminal_colour(
            self.r, self.g, self.b)

    def _match_validity(self, value: int) -> None:
        """Make all components equally valid or invalid."""
        if 0 <= value <= 255:
            self._r = min(255, max(0, self._r))
            self._g = min(255, max(0, self._g))
            self._b = min(255, max(0, self._b))
        else:
            self._r = self._g = self._b = -1

    @classmethod
    @lru_cache(200)
    def _find_closest(cls, r, g, b) -> NamedColour:
        _, closest_name = min(
            (cls._distance(r, g, b, name), name)
            for name in cls._v_colournames
        )
        return cls._v_colournames[closest_name]

    @classmethod
    @lru_cache(200)
    def _find_closest_terminal_colour(cls, r, g, b) -> TerminalColour:
        _, code = min(
            (cls._terminal_distance(r, g, b, colour), colour.number)
            for colour in terminal_colour_list
        )
        return cterm_code_to_colour[code]

    @classmethod
    def _distance(cls, r, g, b, name) -> float:
        other = cls._v_colournames[name]
        rb, gb, bb = other.r, other.g, other.b
        return sqrt((r - rb)**2 + (g - gb)**2  + (b - bb)**2)

    @classmethod
    def _terminal_distance(cls, r, g, b, other) -> float:
        rb, gb, bb = other.r, other.g, other.b
        return sqrt((r - rb)**2 + (g - gb)**2  + (b - bb)**2)


@dataclass
class HighlightSettings:
    """Colour and style settings for a highlight group."""
    # pylint: disable=too-many-instance-attributes

    bold: bool = False
    underline: bool = False
    undercurl: bool = False
    strikethrough: bool = False
    reverse: bool = False
    italic: bool = False
    standout: bool = False
    nocombine: bool = False
    fg: EditableColour = field(default_factory=EditableColour)
    bg: EditableColour = field(default_factory=EditableColour)
    sp: EditableColour = field(default_factory=EditableColour)
    fg_name: str = ''
    bg_name: str = ''
    sp_name: str = ''

    mode: ClassVar[str]
    ortho_map: ClassVar[dict[str, str]] = {
        'strikethrough': 'strike',
    }
    unused: ClassVar[set[str]] = set()
    meta: ClassVar[set[str]] = set(('fg_name', 'bg_name', 'sp_name'))

    # TODO:
    #     The Vim docs are contradictory for these values. The highlight
    #     command seems to accept them, but they cannot be queried using
    #     synIDattr.
    #- underdouble: bool = False
    #- underdotted: bool = False
    #- underdashed: bool = False

    @classmethod
    def from_syn_id(cls, synid: int) -> HighlightSettings:
        """Create by querying a given highlight group.

        :synid:
            The ID of the syntax group to query.
        """
        kw = {}
        for f in fields(cls):
            query_name = f.name
            if query_name in cls.unused:
                continue
            if query_name in cls.meta:
                continue
            value = vim.synIDattr(synid, f.name, cls.mode)
            if f.name in ('fg', 'bg', 'sp'):
                try:
                    value = int(value)
                except ValueError:
                    pass
                else:
                    t_colour = cterm_code_to_colour.get(
                        value, cterm_code_to_colour[15])
                    value = t_colour.as_hex()

                kw[f.name] = EditableColour.parse(value)
                if not value.startswith('#'):
                    kw[f'{f.name}_name'] = value
                else:
                    kw[f'{f.name}_name'] = ''
            elif value and value in '01':
                kw[f.name] = bool(int(value))
        return cls(**kw)

    def format_args(self) -> dict:
        """Format the arguments for these settings."""
        attrs = []
        args = {}
        for f in fields(self):
            arg_name = f.name
            if arg_name in self.unused:
                continue
            if arg_name in self.meta:
                continue
            value = getattr(self, arg_name)
            if f.type == 'bool':
                if value:
                    attrs.append(arg_name)
            elif arg_name not in self.unused:
                arg_name = self.ortho_map.get(arg_name, arg_name)
                if value.is_valid():
                    args[f'{self.mode}{arg_name}'] = value.as_hex()
        if attrs:
            args[f'{self.mode}'] = ','.join(attrs)
        return args

    def format_args_as_string(self) -> str:
        """Format the arguments for these settings, as a string."""
        parts = [
            f'{name}={value}' for name, value in self.format_args().items()]
        return ' '.join(parts)


class TermSettings(HighlightSettings):
    """Highlight settings for a plain terminal."""

    mode: ClassVar[str] = 'term'
    ortho_map: ClassVar[dict[str, str]] = HighlightSettings.ortho_map | {
        'sp': 'ul',
    }
    unused: ClassVar[set[str]] = set(('fg', 'bg', 'sp'))


class ColourTermSettings(HighlightSettings):
    """Highlight settings for a colour terminal."""

    mode: ClassVar[str] = 'cterm'

    def format_args(self) -> dict:
        """Format the arguments for these settings."""
        args = super().format_args()
        for f in fields(self):
            arg_name = f.name
            value = getattr(self, arg_name)
            arg_name = self.ortho_map.get(arg_name, arg_name)
            arg_name = f'{self.mode}{arg_name}'
            if arg_name not in args or f.type == 'bool':
                continue

            if value.is_valid():
                e_colour = EditableColour.from_colour(value)
                args[arg_name] = str(e_colour.closest_terminal_color.number)
        return args


class GUISettings(HighlightSettings):
    """Highlight settings for a GUI."""

    mode: ClassVar[str] = 'gui'


@dataclass
class Highlight:
    """Pythonic representation of a Vim highlight group.

    This holds details of a highlight group in an easily accessible form.

    @name:
        The highlight group's name.
    @term:
        The simple terminal settings.
    @cterm:
        The colour terminal settings.
    @gui:
        The GUI mode settings.
    @link:
        The name of another highlight group that this links to.
    @subscribers:
        Subscribed callbacks for attribute changes.
    """

    name: str
    term: TermSettings | None = None
    cterm: ColourTermSettings | None = None
    gui: GUISettings | None = None
    link: str | None = None
    subscribers: dict[str, list[Callable]] = field(
        default_factory=partial(defaultdict, list))

    @property
    def is_linked(self) -> bool:
        """Flag indicating if this is just linked to another highlight."""
        return None in (self.term, self.cterm, self.gui)

    def break_link(self) -> None:
        """Break this highlights link by copying the linked group."""
        if not self.is_linked:
            return
        self.copy_from_named_highlight(self.link)

    def copy_from_named_highlight(self, other: str) -> None:
        """Copy settings from another highlight."""
        e_colour = Highlight.from_name(other)
        self.term = e_colour.term
        self.cterm = e_colour.cterm
        self.gui = e_colour.gui

    def adjust_brightness(self, attr: str, inc: float) -> None:
        """Adjust one a colour's brighness."""
        rgb = self.get_colour(attr)
        rgb.adjust_brightness(inc)
        for handler in self.subscribers[attr]:
            handler(rgb)

    def adjust_rgb(self, attr: str, key: str, inc: int) -> None:
        """Adjust one of the RGB attributes."""
        inc = 10 if key.upper() == key else -10
        rgb = self.get_colour(attr)
        rgb.adjust_component(key.lower(), inc)
        for handler in self.subscribers[attr]:
            handler(rgb)

    def toggle_flag(self, mode: str, flag: str) -> None:
        """Adjust one of the flag attributes."""
        settings = getattr(self, mode)
        value = getattr(settings, flag)
        setattr(settings, flag, not value)

    def subscribe(self, attr: str, callback: Callable) -> None:
        """Subscribe to be notified of changes to an attribute."""
        self.subscribers[attr].append(callback)

    def format_args(self) -> dict:
        """Format the arguments for a Vim highlight command."""
        kw = {}
        if not self.is_linked:
            kw.update(self.term.format_args())
            kw.update(self.cterm.format_args())
            kw.update(self.gui.format_args())
        return kw

    def apply(self, *, dump: bool = False) -> None:
        """Update the actual Vim highlight group's settings."""
        kw = self.format_args()
        if kw:
            vpe.highlight(group=self.name, clear=True)
            vpe.highlight(group=self.name, dump=dump, **kw)
        else:
            vpe.highlight(group=self.name, link=self.link, dump=dump)

    def create_property(self, priority: int = 50, level: int = 0):
        """Create a property (type) named after this highlight group."""
        priority = priority + 100 * level
        kw = {
            'priority': priority,
            'combine': True,        # Combine with normal syntax highlighting.
            'start_incl': True,     # Do extend for inserts at the start.
            'end_incl': True,       # Do extend for inserts at the end.
            'highlight': self.name,
        }
        if self.name == 'DocString':
            kw['spell'] = True
        else:
            kw['spell'] = False
        name = self.name if level == 0 else f'{self.name}{level}'
        known_prop_info = vim.prop_type_get(name)
        if not known_prop_info:
            vim.prop_type_add(name, kw)

    def get_colour(self, attr: str) -> Colour:
        """Get a colour for a given attribute name."""
        mode, rgb_name = attr.split('.')
        try:
            return getattr(getattr(self, mode), rgb_name)
        except AttributeError:
            return EditableColour(-1, -1, -1)

    def set_colour(self, attr: str, colour: EditableColour) -> None:
        """Set a colour for a given attribute name."""
        mode, rgb_name = attr.split('.')
        return setattr(getattr(self, mode), rgb_name, colour)

    @classmethod
    def from_name(cls, name: str) -> Highlight:
        """Create by querying a named highlight group."""
        hid = vim.hlID(name)
        synid = vim.synIDtrans(hid)
        kw = {}
        kw['term'] = TermSettings.from_syn_id(synid)
        kw['cterm'] = ColourTermSettings.from_syn_id(synid)
        kw['gui'] = GUISettings.from_syn_id(synid)

        return cls(name=name, **kw)


def create_std_group_highlights() -> dict[str, Highlight]:
    """Create a `Highlight` instances for each standard highlight group."""
    table = {}
    for name, priority in STANDARD_GROUPS:
        group = Highlight.from_name(name)
        table[name] = group
        group.create_property(priority)
        group.create_property(priority, level=1)
    return table


def create_ext_std_group_highlights() -> dict[str, Highlight]:
    """Create a `Highlight` instances for each extension highlight group."""
    table = {}
    for name, link, priority in EXT_STANDARD_GROUPS:
        hid = vim.hlID(name)
        if hid == 0:
            # Group is not defined so add it.
            group = Highlight(name, link=link)
        else:
            # Group is defined so use defined settings.
            attr_dict = dict(vim.hlget(name)[0])
            link_name = attr_dict.get('linksto')
            if link_name:
                group = Highlight(name, link=link_name)
            else:
                group = Highlight.from_name(name)
        table[name] = group
        group.apply()
        group.create_property(priority=priority)
        group.create_property(priority=priority, level=1)
    return table


# A list of the terminal colours.
terminal_colour_list = (
    TerminalColour('#000000', 0),
    TerminalColour('#800000', 1),
    TerminalColour('#008000', 2),
    TerminalColour('#808000', 3),
    TerminalColour('#000080', 4),
    TerminalColour('#800080', 5),
    TerminalColour('#008080', 6),
    TerminalColour('#c0c0c0', 7),
    TerminalColour('#808080', 8),
    TerminalColour('#ff0000', 9),
    TerminalColour('#00ff00', 10),
    TerminalColour('#ffff00', 11),
    TerminalColour('#0000ff', 12),
    TerminalColour('#ff00ff', 13),
    TerminalColour('#00ffff', 14),
    TerminalColour('#ffffff', 15),
    TerminalColour('#000000', 16),
    TerminalColour('#00005f', 17),
    TerminalColour('#000087', 18),
    TerminalColour('#0000af', 19),
    TerminalColour('#0000d7', 20),
    TerminalColour('#0000ff', 21),
    TerminalColour('#005f00', 22),
    TerminalColour('#005f5f', 23),
    TerminalColour('#005f87', 24),
    TerminalColour('#005faf', 25),
    TerminalColour('#005fd7', 26),
    TerminalColour('#005fff', 27),
    TerminalColour('#008700', 28),
    TerminalColour('#00875f', 29),
    TerminalColour('#008787', 30),
    TerminalColour('#0087af', 31),
    TerminalColour('#0087d7', 32),
    TerminalColour('#0087ff', 33),
    TerminalColour('#00af00', 34),
    TerminalColour('#00af5f', 35),
    TerminalColour('#00af87', 36),
    TerminalColour('#00afaf', 37),
    TerminalColour('#00afd7', 38),
    TerminalColour('#00afff', 39),
    TerminalColour('#00d700', 40),
    TerminalColour('#00d75f', 41),
    TerminalColour('#00d787', 42),
    TerminalColour('#00d7af', 43),
    TerminalColour('#00d7d7', 44),
    TerminalColour('#00d7ff', 45),
    TerminalColour('#00ff00', 46),
    TerminalColour('#00ff5f', 47),
    TerminalColour('#00ff87', 48),
    TerminalColour('#00ffaf', 49),
    TerminalColour('#00ffd7', 50),
    TerminalColour('#00ffff', 51),
    TerminalColour('#5f0000', 52),
    TerminalColour('#5f005f', 53),
    TerminalColour('#5f0087', 54),
    TerminalColour('#5f00af', 55),
    TerminalColour('#5f00d7', 56),
    TerminalColour('#5f00ff', 57),
    TerminalColour('#5f5f00', 58),
    TerminalColour('#5f5f5f', 59),
    TerminalColour('#5f5f87', 60),
    TerminalColour('#5f5faf', 61),
    TerminalColour('#5f5fd7', 62),
    TerminalColour('#5f5fff', 63),
    TerminalColour('#5f8700', 64),
    TerminalColour('#5f875f', 65),
    TerminalColour('#5f8787', 66),
    TerminalColour('#5f87af', 67),
    TerminalColour('#5f87d7', 68),
    TerminalColour('#5f87ff', 69),
    TerminalColour('#5faf00', 70),
    TerminalColour('#5faf5f', 71),
    TerminalColour('#5faf87', 72),
    TerminalColour('#5fafaf', 73),
    TerminalColour('#5fafd7', 74),
    TerminalColour('#5fafff', 75),
    TerminalColour('#5fd700', 76),
    TerminalColour('#5fd75f', 77),
    TerminalColour('#5fd787', 78),
    TerminalColour('#5fd7af', 79),
    TerminalColour('#5fd7d7', 80),
    TerminalColour('#5fd7ff', 81),
    TerminalColour('#5fff00', 82),
    TerminalColour('#5fff5f', 83),
    TerminalColour('#5fff87', 84),
    TerminalColour('#5fffaf', 85),
    TerminalColour('#5fffd7', 86),
    TerminalColour('#5fffff', 87),
    TerminalColour('#870000', 88),
    TerminalColour('#87005f', 89),
    TerminalColour('#870087', 90),
    TerminalColour('#8700af', 91),
    TerminalColour('#8700d7', 92),
    TerminalColour('#8700ff', 93),
    TerminalColour('#875f00', 94),
    TerminalColour('#875f5f', 95),
    TerminalColour('#875f87', 96),
    TerminalColour('#875faf', 97),
    TerminalColour('#875fd7', 98),
    TerminalColour('#875fff', 99),
    TerminalColour('#878700', 100),
    TerminalColour('#87875f', 101),
    TerminalColour('#878787', 102),
    TerminalColour('#8787af', 103),
    TerminalColour('#8787d7', 104),
    TerminalColour('#8787ff', 105),
    TerminalColour('#87af00', 106),
    TerminalColour('#87af5f', 107),
    TerminalColour('#87af87', 108),
    TerminalColour('#87afaf', 109),
    TerminalColour('#87afd7', 110),
    TerminalColour('#87afff', 111),
    TerminalColour('#87d700', 112),
    TerminalColour('#87d75f', 113),
    TerminalColour('#87d787', 114),
    TerminalColour('#87d7af', 115),
    TerminalColour('#87d7d7', 116),
    TerminalColour('#87d7ff', 117),
    TerminalColour('#87ff00', 118),
    TerminalColour('#87ff5f', 119),
    TerminalColour('#87ff87', 120),
    TerminalColour('#87ffaf', 121),
    TerminalColour('#87ffd7', 122),
    TerminalColour('#87ffff', 123),
    TerminalColour('#af0000', 124),
    TerminalColour('#af005f', 125),
    TerminalColour('#af0087', 126),
    TerminalColour('#af00af', 127),
    TerminalColour('#af00d7', 128),
    TerminalColour('#af00ff', 129),
    TerminalColour('#af5f00', 130),
    TerminalColour('#af5f5f', 131),
    TerminalColour('#af5f87', 132),
    TerminalColour('#af5faf', 133),
    TerminalColour('#af5fd7', 134),
    TerminalColour('#af5fff', 135),
    TerminalColour('#af8700', 136),
    TerminalColour('#af875f', 137),
    TerminalColour('#af8787', 138),
    TerminalColour('#af87af', 139),
    TerminalColour('#af87d7', 140),
    TerminalColour('#af87ff', 141),
    TerminalColour('#afaf00', 142),
    TerminalColour('#afaf5f', 143),
    TerminalColour('#afaf87', 144),
    TerminalColour('#afafaf', 145),
    TerminalColour('#afafd7', 146),
    TerminalColour('#afafff', 147),
    TerminalColour('#afd700', 148),
    TerminalColour('#afd75f', 149),
    TerminalColour('#afd787', 150),
    TerminalColour('#afd7af', 151),
    TerminalColour('#afd7d7', 152),
    TerminalColour('#afd7ff', 153),
    TerminalColour('#afff00', 154),
    TerminalColour('#afff5f', 155),
    TerminalColour('#afff87', 156),
    TerminalColour('#afffaf', 157),
    TerminalColour('#afffd7', 158),
    TerminalColour('#afffff', 159),
    TerminalColour('#d70000', 160),
    TerminalColour('#d7005f', 161),
    TerminalColour('#d70087', 162),
    TerminalColour('#d700af', 163),
    TerminalColour('#d700d7', 164),
    TerminalColour('#d700ff', 165),
    TerminalColour('#d75f00', 166),
    TerminalColour('#d75f5f', 167),
    TerminalColour('#d75f87', 168),
    TerminalColour('#d75faf', 169),
    TerminalColour('#d75fd7', 170),
    TerminalColour('#d75fff', 171),
    TerminalColour('#d78700', 172),
    TerminalColour('#d7875f', 173),
    TerminalColour('#d78787', 174),
    TerminalColour('#d787af', 175),
    TerminalColour('#d787d7', 176),
    TerminalColour('#d787ff', 177),
    TerminalColour('#d7af00', 178),
    TerminalColour('#d7af5f', 179),
    TerminalColour('#d7af87', 180),
    TerminalColour('#d7afaf', 181),
    TerminalColour('#d7afd7', 182),
    TerminalColour('#d7afff', 183),
    TerminalColour('#d7d700', 184),
    TerminalColour('#d7d75f', 185),
    TerminalColour('#d7d787', 186),
    TerminalColour('#d7d7af', 187),
    TerminalColour('#d7d7d7', 188),
    TerminalColour('#d7d7ff', 189),
    TerminalColour('#d7ff00', 190),
    TerminalColour('#d7ff5f', 191),
    TerminalColour('#d7ff87', 192),
    TerminalColour('#d7ffaf', 193),
    TerminalColour('#d7ffd7', 194),
    TerminalColour('#d7ffff', 195),
    TerminalColour('#ff0000', 196),
    TerminalColour('#ff005f', 197),
    TerminalColour('#ff0087', 198),
    TerminalColour('#ff00af', 199),
    TerminalColour('#ff00d7', 200),
    TerminalColour('#ff00ff', 201),
    TerminalColour('#ff5f00', 202),
    TerminalColour('#ff5f5f', 203),
    TerminalColour('#ff5f87', 204),
    TerminalColour('#ff5faf', 205),
    TerminalColour('#ff5fd7', 206),
    TerminalColour('#ff5fff', 207),
    TerminalColour('#ff8700', 208),
    TerminalColour('#ff875f', 209),
    TerminalColour('#ff8787', 210),
    TerminalColour('#ff87af', 211),
    TerminalColour('#ff87d7', 212),
    TerminalColour('#ff87ff', 213),
    TerminalColour('#ffaf00', 214),
    TerminalColour('#ffaf5f', 215),
    TerminalColour('#ffaf87', 216),
    TerminalColour('#ffafaf', 217),
    TerminalColour('#ffafd7', 218),
    TerminalColour('#ffafff', 219),
    TerminalColour('#ffd700', 220),
    TerminalColour('#ffd75f', 221),
    TerminalColour('#ffd787', 222),
    TerminalColour('#ffd7af', 223),
    TerminalColour('#ffd7d7', 224),
    TerminalColour('#ffd7ff', 225),
    TerminalColour('#ffff00', 226),
    TerminalColour('#ffff5f', 227),
    TerminalColour('#ffff87', 228),
    TerminalColour('#ffffaf', 229),
    TerminalColour('#ffffd7', 230),
    TerminalColour('#ffffff', 231),
    TerminalColour('#080808', 232),
    TerminalColour('#121212', 233),
    TerminalColour('#1c1c1c', 234),
    TerminalColour('#262626', 235),
    TerminalColour('#303030', 236),
    TerminalColour('#3a3a3a', 237),
    TerminalColour('#444444', 238),
    TerminalColour('#4e4e4e', 239),
    TerminalColour('#585858', 240),
    TerminalColour('#626262', 241),
    TerminalColour('#6c6c6c', 242),
    TerminalColour('#767676', 243),
    TerminalColour('#808080', 244),
    TerminalColour('#8a8a8a', 245),
    TerminalColour('#949494', 246),
    TerminalColour('#9e9e9e', 247),
    TerminalColour('#a8a8a8', 248),
    TerminalColour('#b2b2b2', 249),
    TerminalColour('#bcbcbc', 250),
    TerminalColour('#c6c6c6', 251),
    TerminalColour('#d0d0d0', 252),
    TerminalColour('#dadada', 253),
    TerminalColour('#e4e4e4', 254),
    TerminalColour('#eeeeee', 255),
)

# A mapping from cterm code to TerminalColour.
cterm_code_to_colour = {c.number: c for c in terminal_colour_list}

# A mapping from name to `Highlight` instance.
_highlights: dict[str, Highlight] = {}


DynAttrTypes: TypeAlias = (
    dict[str, Highlight]
)


def __getattr__(name: str) -> DynAttrTypes:
    """Dynamic module attribute access.

    Some colour related collections are lazily generated. This allows other Vim
    plugins and initialisation time to, for example, define certain highlght
    groups.
    """
    if name == 'highlights':
        if not _highlights:
            _highlights.update(create_std_group_highlights())
            _highlights.update(create_ext_std_group_highlights())
        return _highlights

    raise AttributeError(name)
