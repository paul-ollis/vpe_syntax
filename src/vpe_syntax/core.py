"""VPE syntax highlighting core module."""
from __future__ import annotations

import re
import time
from collections.abc import Iterable
from dataclasses import dataclass, field

from tree_sitter import Node, TreeCursor

import vpe
from vpe import vim

from vpe_sitter.listen import AffectedLines, Listener
from vpe_syntax.hl_groups import STANDARD_GROUPS

# Short names for use in `tree_data_to_prop_name`.
class_block = 'class_definition.block'
class_def = 'class_definition'
func_def = 'function_definition'
params = f'{func_def}.parameters'
typed_param = f'{params}.typed_parameter'
imp_from = 'import_from_statement'
str_stmt = 'expression_statement.string'

#: A mapping from Tree-sitter syntax tuples to property names.
tree_data_to_prop_name: dict[str, str | None] = {
    # Simple elements.
    'and':                                            'Keyword',
    'as':                                             'Keyword',
    'assert':                                         'Keyword',
    'async':                                          'Keyword',
    'attribute':                                      'Attribute',
    'await':                                          'Keyword',
    'break':                                          'Keyword',
    'class':                                          'Keyword',
    'comment':                                        'Comment',
    'continue':                                       'Keyword',
    'decorator':                                      'Decorator',
    'def':                                            'Keyword',
    'del':                                            'Keyword',
    'elif':                                           'Keyword',
    'else':                                           'Keyword',
    'ERROR':                                          'Error',
    'except':                                         'Keyword',
    'false':                                          'Boolean',
    'finally':                                        'Keyword',
    'float':                                          'Float',
    'for':                                            'Keyword',
    'from':                                           'Keyword',
    'global':                                         'Keyword',
    'identifier':                                     'Identifier',
    'if':                                             'Keyword',
    'import':                                         'Keyword',
    'in':                                             'Keyword',
    'integer':                                        'Number',
    'interpolation':                                  'Interpolation',
    'is':                                             'Keyword',
    'lambda':                                         'Keyword',
    'None':                                           'Keyword',
    'none':                                           'None',
    'nonlocal':                                       'Keyword',
    'not':                                            'Keyword',
    'operator':                                       'Operator',
    'operators':                                      'Operator',
    'or':                                             'Keyword',
    'pass':                                           'Keyword',
    'raise':                                          'Keyword',
    'return':                                         'Return',
    'string':                                         'String',
    'true':                                           'Boolean',
    'try':                                            'Keyword',
    'while':                                          'Keyword',
    'with':                                           'Keyword',
    'yield':                                          'Keyword',

    # Docstrings for modules, classes and functions/methods.
    f'module.{str_stmt}':                             'DocString',
    f'{func_def}.block.{str_stmt}':                   'DocString',
    f'{class_def}.block.{str_stmt}':                  'DocString',

    # Class components.
    'class_definition.class':                         'Class',
    'class_definition.identifier':                    'ClassName',

    # Import statements.
    'import_statement.import':                        'Import',
    'import_statement.dotted_name':                   'ImportedName',
    f'{imp_from}.import':                             'Import',
    f'{imp_from}.from':                               'Import',
    f'{imp_from}.dotted_name':                        'ImportedName',
    f'{imp_from}.aliased_import.as':                  'Import',
    f'{imp_from}.aliased_import.dotted_name':         'ImportedName',
    f'{imp_from}.aliased_import.identifier':          'ImportedAliasedName',

    # Functions and methods.
    f'{func_def}.def':                                'Function',
    f'{func_def}.name:identifier':                    'FunctionName',
    f'{func_def}.identifier':                         'Identifier',
    f'{params}.identifier':                           'Parameter',
    f'{typed_param}.identifier':                      'Parameter',
    f'{class_block}.{func_def}.def':                  'Method',
    f'{class_block}.{func_def}.identifier':           'MethodName',

    # Method and function invocation.
    'call.identifier':                                'CalledFunction',
    'call.attribute+.identifier':                     'CalledMethod',
    'argument_list.identifier':                       'Argument',

    # Type annotations.
    'type_parameter.[':                               'TypeBracket',
    'type_parameter.]':                               'TypeBracket',
    'type.identifier':                                'Type',
}


@dataclass
class MatchNode:
    """A node within the match_tree.

    @prop_name:
        The name of the property used when this node is the tip of a matching
        sequence. The value may be an empty string, which indicates that no
        match applies for this node.
    @choices:
        A dictionary uses to check for parent node matches. Each key is a
        syntax tree node name and each value is another `MatchNode`.
    """
    prop_name: str = ''
    choices: dict[str, MatchNode] = field(default_factory=dict)


# For the tree match_method.
def build_match_tree() -> dict[str, list]:
    """Build the syntax matching tree."""
    tree: MatchNode = MatchNode()

    for cname, property_name in tree_data_to_prop_name.items():
        components = tuple(cname.split('.'))
        node = tree
        last_index = len(components) - 1
        for i, ident in enumerate(reversed(components)):
            if ident.endswith('+'):
                ident = ident[:-1]
                repeat = True
            else:
                repeat = False

            if ':' in ident:
                ident = tuple(ident.split(':'))
            if ident not in node.choices:
                node.choices[ident] = MatchNode()
            node = node.choices[ident]
            if i == last_index:
                node.prop_name = property_name

            if repeat:
                # Note:This makes a the match tree recursive.
                node.choices[ident] = node

    return tree


def dump_match_tree():

    def do_dump(node, name):
        nonlocal pad

        if id(node) in seen:
            print(f'{pad}{name=} ...')
            return
        else:
            print(f'{pad}{name=} {node.prop_name=}')
        seen.add(id(node))
        pad += '    '
        for xname, xnode in node.choices.items():
            do_dump(xnode, xname)
        pad = pad[-4:]

    seen = set()
    pad = ''
    do_dump(match_tree, '')


#: A tree structure used to test a Tree-sitter node for a highligh match.
#:
#: The tree is composed of `MatchNode` instances, including the root.
match_tree: MatchNode = build_match_tree()

#- dump_match_tree()


# My additional non-standard groups.
# TODO: Should be dead.
ADDITIONAL_GROUPS: dict[str, dict] = {
    'Class':              {'priority': 50, 'guifg': 'DarkGoldenrod',},
    'ClassName':          {'priority': 50, 'guifg': 'ForestGreen',},
    'Constructor':        {'priority': 60, 'guifg': 'LightSteelBlue',
                                           'gui':   'bold',},
    'Decorator':          {'priority': 50, 'gui':   'italic',},
    'DocString':          {'priority': 50, 'guifg': 'LightSteelBlue',},
    'FloatNumber':        {'priority': 50, 'guifg': 'LightSeaGreen',},
    'FunctionCall':       {'priority': 50, 'guifg': 'YellowGreen',},
    'FunctionName':       {'priority': 50, 'guifg': 'LightSeaGreen',},
    'FormatIdentifier':   {'priority': 55, 'guifg': 'Goldenrod',},
    'FormatSpecifier':    {'priority': 50, 'guifg': 'PaleGreen',},
    'Interpolation':      {'priority': 40, 'guifg': 'LightGrey',},
    'MethodCall':         {'priority': 50, 'guifg': 'YellowGreen',},
    'NonStandardSelf':    {'priority': 50, 'gui':   'bold',},
    'Pass':               {'priority': 50, 'guifg': 'LightGray',},
    'Self':               {'priority': 50, 'gui':   'italic',},
    'SpecialPunctuation': {'priority': 50, 'guifg': 'LightGray',},
    'StandardConst':      {'priority': 50, 'guifg': 'PowderBlue',},
    'TypeBracket':        {'priority': 60, 'guifg': 'foreground'},

    # Over-rides of standard groups.
    'String':             {'priority': 50, 'guifg': 'LightSalmon',},
}


@dataclass
class WalkingInprogressPropsetOperation:
    """Manager of an in-progress syntax property setting operation.

    This applies syntax highlighting from a Tree-sitter parse tree as a pseudo-
    background task.
    """
    buf: vpe.Buffer
    listener: Listener
    unset_lines: set[int] = field(default_factory=set)
    target_lines: Iterable[int] = field(default_factory=list)
    active: bool = False
    timer: vpe.Timer | None = None
    cursor: TreeCursor | None = None
    root_name: str = ''

    times: list[float] = field(default_factory=list)
    prop_count: int = 0
    prop_set_count: int = 0
    props_per_set: int = 2000
    continuation_count: int = 0
    props_to_add: dict[str, list[list[int, int, int, int]]] = field(
        default_factory=dict)
    props_pending_count: int = 0

    def start(self, _affected_lines: AffectedLines) -> None:
        """Start a new property setting run.

        Any partial run is abandoned.
        """
        if self.active and self.timer:
            self.timer.stop()
            self.timer = None
            self.active = False

        self.cursor = self.listener.tree.walk()
        self.root_name = self.cursor.node.type
        if not self.cursor.goto_first_child():
            # The source is basically an empty file.
            return

        self.times[:] = []
        self.prop_count = 0
        self.continuation_count = 0

        self.active = True

        kwargs = {'bufnr': self.buf.number, 'id': 10_042, 'all': 1}
        vim.prop_remove(kwargs)
        self.props_to_add.clear()
        self.props_pending_count = 0
        self._try_add_props()

    def _walk_a_top_level_element(self):
        """Walk a top level syntatic element.

        This is invoked with the cursor already on a top-level syntatic element
        node.

        :return:
            True if the last element has been processed.
        """

        def apply_prop(node: Node, cname: tuple[str, ...]) -> None:
            """Apply a property if a Tree-sitter node matches.

            :node:
                The Tree-sitter node.
            :cname:
                A tuple of the names of all the Tree-sitter nodes visited to
                reach this node, ending in this node's name.
            """
            def find_match(
                    matching_node, cname, index, best_match=None,
                ) -> tuple[MatchNode | None, int]:
                field_name, node_name = cname[index]
                branches = []
                if field_name:
                    branches.append((field_name, node_name))
                branches.append(node_name)

                matches = []
                for branch in branches:
                    temp_node = matching_node.choices.get(branch)
                    if temp_node:
                        temp_best_match = best_match
                        if temp_node.prop_name:
                            temp_best_match = temp_node
                        if index > 0:
                            deeper_match = find_match(
                                temp_node, cname, index - 1, temp_best_match)
                            if deeper_match not in (best_match, None):
                                matches.append(deeper_match)
                        else:
                            matches.append(temp_best_match)

                for match in matches:
                    if match is not best_match:
                        return match
                return best_match

            best_match = find_match(match_tree, cname, len(cname) - 1)
            if best_match:
                prop_name = best_match.prop_name
                self.prop_count += 1
                sl_idx, sc_idx = node.start_point
                el_idx, ec_idx = node.end_point
                if prop_name not in self.props_to_add:
                    self.props_to_add[prop_name] = []
                self.props_to_add[prop_name].append(
                    [sl_idx + 1, sc_idx + 1, el_idx + 1, ec_idx + 1])
                self.props_pending_count += 1

        def process(node, cname):
            """Recursively process a Tree-sitter node and its decendants."""
            parent = node
            apply_prop(node, cname)
            if not self.cursor.goto_first_child():
                return

            i = 0
            while True:
                field_name = parent.field_name_for_child(i)
                i += 1
                node = self.cursor.node
                process(node, cname + ((field_name, node.type),))
                if not self.cursor.goto_next_sibling():
                    self.cursor.goto_parent()
                    return

        node = self.cursor.node
        cname = (
            ('', self.root_name),
            (self.cursor.field_name, self.cursor.node.type)
        )
        process(node, cname)
        if self.props_pending_count > self.props_per_set:
            self._flush_props()

    def _flush_props(self) -> None:
        kwargs = {'bufnr': self.buf.number, 'id': 10_042}
        for prop_name, locations in self.props_to_add.items():
            kwargs['type'] = prop_name
            try:
                vim.prop_add_list(kwargs, locations)
            except vim.error:
                # The buffer may have changed, making some property line and
                # column offsets invalid.
                pass
            self.prop_set_count += 1
        self.props_to_add.clear()
        self.props_pending_count = 0

    def _try_add_props(self, _timer: vpe.Timer | None = None) -> None:
        self._do_add_props()
        if self.active:
            self._schedule_continuation()
        else:
            if self.timer:
                self.timer = None
            self._flush_props()
            tot_time = sum(self.times)
            print(
                f'All {self.prop_count}({self.prop_set_count})'
                f' props applied in {tot_time=:.4f}'
                f' using {self.continuation_count} continuations'
            )

    def _do_add_props(self) -> None:
        """Add properties to a number of lines."""
        start_time = time.time()
        now = start_time
        while True:
            self._walk_a_top_level_element()
            if not self.cursor.goto_next_sibling():
                break

            now = time.time()
            if now - start_time > 0.05:
                self.times.append(now - start_time)
                return

        # All properties are set/pending.
        self._flush_props()
        now = time.time()
        self.times.append(now - start_time)
        self.active = False

    def _schedule_continuation(self) -> None:
        ms_delay = 10
        self.continuation_count += 1
        self.timer = vpe.Timer(ms_delay, self._try_add_props)


class Highlighter:
    """An object that maintains syntax highlighting for a buffer."""

    def __init__(self, buf: vpe.Buffer, listener: Listener):
        self.buf = buf
        self.listener = listener
        self.prop_set_operation = WalkingInprogressPropsetOperation(
            buf, listener)
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
        'combine': False,       # Over-ride normal syntax highlighting.
        'start_incl': False,    # Do not extend for inserts at the start.
        'end_incl': False,      # Do not extend for inserts at the end.
    }
    known_prop_info = vim.prop_type_get(name)
    if known_prop_info:
        return
    vim.prop_type_add(name, kw)


# TODO: Should be dead.
def create_std_prop_types():
    """Create property types for the standard group names."""
    for name, priority in STANDARD_GROUPS:
        create_prop_type(name, highlight_group_name=name, priority=priority)


# TODO: Should be dead.
def add_or_override_groups():
    """Create property types for the standard group names."""
    for name, data in ADDITIONAL_GROUPS.items():
        data = data.copy()
        priority = data.pop('priority', 50)
        vpe.highlight(group=name, **data)
        create_prop_type(name, highlight_group_name=name, priority=priority)


# create_std_prop_types()
# add_or_override_groups()

#
# Basic regular expression approach                = 0.810
# String building, without matching                = 0.046
# String building, without matching and with xlate = 0.053
# String building, with xlate                      = 0.810
#
# Current mechanism          = 0.21
# Simple recursive matching  = 0.22
# Full recursive matching    = 0.27
