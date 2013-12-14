from PyQt5.QtWidgets import QLineEdit

class CommandEdit(QLineEdit):
    def __init__(self, *args, **kwargs):
        super(CommandEdit, self).__init__(*args, **kwargs)
        self.setStyleSheet('QLineEdit { background: yellow }')
