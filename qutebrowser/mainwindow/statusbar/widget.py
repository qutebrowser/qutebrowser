from abc import ABCMeta, ABC, abstractmethod
from qutebrowser.qt.widgets import QWidget


class QABCMeta(ABCMeta, type(QWidget)):
    """Meta class that combines ABC and the Qt meta class"""
    pass


class StatusBarWidget(ABC, metaclass=QABCMeta):
    """Abstract base class for all status bar widgets"""

    @abstractmethod
    def enable(self):
        pass

    @abstractmethod
    def disable(self):
        pass
