.. _highlight groups:

===========================
VPE-Syntax highlight groups
===========================

Traditional Vim syntax highlighting schemes use a fairly small set of
"standard" group names that are used in the various available colour schemes.
The set of groups is:

  | Comment
  | Constant String Character Number Boolean Float
  | Identifier Function
  | Statement Conditional Repeat Label Operator Keyword Exception
  | PreProc Include Define Macro PreCondit
  | Type StorageClass Structure Typedef
  | Special SpecialChar Tag Delimiter SpecialComment Debug

VPE-Syntax borrows from NeoVim's approach, by defining a much larger extended
set of of "standard" names. These are intended to be used in VPE-Syntax
language configuration files along with the groups listed above. This allows
you to define your own colour scheme using the extended set of groups in order
to provide more detailed and more colourful highlighting. Without an extended
colour scheme, you will probably get more detailed highlighting, but without an
extended colour pallette.

By default (*i.e.* in the absence of an extended colour scheme) all the
additional highlight groups link to one of the above groups. The full set of
extended groups is: shown below. Most of the names come from `NeoVim's set of
names`_.

.. list-table:: Extended highligh group set
   :header-rows: 1

   * - Extended group name
     - Links to
     - Used for
   * - Argument
     - Identifier
     - an argument passed to a function or method
   * - Attribute
     - Identifier
     - attribute annotations (e.g. Python decorators, Rust lifetimes)
   * - AttributeBuiltin
     - Keyword
     - builtin annotations (e.g. @property in Python)
   * - CalledFunction
     - Identifier
     - the name part for a function invocation
   * - CalledMethod
     - Identifier
     - the name part for a method invocation
   * - CharacterSpecial
     - SpecialChar
     - special characters (e.g. wildcards)
   * - Class
     - Keyword
     - the keyword introducing a class definition
   * - ClassName
     - Identifier
     - the name os a class
   * - CommentDocumentation
     - Comment
     - comments documenting code
   * - CommentError
     - Todo
     - error-type comments (e.g. ERROR, FIXME, DEPRECATED)
   * - CommentNote
     - Todo
     - note-type comments (e.g. NOTE, INFO, XXX)
   * - CommentTodo
     - Todo
     - todo-type comments (e.g. TODO, WIP)
   * - CommentWarning
     - Todo
     - warning-type comments (e.g. WARNING, FIX, HACK)
   * - ConstantBuiltin
     - Constant
     - built-in constant values
   * - ConstantMacro
     - Constant
     - constants defined by the preprocessor
   * - Constructor
     - Normal
     - constructor calls and definitions
   * - Decorator
     - Identifier
     - a function, method, class, *etc* decorator
   * - DefinitionStarter
     - Identifier
     - the keyword starting a definition (*e.g.* 'def')
   * - DiffDelta
     - DiffChange
     - changed text (for diff files)
   * - DiffMinus
     - DiffDelete
     - deleted text (for diff files)
   * - DiffPlus
     - DiffAdd
     - added text (for diff files)
   * - FunctionBuiltin
     - Function
     - built-in functions
   * - FunctionCall
     - Normal
     - function calls
   * - FunctionDef
     - Keyword
     - the keyword introducing a function definition
   * - FunctionMacro
     - Macro
     - preprocessor macros
   * - FunctionMethodCall
     - Normal
     - method calls
   * - FunctionMethod
     - Normal
     - method definitions
   * - FunctionName
     - Identifier
     - the name of a function
   * - GenericType
     - Type
     - the name of a generic type
   * - ImportedAliasedName
     - Normal
     - an name imported using an alias
   * - ImportedName
     - Normal
     - a simple imported name
   * - Import
     - Include
     - keywords use in an import
   * - Interpolation
     - String
     - a string used for interpoation
   * - KeywordConditional
     - Keyword
     - keywords related to conditionals (e.g. if, else)
   * - KeywordConditionalTernary
     - KeyWord
     - ternary operator (e.g. ?, :)
   * - KeywordCoroutine
     - KeyWord
     - keywords related to coroutines (e.g. go in Go, async/await in Python)
   * - KeywordDebug
     - KeyWord
     - keywords related to debugging
   * - KeywordDirective
     - KeyWord
     - various preprocessor directives and shebangs
   * - KeywordDirectiveDefine
     - KeyWord
     - preprocessor definition directives
   * - KeywordException
     - KeyWord
     - keywords related to exceptions (e.g. throw, catch)
   * - KeywordFunction
     - KeyWord
     - keywords that define a function (e.g. func in Go, def in Python)
   * - KeywordImport
     - KeyWord
     - keywords for including or exporting modules (e.g. import, from in Python)
   * - KeywordModifier
     - KeyWord
     - keywords modifying other constructs (e.g. const, static, public)
   * - KeywordOperator
     - KeyWord
     - operators that are English words (e.g. and, or)
   * - KeywordRepeat
     - KeyWord
     - keywords related to loops (e.g. for, while)
   * - KeywordReturn
     - KeyWord
     - keywords like return and yield
   * - KeywordType
     - KeyWord
     - keywords describing namespaces and composite types (e.g. struct, enum)
   * - MarkupHeading1
     - Underlined
     - top-level heading
   * - MarkupHeading2
     - Underlined
     - section heading
   * - MarkupHeading3
     - Underlined
     - subsection heading
   * - MarkupHeading4
     - Underlined
     - and so on
   * - MarkupHeading5
     - Underlined
     - and so forth
   * - MarkupHeading6
     - Underlined
     - six levels ought to be enough for anybody
   * - MarkupHeading
     - Underlined
     - headings, titles (including markers)
   * - MarkupItalic
     - Normal
     - italic text
   * - MarkupLinkLabel
     - Normal
     - link, reference descriptions
   * - MarkupLink
     - Normal
     - text references, footnotes, citations, etc.
   * - MarkupLinkUrl
     - Underlined
     - URL-style links
   * - MarkupListChecked
     - Normal
     - checked todo-style list markers
   * - MarkupList
     - Normal
     - list markers
   * - MarkupListUnchecked
     - Normal
     - unchecked todo-style list markers
   * - MarkupMath
     - Normal
     - math environments (e.g. $ ... $ in LaTeX)
   * - MarkupQuote
     - Normal
     - block quotes
   * - MarkupRawBlock
     - Normal
     - literal or verbatim text as a stand-alone block
   * - MarkupRaw
     - Normal
     - literal or verbatim text (e.g. inline code)
   * - MarkupStrikethrough
     - Normal
     - struck-through text
   * - MarkupStrong
     - Normal
     - bold text
   * - MarkupUnderline
     - Underlined
     - underlined text (only for literal underline markup!)
   * - MethodCall
     - Normal
     - the name of a method being invoked
   * - MethodDef
     - Keyword
     - the keyword introducing a method definition
   * - MethodName
     - Identifier
     - the name of a method
   * - Module
     - Identifier
     - modules or namespaces
   * - ModuleBuiltin
     - Keyword
     - built-in modules or namespaces
   * - None
     - Special
     - keywork "None", "nil", *etc*.
   * - NonStandardSelf
     - Normal
     - a name that would normall be "selfW, "this", *etc.*
   * - NumberFloat
     - Float
     - floating-point number literals
   * - Parameter
     - Normal
     - a parameter in function or method defnition
   * - Property
     - String
     - the key in key/value pairs
   * - PunctuationBracket
     - Normal
     - brackets (e.g. (), {}, [])
   * - PunctuationDelimiter
     - Normal
     - delimiters (e.g. ;, ., ,)
   * - PunctuationSpecial
     - Normal
     - special symbols (e.g. {} in string interpolation)
   * - Return
     - Keyword
     - the "return" or equivalent keyword
   * - Self
     - Normal
     - for "self", "this", *etc.*
   * - SpecialPunctuation
     - Normal
     - for punctuation with unusual or special meaning
   * - StandardConst
     - Identifier
     - a constant that is predefined for the language
   * - StringDocumentation
     - Comment
     - string documenting code (e.g. Python docstrings)
   * - StringEscape
     - String
     - escape sequences
   * - StringRegexp
     - String
     - regular expressions
   * - StringSpecial
     - String
     - other special strings (e.g. dates)
   * - StringSpecialPath
     - String
     - filenames
   * - StringSpecialSymbol
     - String
     - symbols or atoms
   * - StringSpecialUrl
     - Underlines
     - URIs (e.g. hyperlinks)
   * - SyntaxError
     - WarningMsg
     - used to highlight syntax parsing errors
   * - TagAttribute
     - Normal
     - XML-style tag attributes
   * - TagBuiltin
     - Normal
     - builtin tag names (e.g. HTML5 tags)
   * - TagDelimiter
     - Normal
     - XML-style tag delimiters
   * - TypeBracket
     - Normal
     - bracket, brace or parenthesis used in a type definition
   * - TypeBuiltin
     - Keyword
     - built-in types
   * - TypeDefinition
     - Type
     - identifiers in type definitions (e.g. typedef <type> <identifier> in C)
   * - TypeParameter
     - Type
     - a parameter uses in a type definition
   * - Variable
     - Identifier
     - various variable names
   * - VariableBuiltin
     - Keyword
     - built-in variable names (e.g. this, self)
   * - VariableMember
     - Identifier
     - object and struct fields
   * - VariableParameterBuiltin
     - Identifier
     - special parameters (e.g. _, it)
   * - VariableParameter
     - Keyword
     - parameters of a function


.. _NeoVim's set of names:
    https://neovim.io/doc/user/treesitter.html#treesitter-highlight-groups


.. vim: nospell
