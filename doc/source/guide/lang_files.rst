============================
Language configuration files
============================

Naming and location
===================

Each supported language requires a configuration file that defines how to
process the Tree-sitter syntax tree provided by VPE-Sitter. The most important
(and currently only) function is to define how to add syntax highlighting.
Hence the files have a ``.syn`` extension. For example the configuration file
for Python is called 'python.syn'.

Files are searched for in 2 places:

1. Under the installation directory of VPE-Syntax. The following command will
   display its name.

   .. code-block:: vim

       Synsit confdir

2. In your Vim configuration directory tree in the sub-directory
   ``plugin/vpe_syntax``. Use this command to display the full directory name.

   .. code-block:: vim

       Synsit confdir --user

Settings in the user configuration file, if it exists, override matching
settings in the installation configuration file.


Syntax trees
============

In order to understand the language configuration files, it is necessary to
understand the Tree-sitter syntax trees used by VPE-Syntax. Let us start with a
very short Python module:

.. code-block:: python
    :linenos:

    """Module docstring."""

    WIDTH = 30

    class LevelStore:
        """Source of the levels."""
        def retrieve_content(self, level: int) -> list[str]:
            """The text for this level."""
            return [line.replace('@', 'X')
                for line in text.decode('utf-8').splitlines()]

If you are editing this file and have enabled VPE-Syntax for the buffer then
you can display the Tree-sitter tree using the command:

.. code-block:: vim

    Treesit log tree --all

Which produces a tree representation of over 90 lines in the VPE log! The whole
tree is typically not easy to use, so instead we can get a subset for a given
line using the command:

.. code-block:: vim

    Treesit log tree --start <lnum>

Or by placing the cursor on a line and doing:

.. code-block:: vim

    Treesit log tree --ranges

For the third line, the tree produced is::

    module (0, 0)->(9, 58)
      expression_statement (2, 0)->(2, 10)
        assignment (2, 0)->(2, 10)
          left:identifier (2, 0)->(2, 5)
          = (2, 6)->(2, 7)
          right:integer (2, 8)->(2, 10)

All the syntactic elements for line 3 (index 2) are displayed along with
ancestor elements up to the top ``module`` element. The output is fairly easy
to interpret.

- The numbers in parentheses are row and byte indices. For example the ``(0,
  0)->(7, 58)`` after ``module`` means that the entire module starts at line
  zero, byte zero and ends at line 7, byte 58 (note that 58 is the index just
  after the last byte).

- The syntactic elements are known as "nodes" are and consist of two parts:

  1. A name. Examples from a above are "module", "identifier" and "=".

  2. A field name prefix - "left" and "right" above.

For our discussion, the ranges of the above tree are not of much interest, so
this discussion normally omits them provide cleaner partial trees.::

    module
      expression_statement
        assignment
          left:identifier
          =
          right:integer


Configuration files
===================

The job of a configuration file is to map parts of the syntax tree to Vim
highlight group names. It has fairly simply formatting rules.

A configuration file has a fairly simple format.

1. Lines that start with a '#' followed by a space are comments.
2. Blank lines are ignored and optional.
3. All other lines provide tree-match rules.

A tree-match rule consists of one or more lines that form tree structures,
which is very similar to a portion of the syntax tree of the language. For
example::

    yield
        yield                          Keyword

    module
        expression_statement
            string                     StringDocumentation

The indentation used to form the tree structure **must** use increasing blocks
of four spaces for each level. The words on the right are Vim highlight groups
to be used for matching syntax tree nodes. It is not necessary to align the
right hand side as shown above, but it is highly recommended.

A tree-match rule may consist of a single node. The following rule causes any
identifier node (with or without a field name prefix) to be highlighted using
the "Identifier" group, unless a more specific match is found - see later. So
the ``left:identifier`` above would be matched by the rule.
::

    identifier                         Identifier

The algorithm that maps tree nodes to highlight groups chooses the most
specific match. Basically "longest match wins". Here is the example Python
module again.

.. code-block:: python
    :linenos:

    """Module docstring."""

    WIDTH = 30

    class LevelStore:
        """Source of the levels."""
        def retrieve_content(self, level: int) -> list[str]:
            """The text for this level."""
            return [line.replace('@', 'X')
                for line in text.decode('utf-8').splitlines()]

The partial tree for for the docstring on line 1 is:

.. code-block::
    :linenos:

    module (0, 0)->(9, 58)
     expression_statement (0, 0)->(0, 23)
       string (0, 0)->(0, 23)
         string_start (0, 0)->(0, 3)
         string_content (0, 3)->(0, 20)
         string_end (0, 20)->(0, 23)

The relevant tree-match rules from the supplied configuration are::

    string                             String

    module
        expression_statement
            string                     StringDocumentation

The first rule will match the ``string`` node on line 3, but the second rule
matches the parent-child sequence ``module -> expression_statement -> string``,
which is 3 nodes long. So the string on line 1 is highlighted using the
"StringDocumentation" group.

A tree-match rule can appear quite complex. This is one of the longest in the
supplied Python rule set.::

    class_definition
        class                          Class
        name:identifier                ClassName
        block
            expression_statement
                string                 StringDocumentation
            function_definition
                def                    MethodDef
            function_definition
                identifier             MethodName

However, it is actually just a more compact way of representing multiple rules
within one tree structure. The above could be split up as::

    class_definition
        class                          Class

    class_definition
        name:identifier                ClassName

    class_definition
        block
            expression_statement
                string                 StringDocumentation

    class_definition
        block
            function_definition
                def                    MethodDef

    class_definition
        block
            function_definition
                identifier             MethodName

The second forms can be thought of as 'pure' rules, where each node has only a
single child.


Field name prefix
-----------------

When a field name prefix appears in the Tree-sitter tree it can be used in a
tree-match rule as a way of making the rule more specific. For example the
``class_definition`` compound rule above uses ``name:identifier`` rather than
just ``name``. In general, rules that include field name prefixes are preferred
over those that do not.

.. vim: nospell
