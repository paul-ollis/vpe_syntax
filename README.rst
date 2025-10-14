::

   _    ______  ______    _____             __
  | |  / / __ \/ ____/   / ___/__  ______  / /_____ __  __
  | | / / /_/ / __/      \__ \/ / / / __ \/ __/ __ `/ |/_/  Syntax highlighing
  | |/ / ____/ /___     ___/ / /_/ / / / / /_/ /_/ />  <    using Tree-sitter
  |___/_/   /_____/____/____/\__, /_/ /_/\__/\__,_/_/|_|
                              /____/

Welcome to the Tree-sitter support for Vim.

:status:
    This is version 0.2.0

    This is alpha software, but I use it all the time and it has been behaving
    reliably for me.

    Built in support for Python and C code. The documentation added in version
    0.2 provided guidelines on how to add other languages. Submissions for
    additional languages support gratefully received.


News
====

Version 0.2 significant changes:

- Some initial documentation at https://vpe-syntax.readthedocs.io/en/latest/.
  This is in its very early stages, but does include a tutorial on adding
  languages.

  Any feedback is welcome at https://github.com/paul-ollis/vpe_syntax, either as
  issues or discussions.

- A (hopefully) well defined set of highlight groups (modelled on NeoVim's set).
  This should support suitably rich colour schemes.

  .. image:: https://raw.githubusercontent.com/paul-ollis/vpe_syntax/refs/heads/v0.2/doc/source/_static/added-colour.png

  The right hand side Vim session above is using VPE-Syntax with the colour scheme
  in ``examples/colour_scheme.vim``.

- A functional colour scheme editor is available. Start it with the command::

     Synsit tweak

  https://github.com/user-attachments/assets/52d80562-0ce1-43e4-857e-f7be479cec6c

- This version uses version 0.2 of VPE-Sitter, which has New code to work
  around the way older versions of Vim (before 9.1.1782) buffer changes when
  using the ``listener_add`` function.

  Several days of running with this change suggest that it is stable, providing
  solid syntax highlighting.


Requirements
============

You will need Vim 9.0 or greater and obviously it will have to have been built
with Python 3 support, at least version 3.11.


Limitations
===========

1. No support for selective spell checking.

   Vim's regular expression based syntax highlighting provides a mechanism
   to mark only some parts of a buffer (*e.g.* comments) to be spell checked.
   VPE_Syntax uses text properties to provide highlighting. Text properties
   do not currently provide support for this. I hope to supply a pull request to
   get this added to Vim.

   If possible, release 0.3 will contain a work around.

2. No support for embedded languages. This is planned work.


Installation
============

I have only used this on Linux and Windows.


Linux
~~~~~

As advised for `VPE`_, it is recommended that you use a virtual environment,
hosted within your Vim configuration tree. You may find it useful to read
the `VPE Linux installation`_ instructions for some background. The following
assumes that your Vim configuration directory is $HOME/.vim.

1.  If you do not already have a virtual environment then create one:

    .. code-block:: bash

        # Make sure you are in your $HOME directory
        python -m venv .vim/lib/python


2.  Activate the virtual environment and install vpe_syntax.

    .. code-block:: bash

        # Activate the virtual environment.
        source .vim/lib/python/bin/activate

        # Install VPE.
        python -m pip install vpe_syntax

3.  If you did not already have `VPE`_ installed then you will need to perform
    additional one-off installation of support Vim plugin code. Follow the
    `VPE first installations`_, steps 2 to 4.


Windows
~~~~~~~

A user install is recommended.

1.  Install using the command.

    .. code-block:: bash

        # Install VPE.
        python -m pip install --user vpe_syntax

2.  If you did not already have `VPE`_ installed then you will need to perform
    additional one-off installation of support Vim plugin code. Follow the
    `VPE first installations`_, steps 2 to 4.


Install Tree-sitter parsers
---------------------------

The above steps should install all the direct dependencies of VPE_Syntax, but
you will need to separately install parsers for the languages you wish to
highlight. Assuming you want to use both supported languages then before you
exit the virtual environment do:

    .. code-block:: bash

        python3 -m pip install tree-sitter-python==0.23.6 tree-sitter-c==0.21.4

The Tree-sitter API seems to be somewhat fast moving, so I recommend using the
exact versions given above.

You can then deactivate the virtual environment.

    .. code-block:: bash

        deactivate


Using Vpe_Syntax
================

One everything is correctly installed, you should find that your Vim has gained
a ``Synsit`` command. The important form of this is:

    .. code-block:: vim

        Synsit on

Which will enable Tree-sitter based highlighting in the current buffer, provided
it contains C or Python code. If everything is working you will likely see some
differences in the way your code is coloured, but by an large things will be
quite similar.


.. _Tree-sitter: https://tree-sitter.github.io/tree-sitter/
.. _Vim: https://www.vim.org/
.. _support for Tree-sitter: https://neovim.io/doc/user/treesitter.html
.. _vpe: https://github.com/paul-ollis/vim-vpe
.. _vpe_sitter: https://github.com/paul-ollis/vpe_sitter
.. _the Tree=sitter Tree:
    https://tree-sitter.github.io/py-tree-sitter/classes/tree_sitter.Tree.html

.. _VPE Linux installation:
    https://vim-vpe.readthedocs.io/en/latest/inst_linux.html

.. _VPE first installations:
    https://vim-vpe.readthedocs.io/en/latest/inst_linux.html#for-the-first-ever-installation
