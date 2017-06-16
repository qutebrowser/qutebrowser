# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2017 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# This file is part of qutebrowser.
#
# qutebrowser is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# qutebrowser is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with qutebrowser.  If not, see <http://www.gnu.org/licenses/>.

"""Configuration data for config.py.

Module attributes:

FIRST_COMMENT: The initial comment header to place in the config.
SECTION_DESC: A dictionary with descriptions for sections.
DATA: A global read-only copy of the default config, an OrderedDict of
      sections.
"""

# FIXME:conf reintroduce interpolation?

import sys
import re
import collections

from qutebrowser.config import configtypes
from qutebrowser.utils import usertypes, qtutils, utils

DATA = None


FIRST_COMMENT = r"""
# vim: ft=dosini

# Configfile for qutebrowser.
#
# This configfile is parsed by python's configparser in extended
# interpolation mode. The format is very INI-like, so there are
# categories like [general] with "key = value"-pairs.
#
# Note that you shouldn't add your own comments, as this file is
# regenerated every time the config is saved.
#
# Interpolation looks like  ${value}  or  ${section:value} and will be
# replaced by the respective value.
#
# Some settings will expand environment variables. Note that, since
# interpolation is run first, you will need to escape the  $  char as
# described below.
#
# This is the default config, so if you want to remove anything from
# here (as opposed to change/add), for example a key binding, set it to
# an empty value.
#
# You will need to escape the following values:
#   - # at the start of the line (at the first position of the key) (\#)
#   - $ in a value ($$)
"""


DEFAULT_FONT_SIZE = '10pt' if sys.platform == 'darwin' else '8pt'
# FIXME:conf what to do about this?
MONOSPACE = (' xos4 Terminus, Terminus, Monospace, '
             '"DejaVu Sans Mono", Monaco, '
             '"Bitstream Vera Sans Mono", "Andale Mono", '
             '"Courier New", Courier, "Liberation Mono", '
             'monospace, Fixed, Consolas, Terminal')


KEY_FIRST_COMMENT = """
# vim: ft=conf
#
# In this config file, qutebrowser's key bindings are configured.
# The format looks like this:
#
# [keymode]
#
# command
#   keychain
#   keychain2
#   ...
#
# All blank lines and lines starting with '#' are ignored.
# Inline-comments are not permitted.
#
# keymode is a comma separated list of modes in which the key binding should be
# active. If keymode starts with !, the key binding is active in all modes
# except the listed modes.
#
# For special keys (can't be part of a keychain), enclose them in `<`...`>`.
# For modifiers, you can use either `-` or `+` as delimiters, and these names:
#
#  * Control: `Control`, `Ctrl`
#  * Meta:    `Meta`, `Windows`, `Mod4`
#  * Alt:     `Alt`, `Mod1`
#  * Shift:   `Shift`
#
# For simple keys (no `<>`-signs), a capital letter means the key is pressed
# with Shift. For special keys (with `<>`-signs), you need to explicitly add
# `Shift-` to match a key pressed with shift.
#
# Note that default keybindings are always bound, and need to be explicitly
# unbound if you wish to remove them:
#
# <unbound>
#   keychain
#   keychain2
#   ...
"""

KEY_SECTION_DESC = {
    'all': "Keybindings active in all modes.",
    'normal': "Keybindings for normal mode.",
    'insert': (
        "Keybindings for insert mode.\n"
        "Since normal keypresses are passed through, only special keys are "
        "supported in this mode.\n"
        "Useful hidden commands to map in this section:\n\n"
        " * `open-editor`: Open a texteditor with the focused field.\n"
        " * `paste-primary`: Paste primary selection at cursor position."),
    'hint': (
        "Keybindings for hint mode.\n"
        "Since normal keypresses are passed through, only special keys are "
        "supported in this mode.\n"
        "Useful hidden commands to map in this section:\n\n"
        " * `follow-hint`: Follow the currently selected hint."),
    'passthrough': (
        "Keybindings for passthrough mode.\n"
        "Since normal keypresses are passed through, only special keys are "
        "supported in this mode."),
    'command': (
        "Keybindings for command mode.\n"
        "Since normal keypresses are passed through, only special keys are "
        "supported in this mode.\n"
        "Useful hidden commands to map in this section:\n\n"
        " * `command-history-prev`: Switch to previous command in history.\n"
        " * `command-history-next`: Switch to next command in history.\n"
        " * `completion-item-focus`: Select another item in completion.\n"
        " * `command-accept`: Execute the command currently in the "
        "commandline."),
    'prompt': (
        "Keybindings for prompts in the status line.\n"
        "You can bind normal keys in this mode, but they will be only active "
        "when a yes/no-prompt is asked. For other prompt modes, you can only "
        "bind special keys.\n"
        "Useful hidden commands to map in this section:\n\n"
        " * `prompt-accept`: Confirm the entered value.\n"
        " * `prompt-accept yes`: Answer yes to a yes/no question.\n"
        " * `prompt-accept no`: Answer no to a yes/no question."),
    'caret': (
        ""),
}

# Keys which are similar to Return and should be bound by default where Return
# is bound.

RETURN_KEYS = ['<Return>', '<Ctrl-M>', '<Ctrl-J>', '<Shift-Return>', '<Enter>',
               '<Shift-Enter>']


KEY_DATA = collections.OrderedDict([
    ('!normal', collections.OrderedDict([
        ('leave-mode', ['<Escape>', '<Ctrl-[>']),
    ])),

    ('normal', collections.OrderedDict([
        ('clear-keychain ;; search ;; fullscreen --leave',
            ['<Escape>', '<Ctrl-[>']),
        ('set-cmd-text -s :open', ['o']),
        ('set-cmd-text :open {url:pretty}', ['go']),
        ('set-cmd-text -s :open -t', ['O']),
        ('set-cmd-text :open -t -i {url:pretty}', ['gO']),
        ('set-cmd-text -s :open -b', ['xo']),
        ('set-cmd-text :open -b -i {url:pretty}', ['xO']),
        ('set-cmd-text -s :open -w', ['wo']),
        ('set-cmd-text :open -w {url:pretty}', ['wO']),
        ('set-cmd-text /', ['/']),
        ('set-cmd-text ?', ['?']),
        ('set-cmd-text :', [':']),
        ('open -t', ['ga', '<Ctrl-T>']),
        ('open -w', ['<Ctrl-N>']),
        ('tab-close', ['d', '<Ctrl-W>']),
        ('tab-close -o', ['D']),
        ('tab-only', ['co']),
        ('tab-focus', ['T']),
        ('tab-move', ['gm']),
        ('tab-move -', ['gl']),
        ('tab-move +', ['gr']),
        ('tab-next', ['J', '<Ctrl-PgDown>']),
        ('tab-prev', ['K', '<Ctrl-PgUp>']),
        ('tab-clone', ['gC']),
        ('reload', ['r', '<F5>']),
        ('reload -f', ['R', '<Ctrl-F5>']),
        ('back', ['H', '<back>']),
        ('back -t', ['th']),
        ('back -w', ['wh']),
        ('forward', ['L', '<forward>']),
        ('forward -t', ['tl']),
        ('forward -w', ['wl']),
        ('fullscreen', ['<F11>']),
        ('hint', ['f']),
        ('hint all tab', ['F']),
        ('hint all window', ['wf']),
        ('hint all tab-bg', [';b']),
        ('hint all tab-fg', [';f']),
        ('hint all hover', [';h']),
        ('hint images', [';i']),
        ('hint images tab', [';I']),
        ('hint links fill :open {hint-url}', [';o']),
        ('hint links fill :open -t -i {hint-url}', [';O']),
        ('hint links yank', [';y']),
        ('hint links yank-primary', [';Y']),
        ('hint --rapid links tab-bg', [';r']),
        ('hint --rapid links window', [';R']),
        ('hint links download', [';d']),
        ('hint inputs', [';t']),
        ('scroll left', ['h']),
        ('scroll down', ['j']),
        ('scroll up', ['k']),
        ('scroll right', ['l']),
        ('undo', ['u', '<Ctrl-Shift-T>']),
        ('scroll-perc 0', ['gg']),
        ('scroll-perc', ['G']),
        ('search-next', ['n']),
        ('search-prev', ['N']),
        ('enter-mode insert', ['i']),
        ('enter-mode caret', ['v']),
        ('enter-mode set_mark', ['`']),
        ('enter-mode jump_mark', ["'"]),
        ('yank', ['yy']),
        ('yank -s', ['yY']),
        ('yank title', ['yt']),
        ('yank title -s', ['yT']),
        ('yank domain', ['yd']),
        ('yank domain -s', ['yD']),
        ('yank pretty-url', ['yp']),
        ('yank pretty-url -s', ['yP']),
        ('open -- {clipboard}', ['pp']),
        ('open -- {primary}', ['pP']),
        ('open -t -- {clipboard}', ['Pp']),
        ('open -t -- {primary}', ['PP']),
        ('open -w -- {clipboard}', ['wp']),
        ('open -w -- {primary}', ['wP']),
        ('quickmark-save', ['m']),
        ('set-cmd-text -s :quickmark-load', ['b']),
        ('set-cmd-text -s :quickmark-load -t', ['B']),
        ('set-cmd-text -s :quickmark-load -w', ['wb']),
        ('bookmark-add', ['M']),
        ('set-cmd-text -s :bookmark-load', ['gb']),
        ('set-cmd-text -s :bookmark-load -t', ['gB']),
        ('set-cmd-text -s :bookmark-load -w', ['wB']),
        ('save', ['sf']),
        ('set-cmd-text -s :set', ['ss']),
        ('set-cmd-text -s :set -t', ['sl']),
        ('set-cmd-text -s :bind', ['sk']),
        ('zoom-out', ['-']),
        ('zoom-in', ['+']),
        ('zoom', ['=']),
        ('navigate prev', ['[[']),
        ('navigate next', [']]']),
        ('navigate prev -t', ['{{']),
        ('navigate next -t', ['}}']),
        ('navigate up', ['gu']),
        ('navigate up -t', ['gU']),
        ('navigate increment', ['<Ctrl-A>']),
        ('navigate decrement', ['<Ctrl-X>']),
        ('inspector', ['wi']),
        ('download', ['gd']),
        ('download-cancel', ['ad']),
        ('download-clear', ['cd']),
        ('view-source', ['gf']),
        ('set-cmd-text -s :buffer', ['gt']),
        ('tab-focus last', ['<Ctrl-Tab>', '<Ctrl-6>', '<Ctrl-^>']),
        ('enter-mode passthrough', ['<Ctrl-V>']),
        ('quit', ['<Ctrl-Q>', 'ZQ']),
        ('wq', ['ZZ']),
        ('scroll-page 0 1', ['<Ctrl-F>']),
        ('scroll-page 0 -1', ['<Ctrl-B>']),
        ('scroll-page 0 0.5', ['<Ctrl-D>']),
        ('scroll-page 0 -0.5', ['<Ctrl-U>']),
        ('tab-focus 1', ['<Alt-1>', 'g0', 'g^']),
        ('tab-focus 2', ['<Alt-2>']),
        ('tab-focus 3', ['<Alt-3>']),
        ('tab-focus 4', ['<Alt-4>']),
        ('tab-focus 5', ['<Alt-5>']),
        ('tab-focus 6', ['<Alt-6>']),
        ('tab-focus 7', ['<Alt-7>']),
        ('tab-focus 8', ['<Alt-8>']),
        ('tab-focus -1', ['<Alt-9>', 'g$']),
        ('home', ['<Ctrl-h>']),
        ('stop', ['<Ctrl-s>']),
        ('print', ['<Ctrl-Alt-p>']),
        ('open qute://settings', ['Ss']),
        ('follow-selected', RETURN_KEYS),
        ('follow-selected -t', ['<Ctrl-Return>', '<Ctrl-Enter>']),
        ('repeat-command', ['.']),
        ('tab-pin', ['<Ctrl-p>']),
        ('record-macro', ['q']),
        ('run-macro', ['@']),
    ])),

    ('insert', collections.OrderedDict([
        ('open-editor', ['<Ctrl-E>']),
        ('insert-text {primary}', ['<Shift-Ins>']),
    ])),

    ('hint', collections.OrderedDict([
        ('follow-hint', RETURN_KEYS),
        ('hint --rapid links tab-bg', ['<Ctrl-R>']),
        ('hint links', ['<Ctrl-F>']),
        ('hint all tab-bg', ['<Ctrl-B>']),
    ])),

    ('passthrough', {}),

    ('command', collections.OrderedDict([
        ('command-history-prev', ['<Ctrl-P>']),
        ('command-history-next', ['<Ctrl-N>']),
        ('completion-item-focus prev', ['<Shift-Tab>', '<Up>']),
        ('completion-item-focus next', ['<Tab>', '<Down>']),
        ('completion-item-focus next-category', ['<Ctrl-Tab>']),
        ('completion-item-focus prev-category', ['<Ctrl-Shift-Tab>']),
        ('completion-item-del', ['<Ctrl-D>']),
        ('command-accept', RETURN_KEYS),
    ])),

    ('prompt', collections.OrderedDict([
        ('prompt-accept', RETURN_KEYS),
        ('prompt-accept yes', ['y']),
        ('prompt-accept no', ['n']),
        ('prompt-open-download', ['<Ctrl-X>']),
        ('prompt-item-focus prev', ['<Shift-Tab>', '<Up>']),
        ('prompt-item-focus next', ['<Tab>', '<Down>']),
    ])),

    ('command,prompt', collections.OrderedDict([
        ('rl-backward-char', ['<Ctrl-B>']),
        ('rl-forward-char', ['<Ctrl-F>']),
        ('rl-backward-word', ['<Alt-B>']),
        ('rl-forward-word', ['<Alt-F>']),
        ('rl-beginning-of-line', ['<Ctrl-A>']),
        ('rl-end-of-line', ['<Ctrl-E>']),
        ('rl-unix-line-discard', ['<Ctrl-U>']),
        ('rl-kill-line', ['<Ctrl-K>']),
        ('rl-kill-word', ['<Alt-D>']),
        ('rl-unix-word-rubout', ['<Ctrl-W>']),
        ('rl-backward-kill-word', ['<Alt-Backspace>']),
        ('rl-yank', ['<Ctrl-Y>']),
        ('rl-delete-char', ['<Ctrl-?>']),
        ('rl-backward-delete-char', ['<Ctrl-H>']),
    ])),

    ('caret', collections.OrderedDict([
        ('toggle-selection', ['v', '<Space>']),
        ('drop-selection', ['<Ctrl-Space>']),
        ('enter-mode normal', ['c']),
        ('move-to-next-line', ['j']),
        ('move-to-prev-line', ['k']),
        ('move-to-next-char', ['l']),
        ('move-to-prev-char', ['h']),
        ('move-to-end-of-word', ['e']),
        ('move-to-next-word', ['w']),
        ('move-to-prev-word', ['b']),
        ('move-to-start-of-next-block', [']']),
        ('move-to-start-of-prev-block', ['[']),
        ('move-to-end-of-next-block', ['}']),
        ('move-to-end-of-prev-block', ['{']),
        ('move-to-start-of-line', ['0']),
        ('move-to-end-of-line', ['$']),
        ('move-to-start-of-document', ['gg']),
        ('move-to-end-of-document', ['G']),
        ('yank selection -s', ['Y']),
        ('yank selection', ['y'] + RETURN_KEYS),
        ('scroll left', ['H']),
        ('scroll down', ['J']),
        ('scroll up', ['K']),
        ('scroll right', ['L']),
    ])),
])


# A list of (regex, replacement) tuples of changed key commands.

CHANGED_KEY_COMMANDS = [
    (re.compile(r'^open -([twb]) about:blank$'), r'open -\1'),

    (re.compile(r'^download-page$'), r'download'),
    (re.compile(r'^cancel-download$'), r'download-cancel'),

    (re.compile(r"""^search (''|"")$"""),
        r'clear-keychain ;; search ;; fullscreen --leave'),
    (re.compile(r'^search$'),
        r'clear-keychain ;; search ;; fullscreen --leave'),
    (re.compile(r'^clear-keychain ;; search$'),
        r'clear-keychain ;; search ;; fullscreen --leave'),

    (re.compile(r"""^set-cmd-text ['"](.*) ['"]$"""), r'set-cmd-text -s \1'),
    (re.compile(r"""^set-cmd-text ['"](.*)['"]$"""), r'set-cmd-text \1'),

    (re.compile(r"^hint links rapid$"), r'hint --rapid links tab-bg'),
    (re.compile(r"^hint links rapid-win$"), r'hint --rapid links window'),

    (re.compile(r'^scroll -50 0$'), r'scroll left'),
    (re.compile(r'^scroll 0 50$'), r'scroll down'),
    (re.compile(r'^scroll 0 -50$'), r'scroll up'),
    (re.compile(r'^scroll 50 0$'), r'scroll right'),
    (re.compile(r'^scroll ([-\d]+ [-\d]+)$'), r'scroll-px \1'),

    (re.compile(r'^search *;; *clear-keychain$'),
        r'clear-keychain ;; search ;; fullscreen --leave'),
    (re.compile(r'^clear-keychain *;; *leave-mode$'), r'leave-mode'),

    (re.compile(r'^download-remove --all$'), r'download-clear'),

    (re.compile(r'^hint links fill "([^"]*)"$'), r'hint links fill \1'),

    (re.compile(r'^yank -t(\S+)'), r'yank title -\1'),
    (re.compile(r'^yank -t'), r'yank title'),
    (re.compile(r'^yank -d(\S+)'), r'yank domain -\1'),
    (re.compile(r'^yank -d'), r'yank domain'),
    (re.compile(r'^yank -p(\S+)'), r'yank pretty-url -\1'),
    (re.compile(r'^yank -p'), r'yank pretty-url'),
    (re.compile(r'^yank-selected -p'), r'yank selection -s'),
    (re.compile(r'^yank-selected'), r'yank selection'),

    (re.compile(r'^paste$'), r'open -- {clipboard}'),
    (re.compile(r'^paste -s$'), r'open -- {primary}'),
    (re.compile(r'^paste -([twb])$'), r'open -\1 -- {clipboard}'),
    (re.compile(r'^paste -([twb])s$'), r'open -\1 -- {primary}'),
    (re.compile(r'^paste -s([twb])$'), r'open -\1 -- {primary}'),

    (re.compile(r'^completion-item-next'), r'completion-item-focus next'),
    (re.compile(r'^completion-item-prev'), r'completion-item-focus prev'),

    (re.compile(r'^open {clipboard}$'), r'open -- {clipboard}'),
    (re.compile(r'^open -([twb]) {clipboard}$'), r'open -\1 -- {clipboard}'),
    (re.compile(r'^open {primary}$'), r'open -- {primary}'),
    (re.compile(r'^open -([twb]) {primary}$'), r'open -\1 -- {primary}'),

    (re.compile(r'^paste-primary$'), r'insert-text {primary}'),

    (re.compile(r'^set-cmd-text -s :search$'), r'set-cmd-text /'),
    (re.compile(r'^set-cmd-text -s :search -r$'), r'set-cmd-text ?'),
    (re.compile(r'^set-cmd-text -s :$'), r'set-cmd-text :'),
    (re.compile(r'^set-cmd-text -s :set keybind$'), r'set-cmd-text -s :bind'),

    (re.compile(r'^prompt-yes$'), r'prompt-accept yes'),
    (re.compile(r'^prompt-no$'), r'prompt-accept no'),

    (re.compile(r'^tab-close -l$'), r'tab-close --prev'),
    (re.compile(r'^tab-close --left$'), r'tab-close --prev'),
    (re.compile(r'^tab-close -r$'), r'tab-close --next'),
    (re.compile(r'^tab-close --right$'), r'tab-close --next'),

    (re.compile(r'^tab-only -l$'), r'tab-only --prev'),
    (re.compile(r'^tab-only --left$'), r'tab-only --prev'),
    (re.compile(r'^tab-only -r$'), r'tab-only --next'),
    (re.compile(r'^tab-only --right$'), r'tab-only --next'),
]


Option = collections.namedtuple('Option', ['name', 'typ', 'default',
                                           'backends', 'description'])


def _raise_invalid_node(name, what, node):
    """Raise an exception for an invalid configdata YAML node.

    Args:
        name: The name of the setting being parsed.
        what: The name of the thing being parsed.
        node: The invalid node.
    """
    raise ValueError("Invalid node for {} while reading {}: {!r}".format(
        name, what, node))


def _parse_yaml_type(name, node):
    if isinstance(node, str):
        # e.g:
        #  type: Bool
        # -> create the type object without any arguments
        type_name = node
        kwargs = {}
    elif isinstance(node, dict):
        # e.g:
        #  type:
        #    name: String
        #    none_ok: true
        # -> create the type object and pass arguments
        type_name = node.pop('name')
        kwargs = node
        valid_values = kwargs.get('valid_values', None)
        if valid_values is not None:
            kwargs['valid_values'] = configtypes.ValidValues(*valid_values)
    else:
        _raise_invalid_node(name, 'type', node)

    try:
        typ = getattr(configtypes, type_name)
    except AttributeError as e:
        raise AttributeError("Did not find type {} for {}".format(
            type_name, name))

    # Parse sub-types
    try:
        if typ is configtypes.Dict:
            kwargs['keytype'] = _parse_yaml_type(name, kwargs['keytype'])
            kwargs['valtype'] = _parse_yaml_type(name, kwargs['valtype'])
        elif typ is configtypes.List:
            kwargs['valtype'] = _parse_yaml_type(name, kwargs['valtype'])
    except KeyError as e:
        _raise_invalid_node(name, str(e), node)

    try:
        return typ(**kwargs)
    except TypeError as e:
        raise TypeError("Error while creating {} with {}: {}".format(
            type_name, node, e))


def _parse_yaml_backends_dict(name, node):
    """Parse a dict definition for backends.

    Example:

    backends:
      QtWebKit: true
      QtWebEngine: Qt 5.9
    """
    str_to_backend = {
        'QtWebKit': usertypes.Backend.QtWebKit,
        'QtWebEngine': usertypes.Backend.QtWebEngine,
    }

    if node.keys() != str_to_backend.keys():
        _raise_invalid_node(name, 'backends', node)

    backends = []

    # The value associated to the key, and whether we should add that backend
    # or not.
    conditionals = {
        True: True,
        False: False,
        'Qt 5.8': qtutils.version_check('5.8'),
        'Qt 5.9': qtutils.version_check('5.9'),
    }
    for key in node.keys():
        if conditionals[node[key]]:
            backends.append(str_to_backend[key])

    return backends


def _parse_yaml_backends(name, node):
    """Parse a backend node in the yaml.

    It can have one of those four forms:
    - Not present -> setting applies to both backends.
    - backend: QtWebKit -> setting only available with QtWebKit
    - backend: QtWebEngine -> setting only available with QtWebEngine
    - backend:
       QtWebKit: true
       QtWebEngine: Qt 5.9
      -> setting available based on the given conditionals.
    """
    if node is None:
        return [usertypes.Backend.QtWebKit, usertypes.Backend.QtWebEngine]
    elif node == 'QtWebKit':
        return [usertypes.Backend.QtWebKit]
    elif node == 'QtWebEngine':
        return [usertypes.Backend.QtWebEngine]
    elif isinstance(node, dict):
        return _parse_yaml_backends_dict(name, node)
    _raise_invalid_node(name, 'backends', node)


def _read_yaml(yaml_data):
    """Read config data from a YAML file.

    Args:
        yaml_data: The YAML string to parse.

    Return:
        A dict mapping option names to Option elements.
    """
    parsed = {}
    data = utils.yaml_load(yaml_data)

    keys = {'type', 'default', 'desc', 'backend'}

    for name, option in data.items():
        if not set(option.keys()).issubset(keys):
            raise ValueError("Invalid keys {} for {}".format(
                option.keys(), name))

        parsed[name] = Option(
            name=name,
            typ=_parse_yaml_type(name, option['type']),
            default=option['default'],
            backends=_parse_yaml_backends(name, option.get('backend', None)),
            description=option['desc'])

    # Make sure no key shadows another.
    for key1 in parsed:
        for key2 in parsed:
            if key2.startswith(key1 + '.'):
                raise ValueError("Shadowing keys {} and {}".format(key1, key2))

    return parsed


def is_valid_prefix(prefix):
    """Check whether the given prefix is a valid prefix for some option."""
    return any(key.startswith(prefix + '.') for key in DATA)


def init():
    """Initialize configdata from the YAML file."""
    global DATA
    DATA = _read_yaml(utils.read_file('config/configdata.yml'))
