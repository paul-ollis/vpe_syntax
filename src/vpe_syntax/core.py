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
    'attribute':                  'Decorator',
    'boolean':                    'Boolean',
    'comment':                    'Comment',
    'conditional':                'Conditional',
    'constant.builtin':           'Constant',
    'constant':                   'Constant',
    'constructor':                'Constructor',
    'error':                      'Error',
    'function.builtin':           'Function',
    'function.call':              None,
    'function':                   'Function',
    'include':                    'Include',
    'interpolation':              'Interpolation',
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
    'punctuation.special':        'SpecialPunctuation',
    'repeat':                     'Repeat',
    'spell':                      None,
    'string':                     'String',
    'type.builtin':               'Type',
    'type.definition':            None,
    'type':                       'Type',
    'variable':                   None,

    # These Tree-sitter names have been added to the SCM file by me.
    'docstring':                  'DocString',
    'format.identifier':          'FormatIdentifier',
    'format.specifier':           'FormatSpecifier',
}

#: A list of standard highlight group names.
#:
#: These groups are created as a result of 'syntax on' being executed.
STANDARD_GROUPS = (
    ('Added', 50),
    ('Boolean', 50),
    ('Changed', 50),
    ('Character', 50),
    ('Comment', 50),
    ('Conditional', 50),
    ('Constant', 50),
    ('Debug', 50),
    ('Define', 50),
    ('Delimiter', 50),
    ('Error', 50),
    ('Exception', 50),
    ('Float', 50),
    ('Function', 50),
    ('Identifier', 20),
    ('Include', 50),
    ('Keyword', 50),
    ('Label', 50),
    ('Macro', 50),
    ('Number', 50),
    ('Operator', 50),
    ('PreCondit', 50),
    ('PreProc', 50),
    ('Removed', 50),
    ('Repeat', 50),
    ('Special', 50),
    ('SpecialChar', 50),
    ('SpecialComment', 50),
    ('Statement', 50),
    ('StorageClass', 50),
    ('String', 30),
    ('Structure', 50),
    ('Tag', 50),
    ('Todo', 50),
    ('Type', 50),
    ('Typedef', 50),
    ('Underlined', 50),
)

# My additional non-standard groups.
ADDITIONAL_GROUPS: dict[str, dict] = {
    'Class': {
         'priority': 50, 'guifg': 'DarkGoldenrod',
    },
    'ClassName': {
         'priority': 50, 'guifg': 'ForestGreen',
    },
    'Constructor': {
         'priority': 60, 'guifg': 'LightSteelBlue', 'gui': 'bold',
    },
    'Decorator': {
         'priority': 50, 'gui': 'italic',
    },
    'DocString': {
         'priority': 50, 'guifg': 'LightSteelBlue',
    },
    'FloatNumber': {
         'priority': 50, 'guifg': 'LightSeaGreen',
    },
    'FormatSpecifier': {
         'priority': 50, 'guifg': 'PaleGreen',
    },
    'Interpolation': {
         'priority': 40, 'guifg': 'LightGrey',
    },
    'FormatIdentifier': {
         'priority': 55, 'guifg': 'Goldenrod',
    },
    'FunctionName': {
         'priority': 50, 'guifg': 'LightSeaGreen',
    },
    'NonStandardSelf': {
         'priority': 50, 'gui': 'bold',
    },
    'Pass': {
         'priority': 50, 'guifg': 'LightGray',
    },
    'Self': {
         'priority': 50, 'gui': 'italic',
    },
    'SpecialPunctuation': {
         'priority': 50, 'guifg': 'LightGray',
    },
    'StandardConst': {
         'priority': 50, 'guifg': 'PowderBlue',
    },

    # Over-rides of standard groups.
    'String': {
         'priority': 50, 'guifg': 'LightSalmon',
    },
}

#: This is used to log any unknown Tree-sitter names when first encountered.
_seen_unkown_names: set[str] = set()


@dataclass
class InprogressPropsetOperation:
    """Data capturing an in-progress syntax property setting operation."""

    buf: vpe.Buffer
    listener: Listener
    unset_lines: set[int] = field(default_factory=set)
    target_lines: Iterable[int] = field(default_factory=list)
    active: bool = False
    timer: vpe.Timer | None = None

    times: list[float] = field(default_factory=list)
    prop_count: int = 0

    def start(self, affected_lines: AffectedLines) -> None:
        """Start a new property setting run.

        Any partial run is abandoned.
        """
        if self.active and self.timer:
            self.timer.stop()
            self.timer = None

        self.times[:] = []
        self.prop_count = 0
        self.listener.syntax_line_spans.debug_reset()

        self.active = True
        #- if affected_lines:
        #-     self.unset_lines = set()
        #-     for a, b in affected_lines:
        #-         self.unset_lines.update(range(a, b))
        #- else:
        #-     print('Propset start for ALL lines!')
        #-     self.unset_lines = set(range(len(self.buf)))

        # If the buffer is visible in one or more windows, start with the lines
        # visible in those windows.
        win_ids = vim.win_findbuf(self.buf.number)
        if win_ids:
            ranges = []
            for win_id in win_ids:
                info = vim.getwininfo(win_id)[0]
                start = info['topline']
                end = info['botline']
                ranges.append(range(start, end))
            self.target_lines = chain(*ranges, range(len(self.buf)))
        else:
            self.target_lines = iter(range(len(self.buf)))

        kwargs = {'bufnr': self.buf.number, 'id': 10_042, 'all': 1}
        vim.prop_remove(kwargs)

        self.unset_lines = set(range(len(self.buf)))
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
            print(f'All {self.prop_count} props applied in {tot_time=:.4f}'
                  f' {map_time=:.4f}')

    def _do_add_props(self) -> None:
        """Add properties to a numebr of lines."""
        debug_line_index = -1
        def dump_line(index):
            print(f'HL: {self.buf[index]!r}')
            for a, b, name in spans[index]:
                print(f'    {a}--{b} = {name}')

        spans = self.listener.syntax_line_spans
        unknown_names = set()
        kwargs = {'bufnr': self.buf.number, 'id': 10_042}
        start_time = time.time()
        now = start_time

        max_line_index = len(self.buf) - 1
        for i in self.target_lines:
            if i not in self.unset_lines:
                continue
            self.unset_lines.discard(i)
            if i == debug_line_index:
                dump_line(i)

            line_len = len(self.buf[i])
            # TODO: I think assert i == sl_idx
            for sl_idx, sc_idx, el_idx, ec_idx, name in spans[i]:
                assert sl_idx == i
                if el_idx > max_line_index:
                    el_idx = max_line_index + 1
                    ec_idx = 0
                else:
                    ec_idx = min(len(self.buf[el_idx]), ec_idx)
                self.prop_count += 1
                if name not in syn_name_to_prop_name:
                    if name not in _seen_unkown_names:
                        unknown_names.add(name)
                        _seen_unkown_names.add(name)
                    continue
                prop_name = syn_name_to_prop_name[name]
                if prop_name is None:
                    continue

                sc_idx = min(sc_idx, line_len)
                kwargs['end_lnum'] = el_idx + 1
                kwargs['end_col'] = ec_idx + 1
                kwargs['type'] = prop_name
                vim.prop_add(i + 1, sc_idx + 1, kwargs)
                if i < 0:
                    print(
                        f'Add {i + 1},{sc_idx + 1}, {el_idx + 1},{ec_idx + 1}'
                        f' - {prop_name}')

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

    def old_do_add_props(self) -> None:
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
        now = start_time

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
    """An object that maintains syntax highlighting for a buffer."""

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
        # print(f'Win change:  {top_index=} {bottom_index=}')


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
    for name, priority in STANDARD_GROUPS:
        create_prop_type(name, highlight_group_name=name, priority=priority)


def add_or_override_groups():
    """Create property types for the standard group names."""
    for name, data in ADDITIONAL_GROUPS.items():
        data = data.copy()
        priority = data.pop('priority', 50)
        vpe.highlight(group=name, **data)
        create_prop_type(name, highlight_group_name=name, priority=priority)


create_std_prop_types()
add_or_override_groups()
