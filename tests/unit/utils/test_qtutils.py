# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2016 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
import sys
import operator
import os.path
try:
    # pylint: disable=no-name-in-module,useless-suppression
    from test import test_file
except ImportError:
    # Debian patches Python to remove the tests...
    test_file = None

import pytest
import unittest
import unittest.mock
from PyQt5.QtCore import (QDataStream, QPoint, QUrl, QByteArray, QIODevice,
                          QTimer, QBuffer, QFile, QProcess, QFileDevice)

from qutebrowser import qutebrowser
from qutebrowser.utils import qtutils
import overflow_test_cases


@pytest.mark.parametrize('qversion, version, op, expected', [
    ('5.4.0', '5.4.0', operator.ge, True),
    ('5.4.0', '5.4.0', operator.eq, True),
    ('5.4.0', '5.4', operator.eq, True),
    ('5.4.1', '5.4', operator.ge, True),
    ('5.3.2', '5.4', operator.ge, False),
    ('5.3.0', '5.3.2', operator.ge, False),
])
def test_version_check(monkeypatch, qversion, version, op, expected):
    """Test for version_check().

    Args:
        monkeypatch: The pytest monkeypatch fixture.
        qversion: The version to set as fake qVersion().
        version: The version to compare with.
        op: The operator to use when comparing.
        expected: The expected result.
    """
    monkeypatch.setattr('qutebrowser.utils.qtutils.qVersion', lambda: qversion)
    assert qtutils.version_check(version, op) == expected


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


class TestGetQtArgs:

    """Tests for get_args."""

    @pytest.fixture
    def parser(self, mocker):
        """Fixture to provide an argparser.

        Monkey-patches .exit() of the argparser so it doesn't exit on errors.
        """
        parser = qutebrowser.get_argparser()
        mocker.patch.object(parser, 'exit', side_effect=Exception)
        return parser

    @pytest.mark.parametrize('args, expected', [
        # No Qt arguments
        (['--debug'], [sys.argv[0]]),
        # Qt flag
        (['--debug', '--qt-reverse', '--nocolor'], [sys.argv[0], '-reverse']),
        # Qt argument with value
        (['--qt-stylesheet', 'foo'], [sys.argv[0], '-stylesheet', 'foo']),
    ])
    def test_qt_args(self, args, expected, parser):
        """Test commandline with no Qt arguments given."""
        parsed = parser.parse_args(args)
        assert qtutils.get_args(parsed) == expected

    def test_qt_both(self, parser):
        """Test commandline with a Qt argument and flag."""
        args = parser.parse_args(['--qt-stylesheet', 'foobar', '--qt-reverse'])
        qt_args = qtutils.get_args(args)
        assert qt_args[0] == sys.argv[0]
        assert '-reverse' in qt_args
        assert '-stylesheet' in qt_args
        assert 'foobar' in qt_args


@pytest.mark.parametrize('os_name, qversion, expected', [
    ('linux', '5.2.1', True),  # unaffected OS
    ('linux', '5.4.1', True),  # unaffected OS
    ('nt', '5.2.1', False),
    ('nt', '5.3.0', True),  # unaffected Qt version
    ('nt', '5.4.1', True),  # unaffected Qt version
])
def test_check_print_compat(os_name, qversion, expected, monkeypatch):
    """Test check_print_compat.

    Args:
        os_name: The fake os.name to set.
        qversion: The fake qVersion() to set.
        expected: The expected return value.
    """
    monkeypatch.setattr('qutebrowser.utils.qtutils.os.name', os_name)
    monkeypatch.setattr('qutebrowser.utils.qtutils.qVersion', lambda: qversion)
    assert qtutils.check_print_compat() == expected


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
        else:
            return self._error

    def isValid(self):
        return self._valid

    def isNull(self):
        return self._null


@pytest.mark.parametrize('func_name, obj, raising, exc_reason, exc_str', [
    # ensure_valid, good examples
    ('ensure_valid', QtObject(valid=True, null=True), False, None, None),
    ('ensure_valid', QtObject(valid=True, null=False), False, None, None),
    # ensure_valid, bad examples
    ('ensure_valid', QtObject(valid=False, null=True), True, None,
     '<QtObject> is not valid'),
    ('ensure_valid', QtObject(valid=False, null=False), True, None,
     '<QtObject> is not valid'),
    ('ensure_valid', QtObject(valid=False, null=True, error='Test'), True,
     'Test', '<QtObject> is not valid: Test'),
    # ensure_not_null, good examples
    ('ensure_not_null', QtObject(valid=True, null=False), False, None, None),
    ('ensure_not_null', QtObject(valid=False, null=False), False, None, None),
    # ensure_not_null, bad examples
    ('ensure_not_null', QtObject(valid=True, null=True), True, None,
     '<QtObject> is null'),
    ('ensure_not_null', QtObject(valid=False, null=True), True, None,
     '<QtObject> is null'),
    ('ensure_not_null', QtObject(valid=False, null=True, error='Test'), True,
     'Test', '<QtObject> is null: Test'),
])
def test_ensure(func_name, obj, raising, exc_reason, exc_str):
    """Test ensure_valid and ensure_not_null.

    The function is parametrized as they do nearly the same.

    Args:
        func_name: The name of the function to call.
        obj: The object to test with.
        raising: Whether QtValueError is expected to be raised.
        exc_reason: The expected .reason attribute of the exception.
        exc_str: The expected string of the exception.
    """
    func = getattr(qtutils, func_name)
    if raising:
        with pytest.raises(qtutils.QtValueError) as excinfo:
            func(obj)
        assert excinfo.value.reason == exc_reason
        assert str(excinfo.value) == exc_str
    else:
        func(obj)


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
        with pytest.raises(OSError) as excinfo:
            qtutils.check_qdatastream(stream)
        assert str(excinfo.value) == message
    else:
        qtutils.check_qdatastream(stream)


def test_qdatastream_status_count():
    """Make sure no new members are added to QDataStream.Status."""
    values = vars(QDataStream).values()
    status_vals = [e for e in values if isinstance(e, QDataStream.Status)]
    assert len(status_vals) == 4


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

        with pytest.raises(OSError) as excinfo:
            qtutils.serialize_stream(stream_mock, QPoint())

        assert not stream_mock.__lshift__.called
        assert str(excinfo.value) == "The data stream has read corrupt data."

    def test_serialize_post_error_mock(self, stream_mock):
        """Test serialize_stream with an error while serializing."""
        obj = QPoint()
        stream_mock.__lshift__.side_effect = lambda _other: self._set_status(
            stream_mock, QDataStream.ReadCorruptData)

        with pytest.raises(OSError) as excinfo:
            qtutils.serialize_stream(stream_mock, obj)

        assert stream_mock.__lshift__.called_once_with(obj)
        assert str(excinfo.value) == "The data stream has read corrupt data."

    def test_deserialize_pre_error_mock(self, stream_mock):
        """Test deserialize_stream with an error already set."""
        stream_mock.status.return_value = QDataStream.ReadCorruptData

        with pytest.raises(OSError) as excinfo:
            qtutils.deserialize_stream(stream_mock, QPoint())

        assert not stream_mock.__rshift__.called
        assert str(excinfo.value) == "The data stream has read corrupt data."

    def test_deserialize_post_error_mock(self, stream_mock):
        """Test deserialize_stream with an error while deserializing."""
        obj = QPoint()
        stream_mock.__rshift__.side_effect = lambda _other: self._set_status(
            stream_mock, QDataStream.ReadCorruptData)

        with pytest.raises(OSError) as excinfo:
            qtutils.deserialize_stream(stream_mock, obj)

        assert stream_mock.__rshift__.called_once_with(obj)
        assert str(excinfo.value) == "The data stream has read corrupt data."

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

    @pytest.mark.qt_log_ignore('^QIODevice::write.*: ReadOnly device',
                               extend=True)
    def test_serialize_readonly_stream(self):
        """Test serialize_stream with a read-only stream."""
        data = QByteArray()
        stream = QDataStream(data, QIODevice.ReadOnly)
        with pytest.raises(OSError) as excinfo:
            qtutils.serialize_stream(stream, QPoint())
        assert str(excinfo.value) == ("The data stream cannot write to the "
                                      "underlying device.")

    @pytest.mark.qt_log_ignore('QIODevice::read.*: WriteOnly device',
                               extend=True)
    def test_deserialize_writeonly_stream(self):
        """Test deserialize_stream with a write-only stream."""
        data = QByteArray()
        obj = QPoint()
        stream = QDataStream(data, QIODevice.WriteOnly)
        with pytest.raises(OSError) as excinfo:
            qtutils.deserialize_stream(stream, obj)
        assert str(excinfo.value) == ("The data stream has read past the end "
                                      "of the data in the underlying device.")


class SavefileTestException(Exception):

    """Exception raised in TestSavefileOpen for testing."""

    pass


@pytest.mark.usefixtures('qapp')
class TestSavefileOpen:

    """Tests for savefile_open."""

    ## Tests with a mock testing that the needed methods are called.

    @pytest.yield_fixture
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

        with pytest.raises(OSError) as excinfo:
            with qtutils.savefile_open('filename'):
                pass

        qsavefile_mock.open.assert_called_once_with(QIODevice.WriteOnly)
        qsavefile_mock.cancelWriting.assert_called_once_with()
        assert str(excinfo.value) == "Hello World"

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

        with pytest.raises(OSError) as excinfo:
            with qtutils.savefile_open('filename'):
                pass

        qsavefile_mock.open.assert_called_once_with(QIODevice.WriteOnly)
        assert not qsavefile_mock.cancelWriting.called
        assert not qsavefile_mock.errorString.called
        assert str(excinfo.value) == "Commit failed!"

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
        errors = ["Filename refers to a directory",  # Qt >= 5.4
                  "Commit failed!"]  # older Qt versions
        assert str(excinfo.value) in errors
        assert tmpdir.listdir() == [filename]

    def test_failing_flush(self, tmpdir):
        """Test with the file being closed before flushing."""
        filename = tmpdir / 'foo'
        with pytest.raises(ValueError) as excinfo:
            with qtutils.savefile_open(str(filename), binary=True) as f:
                f.write(b'Hello')
                f.dev.commit()  # provoke failing flush

        assert str(excinfo.value) == "IO operation on closed device!"
        assert tmpdir.listdir() == [filename]

    def test_failing_commit(self, tmpdir):
        """Test with the file being closed before committing."""
        filename = tmpdir / 'foo'
        with pytest.raises(OSError) as excinfo:
            with qtutils.savefile_open(str(filename), binary=True) as f:
                f.write(b'Hello')
                f.dev.cancelWriting()  # provoke failing commit

        assert str(excinfo.value) == "Commit failed!"
        assert tmpdir.listdir() == []

    def test_line_endings(self, tmpdir):
        """Make sure line endings are translated correctly.

        See https://github.com/The-Compiler/qutebrowser/issues/309
        """
        filename = tmpdir / 'foo'
        with qtutils.savefile_open(str(filename)) as f:
            f.write('foo\nbar\nbaz')
        data = filename.read_binary()
        if os.name == 'nt':
            assert data == b'foo\r\nbar\r\nbaz'
        else:
            assert data == b'foo\nbar\nbaz'


@pytest.mark.parametrize('orgname, expected', [(None, ''), ('test', 'test')])
def test_unset_organization(qapp, orgname, expected):
    """Test unset_organization.

    Args:
        orgname: The organizationName to set initially.
        expected: The organizationName which is expected when reading back.
    """
    qapp.setOrganizationName(orgname)
    assert qapp.organizationName() == expected  # sanity check
    with qtutils.unset_organization():
        assert qapp.organizationName() == ''
    assert qapp.organizationName() == expected


if test_file is not None and sys.platform != 'darwin':
    # If we were able to import Python's test_file module, we run some code
    # here which defines unittest TestCases to run the python tests over
    # PyQIODevice.

    # Those are not run on OS X because that seems to cause a hang sometimes.

    @pytest.yield_fixture(scope='session', autouse=True)
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
            pass

    class PyOtherFileTests(PyIODeviceTestMixin, test_file.OtherFileTests,
                           unittest.TestCase):

        """Unittest testcase to run Python's OtherFileTests."""

        def testSetBufferSize(self):
            """Skip this test as setting buffer size is unsupported."""
            pass

        def testTruncateOnWindows(self):
            """Skip this test truncating is unsupported."""
            pass


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

    def read(self, _maxsize):
        """Simulate failed read."""
        self.setErrorString("Reading failed")
        return None

    def readAll(self):
        return self.read(0)

    def readLine(self, maxsize):
        return self.read(maxsize)


class TestPyQIODevice:

    """Tests for PyQIODevice."""

    @pytest.yield_fixture
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
        with pytest.raises(ValueError) as excinfo:
            func(*args)
        assert str(excinfo.value) == "IO operation on closed device!"

    @pytest.mark.parametrize('method', ['readline', 'read'])
    def test_unreadable(self, pyqiodev, method):
        """Test methods with an unreadable device.

        Args:
            method: The name of the method to call.
        """
        pyqiodev.open(QIODevice.WriteOnly)
        func = getattr(pyqiodev, method)
        with pytest.raises(OSError) as excinfo:
            func()
        assert str(excinfo.value) == "Trying to read unreadable file!"

    def test_unwritable(self, pyqiodev):
        """Test writing with a read-only device."""
        pyqiodev.open(QIODevice.ReadOnly)
        with pytest.raises(OSError) as excinfo:
            pyqiodev.write(b'')
        assert str(excinfo.value) == "Trying to write to unwritable file!"

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

    @pytest.mark.qt_log_ignore('^QBuffer::seek: Invalid pos:', extend=True)
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
            with pytest.raises(OSError) as excinfo:
                pyqiodev.seek(offset, whence)
            assert str(excinfo.value) == "seek failed!"
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
        else:
            pytest.skip("Needs os.SEEK_HOLE or os.SEEK_DATA available.")
        pyqiodev.open(QIODevice.ReadOnly)
        with pytest.raises(io.UnsupportedOperation):
            pyqiodev.seek(0, whence)

    @pytest.mark.flaky(reruns=1)
    def test_qprocess(self, py_proc):
        """Test PyQIODevice with a QProcess which is non-sequential.

        This also verifies seek() and tell() behave as expected.
        """
        proc = QProcess()
        proc.start(*py_proc('print("Hello World")'))
        dev = qtutils.PyQIODevice(proc)
        assert not dev.closed
        with pytest.raises(OSError) as excinfo:
            dev.seek(0)
        assert str(excinfo.value) == 'Random access not allowed!'
        with pytest.raises(OSError) as excinfo:
            dev.tell()
        assert str(excinfo.value) == 'Random access not allowed!'
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
        with pytest.raises(OSError) as excinfo:
            pyqiodev_failing.write(b'x')
        assert str(excinfo.value) == 'Writing failed'

    @pytest.mark.posix
    @pytest.mark.skipif(not os.path.exists('/dev/full'),
                        reason="Needs /dev/full.")
    def test_write_error_real(self):
        """Test a real write error with /dev/full on supported systems."""
        qf = QFile('/dev/full')
        qf.open(QIODevice.WriteOnly | QIODevice.Unbuffered)
        dev = qtutils.PyQIODevice(qf)
        with pytest.raises(OSError) as excinfo:
            dev.write(b'foo')
        qf.close()
        assert str(excinfo.value) == 'No space left on device'

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
        with pytest.raises(OSError) as excinfo:
            func(*args)
        assert str(excinfo.value) == 'Reading failed'


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
