"""Exception classes for commands.utils and commands.template.

Defined here to avoid circular dependency hell.
"""


class NoSuchCommandError(ValueError):
    pass


class ArgumentCountError(TypeError):
    pass
