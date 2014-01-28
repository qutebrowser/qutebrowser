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
    desc = 'Open a page'

class TabOpen(Command):
    nargs = 1
    split_args = False
    desc = 'Open a page in a new tab'

class TabClose(Command):
    nargs = 0
    desc = 'Close the current tab'
    # FIXME also close [count]th tab

class TabNext(Command):
    nargs = 0
    desc = 'Switch to the next tab'
    # FIXME also support [count]

class TabPrev(Command):
    nargs = 0
    desc = 'Switch to the previous tab'
    # FIXME also support [count]

class Quit(Command):
    name = ['quit', 'q']
    nargs = 0
    desc = 'Quit qutebrowser'

class Reload(Command):
    nargs = 0
    desc = 'Reload the current page'

class Stop(Command):
    nargs = 0
    desc = 'Stop loading the current page'

class Back(Command):
    nargs = 0
    desc = 'Go back one page in the history'
    # FIXME also support [count]

class Forward(Command):
    nargs = 0
    desc = 'Go forward one page in the history'
    # FIXME also support [count]

class Print(Command):
    nargs = 0
    desc = 'Print the current page'

class Scroll(Command):
    nargs = 2
    count = True
    hide = True

class Undo(Command):
    nargs = 0
    desc = 'Undo closing a tab'

class ScrollPercentX(Command):
    nargs = '?'
    count = True
    hide = True

class ScrollPercentY(Command):
    nargs = '?'
    count = True
    hide = True

class PyEval(Command):
    nargs = 1
    split_args = False
    desc = 'Evaluate python code'
