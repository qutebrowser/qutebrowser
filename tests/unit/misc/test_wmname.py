# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import os
import sys
import socket
import ctypes
import ctypes.util
import unittest.mock
from collections.abc import Iterator

import pytest
import pytest_mock
import pytestqt.qtbot
from qutebrowser.qt.widgets import QApplication, QWidget

from qutebrowser.misc import wmname


def test_load_libwayland_client():
    """Test loading the Wayland client library, which might or might not exist."""
    try:
        wmname._load_libwayland_client()
    except wmname.Error:
        pass


def test_load_libwayland_client_error(mocker: pytest_mock.MockerFixture):
    """Test that an error in loading the Wayland client library raises an error."""
    mocker.patch("ctypes.CDLL", side_effect=OSError("Library not found"))

    with pytest.raises(wmname.Error, match="Failed to load libwayland-client"):
        wmname._load_libwayland_client()


@pytest.fixture
def sock() -> Iterator[socket.socket]:
    """Fixture to create a Unix domain socket."""
    parent_sock, child_sock = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
    yield parent_sock
    parent_sock.close()
    child_sock.close()


@pytest.mark.linux
def test_pid_from_fd(sock: socket.socket):
    assert wmname._pid_from_fd(sock.fileno()) == os.getpid()


@pytest.mark.skipif(
    not hasattr(socket, "SO_PEERCRED"), reason="socket.SO_PEERCRED not available"
)
def test_pid_from_fd_invalid():
    """Test that an invalid file descriptor raises an error."""
    with pytest.raises(
        wmname.Error,
        match=r"Error creating socket for fd -1: \[Errno 9\] Bad file descriptor",
    ):
        wmname._pid_from_fd(-1)


@pytest.mark.linux
def test_pid_from_fd_getsockopt_error(
    sock: socket.socket, mocker: pytest_mock.MockerFixture
):
    """Test that an error in getsockopt raises an error."""
    mocker.patch.object(
        socket.socket, "getsockopt", side_effect=OSError("Mocked error")
    )

    with pytest.raises(wmname.Error, match="Error getting SO_PEERCRED for fd"):
        wmname._pid_from_fd(sock.fileno())


def test_pid_from_fd_no_so_peercred(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delattr(socket, "SO_PEERCRED", raising=False)
    with pytest.raises(wmname.Error, match=r"Missing socket\.SO_PEERCRED"):
        wmname._pid_from_fd(-1)


@pytest.mark.linux
def test_process_name_from_pid():
    """Test getting the process name from a PID."""
    pid = os.getpid()
    name = wmname._process_name_from_pid(pid)
    assert os.path.basename(name.split()[0]) == os.path.basename(sys.executable)


def test_process_name_from_pid_invalid():
    """Test that an invalid PID raises an error."""
    with pytest.raises(wmname.Error, match=r"Error opening .proc.-1.cmdline"):
        wmname._process_name_from_pid(-1)


@pytest.fixture
def libwayland_client_mock(mocker: pytest_mock.MockerFixture) -> None:
    """Mock the libwayland-client library."""
    return mocker.Mock()


@pytest.fixture
def fake_wayland_display() -> wmname._WaylandDisplay:
    return wmname._WaylandDisplay(ctypes.pointer(wmname._WaylandDisplayStruct()))


def test_wayland_display(
    libwayland_client_mock: unittest.mock.Mock,
    fake_wayland_display: wmname._WaylandDisplay,
):
    """Test getting the Wayland display."""
    libwayland_client_mock.wl_display_connect.return_value = fake_wayland_display

    with wmname._wayland_display(libwayland_client_mock):
        pass

    libwayland_client_mock.wl_display_connect.assert_called_once_with(None)
    libwayland_client_mock.wl_display_disconnect.assert_called_once_with(
        fake_wayland_display
    )


def test_wayland_display_error(libwayland_client_mock: unittest.mock.Mock):
    """Test that an error in getting the Wayland display raises an error."""
    libwayland_client_mock.wl_display_connect.return_value = ctypes.c_void_p(0)

    with pytest.raises(wmname.Error, match="Can't connect to display"):
        with wmname._wayland_display(libwayland_client_mock):
            pass

    libwayland_client_mock.wl_display_disconnect.assert_not_called()  # Not called on error


def test_wayland_get_fd(
    libwayland_client_mock: unittest.mock.Mock,
    fake_wayland_display: wmname._WaylandDisplay,
):
    """Test getting the file descriptor from a Wayland display."""
    libwayland_client_mock.wl_display_get_fd.return_value = 42

    fd = wmname._wayland_get_fd(libwayland_client_mock, fake_wayland_display)
    assert fd == 42

    libwayland_client_mock.wl_display_get_fd.assert_called_once_with(
        fake_wayland_display
    )


def test_wayland_get_fd_error(
    libwayland_client_mock: unittest.mock.Mock,
    fake_wayland_display: wmname._WaylandDisplay,
):
    """Test that an error in getting the file descriptor raises an error."""
    libwayland_client_mock.wl_display_get_fd.return_value = -1

    with pytest.raises(
        wmname.Error, match="Failed to get Wayland display file descriptor: -1"
    ):
        wmname._wayland_get_fd(libwayland_client_mock, fake_wayland_display)

    libwayland_client_mock.wl_display_get_fd.assert_called_once_with(
        fake_wayland_display
    )


def test_wayland_real():
    """Test getting the Wayland window manager name."""
    try:
        name = wmname.wayland_compositor_name()
    except wmname.Error:
        return

    assert isinstance(name, str)
    assert name


def test_load_xlib():
    """Test loading Xlib, which might or might not exist."""
    try:
        wmname._x11_load_lib()
    except wmname.Error:
        pass


def test_load_xlib_not_found(monkeypatch: pytest.MonkeyPatch):
    """Test loading Xlib simulating a missing library."""
    monkeypatch.setattr(ctypes.util, "find_library", lambda x: None)

    with pytest.raises(wmname.Error, match="X11 library not found"):
        wmname._x11_load_lib()


def test_load_xlib_error(mocker: pytest_mock.MockerFixture):
    """Test that an error in loading Xlib raises an error."""
    mocker.patch.object(ctypes.util, "find_library", return_value="libX11.so.6")
    mocker.patch.object(ctypes, "CDLL", side_effect=OSError("Failed to load library"))

    with pytest.raises(
        wmname.Error, match="Failed to load X11 library: Failed to load library"
    ):
        wmname._x11_load_lib()


@pytest.fixture
def xlib_mock(mocker: pytest_mock.MockerFixture) -> None:
    """Mock the XLib library."""
    return mocker.Mock()


@pytest.fixture
def fake_x11_display() -> wmname._X11Display:
    return wmname._X11Display(ctypes.pointer(wmname._X11DisplayStruct()))


def test_x11_display(
    xlib_mock: unittest.mock.Mock,
    fake_x11_display: wmname._X11Display,
):
    """Test getting the X11 display."""
    xlib_mock.XOpenDisplay.return_value = fake_x11_display

    with wmname._x11_open_display(xlib_mock):
        pass

    xlib_mock.XOpenDisplay.assert_called_once_with(None)
    xlib_mock.XCloseDisplay.assert_called_once_with(fake_x11_display)


def test_x11_display_error(xlib_mock: unittest.mock.Mock):
    """Test that an error in getting the X11 display raises an error."""
    xlib_mock.XOpenDisplay.return_value = ctypes.c_void_p(0)

    with pytest.raises(wmname.Error, match="Cannot open display"):
        with wmname._x11_open_display(xlib_mock):
            pass

    xlib_mock.XCloseDisplay.assert_not_called()  # Not called on error


def test_x11_intern_atom(
    xlib_mock: unittest.mock.Mock,
    fake_x11_display: wmname._X11Display,
):
    """Test getting an interned atom from X11."""
    atom_name = b"_NET_WM_NAME"
    atom = 12345
    xlib_mock.XInternAtom.return_value = atom

    result = wmname._x11_intern_atom(xlib_mock, fake_x11_display, atom_name)
    assert result == atom

    xlib_mock.XInternAtom.assert_called_once_with(
        fake_x11_display,
        atom_name,
        True,  # don't create if not found
    )


def test_x11_intern_atom_error(
    xlib_mock: unittest.mock.Mock,
    fake_x11_display: wmname._X11Display,
):
    """Test that an error in getting an interned atom raises an error."""
    xlib_mock.XInternAtom.return_value = 0

    with pytest.raises(wmname.Error, match="Failed to intern atom: b'_NET_WM_NAME'"):
        wmname._x11_intern_atom(xlib_mock, fake_x11_display, b"_NET_WM_NAME")

    xlib_mock.XInternAtom.assert_called_once_with(
        fake_x11_display,
        b"_NET_WM_NAME",
        True,  # don't create if not found
    )


def test_x11_get_wm_name(
    qapp: QApplication,
    qtbot: pytestqt.qtbot.QtBot,
) -> None:
    """Test getting a property from X11.

    This is difficult to mock (as it involves a C layer via ctypes with return
    arguments), so we instead try getting data from a real window.
    """
    if qapp.platformName() != "xcb":
        pytest.skip("This test only works on X11 (xcb) platforms")

    w = QWidget()
    qtbot.add_widget(w)
    w.setWindowTitle("Test Window")

    xlib = wmname._x11_load_lib()
    with wmname._x11_open_display(xlib) as display:
        atoms = wmname._X11Atoms(
            NET_SUPPORTING_WM_CHECK=-1,
            NET_WM_NAME=wmname._x11_intern_atom(xlib, display, b"_NET_WM_NAME"),
            UTF8_STRING=wmname._x11_intern_atom(xlib, display, b"UTF8_STRING"),
        )
        window = wmname._X11Window(int(w.winId()))
        name = wmname._x11_get_wm_name(xlib, display, atoms=atoms, wm_window=window)

    assert name == "Test Window"


def test_x11_real():
    try:
        name = wmname.x11_wm_name()
    except wmname.Error:
        return

    assert isinstance(name, str)
    assert name
