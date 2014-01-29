"""Exception classes for commands.utils and commands.template.

Defined here to avoid circular dependency hell.
"""


class NoSuchCommandError(ValueError):
    """Raised when a command wasn't found."""
    pass


class ArgumentCountError(TypeError):
    """Raised when a command was called with an invalid count of arguments."""
    pass
