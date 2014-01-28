import os.path
import os
import logging

from configparser import ConfigParser

default_config = {
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
    }
}

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
