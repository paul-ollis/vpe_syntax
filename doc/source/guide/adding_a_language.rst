=================
Adding a language
=================

This is a first stab at a tutorial on adding a new language. First we
demonstrate installing a Tree-sitter parser library for JSON then for the rest
of the tutorial the Snake programming language is used.


Installing a parser
===================

You need a language for which a Tree-sitter parse with Python language bindings
exists. For JSON there is the "tree-sitter-json" package. Within Vim you can run:

.. code-block:: vim

    Treesit hint install tree-sitter-json

This will display a ``pip`` command that should be suitable for installing
the package, taking any virtual environment into account.

After installation the following should work, within Vim.

.. code-block:: vim

    py3 import tree_sitter_json

JSON is not very demanding in terms of providing syntax highlighting so for the
rest of the tutorial we switch to Snake.


Make Snake supported by VPE-Sitter
==================================

The Snake programming language we are interested in just happens to look
remarkably similar to Python [#]_. In fact it is so similar that we can use
the tree-sitter-python library to perform the parsing.

We need the VPE-Sitter to recognise Snake as a supported language. This simply
involves a small amount of editing of a ``languages.conf`` file in the
subdirectory ``plugin/vpe_sitter`` within your Vim configuration directory. The
command:

.. code-block:: vim

    Treesit openconfig

will open this file for you and create the directory if necessary. It will
also provide template content if the file does not already exist. The line
required for this example is::

    snake tree_sitter_python

The following command will list all the configured languages. The ``--log``
option will write the output to the VPE log.

.. code-block:: vim

    Treesit [--log] info languages

which will output something like::

     Languages configured:
        c
        python
        snake (user provided)
     Note: Support depends on correctly installed Tree-sitter code.

     Any user configured languages are defined in:
         /home/paul/.config/vim/plugin/vpe_sitter/languages.conf


Create a language configuration
===============================

Getting set up
--------------

You will need:

1. Some example code, which you should open in Vim.

2. A ``snake.syn`` file in your ``plugin/vpe_syntax`` directory (the
   ``syn-file``).

3. The list of highlight groups that VPE-Syntax makes available.

4. The VPE log open in a window.

For this tutorial we will use ``example.snk``.

.. code-block:: python
    :linenos:

    """Module docstring."""

    import inspect
    from typing import TypeAlias

    MIN_HEIGHT: Final[int] = 40            # Height of game display.
    PropertySpec: TypeAlias = [int, int]

    # Mapping from character to highlight group.
    lookup_table = {
        'X': 'String',
        42: 'Number',
    }

    def hello_world() -> int:
        """Greet the globe upon which we live."""
        print('Hello, Wordl!')
        return 42

    class LevelStore:
        """Source of the levels."""
        def __init__(self):
            self.the_answer = 42.0

Edit this file. It will most likely display without any syntax highlighting
because the ``.snk`` extension is not recognised by Vim. You will need to set the
``filetype`` option; use the ``setfiletype`` command  - ``setfiletype snake``.

In the same Vim session, use the following commands to start editing the
``snake.syn`` file.

.. code-block:: vim

    split
    Synsit openconfig snake.syn

Will create any necessary directory and provide basic template text. Save the
file because VPE-Syntax will not enable parsing unless it finds a syn-file.

To see the list of VPE-Syntax highlight groups you can run the scheme tweaker.
Make sure the current buffer is your example Snake code and run the command:

.. code-block:: vim

    Synsit tweak

This will split the window horizontally. The top window will display VPE-Syntax's
built-in (experimental) colour scheme editor. The VPE-Syntax "standard" groups
are also listed in the :ref:`highlight groups` section.

Open the VPE log in a window:

.. code-block:: vim

    Vpe log show

You should now have 4 windows which you can arrange as you see fit.

Now start syntax highlighting by making the example code your current window
and running:

.. code-block:: vim

    Synsit on

If everything is working you will see messages in the log that looks like::

    VPE-sitter: Can parse snake
    VPE-sitter:    parser=<tree_sitter.Parser object at 0x7f9d7d7f8f30>
    VPE-sitter:    parser.language=<Language id=140314393664544, version=14>

If there is a problem then, hopefully, error messages will be displayed that
help you figure out the problem. If you find the diagnostics lacking in any way
please raise an issue (https://github.com/paul-ollis/vpe_syntax/issues).


Writing the language (.syn) file
--------------------------------

This is basically a process of displaying partial syntax trees in the VPE log
and using the displayed tree to add rules to the language configuration
(snake.syn) file. Bit by bit you should be able to fairly quickly build up
a useful configuration.

Start with line 6 by placing the cursor on it and entering the command:

.. code-block:: vim

    Treesit log tree

This will write a partial tree that contains all Tree-sitter nodes for line 2,
plus all ancestor nodes::

    module
        expression_statement
            assignment
                left:identifier
                :
                type:type
                    generic_type
                        identifier
                        type_parameter
                            [
                            type
                                identifier
                            ]
                =
                right:integer
        comment

The mapping from the above tree to the Snake code should be fairly obvious, but
sometimes you might find it easier to show line/column range information for
each node by using ``Treesit log tree --ranges``.

The above tree contains several Tree-sitter nodes of immediate interest -
left:identifier, identifier type_parameter and comment. Let's add simple entries
for each. Update the syn-file to look like::

    # Tree structure                   Property name
    identifier                         Identifier
    comment                            Comment
    type                               Type

The two column layout is a (strongly) recommended convention. Note that there
is no rule for ``left:identifier``. The ``identifier`` rule will match
``left:identifier`` as well as any plain ``identifier``. The ``left:`` part is
called a "field name prefix" (or just "prefix") and it can be included in rules
for more precise matching, as will be shown later.

To see the result go to the example code window and execute the commands:

.. code-block:: vim

    Synsit rebuild
    edit             " Reloading triggers a reparse of the buffer.

The exact appearance will depend on your colour scheme, but you should now see
the comments and identifiers highlighted. Next we can examine line 11, which
has the tree::

    module
        expression_statement
            assignment
                right:dictionary
                    pair
                        key:string
                            string_start
                            string_content
                            string_end
                        :
                        value:string
                            string_start
                            string_content
                            string_end
                    ,

This has two ``string`` nodes, one with a ``key`` prefix and one with a
``value`` prefix. Add these as ``key:string`` and ``string`` so the syn-file
now reads::

    # Tree structure                   Property name
    identifier                         Identifier
    comment                            Comment
    type                               Type
    string                             String
    key:string                         Property

.. sidebar:: Why not query files

    If you have some familiarity with Tree-sitter, you might be wondering why
    VPE-Syntax does not use Tree-sitter query (SCM). The short answer is that,
    after experimentation, I decided it was a faster and nicer solution. But
    it may turn out to be a mistake.

    I would be happy to receive advice on this area.
    https://github.com/paul-ollis/vpe_syntax/discussions/5

and do ``Synsit rebuild | edit`` to see the results. Unless you have already
created an extended colour scheme, you will now see all strings highlighted
identically. However, the 'X' on line 11 uses the ``Property`` highlight rather
than ``String``. By default, VPE-Syntax links ``Property`` to string, so the
'X' looks like other strings.

As a diversion may now wish to experiment with the scheme tweaker to make the
keys distinguishable from string value. Go to the scheme tweaker's window, find
the ``Property`` group and hit ``<Enter>``. Press 'K' to break the link to the
``String`` group and then experiment with changing the colour. If you wish, you
can copy all or the modified the highlight commands into a personal colour
scheme file (``:help colorscheme`` for details).

So far, all of the rules we have added are very simple - node name, highlight
group name. I prefer my Snake docstrings to look more like comments than
strings. So let's make it so. First line 1, with the tree::

    module
        expression_statement
            string
                string_start
                string_content
                string_end

We need a rule that is more specific for this. In this case we can do this::

    # Tree structure                   Property name
    identifier                         Identifier
    comment                            Comment
    type                               Type
    string                             String
    key:string                         Property

    module
        expression_statement
            string                     StringDocumentation

We have now added a rule that means:

    If a ``module`` contains an ``expression_statement`` which in turn contains
    a ``string`` then highlight the ``string`` using the ``StringDocumentation``
    property.

The basic rule for applying syn-file rules is "longest matchinf rule wins". The
new rule involves 3 nodes and so trumps the simpler, single node rule for
strings.

The blank line before the rule is not required, but the indentation used is
mandatory and must use multiples of 4 spaces. The output from ``Treesit log
tree`` uses 4 spaces, so you can cut and paste from the VPE log. Once you start
adding 'tree-style' rules like this, the two column layout convention makes
your syn-file easier to read.

With this change in place, the module docstring will be highlighted like a comment
because the ``StringDocumentation`` highlight group links to the ``Comment`` group.
Once again, you may want to edit your colour scheme to make docstrings look
slightly (or very) different to comments.


Docstrings for functions and classes require additional rules. Here they are::

    class_definition
        block
            expression_statement
                string                 StringDocumentation

    function_definition
        block
            expression_statement
                string                 StringDocumentation

By now the syntax highlighting of your Snake code should be looking quite
reasonable, but much more can, of course be done. For a start, we could pick
out the ``def`` keyword on line 15 and we might also want to make function names
standout. The tree logged for line 15 is::

    module
        function_definition
            def
            name:identifier
            parameters:parameters
                (
                )
            ->
            return_type:type
                identifier
            :

We could add the rule::

    function_definition
        def                            FunctionDef
        name:identifier                FunctionName

but we can also merge this rule with the one we created earlier to get::

    function_definition
        def                            FunctionDef
        name:identifier                FunctionName
        block
            expression_statement
                string                 StringDocumentation

That just about covers the process. Keep logging selected tree snippets, using
them to add match rules. You can view the Python syn-file provided with
VPE-Syntax with the command ``Synsit openconfig --std python.syn``.

You may find some more useful information in ref:`lang files`, but much of it
overlaps with this tutorial.


.. vim: nospell

.. [#] Of course there is at least one real World programming language called Snake.
