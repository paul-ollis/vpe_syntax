"""VPE syntax highlighting core module."""
from __future__ import annotations

import time
from collections.abc import Iterable
from dataclasses import dataclass, field
from itertools import chain

import vpe
from vpe import vim

from vpe_sitter.listen import AffectedLines, Listener

#: A mapping from Tree-sitter syntax names to property names.
syn_name_to_prop_name: dict[str, str | None] = {
    '_annotation':                None,
    'attribute':                  None,
    'boolean':                    'Boolean',
    'comment':                    'Comment',
    'conditional':                'Conditional',
    'constant.builtin':           'Constant',
    'constant':                   'Constant',
    'constructor':                None,
    'error':                      'Error',
    'function.builtin':           'Function',
    'function.call':              None,
    'function':                   'Function',
    'include':                    'Include',
    'keyword':                    'Keyword',
    'keyword.function':           'Keyword',
    'keyword.return':             'Keyword',
    'keyword.operator':           'Keyword',
    'method.call':                None,
    'number':                     'Number',
    'operator':                   'Operator',
    'parameter':                  None,
    'punctuation.bracket':        None,
    'punctuation.delimiter':      'Operator',
    'repeat':                     'Repeat',
    'spell':                      None,
    'string':                     'String',
    'type.builtin':               'Type',
    'type.definition':            None,
    'type':                       'Type',
    'variable':                   'Identifier',
}

#: A list of standard highlight group names.
#:
#: These groups are created as a result of 'syntax on' being executed.
STANDARD_GROUPS = set((
    'Added',
    'Boolean',
    'Changed',
    'Character',
    'Comment',
    'Conditional',
    'Constant',
    'Debug',
    'Define',
    'Delimiter',
    'Error',
    'Exception',
    'Float',
    'Function',
    'Identifier',
    'Include',
    'Keyword',
    'Label',
    'Macro',
    'Number',
    'Operator',
    'PreCondit',
    'PreProc',
    'Removed',
    'Repeat',
    'Special',
    'SpecialChar',
    'SpecialComment',
    'Statement',
    'StorageClass',
    'String',
    'Structure',
    'Tag',
    'Todo',
    'Type',
    'Typedef',
    'Underlined',
))


#: This is used to log any unknown Tree-sitter names when first encountered.
_seen_unkown_names: set[str] = set()


@dataclass
class InprogressPropsetOperation:
    """Data capturing an in-progress syntax property setting operation."""

    buf: vpe.Buffer
    listener: Listener
    unset_lines: set[int] = field(default_factory=list)
    target_lines: Iterable[int] = field(default_factory=list)
    active: bool = False
    timer: vpe.Timer | None = None

    times: list[float] = field(default_factory=list)
    prop_count: int = 0

    def start(self, affected_lines: AffectedLines) -> None:
        """Start a new properrty setting run.

        Any partial run is abandoned.
        """
        if self.active and self.timer:
            self.timer.stop()
            self.timer = None

        self.times[:] = []
        self.prop_count = 0
        self.listener.syntax_line_spans.debug_reset()

        self.active = True
        if affected_lines:
            self.unset_lines = set()
            for a, b in affected_lines:
                self.unset_lines.update(range(a, b))
        else:
            print('Propset start for ALL lines!')
            self.unset_lines = set(range(len(self.buf)))
        win_ids = vim.win_findbuf(self.buf.number)
        if win_ids:
            print(f'Update windows: {list(win_ids)}')
            ranges = []
            for win_id in win_ids:
                info = vim.getwininfo(win_id)[0]
                start = info['topline']
                end = info['botline']
                ranges.append(range(start, end))
            self.target_lines = chain(*ranges, range(len(self.buf)))
        else:
            self.target_lines = iter(range(len(self.buf)))
            print('Start on buffer from the top.')
        self._try_add_props()

    def _try_add_props(self, _timer: vpe.Timer | None = None) -> None:
        self._do_add_props()
        if self.active:
            self._schedule_continuation()
        else:
            if self.timer:
                self.timer = None
            tot_time = sum(self.times)
            map_time = self.listener.syntax_line_spans.tot_time
            print(f'All {self.prop_count} props applied in {tot_time=}'
                  f' {map_time=}')

    def _do_add_props(self) -> None:
        """Add properties to a numebr of lines."""
        debug_line_index = 851
        def dump_line(index):
            print(f'HL: {self.buf[index]!r}')
            for a, b, name in spans[index]:
                print(f'    {a}--{b} = {name}')

        spans = self.listener.syntax_line_spans
        unknown_names = set()
        kwargs = {'bufnr': self.buf.number}
        start_time = time.time()

        debug = True
        for i in self.target_lines:
            if i not in self.unset_lines:
                continue
            if i == debug_line_index:
                dump_line(i)

            if debug and i < 1000:
                print(f'Continue from: {i}')
            debug = False
            vim.prop_clear(i + 1)
            line_len = len(self.buf[i])
            for a, b, name in spans[i]:
                self.prop_count += 1
                if name not in syn_name_to_prop_name:
                    if name not in _seen_unkown_names:
                        unknown_names.add(name)
                        _seen_unkown_names.add(name)
                    continue
                prop_name = syn_name_to_prop_name[name]
                if prop_name is None:
                    continue

                b = min(b, line_len)
                prop_len = b - a
                kwargs['length'] = prop_len
                kwargs['type'] = prop_name
                vim.prop_add(i + 1, a + 1, kwargs)

            now = time.time()
            if now - start_time > 0.08:
                self.times.append(now - start_time)
                if unknown_names:
                    print(f'Unhandled tree-sitter names: {unknown_names}')
                return

        self.active = False
        self.times.append(now - start_time)
        if unknown_names:
            print(f'Unhandled tree-sitter names: {unknown_names}')

    def _schedule_continuation(self) -> None:
        ms_delay = 10
        self.timer = vpe.Timer(ms_delay, self._try_add_props)


class Highlighter:
    """An object that maintaiuns syntax highlighting for a buffer."""

    def __init__(self, buf: vpe.Buffer, listener: Listener):
        self.buf = buf
        self.listener = listener
        self.prop_set_operation = InprogressPropsetOperation(buf, listener)
        self.listener.add_parse_complete_callback(self.handle_parse_complete)

    def handle_parse_complete(self, affected_lines: AffectedLines) -> None:
        """Take action when the buffer's code has been (re)parsed."""
        self.prop_set_operation.start(affected_lines)

    def handle_window_scrolled(self, info: dict) -> None:
        """Handle when a window showing this buffer has scrolled or resized."""
        top_index = info['topline'] - 1
        bottom_index = info['botline'] - 1
        print(f'Win change:  {top_index=} {bottom_index=}')


def create_prop_type(
        name: str,
        highlight_group_name: str,
        priority: int = 0,
    ):
    """Create a single, global Vim property type with a given name.

    :name:
        The name of the property type.
    :highlight_group_name:
        The highlight group for this property type.
    :priority:
        An optional priority.
        TODO: Is this required?
    """
    kw = {
        'highlight': highlight_group_name,
        'priority': priority,
        'combine': False,       # Over-ride noral syntax highlighting.
        'start_incl': False,    # Do not extend for inserts at the start.
        'end_incl': False,      # Do not extend for inserts at the end.
    }
    known_prop_info = vim.prop_type_get(name)
    if known_prop_info:
        return
    vim.prop_type_add(name, kw)


def create_std_prop_types():
    """Create property types for the standard group names."""
    for name in STANDARD_GROUPS:
        create_prop_type(name, highlight_group_name=name)


create_std_prop_types()


# ----------------------------------------------------------------------------
# Dead/broken stuff below this point.
# ----------------------------------------------------------------------------

# TODO: This is non-generic and not being used.
def create_text_prop_types():
    """Create all the standard property types required by Python."""
    create_std_prop_types()

    vpe.highlight(group='FloatNumber', guifg='LightSeaGreen')
    vpe.highlight(group='DocString', guifg='LightSteelBlue')
    vpe.highlight(group='ClassName', guifg='ForestGreen')
    vpe.highlight(group='FunctionName', guifg='PaleGreen')
    vpe.highlight(group='Class', guifg='DarkGoldenrod')
    vpe.highlight(group='Pass', guifg='LightGray')
    vpe.highlight(group='StandardConst', guifg='PowderBlue')
    vpe.highlight(group='Self', guifg='Wheat3', gui='italic')
    vpe.highlight(group='NonStandardSelf', guifg='OrangeRed', gui='bold')
    vpe.highlight(group='StandardDecorator', guifg='PowderBlue', gui='italic')

    create_prop_type('Class', highlight_group_name='Class')
    create_prop_type('ClassName', highlight_group_name='ClassName')
    create_prop_type('DocString', highlight_group_name='DocString')
    create_prop_type('FunctionName', highlight_group_name='FunctionName')
    create_prop_type('MethodName', highlight_group_name='FunctionName')
    create_prop_type('Pass', highlight_group_name='Pass')
    create_prop_type('Self', highlight_group_name='Self')
    create_prop_type('Cls', highlight_group_name='Self')
    create_prop_type('NonStandardSelf', highlight_group_name='NonStandardSelf')
    create_prop_type('NonStandardCls', highlight_group_name='NonStandardSelf')
    create_prop_type('StandardConst', highlight_group_name='StandardConst')
    create_prop_type('ClassMethodDecorator', highlight_group_name='StandardDecorator')
    create_prop_type('StaticMethodDecorator', highlight_group_name='StandardDecorator')

    create_prop_type('FloatNumber', highlight_group_name='Float')


# create_text_prop_types()
