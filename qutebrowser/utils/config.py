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
        'gg': 'scrollpercenty 0',
        'G': 'scrollpercenty',
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
        self.read_dict(default_config)
        self.configdir = configdir
        self.configfile = os.path.join(self.configdir, self.FNAME)
        logging.debug("Reading config from {}".format(self.configfile))
        self.read(self.configfile)

    def save(self):
        if not os.path.exists(self.configdir):
            os.makedirs(self.configdir, 0o755)
            logging.debug("Config directory does not exist, created.")
        logging.debug("Saving config to {}".format(self.configfile))
        with open(self.configfile, 'w') as f:
            self.write(f)
