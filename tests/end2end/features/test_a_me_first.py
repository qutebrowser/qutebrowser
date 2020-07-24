import time

import PyQt5.QtWidgets


def test_this(qapp):
    button = PyQt5.QtWidgets.QPushButton()
    before = time.monotonic()
    button.show()
    after = time.monotonic()
    assert False, '+++++ button.show() runtime: {}'.format(after - before)
