Some notes on performance
=========================

New performance notes
---------------------

Despite being designed for very fast parsing, Tree-Sitter can take longer than
is comfortable for tasks such as dynamic syntax highlighting. The `Old
performance notes` section below shows a publicly discussed case.

However, I have since learnt a number of techniques, such as using
Tree-Sitter's timeout mechanism to iteratively parse difficult source files.


Old performance notes
---------------------

Vim enhancement request #9087 mentions a 2 MB C file that causes terrible lag
(seconds per keystroke) using the Tree-Sitter plug-in. Another comment claims
that Tree-Sitter took over a second to parse a 4MB file. The 2MB file is
referenced, so I was able to try it out.

The file is a big list of '#defines' and about 33,000 lines long. The results
for how long parsing took were:

    Full parse in 0.053 s
    Incr parse in 0.018 s

The incremental parse it not saving a lot, but shows repsonsive per-keystroke
updates are potentially possible. The time taken to set properies for syntax
highlighting were:

    Full parse = 1.50156 s
    Incr parse = 0.31547 s

Those values include the parsing time. These values make the inital load time
very noticable and per-keystroke updates annoyingly clunky, but porbably
tolerable were I making a few small changes to such a file.

Source code file of this size are somewhat extreme and, in situations where
such extreme files are justified, unlikely to be subject to more than very
occasional manual editing.
