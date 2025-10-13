===========
Match trees
===========

VPE-Syntax does not use `Tree-sitter queries`_ as the mechanism to identify which
parts of a source file to highlight. Instead it walks the parse tree and
performs matching against another tree, which is called a "match tree".

There is a match tree for each supported language, which is built from one or
more relatively simple configuration files - typically one main file and an
optional second user supplied file, which can extend or override the main file.


Example tree and match configuration
====================================

The relationship between a Tree-sitter parse tree and the match tree is best
introduced using a small example. Here is a very trivial Python file:

.. code-block:: python

    class MyClass:
        """The docstring."""

The parse tree produced by Tree-sitter can be logged by VPE-Sitter code and
looks like::

    module (0, 0)->(1, 24)
      class_definition (0, 0)->(1, 24)
        class (0, 0)->(0, 5)
        name:identifier (0, 6)->(0, 13)
        : (0, 13)->(0, 14)
        body:block (1, 4)->(1, 24)
          expression_statement (1, 4)->(1, 24)
            string (1, 4)->(1, 24)
              string_start (1, 4)->(1, 7)
              string_content (1, 7)->(1, 21)
              string_end (1, 21)->(1, 24)

The Python match configuration highlights the class keyword, the class's name
and its docstring. The part of the configuration that does this is::

    class_definition
        class                          Class
        name:identifier                ClassName
        block
            expression_statement
                string                 DocString

The configuration mirrors those parts of the parse tree that are of interest.
The indentation defines the tree structure and is therefore required.

The configuration is straightforward to interpret. For example:

1. If a class node is the child of a class_definition node, highlight using the
   ``Class`` highlight group.

2. If a string node is the child of an expression_statement, which is a child of
   a block, which is the child of a class_definition then highlight the string
   using ``DocString``.

Some parse tree nodes are qualified with a field name prefix. In the above tree
the block is prefixed with the field name "body"; *i.e.* "body:block". Field
name prefixes are optional in the match tree configuration. In the above example
the "body:block" is matched by the unqualified "block".


Internal representation
=======================

The match tree is built from `MatchNode` instances. A `MatchNode` has the form:

.. code-block:: python

    @dataclass
    class MatchNode:
        prop_name: str = ''
        choices: dict[ChoiceKey, MatchNode] = field(default_factory=dict)

The ``prop_name`` attributes is the, well, the name of the property (also the name of the
highlight) applied when a `MatchNode`, well, matches.

The ``choices`` attribute is ...

This is a representation of the part of the internal match tree for the current
example configuration::

     R:  name=''
     a:    name='class'
     b:      name='class_definition'         node.prop_name='Class'
     c:    name=('name', 'identifier')
     d:      name='class_definition'         node.prop_name='ClassName'
     e:    name='string'                     node.prop_name='String'
     f:      name='expression_statement'
     g:        name='block'
     h:            name='class_definition'   node.prop_name='DocString'

A comparison with the configuration above reveals that the internal tree is a
kind of inverted form of the configuration. The root node (R) is used as the
starting point for each matching operation. In the above example the root
`MatchNode`'s choices dictionary has entries for "class", "class_definition" and
"string".

The following is a rough description
of how this is used to apply syntax highlighting. The above syntax tree is
reproduced below, with each node numbered for ease of reference.::

    1:  module (0, 0)->(1, 24)
    2:    class_definition (0, 0)->(1, 24)
    3:      class (0, 0)->(0, 5)
    4:      name:identifier (0, 6)->(0, 13)
    5:      : (0, 13)->(0, 14)
    6:      body:block (1, 4)->(1, 24)
    7:        expression_statement (1, 4)->(1, 24)
    8:          string (1, 4)->(1, 24)
    9:            string_start (1, 4)->(1, 7)
    10:           string_content (1, 7)->(1, 21)
    11:           string_end (1, 21)->(1, 24)

The tree is walked depth first. For each visited node, its name is lookup up in
the ``choices`` or the match tree's root (R). If not found then the walk
continues otherwise node in the match tree is tested to see if a highlight
should be applied. The first Tree sitter node that matches is 3
(class) and this matches (a).

The (a) node has a single choice (class_definition, (b)), which is the node name
of the parent of node (3), so this is a potential match. Matching then proceeds
with (b), which has property name "Class", which is stored as a candidate
highlight name. Node (b) has no choices, so matching stops and the candidate
highlight is applied, using the tree node 3 that started the matching process;
i.e. covering (0, 0) -> (0, 5) (line 1, characters 1 to 5 inclusive).

Syntax tree walking continues until node 4, which matches root choice(c), which
is then used to perform the same matching algorithm.

The final node that matches the root choices is 8, matching (e). This has
a property name 'String', which is stored as a candidate highlight. Node (e) has
choice "expression_statement" (f), which matches node 8's parent 7.
Node (f) has choice ""block" (g), which matches node 7's parent (6).
Node (g) has choice ""class_definition" (h), which matches node 6's parent (2).
This has prop_name "DocString", which replaces the "String" candidate stored
earlier. There are no more candidates, so DocString is used to highlight the
extent of node 8 (1, 4) -> (1, 24).

Matching attempts only occur for Tree-sitter nodes that appear in the choices of
the root of the match tree. The general rules applied for a match are:

1. The longest match wins. In the above example a "DocString" wins over a simple
   String because more ancestors in the tree contribute to the match.

2. If a `MatchNode` choice includes a qualifying field name, it is chosen in
   preference to one without; *e.g.* "body:block" is chosen in preference to
   "block".


.. _Tree-sitter queries:
    https://tree-sitter.github.io/tree-sitter/using-parsers/queries/index.html
