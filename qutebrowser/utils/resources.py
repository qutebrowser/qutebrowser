# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Resources related utilities."""

import os.path
import sys
import contextlib
import posixpath
import pathlib
import importlib.resources
from typing import Union
from collections.abc import Iterator, Iterable

if sys.version_info >= (3, 11):  # pragma: no cover
    # https://github.com/python/cpython/issues/90276
    from importlib.resources.abc import Traversable
else:
    from importlib.abc import Traversable

import qutebrowser
_cache: dict[str, str] = {}
_bin_cache: dict[str, bytes] = {}


_ResourceType = Union[Traversable, pathlib.Path]


def _path(filename: str) -> _ResourceType:
    """Get a pathlib.Path object for a resource."""
    assert not posixpath.isabs(filename), filename
    assert os.path.pardir not in filename.split(posixpath.sep), filename

    return importlib.resources.files(qutebrowser) / filename

@contextlib.contextmanager
def _keyerror_workaround() -> Iterator[None]:
    """Re-raise KeyErrors as FileNotFoundErrors.

    WORKAROUND for zipfile.Path resources raising KeyError when a file was notfound:
    https://bugs.python.org/issue43063

    Only needed for Python 3.9.
    """
    try:
        yield
    except KeyError as e:
        raise FileNotFoundError(str(e))


def _glob(
    resource_path: _ResourceType,
    subdir: str,
    ext: str,
) -> Iterable[str]:
    """Find resources with the given extension.

    Yields a resource name like "html/log.html" (as string).
    """
    assert '*' not in ext, ext
    assert ext.startswith('.'), ext
    glob_path = resource_path / subdir

    if isinstance(resource_path, pathlib.Path):
        assert isinstance(glob_path, pathlib.Path)
        for full_path in glob_path.glob(f'*{ext}'):  # . is contained in ext
            yield full_path.relative_to(resource_path).as_posix()
    else:  # zipfile.Path or other importlib.resources.abc.Traversable
        assert glob_path.is_dir(), glob_path
        for subpath in glob_path.iterdir():
            if subpath.name.endswith(ext):
                yield posixpath.join(subdir, subpath.name)


def preload() -> None:
    """Load resource files into the cache."""
    resource_path = _path('')
    for subdir, ext in [
            ('html', '.html'),
            ('javascript', '.js'),
            ('javascript/quirks', '.js'),
    ]:
        for name in _glob(resource_path, subdir, ext):
            _cache[name] = read_file(name)

    for name in _glob(resource_path, 'img', '.png'):
        # e.g. broken_qutebrowser_logo.png
        _bin_cache[name] = read_file_binary(name)


def read_file(filename: str) -> str:
    """Get the contents of a file contained with qutebrowser.

    Args:
        filename: The filename to open as string.

    Return:
        The file contents as string.
    """
    if filename in _cache:
        return _cache[filename]

    path = _path(filename)
    with _keyerror_workaround():
        return path.read_text(encoding='utf-8')


def read_file_binary(filename: str) -> bytes:
    """Get the contents of a binary file contained with qutebrowser.

    Args:
        filename: The filename to open as string.

    Return:
        The file contents as a bytes object.
    """
    if filename in _bin_cache:
        return _bin_cache[filename]

    path = _path(filename)
    with _keyerror_workaround():
        return path.read_bytes()
