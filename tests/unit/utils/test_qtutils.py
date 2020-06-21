# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2020 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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


"""Tests for qutebrowser.utils.qtutils."""

import io
import os
import os.path
import unittest
import unittest.mock

import pytest
from PyQt5.QtCore import (QDataStream, QPoint, QUrl, QByteArray, QIODevice,
                          QTimer, QBuffer, QFile, QProcess, QFileDevice)
from PyQt5.QtGui import QColor

from qutebrowser.utils import qtutils, utils, usertypes
import overflow_test_cases

if utils.is_linux:
    # Those are not run on macOS because that seems to cause a hang sometimes.
    # On Windows, we don't run them either because of
    # https://github.com/pytest-dev/pytest/issues/3650
    try:
        # pylint: disable=no-name-in-module,useless-suppression
        from test import test_file
        # pylint: enable=no-name-in-module,useless-suppression
    except ImportError:
        # Debian patches Python to remove the tests...
        test_file = None
else:
    test_file = None


# pylint: disable=bad-continuation
@pytest.mark.parametrize(['qversion', 'compiled', 'pyqt', 'version', 'exact',
                          'expected'], [
    # equal versions
    ('5.4.0', None, None, '5.4.0', False, True),
    ('5.4.0', None, None, '5.4.0', True, True),  # exact=True
    ('5.4.0', None, None, '5.4', True, True),  # without trailing 0
    # newer version installed
    ('5.4.1', None, None, '5.4', False, True),
    ('5.4.1', None, None, '5.4', True, False),  # exact=True
    # older version installed
    ('5.3.2', None, None, '5.4', False, False),
    ('5.3.0', None, None, '5.3.2', False, False),
    ('5.3.0', None, None, '5.3.2', True, False),  # exact=True
    # compiled=True
    # new Qt runtime, but compiled against older version
    ('5.4.0', '5.3.0', '5.4.0', '5.4.0', False, False),
    # new Qt runtime, compiled against new version, but old PyQt
    ('5.4.0', '5.4.0', '5.3.0', '5.4.0', False, False),
    # all up-to-date
    ('5.4.0', '5.4.0', '5.4.0', '5.4.0', False, True),
])
# pylint: enable=bad-continuation
def test_version_check(monkeypatch, qversion, compiled, pyqt, version, exact,
                       expected):
    """Test for version_check().

    Args:
        monkeypatch: The pytest monkeypatch fixture.
        qversion: The version to set as fake qVersion().
        compiled: The value for QT_VERSION_STR (set compiled=False)
        pyqt: The value for PYQT_VERSION_STR (set compiled=False)
        version: The version to compare with.
        exact: Use exact comparing (==)
        expected: The expected result.
    """
    monkeypatch.setattr(qtutils, 'qVersion', lambda: qversion)
    if compiled is not None:
        monkeypatch.setattr(qtutils, 'QT_VERSION_STR', compiled)
        monkeypatch.setattr(qtutils, 'PYQT_VERSION_STR', pyqt)
        compiled_arg = True
    else:
        compiled_arg = False

    actual = qtutils.version_check(version, exact, compiled=compiled_arg)
    assert actual == expected


def test_version_check_compiled_and_exact():
    with pytest.raises(ValueError):
        qtutils.version_check('1.2.3', exact=True, compiled=True)


@pytest.mark.parametrize('version, is_new', [
    ('537.21', False),  # QtWebKit 5.1
    ('538.1', False),   # Qt 5.8
    ('602.1', True)     # new QtWebKit TP5, 5.212 Alpha
])
def test_is_new_qtwebkit(monkeypatch, version, is_new):
    monkeypatch.setattr(qtutils, 'qWebKitVersion', lambda: version)
    assert qtutils.is_new_qtwebkit() == is_new


@pytest.mark.parametrize('backend, arguments, single_process', [
    (usertypes.Backend.QtWebKit, ['--single-process'], False),
    (usertypes.Backend.QtWebEngine, ['--single-process'], True),
    (usertypes.Backend.QtWebEngine, [], False),
])
def test_is_single_process(monkeypatch, stubs, backend, arguments, single_process):
    qapp = stubs.FakeQApplication(arguments=arguments)
    monkeypatch.setattr(qtutils, 'QApplication', qapp)
    monkeypatch.setattr(qtutils.objects, 'backend', backend)
    assert qtutils.is_single_process() == single_process


class TestCheckOverflow:

    """Test check_overflow."""

    @pytest.mark.parametrize('ctype, val',
                             overflow_test_cases.good_values())
    def test_good_values(self, ctype, val):
        """Test values which are inside bounds."""
        qtutils.check_overflow(val, ctype)

    @pytest.mark.parametrize('ctype, val',
                             [(ctype, val) for (ctype, val, _) in
                              overflow_test_cases.bad_values()])
    def test_bad_values_fatal(self, ctype, val):
        """Test values which are outside bounds with fatal=True."""
        with pytest.raises(OverflowError):
            qtutils.check_overflow(val, ctype)

    @pytest.mark.parametrize('ctype, val, repl',
                             overflow_test_cases.bad_values())
    def test_bad_values_nonfatal(self, ctype, val, repl):
        """Test values which are outside bounds with fatal=False."""
        newval = qtutils.check_overflow(val, ctype, fatal=False)
        assert newval == repl


class QtObject:

    """Fake Qt object for test_ensure."""

    def __init__(self, valid=True, null=False, error=None):
        self._valid = valid
        self._null = null
        self._error = error

    def __repr__(self):
        return '<QtObject>'

    def errorString(self):
        """Get the fake error, or raise AttributeError if set to None."""
        if self._error is None:
            raise AttributeError
        return self._error

    def isValid(self):
        return self._valid

    def isNull(self):
        return self._null


@pytest.mark.parametrize('obj, raising, exc_reason, exc_str', [
    # good examples
    (QtObject(valid=True, null=True), False, None, None),
    (QtObject(valid=True, null=False), False, None, None),
    # bad examples
    (QtObject(valid=False, null=True), True, None, '<QtObject> is not valid'),
    (QtObject(valid=False, null=False), True, None, '<QtObject> is not valid'),
    (QtObject(valid=False, null=True, error='Test'), True, 'Test',
     '<QtObject> is not valid: Test'),
])
def test_ensure_valid(obj, raising, exc_reason, exc_str):
    """Test ensure_valid.

    Args:
        obj: The object to test with.
        raising: Whether QtValueError is expected to be raised.
        exc_reason: The expected .reason attribute of the exception.
        exc_str: The expected string of the exception.
    """
    if raising:
        with pytest.raises(qtutils.QtValueError) as excinfo:
            qtutils.ensure_valid(obj)
        assert excinfo.value.reason == exc_reason
        assert str(excinfo.value) == exc_str
    else:
        qtutils.ensure_valid(obj)


@pytest.mark.parametrize('status, raising, message', [
    (QDataStream.Ok, False, None),
    (QDataStream.ReadPastEnd, True, "The data stream has read past the end of "
                                    "the data in the underlying device."),
    (QDataStream.ReadCorruptData, True, "The data stream has read corrupt "
                                        "data."),
    (QDataStream.WriteFailed, True, "The data stream cannot write to the "
                                    "underlying device."),
])
def test_check_qdatastream(status, raising, message):
    """Test check_qdatastream.

    Args:
        status: The status to set on the QDataStream we test with.
        raising: Whether check_qdatastream is expected to raise OSError.
        message: The expected exception string.
    """
    stream = QDataStream()
    stream.setStatus(status)
    if raising:
        with pytest.raises(OSError, match=message):
            qtutils.check_qdatastream(stream)
    else:
        qtutils.check_qdatastream(stream)


def test_qdatastream_status_count():
    """Make sure no new members are added to QDataStream.Status."""
    values = vars(QDataStream).values()
    status_vals = [e for e in values if isinstance(e, QDataStream.Status)]
    assert len(status_vals) == 4


@pytest.mark.parametrize('color, expected', [
    (QColor('red'), 'rgba(255, 0, 0, 255)'),
    (QColor('blue'), 'rgba(0, 0, 255, 255)'),
    (QColor(1, 3, 5, 7), 'rgba(1, 3, 5, 7)'),
])
def test_qcolor_to_qsscolor(color, expected):
    assert qtutils.qcolor_to_qsscolor(color) == expected


def test_qcolor_to_qsscolor_invalid():
    with pytest.raises(qtutils.QtValueError):
        qtutils.qcolor_to_qsscolor(QColor())


@pytest.mark.parametrize('obj', [
    QPoint(23, 42),
    QUrl('http://www.qutebrowser.org/'),
])
def test_serialize(obj):
    """Test a serialize/deserialize round trip.

    Args:
        obj: The object to test with.
    """
    new_obj = type(obj)()
    qtutils.deserialize(qtutils.serialize(obj), new_obj)
    assert new_obj == obj


class TestSerializeStream:

    """Tests for serialize_stream and deserialize_stream."""

    def _set_status(self, stream, status):
        """Helper function so mocks can set an error status when used."""
        stream.status.return_value = status

    @pytest.fixture
    def stream_mock(self):
        """Fixture providing a QDataStream-like mock."""
        m = unittest.mock.MagicMock(spec=QDataStream)
        m.status.return_value = QDataStream.Ok
        return m

    def test_serialize_pre_error_mock(self, stream_mock):
        """Test serialize_stream with an error already set."""
        stream_mock.status.return_value = QDataStream.ReadCorruptData

        with pytest.raises(OSError, match="The data stream has read corrupt "
                                          "data."):
            qtutils.serialize_stream(stream_mock, QPoint())

        assert not stream_mock.__lshift__.called

    def test_serialize_post_error_mock(self, stream_mock):
        """Test serialize_stream with an error while serializing."""
        obj = QPoint()
        stream_mock.__lshift__.side_effect = lambda _other: self._set_status(
            stream_mock, QDataStream.ReadCorruptData)

        with pytest.raises(OSError, match="The data stream has read corrupt "
                                          "data."):
            qtutils.serialize_stream(stream_mock, obj)

        assert stream_mock.__lshift__.called_once_with(obj)

    def test_deserialize_pre_error_mock(self, stream_mock):
        """Test deserialize_stream with an error already set."""
        stream_mock.status.return_value = QDataStream.ReadCorruptData

        with pytest.raises(OSError, match="The data stream has read corrupt "
                                          "data."):
            qtutils.deserialize_stream(stream_mock, QPoint())

        assert not stream_mock.__rshift__.called

    def test_deserialize_post_error_mock(self, stream_mock):
        """Test deserialize_stream with an error while deserializing."""
        obj = QPoint()
        stream_mock.__rshift__.side_effect = lambda _other: self._set_status(
            stream_mock, QDataStream.ReadCorruptData)

        with pytest.raises(OSError, match="The data stream has read corrupt "
                                          "data."):
            qtutils.deserialize_stream(stream_mock, obj)

        assert stream_mock.__rshift__.called_once_with(obj)

    def test_round_trip_real_stream(self):
        """Test a round trip with a real QDataStream."""
        src_obj = QPoint(23, 42)
        dest_obj = QPoint()
        data = QByteArray()

        write_stream = QDataStream(data, QIODevice.WriteOnly)
        qtutils.serialize_stream(write_stream, src_obj)

        read_stream = QDataStream(data, QIODevice.ReadOnly)
        qtutils.deserialize_stream(read_stream, dest_obj)

        assert src_obj == dest_obj

    @pytest.mark.qt_log_ignore('^QIODevice::write.*: ReadOnly device')
    def test_serialize_readonly_stream(self):
        """Test serialize_stream with a read-only stream."""
        data = QByteArray()
        stream = QDataStream(data, QIODevice.ReadOnly)
        with pytest.raises(OSError, match="The data stream cannot write to "
                                          "the underlying device."):
            qtutils.serialize_stream(stream, QPoint())

    @pytest.mark.qt_log_ignore('QIODevice::read.*: WriteOnly device')
    def test_deserialize_writeonly_stream(self):
        """Test deserialize_stream with a write-only stream."""
        data = QByteArray()
        obj = QPoint()
        stream = QDataStream(data, QIODevice.WriteOnly)
        with pytest.raises(OSError, match="The data stream has read past the "
                           "end of the data in the underlying device."):
            qtutils.deserialize_stream(stream, obj)


class SavefileTestException(Exception):

    """Exception raised in TestSavefileOpen for testing."""


@pytest.mark.usefixtures('qapp')
class TestSavefileOpen:

    """Tests for savefile_open."""

    ## Tests with a mock testing that the needed methods are called.

    @pytest.fixture
    def qsavefile_mock(self, mocker):
        """Mock for QSaveFile."""
        m = mocker.patch('qutebrowser.utils.qtutils.QSaveFile')
        instance = m()
        yield instance
        instance.commit.assert_called_once_with()

    def test_mock_open_error(self, qsavefile_mock):
        """Test with a mock and a failing open()."""
        qsavefile_mock.open.return_value = False
        qsavefile_mock.errorString.return_value = "Hello World"

        with pytest.raises(OSError, match="Hello World"):
            with qtutils.savefile_open('filename'):
                pass

        qsavefile_mock.open.assert_called_once_with(QIODevice.WriteOnly)
        qsavefile_mock.cancelWriting.assert_called_once_with()

    def test_mock_exception(self, qsavefile_mock):
        """Test with a mock and an exception in the block."""
        qsavefile_mock.open.return_value = True

        with pytest.raises(SavefileTestException):
            with qtutils.savefile_open('filename'):
                raise SavefileTestException

        qsavefile_mock.open.assert_called_once_with(QIODevice.WriteOnly)
        qsavefile_mock.cancelWriting.assert_called_once_with()

    def test_mock_commit_failed(self, qsavefile_mock):
        """Test with a mock and an exception in the block."""
        qsavefile_mock.open.return_value = True
        qsavefile_mock.commit.return_value = False

        with pytest.raises(OSError, match="Commit failed!"):
            with qtutils.savefile_open('filename'):
                pass

        qsavefile_mock.open.assert_called_once_with(QIODevice.WriteOnly)
        assert not qsavefile_mock.cancelWriting.called
        assert not qsavefile_mock.errorString.called

    def test_mock_successful(self, qsavefile_mock):
        """Test with a mock and a successful write."""
        qsavefile_mock.open.return_value = True
        qsavefile_mock.errorString.return_value = "Hello World"
        qsavefile_mock.commit.return_value = True
        qsavefile_mock.write.side_effect = len
        qsavefile_mock.isOpen.return_value = True

        with qtutils.savefile_open('filename') as f:
            f.write("Hello World")

        qsavefile_mock.open.assert_called_once_with(QIODevice.WriteOnly)
        assert not qsavefile_mock.cancelWriting.called
        qsavefile_mock.write.assert_called_once_with(b"Hello World")

    ## Tests with real files

    @pytest.mark.parametrize('data', ["Hello World", "Snowman! ☃"])
    def test_utf8(self, data, tmpdir):
        """Test with UTF8 data."""
        filename = tmpdir / 'foo'
        filename.write("Old data")
        with qtutils.savefile_open(str(filename)) as f:
            f.write(data)
        assert tmpdir.listdir() == [filename]
        assert filename.read_text(encoding='utf-8') == data

    def test_binary(self, tmpdir):
        """Test with binary data."""
        filename = tmpdir / 'foo'
        with qtutils.savefile_open(str(filename), binary=True) as f:
            f.write(b'\xde\xad\xbe\xef')
        assert tmpdir.listdir() == [filename]
        assert filename.read_binary() == b'\xde\xad\xbe\xef'

    def test_exception(self, tmpdir):
        """Test with an exception in the block."""
        filename = tmpdir / 'foo'
        filename.write("Old content")
        with pytest.raises(SavefileTestException):
            with qtutils.savefile_open(str(filename)) as f:
                f.write("Hello World!")
                raise SavefileTestException
        assert tmpdir.listdir() == [filename]
        assert filename.read_text(encoding='utf-8') == "Old content"

    def test_existing_dir(self, tmpdir):
        """Test with the filename already occupied by a directory."""
        filename = tmpdir / 'foo'
        filename.mkdir()
        with pytest.raises(OSError) as excinfo:
            with qtutils.savefile_open(str(filename)):
                pass

        msg = "Filename refers to a directory: {!r}".format(str(filename))
        assert str(excinfo.value) == msg
        assert tmpdir.listdir() == [filename]

    def test_failing_flush(self, tmpdir):
        """Test with the file being closed before flushing."""
        filename = tmpdir / 'foo'
        with pytest.raises(ValueError, match="IO operation on closed device!"):
            with qtutils.savefile_open(str(filename), binary=True) as f:
                f.write(b'Hello')
                f.dev.commit()  # provoke failing flush

        assert tmpdir.listdir() == [filename]

    def test_failing_commit(self, tmpdir):
        """Test with the file being closed before committing."""
        filename = tmpdir / 'foo'
        with pytest.raises(OSError, match='Commit failed!'):
            with qtutils.savefile_open(str(filename), binary=True) as f:
                f.write(b'Hello')
                f.dev.cancelWriting()  # provoke failing commit

        assert tmpdir.listdir() == []

    def test_line_endings(self, tmpdir):
        """Make sure line endings are translated correctly.

        See https://github.com/qutebrowser/qutebrowser/issues/309
        """
        filename = tmpdir / 'foo'
        with qtutils.savefile_open(str(filename)) as f:
            f.write('foo\nbar\nbaz')
        data = filename.read_binary()
        if utils.is_windows:
            assert data == b'foo\r\nbar\r\nbaz'
        else:
            assert data == b'foo\nbar\nbaz'


if test_file is not None:
    # If we were able to import Python's test_file module, we run some code
    # here which defines unittest TestCases to run the python tests over
    # PyQIODevice.

    @pytest.fixture(scope='session', autouse=True)
    def clean_up_python_testfile():
        """Clean up the python testfile after tests if tests didn't."""
        yield
        try:
            os.remove(test_file.TESTFN)
        except FileNotFoundError:
            pass

    class PyIODeviceTestMixin:

        """Some helper code to run Python's tests with PyQIODevice.

        Attributes:
            _data: A QByteArray containing the data in memory.
            f: The opened PyQIODevice.
        """

        def setUp(self):
            """Set up self.f using a PyQIODevice instead of a real file."""
            self._data = QByteArray()
            self.f = self.open(test_file.TESTFN, 'wb')

        def open(self, _fname, mode):
            """Open an in-memory PyQIODevice instead of a real file."""
            modes = {
                'wb': QIODevice.WriteOnly | QIODevice.Truncate,
                'w': QIODevice.WriteOnly | QIODevice.Text | QIODevice.Truncate,
                'rb': QIODevice.ReadOnly,
                'r': QIODevice.ReadOnly | QIODevice.Text,
            }
            try:
                qt_mode = modes[mode]
            except KeyError:
                raise ValueError("Invalid mode {}!".format(mode))
            f = QBuffer(self._data)
            f.open(qt_mode)
            qiodev = qtutils.PyQIODevice(f)
            # Make sure tests using name/mode don't blow up.
            qiodev.name = test_file.TESTFN
            qiodev.mode = mode
            # Create empty TESTFN file because the Python tests try to unlink
            # it.after the test.
            open(test_file.TESTFN, 'w', encoding='utf-8').close()
            return qiodev

    class PyAutoFileTests(PyIODeviceTestMixin, test_file.AutoFileTests,
                          unittest.TestCase):

        """Unittest testcase to run Python's AutoFileTests."""

        def testReadinto_text(self):
            """Skip this test as BufferedIOBase seems to fail it."""

    class PyOtherFileTests(PyIODeviceTestMixin, test_file.OtherFileTests,
                           unittest.TestCase):

        """Unittest testcase to run Python's OtherFileTests."""

        def testSetBufferSize(self):
            """Skip this test as setting buffer size is unsupported."""

        def testTruncateOnWindows(self):
            """Skip this test truncating is unsupported."""


class FailingQIODevice(QIODevice):

    """A fake QIODevice where reads/writes fail."""

    def isOpen(self):
        return True

    def isReadable(self):
        return True

    def isWritable(self):
        return True

    def write(self, _data):
        """Simulate failed write."""
        self.setErrorString("Writing failed")
        return -1

    def read(self, _maxsize):  # pylint: disable=useless-return
        """Simulate failed read."""
        self.setErrorString("Reading failed")
        return None

    def readAll(self):
        return self.read(0)

    def readLine(self, maxsize):
        return self.read(maxsize)


class TestPyQIODevice:

    """Tests for PyQIODevice."""

    @pytest.fixture
    def pyqiodev(self):
        """Fixture providing a PyQIODevice with a QByteArray to test."""
        data = QByteArray()
        f = QBuffer(data)
        qiodev = qtutils.PyQIODevice(f)
        yield qiodev
        qiodev.close()

    @pytest.fixture
    def pyqiodev_failing(self):
        """Fixture providing a PyQIODevice with a FailingQIODevice to test."""
        failing = FailingQIODevice()
        return qtutils.PyQIODevice(failing)

    @pytest.mark.parametrize('method, args', [
        ('seek', [0]),
        ('flush', []),
        ('isatty', []),
        ('readline', []),
        ('tell', []),
        ('write', [b'']),
        ('read', []),
    ])
    def test_closed_device(self, pyqiodev, method, args):
        """Test various methods with a closed device.

        Args:
            method: The name of the method to call.
            args: The arguments to pass.
        """
        func = getattr(pyqiodev, method)
        with pytest.raises(ValueError, match="IO operation on closed device!"):
            func(*args)

    @pytest.mark.parametrize('method', ['readline', 'read'])
    def test_unreadable(self, pyqiodev, method):
        """Test methods with an unreadable device.

        Args:
            method: The name of the method to call.
        """
        pyqiodev.open(QIODevice.WriteOnly)
        func = getattr(pyqiodev, method)
        with pytest.raises(OSError, match="Trying to read unreadable file!"):
            func()

    def test_unwritable(self, pyqiodev):
        """Test writing with a read-only device."""
        pyqiodev.open(QIODevice.ReadOnly)
        with pytest.raises(OSError, match="Trying to write to unwritable "
                                          "file!"):
            pyqiodev.write(b'')

    @pytest.mark.parametrize('data', [b'12345', b''])
    def test_len(self, pyqiodev, data):
        """Test len()/__len__.

        Args:
            data: The data to write before checking if the length equals
                  len(data).
        """
        pyqiodev.open(QIODevice.WriteOnly)
        pyqiodev.write(data)
        assert len(pyqiodev) == len(data)

    def test_failing_open(self, tmpdir):
        """Test open() which fails (because it's an existent directory)."""
        qf = QFile(str(tmpdir))
        dev = qtutils.PyQIODevice(qf)
        with pytest.raises(qtutils.QtOSError) as excinfo:
            dev.open(QIODevice.WriteOnly)
        assert excinfo.value.qt_errno == QFileDevice.OpenError
        assert dev.closed

    def test_fileno(self, pyqiodev):
        with pytest.raises(io.UnsupportedOperation):
            pyqiodev.fileno()

    @pytest.mark.qt_log_ignore('^QBuffer::seek: Invalid pos:')
    @pytest.mark.parametrize('offset, whence, pos, data, raising', [
        (0, io.SEEK_SET, 0, b'1234567890', False),
        (42, io.SEEK_SET, 0, b'1234567890', True),
        (8, io.SEEK_CUR, 8, b'90', False),
        (-5, io.SEEK_CUR, 0, b'1234567890', True),
        (-2, io.SEEK_END, 8, b'90', False),
        (2, io.SEEK_END, 0, b'1234567890', True),
        (0, io.SEEK_END, 10, b'', False),
    ])
    def test_seek_tell(self, pyqiodev, offset, whence, pos, data, raising):
        """Test seek() and tell().

        The initial position when these tests run is 0.

        Args:
            offset: The offset to pass to .seek().
            whence: The whence argument to pass to .seek().
            pos: The expected position after seeking.
            data: The expected data to read after seeking.
            raising: Whether seeking should raise OSError.
        """
        with pyqiodev.open(QIODevice.WriteOnly) as f:
            f.write(b'1234567890')
        pyqiodev.open(QIODevice.ReadOnly)
        if raising:
            with pytest.raises(OSError, match="seek failed!"):
                pyqiodev.seek(offset, whence)
        else:
            pyqiodev.seek(offset, whence)
        assert pyqiodev.tell() == pos
        assert pyqiodev.read() == data

    def test_seek_unsupported(self, pyqiodev):
        """Test seeking with unsupported whence arguments."""
        # pylint: disable=no-member,useless-suppression
        if hasattr(os, 'SEEK_HOLE'):
            whence = os.SEEK_HOLE
        elif hasattr(os, 'SEEK_DATA'):
            whence = os.SEEK_DATA
        # pylint: enable=no-member,useless-suppression
        else:
            pytest.skip("Needs os.SEEK_HOLE or os.SEEK_DATA available.")
        pyqiodev.open(QIODevice.ReadOnly)
        with pytest.raises(io.UnsupportedOperation):
            pyqiodev.seek(0, whence)

    @pytest.mark.flaky()
    def test_qprocess(self, py_proc):
        """Test PyQIODevice with a QProcess which is non-sequential.

        This also verifies seek() and tell() behave as expected.
        """
        proc = QProcess()
        proc.start(*py_proc('print("Hello World")'))
        dev = qtutils.PyQIODevice(proc)
        assert not dev.closed
        with pytest.raises(OSError, match='Random access not allowed!'):
            dev.seek(0)
        with pytest.raises(OSError, match='Random access not allowed!'):
            dev.tell()
        proc.waitForFinished(1000)
        proc.kill()
        assert bytes(dev.read()).rstrip() == b'Hello World'

    def test_truncate(self, pyqiodev):
        with pytest.raises(io.UnsupportedOperation):
            pyqiodev.truncate()

    def test_closed(self, pyqiodev):
        """Test the closed attribute."""
        assert pyqiodev.closed
        pyqiodev.open(QIODevice.ReadOnly)
        assert not pyqiodev.closed
        pyqiodev.close()
        assert pyqiodev.closed

    def test_contextmanager(self, pyqiodev):
        """Make sure using the PyQIODevice as context manager works."""
        assert pyqiodev.closed
        with pyqiodev.open(QIODevice.ReadOnly) as f:
            assert not f.closed
            assert f is pyqiodev
        assert pyqiodev.closed

    def test_flush(self, pyqiodev):
        """Make sure flushing doesn't raise an exception."""
        pyqiodev.open(QIODevice.WriteOnly)
        pyqiodev.write(b'test')
        pyqiodev.flush()

    @pytest.mark.parametrize('method, ret', [
        ('isatty', False),
        ('seekable', True),
    ])
    def test_bools(self, method, ret, pyqiodev):
        """Make sure simple bool arguments return the right thing.

        Args:
            method: The name of the method to call.
            ret: The return value we expect.
        """
        pyqiodev.open(QIODevice.WriteOnly)
        func = getattr(pyqiodev, method)
        assert func() == ret

    @pytest.mark.parametrize('mode, readable, writable', [
        (QIODevice.ReadOnly, True, False),
        (QIODevice.ReadWrite, True, True),
        (QIODevice.WriteOnly, False, True),
    ])
    def test_readable_writable(self, mode, readable, writable, pyqiodev):
        """Test readable() and writable().

        Args:
            mode: The mode to open the PyQIODevice in.
            readable:  Whether the device should be readable.
            writable:  Whether the device should be writable.
        """
        assert not pyqiodev.readable()
        assert not pyqiodev.writable()
        pyqiodev.open(mode)
        assert pyqiodev.readable() == readable
        assert pyqiodev.writable() == writable

    @pytest.mark.parametrize('size, chunks', [
        (-1, [b'one\n', b'two\n', b'three', b'']),
        (0, [b'', b'', b'', b'']),
        (2, [b'on', b'e\n', b'tw', b'o\n', b'th', b're', b'e']),
        (10, [b'one\n', b'two\n', b'three', b'']),
    ])
    def test_readline(self, size, chunks, pyqiodev):
        """Test readline() with different sizes.

        Args:
            size: The size to pass to readline()
            chunks: A list of expected chunks to read.
        """
        with pyqiodev.open(QIODevice.WriteOnly) as f:
            f.write(b'one\ntwo\nthree')
        pyqiodev.open(QIODevice.ReadOnly)
        for i, chunk in enumerate(chunks, start=1):
            print("Expecting chunk {}: {!r}".format(i, chunk))
            assert pyqiodev.readline(size) == chunk

    def test_write(self, pyqiodev):
        """Make sure writing and re-reading works."""
        with pyqiodev.open(QIODevice.WriteOnly) as f:
            f.write(b'foo\n')
            f.write(b'bar\n')
        pyqiodev.open(QIODevice.ReadOnly)
        assert pyqiodev.read() == b'foo\nbar\n'

    def test_write_error(self, pyqiodev_failing):
        """Test writing with FailingQIODevice."""
        with pytest.raises(OSError, match="Writing failed"):
            pyqiodev_failing.write(b'x')

    @pytest.mark.posix
    @pytest.mark.skipif(not os.path.exists('/dev/full'),
                        reason="Needs /dev/full.")
    def test_write_error_real(self):
        """Test a real write error with /dev/full on supported systems."""
        qf = QFile('/dev/full')
        qf.open(QIODevice.WriteOnly | QIODevice.Unbuffered)
        dev = qtutils.PyQIODevice(qf)
        with pytest.raises(OSError, match='No space left on device'):
            dev.write(b'foo')
        qf.close()

    @pytest.mark.parametrize('size, chunks', [
        (-1, [b'1234567890']),
        (0, [b'']),
        (3, [b'123', b'456', b'789', b'0']),
        (20, [b'1234567890'])
    ])
    def test_read(self, size, chunks, pyqiodev):
        """Test reading with different sizes.

        Args:
            size: The size to pass to read()
            chunks: A list of expected data chunks.
        """
        with pyqiodev.open(QIODevice.WriteOnly) as f:
            f.write(b'1234567890')
        pyqiodev.open(QIODevice.ReadOnly)
        for i, chunk in enumerate(chunks):
            print("Expecting chunk {}: {!r}".format(i, chunk))
            assert pyqiodev.read(size) == chunk

    @pytest.mark.parametrize('method, args', [
        ('read', []),
        ('read', [5]),
        ('readline', []),
        ('readline', [5]),
    ])
    def test_failing_reads(self, method, args, pyqiodev_failing):
        """Test reading with a FailingQIODevice.

        Args:
            method: The name of the method to call.
            args: A list of arguments to pass.
        """
        func = getattr(pyqiodev_failing, method)
        with pytest.raises(OSError, match='Reading failed'):
            func(*args)


@pytest.mark.usefixtures('qapp')
class TestEventLoop:

    """Tests for EventLoop.

    Attributes:
        loop: The EventLoop we're testing.
    """

    # pylint: disable=attribute-defined-outside-init

    def _assert_executing(self):
        """Slot which gets called from timers to be sure the loop runs."""
        assert self.loop._executing

    def _double_exec(self):
        """Slot which gets called from timers to assert double-exec fails."""
        with pytest.raises(AssertionError):
            self.loop.exec_()

    def test_normal_exec(self):
        """Test exec_ without double-executing."""
        self.loop = qtutils.EventLoop()
        QTimer.singleShot(100, self._assert_executing)
        QTimer.singleShot(200, self.loop.quit)
        self.loop.exec_()
        assert not self.loop._executing

    def test_double_exec(self):
        """Test double-executing."""
        self.loop = qtutils.EventLoop()
        QTimer.singleShot(100, self._assert_executing)
        QTimer.singleShot(200, self._double_exec)
        QTimer.singleShot(300, self._assert_executing)
        QTimer.singleShot(400, self.loop.quit)
        self.loop.exec_()
        assert not self.loop._executing
