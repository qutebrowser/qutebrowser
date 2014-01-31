"""Configuration storage and config-related utilities.

config         -- The main Config object.
colordict      -- All configured colors.
default_config -- The default config as dict.
MONOSPACE      -- A list of suitable monospace fonts.
"""

import os.path
import os
import io
import logging
from configparser import ConfigParser

config = None
colordict = {}

default_config = """
    [general]
    show_completion = true
    space_scroll = 200
    ignorecase = true
    wrapsearch = true
    startpage = http://www.duckduckgo.com/

    [keybind]
    o = open
    O = tabopen
    d = tabclose
    J = tabnext
    K = tabprev
    r = reload
    H = back
    L = forward
    h = scroll -50 0
    j = scroll 0 50
    k = scroll 0 -50
    l = scroll 50 0
    u = undo
    gg = scroll_perc_y 0
    G = scroll_perc_y
    n = nextsearch
    yy = yank
    yY = yank sel
    yt = yanktitle
    yT = yanktitle sel
    pp = paste
    pP = paste sel
    Pp = tabpaste
    PP = tabpaste sel

    [colors]
    completion.fg = #333333
    completion.item.bg = white
    completion.category.bg = qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                             stop:0 #e4e4e4, stop:1 #dbdbdb)
    completion.category.border.top = #808080
    completion.category.border.bottom = #bbbbbb
    completion.item.selected.fg = #333333
    completion.item.selected.bg = #ffec8b
    completion.item.selected.border.top = #f2f2c0
    completion.item.selected.border.bottom = #e6e680
    completion.match.fg = red
    statusbar.progress.bg = white
    statusbar.progress.bg.error = red
    statusbar.bg = black
    statusbar.fg = white
    statusbar.bg.error = red
    tab.bg = grey
    tab.bg.selected = black
    tab.fg = white
    tab.seperator = white
"""

_MONOSPACE = ['Monospace', 'DejaVu Sans Mono', 'Consolas', 'Monaco',
              'Bitstream Vera Sans Mono', 'Andale Mono', 'Liberation Mono',
              'Courier New', 'Courier', 'monospace', 'Fixed', 'Terminal']

MONOSPACE = ', '.join(_MONOSPACE)


def init(confdir):
    """Initialize the global objects based on the config in configdir."""
    global config, colordict
    config = Config(confdir)
    try:
        colordict = ColorDict(config['colors'])
    except KeyError:
        colordict = ColorDict()


def get_stylesheet(template):
    """Return a formatted stylesheet based on a template."""
    return template.strip().format(color=colordict, monospace=MONOSPACE)


class ColorDict(dict):
    """A dict aimed at Qt stylesheet colors."""

    def __getitem__(self, key):

        """Override dict __getitem__.

        If a value wasn't found, return an empty string.
        (Color not defined, so no output in the stylesheet)

        If the key has a .fg. element in it, return  color: X;.
        If the key has a .bg. element in it, return  background-color: X;.

        In all other cases, return the plain value.
        """

        try:
            val = super().__getitem__(key)
        except KeyError:
            return ''
        if 'fg' in key.split('.'):
            return 'color: {};'.format(val)
        elif 'bg' in key.split('.'):
            return 'background-color: {};'.format(val)
        else:
            return val

    def getraw(self, key):
        """Get a value without the transformations done in __getitem__.

        Returns a value, or None if the value wasn't found.
        """
        try:
            return super().__getitem__(key)
        except KeyError:
            return None


class Config(ConfigParser):
    """Our own ConfigParser subclass."""

    configdir = None
    FNAME = 'config'
    default_cp = None
    config_loaded = False

    def __init__(self, configdir):
        """Config constructor.

        configdir -- directory to store the config in.
        """
        super().__init__()
        self.default_cp = ConfigParser()
        self.default_cp.optionxform = lambda opt: opt  # be case-insensitive
        self.default_cp.read_string(default_config)
        self.optionxform = lambda opt: opt  # be case-insensitive
        self.configdir = configdir
        self.configfile = os.path.join(self.configdir, self.FNAME)
        if not os.path.isfile(self.configfile):
            return
        logging.debug("Reading config from {}".format(self.configfile))
        self.read(self.configfile)
        self.config_loaded = True

    def __getitem__(self, key):
        """Get an item from the configparser or default dict.

        Extends ConfigParser's __getitem__.
        """
        try:
            return super().__getitem__(key)
        except KeyError:
            return self.default_cp[key]

    def get(self, *args, **kwargs):
        """Get an item from the configparser or default dict.

        Extends ConfigParser's get().
        """
        if 'fallback' in kwargs:
            del kwargs['fallback']
        fallback = self.default_cp.get(*args, **kwargs)
        return super().get(*args, fallback=fallback, **kwargs)

    def save(self):
        """Save the config file."""
        if self.configdir is None or not self.config_loaded:
            return
        if not os.path.exists(self.configdir):
            os.makedirs(self.configdir, 0o755)
        logging.debug("Saving config to {}".format(self.configfile))
        with open(self.configfile, 'w') as f:
            self.write(f)
            f.flush()
            os.fsync(f.fileno())

    def dump_userconfig(self):
        """Returns the part of the config which was changed by the user as a
        string.
        """
        with io.StringIO() as f:
            self.write(f)
            return f.getvalue()
