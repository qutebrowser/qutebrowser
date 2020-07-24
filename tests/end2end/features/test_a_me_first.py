import time

import PyQt5.QtWidgets


def test_this(qapp):
    button = QtWidgets.QPushButton()
    before = time.monotonic()
    button.show()
    after = time.monotonic()
    assert False, '+++++ button.show() runtime: {}'.format(after - before)
