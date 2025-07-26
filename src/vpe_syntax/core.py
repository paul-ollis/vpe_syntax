"""VPE syntax highlighting core module."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from importlib.resources.abc import Traversable
from typing import NamedTuple, TypeAlias

from tree_sitter import Node, Point, Tree, TreeCursor

import vpe
from vpe import vim

from vpe_sitter import parsers
from vpe_sitter.listen import (
    AffectedLines, ConditionCode, Listener, debug_settings)

#: Qualfied Tree-sitter type name - field_name, type_name.
QualTreeNodeName: TypeAlias = tuple[str, str]

#: Canonical Tree-sitter node name.
#:
#: A sequence if qualified names starting from the root.
CName: TypeAlias = tuple[QualTreeNodeName]

#: Tree structures used to test a Tree-sitter node for a highligh match.
#:
#: Each tree is composed of `MatchNode` instances, including the root.
match_trees: dict[str, MatchNode] = {}

# A table of registered handlers for embedded syntax handling.
#
# The key is a two string tuple. The first string is the main language and
# the second string is the embedded language, which may be the same.
#
# The value is an `EmbeddedHighlighter` instance, which provides the methods
# to identify embedded code and trigger highlighting.
#
# This table is populated by `vpe_syntax.register_embedded_language` function.
embedded_syntax_handlers: dict[tuple[str, str], EmbeddedHighlighter] = {}


class State(Enum):
    """The states for the `InprogressPropsetOperation`."""

    INCOMPLETE = 1
    COMPLETE = 2


class ActionTimer:
    """A class that times how long something takes.

    @start: Start time, in seconds, for this timer.
    """

    def __init__(self):
        self.start: float = time.time()

    def restart(self) -> None:
        """Restart this timer."""
        self.start = time.time()

    @property
    def elapsed(self) -> float:
        """The current elapsed time."""
        return time.time() - self.start


class PseudoNode(NamedTuple):
    """A Tree-sitter ``Node`` like object."""

    start_point: Point
    end_point: Point
    type: str


@dataclass
class MatchNode:
    """A node within the match_tree.

    @prop_name:
        The name of the property used when this node is the tip of a matching
        sequence. The value may be an empty string, which indicates that no
        match applies for this node.
    @choices:
        A dictionary defining parent nodes that are tested as part of matching.
        Each key is a syntax tree node name and each value is a parent
        `MatchNode`.
    @embedded_parser:
        The embedded parser for this node.
    """
    prop_name: str = ''
    choices: dict[str, MatchNode] = field(default_factory=dict)
    embedded_syntax: str = ''


def _update_part_of_table(
        tree: MatchNode, cname: str, property_name: str, embedded_syntax: str,
    ) -> None:
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
            node.embedded_syntax = embedded_syntax

        if repeat:
            # Note:This makes a the match tree recursive.
            node.choices[ident] = node


def build_tables(
        filetype: str, traversables: list[Traversable], rebuild: bool = False,
    ) -> None:
    """Build the syntax matching tree."""
    if filetype in match_trees and not rebuild:
        return

    def all_lines():
        for traversable in traversables:
            yield from traversable.read_text(encoding='utf-8').splitlines()

    tree = match_trees[filetype] = MatchNode()
    cname_list = []
    for raw_line in all_lines():
        line = raw_line.rstrip()
        if line.startswith('# ') or not line.strip():
            continue

        parts = line.split()
        index = (len(line) - len(line.lstrip())) // 4
        extensions = []
        if len(parts) == 1:
            type_name, property_name = parts[0], ''
        else:
            type_name, property_name, *extensions = parts
        embedded_syntax = ''
        if extensions:
            ext = extensions[0]
            if ext.startswith('embed:'):
                _, embedded_syntax = ext.split(':')

        cname_list[index:] = []
        cname_list.append(type_name)
        if property_name:
            _update_part_of_table(
                tree, '.'.join(cname_list), property_name, embedded_syntax)

    #-dump_match_tree(filetype)


def dump_match_tree(filetype: str):
    """Dump a match tree - for debugging."""
    def do_dump(node, name):
        nonlocal pad

        if id(node) in seen:
            print(f'{pad}{name=} ...')
            return
        else:
            print(f'{pad}{name=} {node.prop_name=} {node.embedded_syntax}')
        seen.add(id(node))
        pad += '    '
        for xname, xnode in node.choices.items():
            do_dump(xnode, xname)
        pad = pad[-4:]

    seen = set()
    pad = ''
    do_dump(match_trees[filetype], '')


@dataclass
class PropertyData:
    """Data about properties set and being set."""

    prop_count: int = 0      # TODO: Unclear name.
    prop_set_count: int = 0  # TODO: Unclear name.
    props_per_set: int = 2000
    props_to_add: dict[str, list[list[int, int, int, int]]] = field(
        default_factory=dict)
    props_pending_count: int = 0
    continuation_count: int = 0

    @property
    def flush_required(self) -> bool:
        """A flag indicating that the `props_to_add` should be flushed."""
        return self.props_pending_count >= self.props_per_set

    def add_prop(self, prop_name: str, node: Node, prop_adjuster) -> None:
        """Buffer a property set operation."""
        sl_idx, sc_idx = node.start_point
        el_idx, ec_idx = node.end_point
        self.prop_count += 1
        if prop_adjuster:
            prop_name = f'{prop_name}'
        if prop_name not in self.props_to_add:
            self.props_to_add[prop_name] = []
        if prop_adjuster:
            sl_idx, sc_idx, el_idx, ec_idx = prop_adjuster(
                sl_idx, sc_idx, el_idx, ec_idx)

        self.props_to_add[prop_name].append(
            [sl_idx + 1, sc_idx + 1, el_idx + 1, ec_idx + 1])
        self.props_pending_count += 1

    def reset_buffer(self) -> None:
        """Reset the pending properties buffer."""
        self.props_to_add.clear()
        self.props_pending_count = 0

    def reset(self) -> None:
        """Reset all values."""
        self.prop_count = 0
        self.prop_set_count = 0
        self.props_to_add.clear()
        self.props_pending_count = 0
        self.continuation_count = 0


@dataclass
class TreeData:
    """Tree related data used during property setting."""

    tree: Tree | None = None
    affected_lines: list[range] | None = None

    def __post_init__(self) -> None:
        if self.affected_lines:
            self.affected_lines = list(self.affected_lines)


class SpellBlocks:
    """An object to track blocks where spelling should be enabled."""

    def __init__(self):
        self.blocks = []

    def add_block(self, start_lidx, count):
        """Add a block of lines."""
        self.blocks.append((start_lidx, count))


@dataclass
class InprogressPropsetOperation:
    """Manager of an in-progress syntax property setting operation.

    This applies syntax highlighting from a Tree-sitter parse tree as a pseudo-
    background task. The 'background' mode is only used when necessary. For
    most of the time syntax highlighting changes are applied syncronously as
    follows:

    1. A callback from the vpe_sitter indicates that the syntax tree has been
       updated and provides a list of affected line ranges. This triggers an
       invocation of the `start` method.

    2. The `start` invokes the code that updates syntax highlighting properties
       within a reasonable time.

    The synchronous operation can fail for a number of reasons.

    - Step 2 above does not manage to perform all the updates before timing
      out.
    - The callback in step 1 provides an empty list of ranges. This indicates
      that parsing took long enough for changes to be made to the buffer in the
      mean time.

    When this happens, the `start` method triggers a 'background' update that
    will apply properties for all the lines in the buffer.
    """
    # pylint: disable=too-many-instance-attributes
    buf: vpe.Buffer
    listener: Listener
    state: State = State.INCOMPLETE
    timer: vpe.Timer | None = None
    cursor: TreeCursor | None = None
    root_name: str = ''

    apply_time: ActionTimer | None = None
    prop_data: PropertyData = field(default_factory=PropertyData)

    tree_data: TreeData = field(default_factory=TreeData)
    pending_tree: bool = False
    buf_changed: bool = False
    rerun_scheduled: bool = False

    @property
    def match_tree(self) -> MatchNode:
        """The match tree used to apply properties."""
        # TODO: Will go bang is buffer's filetype is changed.
        return match_trees[self.buf.options.filetype]

    @property
    def active(self) -> bool:
        """Flag that is ``True`` when applying properties is ongoing."""
        return self.apply_time is not None

    def handle_tree_change(
            self, code: ConditionCode, affected_lines: AffectedLines) -> None:
        """Handle a change in the parse tree or associate buffer."""
        if self.state == State.INCOMPLETE:
            affected_lines = None

        match code:
            case ConditionCode.NEW_CLEAN_TREE:
                if not self.rerun_scheduled:
                    self.start(affected_lines)

            case ConditionCode.NEW_OUT_OF_DATE_TREE:
                if not self.rerun_scheduled:
                    self.start(affected_lines)

            case ConditionCode.PENDING_CHANGES:
                if self.active:
                    self.buf_changed = True

    def start(self, affected_lines: AffectedLines | None) -> None:
        """Start a new property setting run, if appropriate.

        If a run is in progress, then the affected lines and tree are saved for
        a subsequent run, which is triggered as soon as the active run
        completes.

        :affected_lines:
            The lines that need updating.
        :whole_buffer:
            If ``True`` then affected_lines is not used, properties are applied
            to the whole buffer.
        """
        self.rerun_scheduled = False
        if self.active:
            # Another run will be required when the current one finishes.
            self.pending_tree = True
            return

        self.tree_data = TreeData(self.listener.tree, affected_lines)
        self.cursor = self.tree_data.tree.walk()
        self.root_name = self.cursor.node.type
        if not self.cursor.goto_first_child():
            # The source is basically an empty file.
            self.state = State.COMPLETE
            return

        self.pending_tree = False
        self.buf_changed = False
        self.prop_data.reset()
        self.apply_time = ActionTimer()
        self._try_add_props()

    def _try_add_props(self, _timer: vpe.Timer | None = None) -> None:
        if not self._do_add_props():
            ms_delay = 10
            self.prop_data.continuation_count += 1
            self.timer = vpe.Timer(ms_delay, self._try_add_props)
        else:
            self.timer = None
            self._flush_props()
            tot_time = self.apply_time.elapsed
            if debug_settings.log_performance:
                data = self.prop_data
                print(
                    f'All {data.prop_count} props applied in {tot_time=:.4f}'
                    f' {data.prop_set_count} prop_add_list calls made,'
                    f' using {self.prop_data.continuation_count} continuations'
                )
            self.apply_time = None

            if self.pending_tree or self.buf_changed:
                # There may be mistakes in the applied properties so the state
                # must swith to INCOMPLETE.
                self.state = State.INCOMPLETE
                self.pending_tree = False
                if self.pending_tree is not None:
                    # A new syntax tree is ready to apply.
                    self.rerun_scheduled = True
                    vpe.call_soon(self.start, None)
            else:
                if self.tree_data.affected_lines is None:
                    # We have completed a full property update so must be in
                    # complete state.
                    self.state = State.COMPLETE

    def _do_add_props(self) -> bool:
        """Add properties to a number of lines.

        :return: True if all properties have been added.
        """
        start_time = time.time()
        now = start_time
        while True:
            self._walk_a_top_level_element(
                self.cursor, self.tree_data.affected_lines)
            if self.prop_data.flush_required:
                self._flush_props()
            if not self.cursor.goto_next_sibling():
                break

            now = time.time()
            if now - start_time > 0.05:
                # Operation has timed out and will need to be continued later.
                return False

        # All properties are set/pending.
        self._flush_props()
        now = time.time()
        return True

    def _walk_a_top_level_element(
            self, cursor: TreeCursor, affected_lines: list[range],
            remove_old_props: bool = True,
            prop_adjuster=None,
        ) -> None:
        """Walk a top level syntatic element.

        This is invoked with the tree cursor already on a top-level syntatic
        element node.
        """

        def apply_prop(ts_node: Node, cname: tuple[str, ...]) -> None:
            """Apply a property if a Tree-sitter node matches.

            :ts_node:
                The Tree-sitter node.
            :cname:
                A tuple of the names of all the Tree-sitter nodes visited to
                reach this node, ending in this node's name.
            """
            def find_match(
                    matching_node: MatchNode,
                    cname: CName,
                    index: int,
                    best_match: MatchNode | None = None,
                ) -> tuple[MatchNode | None, int]:
                """Recursively match `cname` against the `matching_node`.

                Recursive calls try to match against possible parents of the
                `matching_node`. The deepest recursive match is considered the
                bests match.

                :matching_node:
                    A node within the syntax highlighting match tree.
                :cname:
                    A sequence of tree-sitter qualified names.
                :index:
                    The index within cname that identifies the tree-sitter
                    node. For the first, non-recursive call, this indexes the
                    last element of `cname`. It is decremented for each level
                    of recursion.
                :best_match:
                    A previous best matching `MatchNode`, provided for
                    recursive calls.
                """
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

            best_match = find_match(self.match_tree, cname, len(cname) - 1)
            if best_match:
                splits = []
                if best_match.embedded_syntax and prop_adjuster is None:
                    splits = self._apply_embedded_syntax(
                        best_match.embedded_syntax, ts_node)
                if splits:
                    for node in splits:
                        self.prop_data.add_prop(
                            best_match.prop_name, node, prop_adjuster)
                else:
                    self.prop_data.add_prop(
                        best_match.prop_name, ts_node, prop_adjuster)

        def process(ts_node, cname):
            """Recursively process a Tree-sitter node and its decendants."""
            apply_prop(ts_node, cname)
            if not cursor.goto_first_child():
                return

            while True:
                ts_node = cursor.node
                process(
                    ts_node, cname + ((cursor.field_name, ts_node.type),))
                if not cursor.goto_next_sibling():
                    cursor.goto_parent()
                    return

        # Check whether top level node intersects with any of the affected line
        # ranges. Do nothing if it does not.
        ts_node = cursor.node
        start_lidx = ts_node.start_point.row
        end_lidx = ts_node.end_point.row + 1
        print("DO TOP", affected_lines is not None)
        if affected_lines is not None:
            for rng in affected_lines:
                if not (rng.stop <= start_lidx or end_lidx <= rng.start):
                    break
            else:
                return

        print("DO TOP intersection found")
        kwargs = {'bufnr': self.buf.number, 'id': 10_042, 'all': 1}
        if remove_old_props:
            vim.prop_remove(
                kwargs, start_lidx + 1, min(end_lidx, len(self.buf)))

        cname = (
            ('', self.root_name),
            (cursor.field_name, cursor.node.type)
        )
        process(ts_node, cname)

    def _walk_all_top_level_elements(
            self, cursor: TreeCursor, prop_adjuster):
        """Walk a top level syntatic element.

        This is invoked with the cursor already on a top-level syntatic element
        node.

        :return:
            True if the last element has been processed.
        """
        while True:
            self._walk_a_top_level_element(
                cursor, None, remove_old_props=False,
                prop_adjuster=prop_adjuster)
            if not cursor.goto_next_sibling():
                break

    def _apply_embedded_syntax(self, lang: str, ts_node: Node) -> list:
        # pylint: disable=too-many-locals
        def prop_adjuster(sl_idx, sc_idx, el_idx, ec_idx):
            sl_idx += node_s_lidx + block.start_lidx
            el_idx += node_s_lidx + block.start_lidx

            # TODO: These need to handle codepoint size.
            sc_idx += block.indent
            ec_idx += block.indent

            return sl_idx, sc_idx, el_idx, ec_idx

        def split_node(node, a, b):
            if node is None:
                return None, None
            if node.start_point.row >= a:
                before_node = None
            else:
                nsp = node.start_point
                nep = Point(a, 0)
                before_node = PseudoNode(nsp, nep, ts_node.type)
            if node.end_point.row <= b:
                after_node = None
            else:
                nep = node.end_point
                nsp = Point(b, 0)
                after_node = PseudoNode(nsp, nep, ts_node.type)
            return before_node, after_node

        main_lang = self.buf.options.filetype
        em_highlighter = embedded_syntax_handlers.get((main_lang, lang))
        if em_highlighter is None:
            return []

        node_s_lidx = ts_node.start_point[0]
        e_lidx = ts_node.end_point[0]
        blocks = em_highlighter.find_embedded_code(
            self.buf[node_s_lidx: e_lidx])
        if not blocks:
            return []

        splits = []
        for block in blocks:
            a = node_s_lidx + block.start_lidx
            b = a + block.line_count
            pre_node, ts_node = split_node(ts_node, a, b)
            if pre_node is not None:
                splits.append(pre_node)

            code_lines = self.buf[a:b]
            code_lines = [line[block.indent:] for line in code_lines]
            code_bytes = '\n'.join(code_lines).encode('utf-8')
            tree = em_highlighter.parser.parse(code_bytes, encoding='utf-8')
            print(f'Parsed to tree {tree.root_node}')
            cursor = tree.walk()
            self._walk_all_top_level_elements(cursor, prop_adjuster)

        if ts_node is not None:
            splits.append(ts_node)
        print("SPLITS", splits)
        return splits

    def _flush_props(self) -> None:
        kwargs = {'bufnr': self.buf.number, 'id': 10_042}
        for prop_name, locations in self.prop_data.props_to_add.items():
            kwargs['type'] = prop_name
            with vpe.suppress_vim_invocation_errors:
                # The buffer may have changed, making some property line and
                # column offsets invalid. Hence suppression of errors.
                vim.prop_add_list(kwargs, locations)
            self.prop_data.prop_set_count += 1
        self.prop_data.reset_buffer()


class Highlighter:
    """An object that maintains syntax highlighting for a buffer."""

    def __init__(self, buf: vpe.Buffer, listener: Listener):
        self.buf = buf
        self.listener = listener
        self.prop_set_operation = InprogressPropsetOperation(
            buf, listener)
        self.listener.add_parse_complete_callback(self.handle_tree_change)

    def handle_tree_change(
            self, code: ConditionCode, affected_lines: AffectedLines) -> None:
        """Take action when the buffer's code tree has changed."""
        self.prop_set_operation.handle_tree_change(code, affected_lines)


@dataclass
class NestedCodeBlockSpec:
    """Details about a nested code block.

    @start_lidx:
        The index of the first line of code, with respect to the containing
        Tree-sitter node.
    @line_count:
        The number of lines of code in the code block.
    @indent:
        The number of characters by which the code is indented. This number of
        characters is removed from each line before the code is processed.
    """
    start_lidx: int
    line_count: int
    indent: int


class EmbeddedHighlighter:
    """Base class for user supplied embedded highlighters."""

    def __init__(self, lang: str):
        # TODO:
        #   Make this a lazy property so that the Tree-sitter parser is
        #   not unconditionally imported.
        self.parser = parsers.provide_parser(lang)

    def find_embedded_code(
            self, lines: list[str]) -> list[NestedCodeBlockSpec]:
        """Find all blocks of embedded code.

        This must be overridden in a user supplied subclass.

        :return:
            A list of embedded code blocks. Each block is a list of line
            sections, where each section is a tuple of line_index, start_column
            and end_column. The start and end columns for a Python range. Each
            start column should be set to trim off any unwanted indentation.
        """
