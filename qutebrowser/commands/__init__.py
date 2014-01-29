"""All command classes.

These are automatically propagated from commands.utils
via inspect.

A command class can set the following properties:

    nargs -- Number of arguments. Either a number, '?' (0 or 1), '+' (1 or
    more), or '*' (any). Default: 0

    name -- The name of the command, or a list of aliases.

    split_args -- If arguments should be split or not. Default: True

    count -- If the command supports a count. Default: False

    hide -- If the command should be hidden in tab completion. Default: False

    desc -- Description of the command.
"""

from qutebrowser.commands.template import Command


class Open(Command):
    """Open a page.

    arg: The URL to open.
    """

    nargs = 1
    split_args = False


class TabOpen(Command):
    """Open a page in a new tab.

    arg: The URL to open.
    """

    nargs = 1
    split_args = False


class TabClose(Command):
    """Close the current tab."""
    nargs = 0
    # FIXME also close [count]th tab


class TabNext(Command):
    """Switch to the next tab."""
    nargs = 0
    # FIXME also support [count]


class TabPrev(Command):
    """Switch to the previous tab."""
    nargs = 0
    # FIXME also support [count]


class Quit(Command):
    """Quit qutebrowser."""
    name = ['quit', 'q']
    nargs = 0


class Reload(Command):
    """Reload the current page."""
    nargs = 0


class Stop(Command):
    """Stop loading the current page."""
    nargs = 0


class Back(Command):
    """Go back one page in the history."""
    nargs = 0
    # FIXME also support [count]


class Forward(Command):
    """Go forward one page in the history."""
    nargs = 0
    # FIXME also support [count]


class Print(Command):
    """Print the current page."""
    nargs = 0


class Scroll(Command):
    """Scroll in x/y direction by a number of pixels.

    arg 1: delta x
    arg 2: delta y
    count: multiplicator
    """

    nargs = 2
    count = True
    hide = True


class Undo(Command):
    """Undo closing a tab."""
    nargs = 0


class ScrollPercX(Command):
    """Scroll N percent horizontally.

    optional arg: How many percent to scroll.
    count: How many percent to scroll.
    """

    nargs = '?'
    count = True
    hide = True
    name = 'scroll_perc_x'


class ScrollPercY(Command):
    """Scroll N percent vertically.

    optional arg: How many percent to scroll.
    count: How many percent to scroll.
    """

    nargs = '?'
    count = True
    hide = True
    name = 'scroll_perc_y'


class PyEval(Command):
    """Evaluate python code.

    arg: The python code to evaluate.
    """

    nargs = 1
    split_args = False
