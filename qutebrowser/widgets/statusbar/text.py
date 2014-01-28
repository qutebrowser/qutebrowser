import logging
from PyQt5.QtWidgets import QLabel


class Text(QLabel):
    """The text part of the status bar, composed of several 'widgets'"""
    keystring = ''
    error = ''
    text = ''
    scrollperc = ''

    def __init__(self, bar):
        super().__init__(bar)
        self.setStyleSheet("padding-right: 1px")

    def __setattr__(self, name, value):
        super().__setattr__(name, value)
        self.update()

    def set_keystring(self, s):
        """Setter to be used as a Qt slot"""
        self.keystring = s

    def set_perc(self, x, y):
        """Setter to be used as a Qt slot"""
        if y == 0:
            self.scrollperc = '[top]'
        elif y == 100:
            self.scrollperc = '[bot]'
        else:
            self.scrollperc = '[{}%]'.format(y)

    def set_text(self, text):
        logging.debug('Setting text to "{}"'.format(text))
        self.text = text

    def update(self):
        """Update the text displayed"""
        self.setText(' '.join([self.keystring, self.error, self.text,
                               self.scrollperc]))
