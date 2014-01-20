from qutebrowser.commands.utils import Command

"""All command classes. These are automatically propagated from commands.utils
via inspect.

A command class can set the following properties:

    nargs -- Number of arguments. Either a number, '?' (0 or 1), '+' (1 or
    more), or '*' (any). Default: 0

    name -- The name of the command, or a list of aliases

    split_args -- If arguments should be split or not. Default: True

    count -- If the command supports a count. Default: False
"""


class Open(Command):
    nargs = 1
    split_args = False

class TabOpen(Command):
    nargs = 1
    split_args = False

class TabClose(Command):
    nargs = 0

class TabNext(Command):
    nargs = 0

class TabPrev(Command):
    nargs = 0

class Quit(Command):
    name = ['quit', 'q']
    nargs = 0

class Reload(Command):
    nargs = 0

class Stop(Command):
    nargs = 0

class Back(Command):
    nargs = 0

class Forward(Command):
    nargs = 0

class Print(Command):
    nargs = 0

class Scroll(Command):
    nargs = 2
    count = True

class Undo(Command):
    nargs = 0

class ScrollStart(Command):
    nargs = 0

class ScrollEnd(Command):
    nargs = 0

class PyEval(Command):
    nargs = 1
    split_args = False
