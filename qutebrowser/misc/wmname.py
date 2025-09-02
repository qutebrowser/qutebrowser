# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Utilities to get the name of the window manager (X11) / compositor (Wayland)."""

from typing import NewType
from collections.abc import Iterator
import ctypes
import socket
import struct
import pathlib
import dataclasses
import contextlib
import ctypes.util


class Error(Exception):
    """Base class for errors in this module."""


class _WaylandDisplayStruct(ctypes.Structure):
    pass


_WaylandDisplay = NewType("_WaylandDisplay", "ctypes._Pointer[_WaylandDisplayStruct]")


def _load_libwayland_client() -> ctypes.CDLL:
    """Load the Wayland client library."""
    try:
        return ctypes.CDLL("libwayland-client.so")
    except OSError as e:
        raise Error(f"Failed to load libwayland-client: {e}")


def _pid_from_fd(fd: int) -> int:
    """Get the process ID from a file descriptor using SO_PEERCRED.

    https://stackoverflow.com/a/35827184
    """
    if not hasattr(socket, "SO_PEERCRED"):
        raise Error("Missing socket.SO_PEERCRED")

    # struct ucred {
    #    pid_t pid;
    #    uid_t uid;
    #    gid_t gid;
    # };  // where all of those are integers
    ucred_format = "3i"
    ucred_size = struct.calcsize(ucred_format)

    try:
        sock = socket.fromfd(fd, socket.AF_UNIX, socket.SOCK_STREAM)
    except OSError as e:
        raise Error(f"Error creating socket for fd {fd}: {e}")

    try:
        ucred = sock.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, ucred_size)
    except OSError as e:
        raise Error(f"Error getting SO_PEERCRED for fd {fd}: {e}")
    finally:
        sock.close()

    pid, _uid, _gid = struct.unpack(ucred_format, ucred)
    return pid


def _process_name_from_pid(pid: int) -> str:
    """Get the process name from a PID by reading /proc/[pid]/cmdline."""
    proc_path = pathlib.Path(f"/proc/{pid}/cmdline")
    try:
        return proc_path.read_text(encoding="utf-8").replace("\0", " ").strip()
    except OSError as e:
        raise Error(f"Error opening {proc_path}: {e}")


@contextlib.contextmanager
def _wayland_display(wayland_client: ctypes.CDLL) -> Iterator[_WaylandDisplay]:
    """Context manager to connect to a Wayland display."""
    wayland_client.wl_display_connect.argtypes = [ctypes.c_char_p]  # name
    wayland_client.wl_display_connect.restype = ctypes.POINTER(_WaylandDisplayStruct)

    wayland_client.wl_display_disconnect.argtypes = [
        ctypes.POINTER(_WaylandDisplayStruct)
    ]
    wayland_client.wl_display_disconnect.restype = None

    display = wayland_client.wl_display_connect(None)
    if not display:
        raise Error("Can't connect to display")

    try:
        yield display
    finally:
        wayland_client.wl_display_disconnect(display)


def _wayland_get_fd(wayland_client: ctypes.CDLL, display: _WaylandDisplay) -> int:
    """Get the file descriptor for the Wayland display."""
    wayland_client.wl_display_get_fd.argtypes = [ctypes.POINTER(_WaylandDisplayStruct)]
    wayland_client.wl_display_get_fd.restype = ctypes.c_int

    fd = wayland_client.wl_display_get_fd(display)
    if fd < 0:
        raise Error(f"Failed to get Wayland display file descriptor: {fd}")
    return fd


def wayland_compositor_name() -> str:
    """Get the name of the running Wayland compositor.

    Approach based on:
    https://stackoverflow.com/questions/69302630/wayland-client-get-compositor-name
    """
    wayland_client = _load_libwayland_client()
    with _wayland_display(wayland_client) as display:
        fd = _wayland_get_fd(wayland_client, display)
        pid = _pid_from_fd(fd)
        process_name = _process_name_from_pid(pid)
        return process_name


@dataclasses.dataclass
class _X11Atoms:
    NET_SUPPORTING_WM_CHECK: int
    NET_WM_NAME: int
    UTF8_STRING: int


class _X11DisplayStruct(ctypes.Structure):
    pass


_X11Display = NewType("_X11Display", "ctypes._Pointer[_X11DisplayStruct]")
_X11Window = NewType("_X11Window", int)


def _x11_load_lib() -> ctypes.CDLL:
    """Load the X11 library."""
    lib = ctypes.util.find_library("X11")
    if lib is None:
        raise Error("X11 library not found")

    try:
        return ctypes.CDLL(lib)
    except OSError as e:
        raise Error(f"Failed to load X11 library: {e}")


@contextlib.contextmanager
def _x11_open_display(xlib: ctypes.CDLL) -> Iterator[_X11Display]:
    """Open a connection to the X11 display."""
    xlib.XOpenDisplay.argtypes = [ctypes.c_char_p]
    xlib.XOpenDisplay.restype = ctypes.POINTER(_X11DisplayStruct)

    xlib.XCloseDisplay.argtypes = [ctypes.POINTER(_X11DisplayStruct)]
    xlib.XCloseDisplay.restype = None

    display = xlib.XOpenDisplay(None)
    if not display:
        raise Error("Cannot open display")

    try:
        yield display
    finally:
        xlib.XCloseDisplay(display)


def _x11_intern_atom(
    xlib: ctypes.CDLL, display: _X11Display, name: bytes, only_if_exists: bool = True
) -> int:
    """Call xlib's XInternAtom function."""
    xlib.XInternAtom.argtypes = [
        ctypes.POINTER(_X11DisplayStruct),  # Display
        ctypes.c_char_p,  # Atom name
        ctypes.c_int,  # Only if exists (bool)
    ]
    xlib.XInternAtom.restype = ctypes.c_ulong

    atom = xlib.XInternAtom(display, name, only_if_exists)
    if atom == 0:
        raise Error(f"Failed to intern atom: {name!r}")

    return atom


@contextlib.contextmanager
def _x11_get_window_property(
    xlib: ctypes.CDLL,
    display: _X11Display,
    *,
    window: _X11Window,
    prop: int,
    req_type: int,
    length: int,
    offset: int = 0,
    delete: bool = False,
) -> Iterator[tuple["ctypes._Pointer[ctypes.c_ubyte]", ctypes.c_ulong]]:
    """Call xlib's XGetWindowProperty function."""
    ret_actual_type = ctypes.c_ulong()
    ret_actual_format = ctypes.c_int()
    ret_nitems = ctypes.c_ulong()
    ret_bytes_after = ctypes.c_ulong()
    ret_prop = ctypes.POINTER(ctypes.c_ubyte)()

    xlib.XGetWindowProperty.argtypes = [
        ctypes.POINTER(_X11DisplayStruct),  # Display
        ctypes.c_ulong,  # Window
        ctypes.c_ulong,  # Property
        ctypes.c_long,  # Offset
        ctypes.c_long,  # Length
        ctypes.c_int,  # Delete (bool)
        ctypes.c_ulong,  # Required type (Atom)
        ctypes.POINTER(ctypes.c_ulong),  # return: Actual type (Atom)
        ctypes.POINTER(ctypes.c_int),  # return: Actual format
        ctypes.POINTER(ctypes.c_ulong),  # return: Number of items
        ctypes.POINTER(ctypes.c_ulong),  # return: Bytes after
        ctypes.POINTER(ctypes.POINTER(ctypes.c_ubyte)),  # return: Property value
    ]
    xlib.XGetWindowProperty.restype = ctypes.c_int

    result = xlib.XGetWindowProperty(
        display,
        window,
        prop,
        offset,
        length,
        delete,
        req_type,
        ctypes.byref(ret_actual_type),
        ctypes.byref(ret_actual_format),
        ctypes.byref(ret_nitems),
        ctypes.byref(ret_bytes_after),
        ctypes.byref(ret_prop),
    )
    if result != 0:
        raise Error(f"XGetWindowProperty for {prop} failed: {result}")
    if not ret_prop:
        raise Error(f"Property {prop} is NULL")
    if ret_actual_type.value != req_type:
        raise Error(
            f"Expected type {req_type}, got {ret_actual_type.value} for property {prop}"
        )
    if ret_bytes_after.value != 0:
        raise Error(
            f"Expected no bytes after property {prop}, got {ret_bytes_after.value}"
        )

    try:
        yield ret_prop, ret_nitems
    finally:
        xlib.XFree(ret_prop)


def _x11_get_wm_window(
    xlib: ctypes.CDLL, display: _X11Display, *, atoms: _X11Atoms
) -> _X11Window:
    """Get the _NET_SUPPORTING_WM_CHECK window."""
    xlib.XDefaultScreen.argtypes = [ctypes.POINTER(_X11DisplayStruct)]
    xlib.XDefaultScreen.restype = ctypes.c_int

    xlib.XRootWindow.argtypes = [
        ctypes.POINTER(_X11DisplayStruct),  # Display
        ctypes.c_int,  # Screen number
    ]
    xlib.XRootWindow.restype = ctypes.c_ulong

    screen = xlib.XDefaultScreen(display)
    root_window = xlib.XRootWindow(display, screen)

    with _x11_get_window_property(
        xlib,
        display,
        window=root_window,
        prop=atoms.NET_SUPPORTING_WM_CHECK,
        req_type=33,  # XA_WINDOW
        length=1,
    ) as (prop, _nitems):
        win = ctypes.cast(prop, ctypes.POINTER(ctypes.c_ulong)).contents.value
        return _X11Window(win)


def _x11_get_wm_name(
    xlib: ctypes.CDLL,
    display: _X11Display,
    *,
    atoms: _X11Atoms,
    wm_window: _X11Window,
) -> str:
    """Get the _NET_WM_NAME property of the window manager."""
    with _x11_get_window_property(
        xlib,
        display,
        window=wm_window,
        prop=atoms.NET_WM_NAME,
        req_type=atoms.UTF8_STRING,
        length=1024,  # somewhat arbitrary
    ) as (prop, nitems):
        if nitems.value <= 0:
            raise Error(f"{nitems.value} items found in _NET_WM_NAME property")
        wm_name = ctypes.string_at(prop, nitems.value).decode("utf-8")
        if not wm_name:
            raise Error("Window manager name is empty")
        return wm_name


def x11_wm_name() -> str:
    """Get the name of the running X11 window manager."""
    xlib = _x11_load_lib()
    with _x11_open_display(xlib) as display:
        atoms = _X11Atoms(
            NET_SUPPORTING_WM_CHECK=_x11_intern_atom(
                xlib, display, b"_NET_SUPPORTING_WM_CHECK"
            ),
            NET_WM_NAME=_x11_intern_atom(xlib, display, b"_NET_WM_NAME"),
            UTF8_STRING=_x11_intern_atom(xlib, display, b"UTF8_STRING"),
        )
        wm_window = _x11_get_wm_window(xlib, display, atoms=atoms)
        return _x11_get_wm_name(xlib, display, atoms=atoms, wm_window=wm_window)


if __name__ == "__main__":
    try:
        wayland_name = wayland_compositor_name()
        print(f"Wayland compositor name: {wayland_name}")
    except Error as e:
        print(f"Wayland error: {e}")

    try:
        x11_name = x11_wm_name()
        print(f"X11 window manager name: {x11_name}")
    except Error as e:
        print(f"X11 error: {e}")
