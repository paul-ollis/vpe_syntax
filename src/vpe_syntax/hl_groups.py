"""Highlight groups/properties used for syntax highlighting."""
from __future__ import annotations

from collections import defaultdict
from colorsys import hls_to_rgb, rgb_to_hls
from dataclasses import Field, dataclass, field, fields
from functools import lru_cache, partial
from math import sqrt
from typing import Callable, ClassVar, TypeAlias
from weakref import proxy

import vpe
from vpe import vim

# pylint: disable=too-many-lines

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

    ('Type', 51),
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
    ('DiffAdd', 50),
    ('DiffChange', 50),
    ('DiffDelete', 50),
    ('DiffText', 50),
    ('DiffTextAdd', 50),
)

# TODO:
#     Automatically create some obvious, non-controvertial groups such as
#     'Bold' and 'Italic'. Then they can be link targets in the following list.

#: Some additional syntax highlighting groups for more nuanced highlighting.
#:
#: Tree-sitter parsing make it relatively easy to identify more fine grained
#: syntactic and semantic content from code. Hence this set of extended
#: 'standard' groups.
#:
#: These syntax highlighting group names are based on the names that NeoVim uses
#: for its Tree-Sitter based syntax highlighting. The Tree-sitter names are in
#: the form used in Tree-sitter queries, for example, '@comment.documentation'.
#:
#: This list was formed by taking each name, removing the '@' and '.' characters
#: and capitalizing each word. Any resulting name that matches an existing
#: standard Vim syntax highlighting name was removed. Some other possibly
#: useful names were then added.
#:
#: In this table, each is group is linked to one of the 'standard' groups or
#: `None` as a starting point. The intention is that users or colour schemes
#: may over-ride these group definitions as required.
EXT_STANDARD_GROUPS: list[tuple[str, str | None, int]] = [
    ('Argument',                  'Identifier',      55),
    ('AttributeBuiltin',          'Keyword',         55),
    ('Attribute',                 'Identifier',      55),
    ('CalledFunction',            'Identifier',      55),
    ('CalledMethod',              'Identifier',      58),
    ('CharacterSpecial',          'SpecialChar',     55),
    ('Class',                     'Keyword',         55),
    ('ClassName',                 'Identifier',      55),
    ('CommentDocumentation',      'Comment',         55),
    ('CommentError',              'Todo',            55),
    ('CommentNote',               'Todo',            55),
    ('CommentTodo',               'Todo',            55),
    ('CommentWarning',            'Todo',            55),
    ('ConstantBuiltin',           'Constant',        55),
    ('ConstantMacro',             'Constant',        55),
    ('Constructor',               'Normal',          65),
    ('Decorator',                 'Identifier',      55),
    ('DefinitionStarter',         'Identifier',      55),
    ('DiffDelta',                 'DiffChange',      55),
    ('DiffMinus',                 'DiffDelete',      55),
    ('DiffPlus',                  'DiffAdd',         55),
    ('FunctionBuiltin',           'Function',        55),
    ('FunctionCall',              'Normal',          55),
    ('FunctionDef',               'Keyword',         55),
    ('FunctionMacro',             'Macro',           55),
    ('FunctionMethodCall',        'Normal',          55),
    ('FunctionMethod',            'Normal',          55),
    ('FunctionName',              'Identifier',      55),
    ('GenericType',               'Type',            55),
    ('ImportedAliasedName',       'Normal',          55),
    ('ImportedName',              'Normal',          55),
    ('Import',                    'Include',         55),
    ('Interpolation',             'String',          40),
    ('KeywordConditional',        'Keyword',         55),
    ('KeywordConditionalTernary', 'KeyWord',         55),
    ('KeywordCoroutine',          'KeyWord',         55),
    ('KeywordDebug',              'KeyWord',         55),
    ('KeywordDirectiveDefine',    'KeyWord',         55),
    ('KeywordDirective',          'KeyWord',         55),
    ('KeywordException',          'KeyWord',         55),
    ('KeywordFunction',           'KeyWord',         55),
    ('KeywordImport',             'KeyWord',         55),
    ('KeywordModifier',           'KeyWord',         55),
    ('KeywordOperator',           'KeyWord',         55),
    ('KeywordRepeat',             'KeyWord',         55),
    ('KeywordReturn',             'KeyWord',         55),
    ('KeywordType',               'KeyWord',         55),
    ('MarkupHeading1',            'Underlined',      55),
    ('MarkupHeading2',            'Underlined',      55),
    ('MarkupHeading3',            'Underlined',      55),
    ('MarkupHeading4',            'Underlined',      55),
    ('MarkupHeading5',            'Underlined',      55),
    ('MarkupHeading6',            'Underlined',      55),
    ('MarkupHeading',             'Underlined',      55),
    ('MarkupLinkLabel',           'Normal',          55),
    ('MarkupLink',                'Normal',          55),
    ('MarkupLinkUrl',             'Underlined',      55),
    ('MarkupListChecked',         'Normal',          55),
    ('MarkupList',                'Normal',          55),
    ('MarkupListUnchecked',       'Normal',          55),
    ('MarkupMath',                'Normal',          55),
    ('MarkupQuote',               'Normal',          55),
    ('MarkupRawBlock',            'Normal',          55),
    ('MarkupRaw',                 'Normal',          55),
    ('MarkupStrikethrough',       'Strikethrough',   55),
    ('MarkupStrong',              'Bold',            55),
    ('MarkupUnderline',           'Underlined',      55),
    ('MethodCall',                'Normal',          55),
    ('MethodDef',                 'Keyword',         55),
    ('MethodName',                'Identifier',      55),
    ('ModuleBuiltin',             'Keyword',         55),
    ('Module',                    'Identifier',      55),
    ('None',                      'Special',         55),
    ('NonStandardSelf',           'Normal',          55),
    ('NumberFloat',               'Float',           55),
    ('Parameter',                 'Normal',          55),
    ('Property',                  'String',          55),
    ('PunctuationBracket',        'Normal',          55),
    ('PunctuationDelimiter',      'Normal',          55),
    ('PunctuationSpecial',        'Normal',          55),
    ('Return',                    'Keyword',         55),
    ('Self',                      'Normal',          55),
    ('SpecialPunctuation',        'Normal',          55),
    ('StandardConst',             'Identifier',      55),
    ('StringDocumentation',       'Comment',         55),
    ('StringEscape',              'String',          55),
    ('StringRegexp',              'String',          55),
    ('StringSpecialPath',         'String',          55),
    ('StringSpecial',             'String',          55),
    ('StringSpecialSymbol',       'String',          55),
    ('StringSpecialUrl',          'Underlines',      55),
    ('SyntaxError',               'WarningMsg',      10),
    ('TagAttribute',              'Normal',          55),
    ('TagBuiltin',                'Normal',          55),
    ('TagDelimiter',              'Normal',          55),
    ('TypeBracket',               'Normal',          60),
    ('TypeBuiltin',               'Keyword',         55),
    ('TypeDefinition',            'Type',            55),
    ('TypeParameter',             'Type',            55),
    ('VariableBuiltin',           'Keyword',         55),
    ('Variable',                  'Identifier',      55),
    ('VariableMember',            'Identifier',      55),
    ('VariableParameterBuiltin',  'Keyword',         55),
    ('VariableParameter',         'Identifier',      55),
]


class Colour:
    """The RGB representation of a colour.

    If a colour has a name then it is effectively immutable. If the colour has
    a valid number then it is colour terminal colour and effectively
    immultable.
    """
    # pylint: disable=too-many-instance-attributes

    _v_named_colours: ClassVar[dict] = {}

    #< Construction
    def __init__(
            self, r: int, g: int, b: int, name: str = '', number: int = -1):
        # pylint: disable=too-many-arguments,too-many-positional-arguments
        self._r = r
        self._g = g
        self._b = b
        self._name = name
        self.number = number
        self._closest_colours: None | tuple[Colour, Colour] = None

    @classmethod
    def from_colour(cls, colour: Colour) -> Colour:
        """Create an instance from another colour."""
        return cls(colour.r, colour.g, colour.b)

    @classmethod
    def _from_colour_name(cls, name: str) -> Colour:
        """Create an instance from a colour name."""
        return cls._from_hex_rgb(
            vim.vvars.colornames.get(name.lower(), '#ffffff'))

    @classmethod
    def _from_hex_rgb(cls, rgb_str: str) -> Colour:
        """Create an instance from a Vim RGB colour string."""
        hex_strings = rgb_str[1:3], rgb_str[3:5], rgb_str[5:7]
        r, g, b = [int(s, 16) for s in hex_strings]
        return cls(r, g, b)

    @classmethod
    def create_terminal_colour(
            cls, rgb_str: str, number: int, name: str = '') -> Colour:
        """Create an configured as a terminal colour."""
        hex_strings = rgb_str[1:3], rgb_str[3:5], rgb_str[5:7]
        r, g, b = [int(s, 16) for s in hex_strings]
        colour = cls(r, g, b, name=name, number=number)
        return colour

    @classmethod
    def parse(cls, name_or_hex: str, make_named: bool = False) -> Colour:
        """Create an instance from a colour name or hexadecimal."""
        if not name_or_hex:
            return unused_colour
        elif name_or_hex == 'NONE':
            return none_colour
        elif name_or_hex.startswith('#'):
            return cls._from_hex_rgb(name_or_hex)
        else:
            colour = cls._from_colour_name(name_or_hex)
            if make_named:
                colour.name = name_or_hex
            return colour

    #< Properties and simple queries
    @property
    def r(self) -> int:
        """The red component value in the range -1 (non-colour) to 255."""
        return self._r

    @r.setter
    def r(self, value) -> None:
        self._check_mutable()
        self._r = value

    @property
    def g(self) -> int:
        """The green component value in the range -1 (non-colour) to 255."""
        return self._g

    @g.setter
    def g(self, value) -> None:
        self._check_mutable()
        self._g = value

    @property
    def b(self) -> int:
        """The blue component value in the range -1 (non-colour) to 255."""
        return self._b

    @b.setter
    def b(self, value) -> None:
        self._check_mutable()
        self._b = value

    @property
    def name(self) -> str:
        """The name of this colour, which may be an empty string"""
        if not self._name and self.number >= 0:
            self._name = self.closest_colour.name
        return self._name


    @name.setter
    def name(self, value: str) -> None:
        self._check_mutable()
        self._name = value

    @property
    def closest_colour(self) -> Colour:
        """A named colour that is the closest match to this colour."""
        if self._closest_colours is None:
            self._update_closest_colours()
        assert self._closest_colours is not None
        return self._closest_colours[0]

    @property
    def closest_terminal_colour(self) -> Colour:
        """A terminal colour that is the closest match to this colour."""
        if self._closest_colours is None:
            self._update_closest_colours()
        assert self._closest_colours is not None
        return self._closest_colours[1]

    @property
    def lightness(self) -> float:
        """The lightness of this colour - black=0.0, white=255.0."""
        _h, l, _s = rgb_to_hls(self.r, self.g, self.b)
        return l

    def as_hex(self) -> str:
        """Provide Vim style hex representation."""
        return f'#{self.r:02x}{self.g:02x}{self.b:02x}'

    def as_decimal(self) -> str:
        """Provide decimal values."""
        return f'({self.r},{self.g},{self.b})'

    #< Modification
    def adjust_component(self, name: str, inc: int):
        """Adjust one of the RGB values by defined amount."""
        self._check_mutable()
        if name == 'r':
            self.r = min(255, max(0, self.r + inc))
        elif name == 'g':
            self.g = min(255, max(0, self.g + inc))
        elif name == 'b':
            self.b = min(255, max(0, self.b + inc))
        self._update_closest_colours()

    def adjust_brightness(self, inc: float | int) -> bool:
        """Adjust the brightness of this colour.

        :inc:
            Change in brighness. -255.0 or less will completely darken and
            255.0 or above will completely lighten.
        :return:
            ``True`` if the a change was made.
        """
        self._check_mutable()
        prev = self.r, self.g, self.b
        h, l, s = rgb_to_hls(*prev)
        l = min(255.0, max(0.0, l + inc))
        rf, gf, bf = hls_to_rgb(h, l, s)
        self.r = min(255, max(0, round(rf)))
        self.g = min(255, max(0, round(gf)))
        self.b = min(255, max(0, round(bf)))
        if prev != (self.r, self.g, self.b):
            self._update_closest_colours()
            return True
        else:
            return False

    #< Comparison
    def distance(self, other: Colour) -> float:
        """Calculate the distance between 2 colours."""
        ra, ga, ba = self.r, self.g, self.b
        rb, gb, bb = other.r, other.g, other.b
        d_r = (ra - rb) / 256
        d_g = (ga - gb) / 256
        d_b = (ba - bb) / 256
        return sqrt(d_r**2 + d_g**2  + d_b**2)

    def __eq__(self, other) -> bool:
        if not isinstance(other, Colour):
            return False

        ra, ga, ba = self.r, self.g, self.b
        rb, gb, bb = other.r, other.g, other.b
        return (ra, ga, ba) == (rb, gb, bb)

    #< Support
    def _update_closest_colours(self) -> None:
        """Work out the closest colour match."""
        if len(self._v_named_colours) == 0:
            for name in vim.vvars.colornames:
                self._v_named_colours[name] = Colour.parse(
                    name, make_named=True)

        closest_colour = self._find_closest(self.r, self.g, self.b)
        closest_terminal_color = self._find_closest_terminal_colour(
            self.r, self.g, self.b)
        self._closest_colours = closest_colour, closest_terminal_color

    @classmethod
    @lru_cache(200)
    def _find_closest(cls, r, g, b) -> Colour:
        _, closest_name = min(
            (cls._distance(r, g, b, name), name)
            for name in cls._v_named_colours
        )
        return cls._v_named_colours[closest_name]

    @classmethod
    @lru_cache(200)
    def _find_closest_terminal_colour(cls, r, g, b) -> Colour:
        _, code = min(
            (cls._terminal_distance(r, g, b, colour), colour.number)
            for colour in terminal_colour_list
        )
        return cterm_code_to_colour[code]

    @classmethod
    def _distance(cls, r, g, b, name) -> float:
        other = cls._v_named_colours[name]
        rb, gb, bb = other.r, other.g, other.b
        return sqrt((r - rb)**2 + (g - gb)**2  + (b - bb)**2)

    @classmethod
    def _terminal_distance(cls, r, g, b, other) -> float:
        rb, gb, bb = other.r, other.g, other.b
        return sqrt((r - rb)**2 + (g - gb)**2  + (b - bb)**2)
    def _check_mutable(self) -> None:
        if self.name != '' or self.number >= 0:
            raise AttributeError(f'{self} is immutable')

    def __repr__(self) -> str:
        s = [f'Colour:{self.as_hex()}']
        s.append(self.as_decimal())
        if self.name:
            s.append(f'name={self.name}')
        else:
            s.append('unnamed')
        if self.number >= 0:
            s.append('terminal')
        return ','.join(s)


class UnusedColour(Colour):
    """Used to indicate an unset colour attribute."""

    def __init__(self):
        super().__init__(255, 255, 255, name='_unused_')


#: A colour indicating the absence of a real colour value.
unused_colour = Colour(255, 255, 255, name='_unused_')

#: A colour indicating that a syntax colour is set as ``NONE``.
none_colour = Colour(255, 255, 255, name='_none_')


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
    fg: Colour = field(default_factory=lambda: unused_colour)
    bg: Colour = field(default_factory=lambda: unused_colour)
    sp: Colour = field(default_factory=lambda: unused_colour)
    fg_name: str = ''
    bg_name: str = ''
    sp_name: str = ''
    parent: Highlight | None = None

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
    def _hl_attrs_from_synid_attr_value(
            cls, f: Field, s_value: str) -> dict[str, Colour | str]:
        try:
            value: int = int(s_value)
        except ValueError:
            pass
        else:
            colour = cterm_code_to_colour.get(
                value, cterm_code_to_colour[213])
            s_value = colour.as_hex()

        kw: dict[str, Colour | str] = {}
        kw[f.name] = Colour.parse(s_value or 'NONE')
        if not s_value.startswith('#'):
            kw[f'{f.name}_name'] = s_value
        else:
            kw[f'{f.name}_name'] = ''

        return kw

    @classmethod
    def from_syn_id(cls, synid: int) -> HighlightSettings:
        """Create by querying a given highlight group.

        :synid:
            The ID of the syntax group to query.
        """
        # pylint: disable=too-many-branches
        kw: dict[str, int | str | Colour] = {}
        for f in fields(cls):
            query_name = f.name
            if query_name in cls.unused:
                continue
            if query_name in cls.meta:
                continue
            value = vim.synIDattr(synid, f.name, cls.mode)
            if f.name in ('fg', 'bg', 'sp'):
                kw.update(cls._hl_attrs_from_synid_attr_value(f, value))
            elif value and value in '01':
                kw[f.name] = bool(int(value))
        return cls(**kw)                               # type: ignore[arg-type]

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
            if arg_name in self.unused:
                continue

            value = getattr(self, arg_name)
            assert value is not None, f'Got None for {arg_name}'
            match f.type:
                case 'bool':
                    if value:
                        attrs.append(arg_name)
                case 'Colour':
                    arg_name = self.ortho_map.get(arg_name, arg_name)
                    if value is none_colour:
                        args[f'{self.mode}{arg_name}'] = 'NONE'
                    elif value is not unused_colour:
                        args[f'{self.mode}{arg_name}'] = value.as_hex()

        if attrs:
            args[f'{self.mode}'] = ','.join(attrs)
        return args

    def format_args_as_string(self) -> str:
        """Format the arguments for these settings, as a string."""
        parts = [
            f'{name}={value}' for name, value in self.format_args().items()]
        return ' '.join(parts)

    def __post_init__(self):
        assert self.fg is not None


class TermSettings(HighlightSettings):
    """Highlight settings for a plain terminal."""

    mode: ClassVar[str] = 'term'
    ortho_map: ClassVar[dict[str, str]] = HighlightSettings.ortho_map | {
        'sp': 'ul',
    }
    unused: ClassVar[set[str]] = set(('fg', 'bg', 'sp'))

    def copy(self, parent: Highlight) -> TermSettings:
        """Create a shallow copy, with the given parent `Highlight`."""
        inst = self.__class__(**self.__dict__)
        inst.parent = parent
        return inst


class ColourTermSettings(HighlightSettings):
    """Highlight settings for a colour terminal."""

    mode: ClassVar[str] = 'cterm'
    ortho_map: ClassVar[dict[str, str]] = HighlightSettings.ortho_map | {
        'sp': 'ul',
    }

    def format_args(self) -> dict:
        """Format the arguments for these settings."""
        args = super().format_args()
        for f in fields(self):
            if f.type != 'Colour':
                continue
            arg_name = f.name
            if self.parent is None or not self.parent.cterm_copies_gui:
                value = getattr(self, arg_name)
            else:
                value = getattr(self.parent.gui, arg_name)
            arg_name = self.ortho_map.get(arg_name, arg_name)
            arg_name = f'{self.mode}{arg_name}'
            if arg_name not in args or f.type == 'bool':
                continue

            if value is none_colour:
                args[arg_name] = 'NONE'
            elif value is not unused_colour:
                e_colour = Colour.from_colour(value)
                if e_colour.closest_terminal_colour is not None:
                    args[arg_name] = str(
                        e_colour.closest_terminal_colour.number)
        return args

    def copy(self, parent: Highlight) -> ColourTermSettings:
        """Create a shallow copy, with the given parent `Highlight`."""
        inst = self.__class__(**self.__dict__)
        inst.parent = parent
        return inst


class GUISettings(HighlightSettings):
    """Highlight settings for a GUI."""

    mode: ClassVar[str] = 'gui'

    def copy(self, parent: Highlight) -> GUISettings:
        """Create a shallow copy, with the given parent `Highlight`."""
        inst = self.__class__(**self.__dict__)
        inst.parent = parent
        return inst

    def clear_flags(self) -> None:
        """Clear flags (bold, *etc.*) settings."""
        for f in fields(self.__class__):
            if f.type == 'bool':
                setattr(self, f.name, False)

    def set_flags_from_colour_term_settings(
            self, cterm: ColourTermSettings) -> None:
        """Set flags (bold, *etc.*) using a colour terminal's settings."""
        for f in fields(self.__class__):
            if f.type == 'bool':
                setattr(self, f.name, getattr(cterm, f.name))

    def set_from_colour_term_settings(self, cterm: ColourTermSettings) -> None:
        """Set attributes using a colour terminal's settings."""
        self.fg = cterm.fg
        self.bg = cterm.bg
        self.sp = cterm.sp
        for f in fields(self.__class__):
            if f.type == 'bool':
                setattr(self, f.name, getattr(cterm, f.name))

    def set_from_mono_term_settings(self, cterm: TermSettings) -> None:
        """Set attributes using a mono terminal's settings."""
        for f in fields(self.__class__):
            if f.type == 'bool':
                setattr(self, f.name, getattr(cterm, f.name))


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
    @cterm_copies_gui:
        When set the colour term settings are a copy of the GUI settings. The
        fg, bg and ul settings are set to the closest colour matches.
    """
    name: str
    term: TermSettings | None = None
    cterm: ColourTermSettings | None = None
    gui: GUISettings | None = None
    link: str = ''
    cterm_copies_gui: bool = False

    #< Construction
    def __post_init__(self):
        if self.gui:
            self.gui.parent = proxy(self)
        if self.cterm:
            self.cterm.parent = proxy(self)
        if self.term:
            self.term.parent = proxy(self)

    @classmethod
    def from_name(cls, name: str) -> Highlight:
        """Create by querying a named highlight group."""
        hid = vim.hlID(name)
        synid = vim.synIDtrans(hid)
        kw = {}
        kw['term'] = TermSettings.from_syn_id(synid)
        kw['cterm'] = ColourTermSettings.from_syn_id(synid)
        kw['gui'] = GUISettings.from_syn_id(synid)

        return cls(name=name, **kw)                    # type: ignore[arg-type]

    def copy_from_named_highlight(self, other: str) -> None:
        """Copy settings from another highlight."""
        e_colour = Highlight.from_name(other)
        if e_colour.term is not None:
            self.term = e_colour.term.copy(proxy(self))
        else:
            self.term = None

        if e_colour.cterm is not None:
            self.cterm = e_colour.cterm.copy(proxy(self))
        else:
            self.cterm = None

        if e_colour.gui is not None:
            self.gui = e_colour.gui.copy(proxy(self))
        else:
            self.gui = None

    #< Properties and attribute access
    @property
    def is_linked(self) -> bool:
        """Flag indicating if this is just linked to another highlight."""
        return bool(self.link)

    def resolve_link(self) -> Highlight:
        """Resolve linked name to the `Highlight`."""
        if not self.link:
            return self
        linked_group = _highlights.get(self.link)
        return linked_group.resolve_link()

    def get_colour(self, attr: str) -> Colour:
        """Get a colour for a given attribute name.

        :attr: The name as a two part dotted identifier; *e.g.* gui.fg.
        """
        if self.link:
            linked_group = _highlights.get(self.link)
            if linked_group:
                return linked_group.get_colour(attr)
            else:
                return unused_colour

        mode, rgb_name = attr.split('.')
        try:
            if mode == 'cterm' and self.cterm_copies_gui:
                colour = getattr(getattr(self, 'gui'), rgb_name)
                return colour.closest_terminal_colour
            else:
                return getattr(getattr(self, mode), rgb_name)
        except AttributeError:
            return unused_colour

    def get_flag(self, attr: str) -> bool:
        """Get a boolean value for a given attribute name.

        :attr: The name as a two part dotted identifier; *e.g.* gui.bold.
        """
        if self.link:
            linked_group = _highlights.get(self.link)
            if linked_group:
                return linked_group.get_flag(attr)
            else:
                return False

        mode, flag_name = attr.split('.')
        try:
            if mode == 'cterm' and self.cterm_copies_gui:
                colour = getattr(getattr(self, 'gui'), flag_name)
                return colour.closest_terminal_colour
            else:
                return getattr(getattr(self, mode), flag_name)
        except AttributeError:
            return False

    #< Editing
    def set_colour(self, attr: str, colour: Colour) -> None:
        """Set a colour for a given attribute name.

        :attr:   The name as a two part dotted identifier; *e.g.* gui.fg.
        :colour: The colour value for the attribute.
        """
        assert colour is not None
        mode, rgb_name = attr.split('.')
        if mode == 'cterm' and self.cterm_copies_gui:
            return
        setattr(getattr(self, mode), rgb_name, Colour.from_colour(colour))

    def set_flag(self, attr: str, value: bool) -> None:
        """Set a the boolean value for a given attribute name.

        :attr:  The name as a two part dotted identifier; *e.g.* gui.bold.
        :value: The boolean value for the attribute.
        """
        mode, attr_name = attr.split('.')
        if mode == 'cterm' and self.cterm_copies_gui:
            return
        setattr(getattr(self, mode), attr_name, value)

    def set_copy_gui(self, flag: bool) -> None:
        """Set the cterm_copies_gui flag - useful for undo operations."""
        self.cterm_copies_gui = flag

    def break_link(self) -> None:
        """Break this highlights link by copying the linked group."""
        if not self.link:
            return
        self.copy_from_named_highlight(self.link)
        self.link = ''

    def set_link(self, name: str) -> None:
        """Set the name of the linked group."""
        assert name
        self.link = name

    def adjust_brightness(self, attr: str, inc: float) -> None:
        """Adjust one a colour's brighness."""
        rgb = self.get_colour(attr)
        rgb.adjust_brightness(inc)

    def adjust_rgb(self, attr: str, key: str, inc: int) -> None:
        """Adjust one of the RGB attributes."""
        inc = 10 if key.upper() == key else -10
        rgb = self.get_colour(attr)
        rgb.adjust_component(key.lower(), inc)

    def toggle_flag(self, mode: str, flag: str) -> None:
        """Adjust one of the flag attributes."""
        settings = getattr(self, mode)
        value = getattr(settings, flag)
        setattr(settings, flag, not value)

    #< Manifesting actions
    def format_args(self) -> dict:
        """Format the arguments for a Vim highlight command."""
        kw: dict[str, str | int] = {}
        if self.gui is not None:
            kw.update(self.gui.format_args())
        if self.cterm is not None:
            kw.update(self.cterm.format_args())
        if self.term is not None:
            kw.update(self.term.format_args())
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
        if self.name == 'StringDocumentation':
            kw['spell'] = True
        else:
            kw['spell'] = False
        name = self.name if level == 0 else f'{self.name}{level}'
        known_prop_info = vim.prop_type_get(name)
        if not known_prop_info:
            vim.prop_type_add(name, kw)


def create_std_group_highlights() -> dict[str, Highlight]:
    """Create a `Highlight` instances for each standard highlight group."""
    table = {}
    for name, priority in STANDARD_GROUPS:
        group = None
        if vim.hlID(name) == 0:
            # Just because the Vim help says it is a standard group does not
            # mean it actually exists.
            if name not in _should_be_standard_goups:
                continue
            group = _should_be_standard_goups[name]
            group.apply()

        if group is None:
            group = Highlight.from_name(name)
        table[name] = group
        group.create_property(priority)
        group.create_property(priority, level=1)
    return table


def create_ext_std_group_highlights() -> dict[str, Highlight]:
    """Create a `Highlight` instances for each extension highlight group."""
    table = {}
    for name, link, priority in EXT_STANDARD_GROUPS:
        link = link or ''
        hid = vim.hlID(name)
        if hid == 0:
            # Group is not defined so add it.
            if vim.hlID(link) == 0:
                # In case the linked to default does not exists.
                group = Highlight(name, link='Normal')
            else:
                group = Highlight(name, link=link)
            group.apply()
        else:
            # Group is defined so use defined settings.
            attr_dict = dict(vim.hlget(name)[0])
            link_name = attr_dict.get('linksto')
            if link_name:
                group = Highlight(name, link=link_name)
            else:
                group = Highlight.from_name(name)
        table[name] = group
        group.create_property(priority=priority)
        group.create_property(priority=priority, level=1)
    return table


terminal_16_colour_list = (
    Colour.create_terminal_colour('#000000', number=0, name='Black'),
    Colour.create_terminal_colour('#800000', number=1, name='DarkBlue'),
    Colour.create_terminal_colour('#008000', number=2, name='DarkGreen'),
    Colour.create_terminal_colour('#808000', number=3, name='DarkCyan'),
    Colour.create_terminal_colour('#000080', number=4, name='DarkRed'),
    Colour.create_terminal_colour('#800080', number=5, name='DarkMagenta'),
    Colour.create_terminal_colour('#008080', number=6, name='DarkYellow'),
    Colour.create_terminal_colour('#c0c0c0', number=7, name='LightGray'),
    Colour.create_terminal_colour('#808080', number=8, name='DarkGray'),
    Colour.create_terminal_colour('#ff0000', number=9, name='LightBlue'),
    Colour.create_terminal_colour('#00ff00', number=10, name='LightGreen'),
    Colour.create_terminal_colour('#ffff00', number=11, name='LightCyan'),
    Colour.create_terminal_colour('#0000ff', number=12, name='LightRed'),
    Colour.create_terminal_colour('#ff00ff', number=13, name='LightMagenta'),
    Colour.create_terminal_colour('#00ffff', number=14, name='LightYellow'),
    Colour.create_terminal_colour('#ffffff', number=15, name='White'),
)
terminal_colour_list = (
    Colour.create_terminal_colour('#000000', number=16),
    Colour.create_terminal_colour('#00005f', number=17),
    Colour.create_terminal_colour('#000087', number=18),
    Colour.create_terminal_colour('#0000af', number=19),
    Colour.create_terminal_colour('#0000d7', number=20),
    Colour.create_terminal_colour('#0000ff', number=21),
    Colour.create_terminal_colour('#005f00', number=22),
    Colour.create_terminal_colour('#005f5f', number=23),
    Colour.create_terminal_colour('#005f87', number=24),
    Colour.create_terminal_colour('#005faf', number=25),
    Colour.create_terminal_colour('#005fd7', number=26),
    Colour.create_terminal_colour('#005fff', number=27),
    Colour.create_terminal_colour('#008700', number=28),
    Colour.create_terminal_colour('#00875f', number=29),
    Colour.create_terminal_colour('#008787', number=30),
    Colour.create_terminal_colour('#0087af', number=31),
    Colour.create_terminal_colour('#0087d7', number=32),
    Colour.create_terminal_colour('#0087ff', number=33),
    Colour.create_terminal_colour('#00af00', number=34),
    Colour.create_terminal_colour('#00af5f', number=35),
    Colour.create_terminal_colour('#00af87', number=36),
    Colour.create_terminal_colour('#00afaf', number=37),
    Colour.create_terminal_colour('#00afd7', number=38),
    Colour.create_terminal_colour('#00afff', number=39),
    Colour.create_terminal_colour('#00d700', number=40),
    Colour.create_terminal_colour('#00d75f', number=41),
    Colour.create_terminal_colour('#00d787', number=42),
    Colour.create_terminal_colour('#00d7af', number=43),
    Colour.create_terminal_colour('#00d7d7', number=44),
    Colour.create_terminal_colour('#00d7ff', number=45),
    Colour.create_terminal_colour('#00ff00', number=46),
    Colour.create_terminal_colour('#00ff5f', number=47),
    Colour.create_terminal_colour('#00ff87', number=48),
    Colour.create_terminal_colour('#00ffaf', number=49),
    Colour.create_terminal_colour('#00ffd7', number=50),
    Colour.create_terminal_colour('#00ffff', number=51),
    Colour.create_terminal_colour('#5f0000', number=52),
    Colour.create_terminal_colour('#5f005f', number=53),
    Colour.create_terminal_colour('#5f0087', number=54),
    Colour.create_terminal_colour('#5f00af', number=55),
    Colour.create_terminal_colour('#5f00d7', number=56),
    Colour.create_terminal_colour('#5f00ff', number=57),
    Colour.create_terminal_colour('#5f5f00', number=58),
    Colour.create_terminal_colour('#5f5f5f', number=59),
    Colour.create_terminal_colour('#5f5f87', number=60),
    Colour.create_terminal_colour('#5f5faf', number=61),
    Colour.create_terminal_colour('#5f5fd7', number=62),
    Colour.create_terminal_colour('#5f5fff', number=63),
    Colour.create_terminal_colour('#5f8700', number=64),
    Colour.create_terminal_colour('#5f875f', number=65),
    Colour.create_terminal_colour('#5f8787', number=66),
    Colour.create_terminal_colour('#5f87af', number=67),
    Colour.create_terminal_colour('#5f87d7', number=68),
    Colour.create_terminal_colour('#5f87ff', number=69),
    Colour.create_terminal_colour('#5faf00', number=70),
    Colour.create_terminal_colour('#5faf5f', number=71),
    Colour.create_terminal_colour('#5faf87', number=72),
    Colour.create_terminal_colour('#5fafaf', number=73),
    Colour.create_terminal_colour('#5fafd7', number=74),
    Colour.create_terminal_colour('#5fafff', number=75),
    Colour.create_terminal_colour('#5fd700', number=76),
    Colour.create_terminal_colour('#5fd75f', number=77),
    Colour.create_terminal_colour('#5fd787', number=78),
    Colour.create_terminal_colour('#5fd7af', number=79),
    Colour.create_terminal_colour('#5fd7d7', number=80),
    Colour.create_terminal_colour('#5fd7ff', number=81),
    Colour.create_terminal_colour('#5fff00', number=82),
    Colour.create_terminal_colour('#5fff5f', number=83),
    Colour.create_terminal_colour('#5fff87', number=84),
    Colour.create_terminal_colour('#5fffaf', number=85),
    Colour.create_terminal_colour('#5fffd7', number=86),
    Colour.create_terminal_colour('#5fffff', number=87),
    Colour.create_terminal_colour('#870000', number=88),
    Colour.create_terminal_colour('#87005f', number=89),
    Colour.create_terminal_colour('#870087', number=90),
    Colour.create_terminal_colour('#8700af', number=91),
    Colour.create_terminal_colour('#8700d7', number=92),
    Colour.create_terminal_colour('#8700ff', number=93),
    Colour.create_terminal_colour('#875f00', number=94),
    Colour.create_terminal_colour('#875f5f', number=95),
    Colour.create_terminal_colour('#875f87', number=96),
    Colour.create_terminal_colour('#875faf', number=97),
    Colour.create_terminal_colour('#875fd7', number=98),
    Colour.create_terminal_colour('#875fff', number=99),
    Colour.create_terminal_colour('#878700', number=100),
    Colour.create_terminal_colour('#87875f', number=101),
    Colour.create_terminal_colour('#878787', number=102),
    Colour.create_terminal_colour('#8787af', number=103),
    Colour.create_terminal_colour('#8787d7', number=104),
    Colour.create_terminal_colour('#8787ff', number=105),
    Colour.create_terminal_colour('#87af00', number=106),
    Colour.create_terminal_colour('#87af5f', number=107),
    Colour.create_terminal_colour('#87af87', number=108),
    Colour.create_terminal_colour('#87afaf', number=109),
    Colour.create_terminal_colour('#87afd7', number=110),
    Colour.create_terminal_colour('#87afff', number=111),
    Colour.create_terminal_colour('#87d700', number=112),
    Colour.create_terminal_colour('#87d75f', number=113),
    Colour.create_terminal_colour('#87d787', number=114),
    Colour.create_terminal_colour('#87d7af', number=115),
    Colour.create_terminal_colour('#87d7d7', number=116),
    Colour.create_terminal_colour('#87d7ff', number=117),
    Colour.create_terminal_colour('#87ff00', number=118),
    Colour.create_terminal_colour('#87ff5f', number=119),
    Colour.create_terminal_colour('#87ff87', number=120),
    Colour.create_terminal_colour('#87ffaf', number=121),
    Colour.create_terminal_colour('#87ffd7', number=122),
    Colour.create_terminal_colour('#87ffff', number=123),
    Colour.create_terminal_colour('#af0000', number=124),
    Colour.create_terminal_colour('#af005f', number=125),
    Colour.create_terminal_colour('#af0087', number=126),
    Colour.create_terminal_colour('#af00af', number=127),
    Colour.create_terminal_colour('#af00d7', number=128),
    Colour.create_terminal_colour('#af00ff', number=129),
    Colour.create_terminal_colour('#af5f00', number=130),
    Colour.create_terminal_colour('#af5f5f', number=131),
    Colour.create_terminal_colour('#af5f87', number=132),
    Colour.create_terminal_colour('#af5faf', number=133),
    Colour.create_terminal_colour('#af5fd7', number=134),
    Colour.create_terminal_colour('#af5fff', number=135),
    Colour.create_terminal_colour('#af8700', number=136),
    Colour.create_terminal_colour('#af875f', number=137),
    Colour.create_terminal_colour('#af8787', number=138),
    Colour.create_terminal_colour('#af87af', number=139),
    Colour.create_terminal_colour('#af87d7', number=140),
    Colour.create_terminal_colour('#af87ff', number=141),
    Colour.create_terminal_colour('#afaf00', number=142),
    Colour.create_terminal_colour('#afaf5f', number=143),
    Colour.create_terminal_colour('#afaf87', number=144),
    Colour.create_terminal_colour('#afafaf', number=145),
    Colour.create_terminal_colour('#afafd7', number=146),
    Colour.create_terminal_colour('#afafff', number=147),
    Colour.create_terminal_colour('#afd700', number=148),
    Colour.create_terminal_colour('#afd75f', number=149),
    Colour.create_terminal_colour('#afd787', number=150),
    Colour.create_terminal_colour('#afd7af', number=151),
    Colour.create_terminal_colour('#afd7d7', number=152),
    Colour.create_terminal_colour('#afd7ff', number=153),
    Colour.create_terminal_colour('#afff00', number=154),
    Colour.create_terminal_colour('#afff5f', number=155),
    Colour.create_terminal_colour('#afff87', number=156),
    Colour.create_terminal_colour('#afffaf', number=157),
    Colour.create_terminal_colour('#afffd7', number=158),
    Colour.create_terminal_colour('#afffff', number=159),
    Colour.create_terminal_colour('#d70000', number=160),
    Colour.create_terminal_colour('#d7005f', number=161),
    Colour.create_terminal_colour('#d70087', number=162),
    Colour.create_terminal_colour('#d700af', number=163),
    Colour.create_terminal_colour('#d700d7', number=164),
    Colour.create_terminal_colour('#d700ff', number=165),
    Colour.create_terminal_colour('#d75f00', number=166),
    Colour.create_terminal_colour('#d75f5f', number=167),
    Colour.create_terminal_colour('#d75f87', number=168),
    Colour.create_terminal_colour('#d75faf', number=169),
    Colour.create_terminal_colour('#d75fd7', number=170),
    Colour.create_terminal_colour('#d75fff', number=171),
    Colour.create_terminal_colour('#d78700', number=172),
    Colour.create_terminal_colour('#d7875f', number=173),
    Colour.create_terminal_colour('#d78787', number=174),
    Colour.create_terminal_colour('#d787af', number=175),
    Colour.create_terminal_colour('#d787d7', number=176),
    Colour.create_terminal_colour('#d787ff', number=177),
    Colour.create_terminal_colour('#d7af00', number=178),
    Colour.create_terminal_colour('#d7af5f', number=179),
    Colour.create_terminal_colour('#d7af87', number=180),
    Colour.create_terminal_colour('#d7afaf', number=181),
    Colour.create_terminal_colour('#d7afd7', number=182),
    Colour.create_terminal_colour('#d7afff', number=183),
    Colour.create_terminal_colour('#d7d700', number=184),
    Colour.create_terminal_colour('#d7d75f', number=185),
    Colour.create_terminal_colour('#d7d787', number=186),
    Colour.create_terminal_colour('#d7d7af', number=187),
    Colour.create_terminal_colour('#d7d7d7', number=188),
    Colour.create_terminal_colour('#d7d7ff', number=189),
    Colour.create_terminal_colour('#d7ff00', number=190),
    Colour.create_terminal_colour('#d7ff5f', number=191),
    Colour.create_terminal_colour('#d7ff87', number=192),
    Colour.create_terminal_colour('#d7ffaf', number=193),
    Colour.create_terminal_colour('#d7ffd7', number=194),
    Colour.create_terminal_colour('#d7ffff', number=195),
    Colour.create_terminal_colour('#ff0000', number=196),
    Colour.create_terminal_colour('#ff005f', number=197),
    Colour.create_terminal_colour('#ff0087', number=198),
    Colour.create_terminal_colour('#ff00af', number=199),
    Colour.create_terminal_colour('#ff00d7', number=200),
    Colour.create_terminal_colour('#ff00ff', number=201),
    Colour.create_terminal_colour('#ff5f00', number=202),
    Colour.create_terminal_colour('#ff5f5f', number=203),
    Colour.create_terminal_colour('#ff5f87', number=204),
    Colour.create_terminal_colour('#ff5faf', number=205),
    Colour.create_terminal_colour('#ff5fd7', number=206),
    Colour.create_terminal_colour('#ff5fff', number=207),
    Colour.create_terminal_colour('#ff8700', number=208),
    Colour.create_terminal_colour('#ff875f', number=209),
    Colour.create_terminal_colour('#ff8787', number=210),
    Colour.create_terminal_colour('#ff87af', number=211),
    Colour.create_terminal_colour('#ff87d7', number=212),
    Colour.create_terminal_colour('#ff87ff', number=213),
    Colour.create_terminal_colour('#ffaf00', number=214),
    Colour.create_terminal_colour('#ffaf5f', number=215),
    Colour.create_terminal_colour('#ffaf87', number=216),
    Colour.create_terminal_colour('#ffafaf', number=217),
    Colour.create_terminal_colour('#ffafd7', number=218),
    Colour.create_terminal_colour('#ffafff', number=219),
    Colour.create_terminal_colour('#ffd700', number=220),
    Colour.create_terminal_colour('#ffd75f', number=221),
    Colour.create_terminal_colour('#ffd787', number=222),
    Colour.create_terminal_colour('#ffd7af', number=223),
    Colour.create_terminal_colour('#ffd7d7', number=224),
    Colour.create_terminal_colour('#ffd7ff', number=225),
    Colour.create_terminal_colour('#ffff00', number=226),
    Colour.create_terminal_colour('#ffff5f', number=227),
    Colour.create_terminal_colour('#ffff87', number=228),
    Colour.create_terminal_colour('#ffffaf', number=229),
    Colour.create_terminal_colour('#ffffd7', number=230),
    Colour.create_terminal_colour('#ffffff', number=231),
    Colour.create_terminal_colour('#080808', number=232),
    Colour.create_terminal_colour('#121212', number=233),
    Colour.create_terminal_colour('#1c1c1c', number=234),
    Colour.create_terminal_colour('#262626', number=235),
    Colour.create_terminal_colour('#303030', number=236),
    Colour.create_terminal_colour('#3a3a3a', number=237),
    Colour.create_terminal_colour('#444444', number=238),
    Colour.create_terminal_colour('#4e4e4e', number=239),
    Colour.create_terminal_colour('#585858', number=240),
    Colour.create_terminal_colour('#626262', number=241),
    Colour.create_terminal_colour('#6c6c6c', number=242),
    Colour.create_terminal_colour('#767676', number=243),
    Colour.create_terminal_colour('#808080', number=244),
    Colour.create_terminal_colour('#8a8a8a', number=245),
    Colour.create_terminal_colour('#949494', number=246),
    Colour.create_terminal_colour('#9e9e9e', number=247),
    Colour.create_terminal_colour('#a8a8a8', number=248),
    Colour.create_terminal_colour('#b2b2b2', number=249),
    Colour.create_terminal_colour('#bcbcbc', number=250),
    Colour.create_terminal_colour('#c6c6c6', number=251),
    Colour.create_terminal_colour('#d0d0d0', number=252),
    Colour.create_terminal_colour('#dadada', number=253),
    Colour.create_terminal_colour('#e4e4e4', number=254),
    Colour.create_terminal_colour('#eeeeee', number=255),
)

# A single white Colour instance to use as a default.
default_white = Colour(255, 255, 255, 'White')

#: A mapping from cterm code to TerminalColour.
#:
#: Note that the entries for colour numbers 0 to 15 map to the closest matching
#: entries in the 16 to 255 range.
cterm_code_to_colour = {c.number: c for c in terminal_colour_list}
for t_colour in terminal_16_colour_list:
    _, closest = min(
        ((t_colour.distance(ext_colour), ext_colour)
        for ext_colour in terminal_colour_list),
        key=lambda el: el[0])
    cterm_code_to_colour[t_colour.number] = closest

# A mapping from name to `Highlight` instance.
_highlights: dict[str, Highlight] = {}

# A list of groups that should be standard but, at time of writing, are not.
_should_be_standard_goups = {
    'Bold': Highlight(
        name='Bold',
        term=TermSettings(bold=True),
        cterm=ColourTermSettings(bold=True),
        gui=GUISettings(bold=True),
    ),
    'Italic': Highlight(
        name='Italic',
        term=TermSettings(bold=True),
        cterm=ColourTermSettings(bold=True),
        gui=GUISettings(bold=True),
    ),
    'Strikethrough': Highlight(
        name='Strikethrough',
        term=TermSettings(strikethrough=True),
        cterm=ColourTermSettings(strikethrough=True),
        gui=GUISettings(strikethrough=True),
    ),
}

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
