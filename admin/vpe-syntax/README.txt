                      Welcome to VPE-Syntax for Vim

This is a minimal download that provides a Python script to install VPE-Syntax.
The script attempts to automate the most of the instructions provided in the
README at:

    https://github.com/paul-ollis/vpe_syntax

and also to automate setting up the dependencies; in particular VPE. I cannot
guarantee that the script will work reliably, especially on Windows. So you may
need to falback to a manual installation. However, I would be pleased to receive
problem reports at:

    https://github.com/paul-ollis/vpe_syntax/issues

so that I can fix any issues.

The install script is "install.py". The "inst-vpe.vim" script used by
"install.py".

NOTE: You must be in the same directory as this README to run the script.

The install script has help.

    python install.py -h

    usage: Install VPE-Syntax and dependencies. [-h] [--make-vim-dir] [--add-languages] [--vim-path VIM_PATH]

    options:
      -h, --help           show this help message and exit
      --make-vim-dir       Create Vim config directory if required.
      --add-languages      Install C and Python language parsers.
      --vim-path VIM_PATH  Specify the Vim program's path.

You will probably want to install some language parsers, so most people should
try running:

    python install.py --add-languages

The script may encounter fixable issues, such as not being able to find and run
your installed Vim program. It will try to provide a useful error message and
suggest which option might fix the problem.
