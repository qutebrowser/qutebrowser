import os.path
import os
import logging

from configparser import ConfigParser

config = None
colordict = {}

default_config = {
    'general': {
        'show_completion': 'true',
    },
    'keybind': {
        'o': 'open',
        'O': 'tabopen',
        'd': 'tabclose',
        'J': 'tabnext',
        'K': 'tabprev',
        'r': 'reload',
        'H': 'back',
        'L': 'forward',
        'h': 'scroll -50 0',
        'j': 'scroll 0 50',
        'k': 'scroll 0 -50',
        'l': 'scroll 50 0',
        'u': 'undo',
        'gg': 'scroll_perc_y 0',
        'G': 'scroll_perc_y',
    },
    'colors': {
        'completion.fg': '#333333',
        'completion.item.bg': 'white',
        'completion.category.bg': 'qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #e4e4e4, stop:1 #dbdbdb)',
        'completion.category.border.top': '#808080',
        'completion.category.border.bottom': '#bbbbbb',
        'completion.item.selected.fg': '#333333',
        'completion.item.selected.bg': '#ffec8b',
        'completion.item.selected.border.top': '#f2f2c0',
        'completion.item.selected.border.bottom': '#e6e680',
        'completion.match.fg': 'red',
        'statusbar.progress.bg': 'white',
        'statusbar.progress.bg.error': 'red',
        'statusbar.bg': 'black',
        'statusbar.fg': 'white',
        'statusbar.bg.error': 'red',
        'tab.bg': 'grey',
        'tab.bg.selected': 'black',
        'tab.fg': 'white',
        'tab.seperator': 'white',
    },
}

def init(confdir):
    global config, colordict
    config = Config(confdir)
    try:
        colordict = ColorDict(config['colors'])
    except KeyError:
        colordict = ColorDict()

def get_stylesheet(template):
    global colordict
    return template.strip().format(color=colordict)

class ColorDict(dict):
    def __getitem__(self, key):
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
        try:
            return super().__getitem__(key)
        except KeyError:
            return None

class Config(ConfigParser):
    """Our own ConfigParser"""
    configdir = None
    FNAME = 'config'

    def __init__(self, configdir):
        """configdir: directory to store the config in"""
        super().__init__()
        self.optionxform = lambda opt: opt # be case-insensitive
        self.configdir = configdir
        if self.configdir is None:
            self.init_config()
            return
        self.configfile = os.path.join(self.configdir, self.FNAME)
        if not os.path.isfile(self.configfile):
            self.init_config()
        logging.debug("Reading config from {}".format(self.configfile))
        self.read(self.configfile)

    def init_config(self):
        logging.info("Initializing default config.")
        if self.configdir is None:
            self.read_dict(default_config)
            return
        cp = ConfigParser()
        cp.optionxform = lambda opt: opt # be case-insensitive
        cp.read_dict(default_config)
        if not os.path.exists(self.configdir):
            os.makedirs(self.configdir, 0o755)
        with open(self.configfile, 'w') as f:
            cp.write(f)

    def save(self):
        if self.configdir is None:
            return
        if not os.path.exists(self.configdir):
            os.makedirs(self.configdir, 0o755)
        logging.debug("Saving config to {}".format(self.configfile))
        with open(self.configfile, 'w') as f:
            self.write(f)
