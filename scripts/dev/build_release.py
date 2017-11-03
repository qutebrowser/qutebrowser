#!/usr/bin/env python3
# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2017 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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

"""Build a new release."""


import os
import sys
import glob
import os.path
import shutil
import plistlib
import subprocess
import argparse
import tarfile
import tempfile
import collections

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir,
                                os.pardir))

import qutebrowser
from scripts import utils
# from scripts.dev import update_3rdparty


def call_script(name, *args, python=sys.executable):
    """Call a given shell script.

    Args:
        name: The script to call.
        *args: The arguments to pass.
        python: The python interpreter to use.
    """
    path = os.path.join(os.path.dirname(__file__), os.pardir, name)
    subprocess.run([python, path] + list(args), check=True)


def call_tox(toxenv, *args, python=sys.executable):
    """Call tox.

    Args:
        toxenv: Which tox environment to use
        *args: The arguments to pass.
        python: The python interpreter to use.
    """
    env = os.environ.copy()
    env['PYTHON'] = python
    env['PATH'] = os.environ['PATH'] + os.pathsep + os.path.dirname(python)
    subprocess.run(
        [sys.executable, '-m', 'tox', '-vv', '-e', toxenv] + list(args),
        env=env, check=True)


def run_asciidoc2html(args):
    """Common buildsteps used for all OS'."""
    utils.print_title("Running asciidoc2html.py")
    if args.asciidoc is not None:
        a2h_args = ['--asciidoc'] + args.asciidoc
    else:
        a2h_args = []
    call_script('asciidoc2html.py', *a2h_args)


def _maybe_remove(path):
    """Remove a path if it exists."""
    try:
        shutil.rmtree(path)
    except FileNotFoundError:
        pass


def smoke_test(executable):
    """Try starting the given qutebrowser executable."""
    subprocess.run([executable, '--no-err-windows', '--nowindow',
                    '--temp-basedir', 'about:blank', ':later 500 quit'],
                   check=True)


def patch_mac_app():
    """Patch .app to copy missing data and link some libs.

    See https://github.com/pyinstaller/pyinstaller/issues/2276
    """
    app_path = os.path.join('dist', 'qutebrowser.app')
    qtwe_core_dir = os.path.join('.tox', 'pyinstaller', 'lib', 'python3.6',
                                 'site-packages', 'PyQt5', 'Qt', 'lib',
                                 'QtWebEngineCore.framework')
    # Copy QtWebEngineProcess.app
    proc_app = 'QtWebEngineProcess.app'
    shutil.copytree(os.path.join(qtwe_core_dir, 'Helpers', proc_app),
                    os.path.join(app_path, 'Contents', 'MacOS', proc_app))
    # Copy resources
    for f in glob.glob(os.path.join(qtwe_core_dir, 'Resources', '*')):
        dest = os.path.join(app_path, 'Contents', 'Resources')
        if os.path.isdir(f):
            dir_dest = os.path.join(dest, os.path.basename(f))
            print("Copying directory {} to {}".format(f, dir_dest))
            shutil.copytree(f, dir_dest)
        else:
            print("Copying {} to {}".format(f, dest))
            shutil.copy(f, dest)
    # Link dependencies
    for lib in ['QtCore', 'QtWebEngineCore', 'QtQuick', 'QtQml', 'QtNetwork',
                'QtGui', 'QtWebChannel', 'QtPositioning']:
        dest = os.path.join(app_path, lib + '.framework', 'Versions', '5')
        os.makedirs(dest)
        os.symlink(os.path.join(os.pardir, os.pardir, os.pardir, 'Contents',
                                'MacOS', lib),
                   os.path.join(dest, lib))
    # Patch Info.plist - pyinstaller's options are too limiting
    plist_path = os.path.join(app_path, 'Contents', 'Info.plist')
    with open(plist_path, "rb") as f:
        plist_data = plistlib.load(f)
    plist_data.update(INFO_PLIST_UPDATES)
    with open(plist_path, "wb") as f:
        plistlib.dump(plist_data, f)


INFO_PLIST_UPDATES = {
    'CFBundleVersion': qutebrowser.__version__,
    'CFBundleShortVersionString': qutebrowser.__version__,
    'NSSupportsAutomaticGraphicsSwitching': True,
    'NSHighResolutionCapable': True,
    'CFBundleURLTypes': [{
        "CFBundleURLName": "http(s) URL",
        "CFBundleURLSchemes": ["http", "https"]
    }, {
        "CFBundleURLName": "local file URL",
        "CFBundleURLSchemes": ["file"]
    }],
    'CFBundleDocumentTypes': [{
        "CFBundleTypeExtensions": ["html", "htm"],
        "CFBundleTypeMIMETypes": ["text/html"],
        "CFBundleTypeName": "HTML document",
        "CFBundleTypeOSTypes": ["HTML"],
        "CFBundleTypeRole": "Viewer",
    }, {
        "CFBundleTypeExtensions": ["xhtml"],
        "CFBundleTypeMIMETypes": ["text/xhtml"],
        "CFBundleTypeName": "XHTML document",
        "CFBundleTypeRole": "Viewer",
    }]
}


def build_mac():
    """Build macOS .dmg/.app."""
    utils.print_title("Cleaning up...")
    for f in ['wc.dmg', 'template.dmg']:
        try:
            os.remove(f)
        except FileNotFoundError:
            pass
    for d in ['dist', 'build']:
        shutil.rmtree(d, ignore_errors=True)
    utils.print_title("Updating 3rdparty content")
    # Currently disabled because QtWebEngine has no pdfjs support
    # update_3rdparty.run(ace=False, pdfjs=True, fancy_dmg=False)
    utils.print_title("Building .app via pyinstaller")
    call_tox('pyinstaller', '-r')
    utils.print_title("Patching .app")
    patch_mac_app()
    utils.print_title("Building .dmg")
    subprocess.run(['make', '-f', 'scripts/dev/Makefile-dmg'], check=True)

    dmg_name = 'qutebrowser-{}.dmg'.format(qutebrowser.__version__)
    os.rename('qutebrowser.dmg', dmg_name)

    utils.print_title("Running smoke test")

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            subprocess.run(['hdiutil', 'attach', dmg_name,
                            '-mountpoint', tmpdir], check=True)
            try:
                binary = os.path.join(tmpdir, 'qutebrowser.app', 'Contents',
                                      'MacOS', 'qutebrowser')
                smoke_test(binary)
            finally:
                subprocess.run(['hdiutil', 'detach', tmpdir])
    except PermissionError as e:
        print("Failed to remove tempdir: {}".format(e))

    return [(dmg_name, 'application/x-apple-diskimage', 'macOS .dmg')]


def patch_windows(out_dir):
    """Copy missing DLLs for windows into the given output."""
    dll_dir = os.path.join('.tox', 'pyinstaller', 'lib', 'site-packages',
                           'PyQt5', 'Qt', 'bin')
    dlls = ['libEGL.dll', 'libGLESv2.dll', 'libeay32.dll', 'ssleay32.dll']
    for dll in dlls:
        shutil.copy(os.path.join(dll_dir, dll), out_dir)


def build_windows():
    """Build windows executables/setups."""
    utils.print_title("Updating 3rdparty content")
    # Currently disabled because QtWebEngine has no pdfjs support
    # update_3rdparty.run(ace=False, pdfjs=True, fancy_dmg=False)

    utils.print_title("Building Windows binaries")
    parts = str(sys.version_info.major), str(sys.version_info.minor)
    ver = ''.join(parts)
    python_x86 = r'C:\Python{}-32\python.exe'.format(ver)
    python_x64 = r'C:\Python{}\python.exe'.format(ver)
    out_pyinstaller = os.path.join('dist', 'qutebrowser')
    out_32 = os.path.join('dist',
                          'qutebrowser-{}-x86'.format(qutebrowser.__version__))
    out_64 = os.path.join('dist',
                          'qutebrowser-{}-x64'.format(qutebrowser.__version__))

    artifacts = []

    utils.print_title("Running pyinstaller 32bit")
    _maybe_remove(out_32)
    call_tox('pyinstaller', '-r', python=python_x86)
    shutil.move(out_pyinstaller, out_32)
    patch_windows(out_32)

    utils.print_title("Running pyinstaller 64bit")
    _maybe_remove(out_64)
    call_tox('pyinstaller', '-r', python=python_x64)
    shutil.move(out_pyinstaller, out_64)
    patch_windows(out_64)

    utils.print_title("Building installers")
    subprocess.run(['makensis.exe',
                    '/DVERSION={}'.format(qutebrowser.__version__),
                    'misc/qutebrowser.nsi'], check=True)
    subprocess.run(['makensis.exe',
                    '/DX64',
                    '/DVERSION={}'.format(qutebrowser.__version__),
                    'misc/qutebrowser.nsi'], check=True)

    name_32 = 'qutebrowser-{}-win32.exe'.format(qutebrowser.__version__)
    name_64 = 'qutebrowser-{}-amd64.exe'.format(qutebrowser.__version__)

    artifacts += [
        (os.path.join('dist', name_32),
         'application/vnd.microsoft.portable-executable',
         'Windows 32bit installer'),
        (os.path.join('dist', name_64),
         'application/vnd.microsoft.portable-executable',
         'Windows 64bit installer'),
    ]

    utils.print_title("Running 32bit smoke test")
    smoke_test(os.path.join(out_32, 'qutebrowser.exe'))
    utils.print_title("Running 64bit smoke test")
    smoke_test(os.path.join(out_64, 'qutebrowser.exe'))

    utils.print_title("Zipping 32bit standalone...")
    name = 'qutebrowser-{}-windows-standalone-win32'.format(
        qutebrowser.__version__)
    shutil.make_archive(name, 'zip', 'dist', os.path.basename(out_32))
    artifacts.append(('{}.zip'.format(name),
                      'application/zip',
                      'Windows 32bit standalone'))

    utils.print_title("Zipping 64bit standalone...")
    name = 'qutebrowser-{}-windows-standalone-amd64'.format(
        qutebrowser.__version__)
    shutil.make_archive(name, 'zip', 'dist', os.path.basename(out_64))
    artifacts.append(('{}.zip'.format(name),
                      'application/zip',
                      'Windows 64bit standalone'))

    return artifacts


def build_sdist():
    """Build an sdist and list the contents."""
    utils.print_title("Building sdist")

    _maybe_remove('dist')

    subprocess.run([sys.executable, 'setup.py', 'sdist'], check=True)
    dist_files = os.listdir(os.path.abspath('dist'))
    assert len(dist_files) == 1

    dist_file = os.path.join('dist', dist_files[0])
    subprocess.run(['gpg', '--detach-sign', '-a', dist_file], check=True)

    tar = tarfile.open(dist_file)
    by_ext = collections.defaultdict(list)

    for tarinfo in tar.getmembers():
        if not tarinfo.isfile():
            continue
        name = os.sep.join(tarinfo.name.split(os.sep)[1:])
        _base, ext = os.path.splitext(name)
        by_ext[ext].append(name)

    assert '.pyc' not in by_ext

    utils.print_title("sdist contents")

    for ext, files in sorted(by_ext.items()):
        utils.print_subtitle(ext)
        print('\n'.join(files))

    filename = 'qutebrowser-{}.tar.gz'.format(qutebrowser.__version__)
    artifacts = [
        (os.path.join('dist', filename), 'application/gzip', 'Source release'),
        (os.path.join('dist', filename + '.asc'), 'application/pgp-signature',
         'Source release - PGP signature'),
    ]

    return artifacts


def read_github_token():
    """Read the GitHub API token from disk."""
    token_file = os.path.join(os.path.expanduser('~'), '.gh_token')
    with open(token_file, encoding='ascii') as f:
        token = f.read().strip()
    return token


def github_upload(artifacts, tag):
    """Upload the given artifacts to GitHub.

    Args:
        artifacts: A list of (filename, mimetype, description) tuples
        tag: The name of the release tag
    """
    import github3
    utils.print_title("Uploading to github...")

    token = read_github_token()
    gh = github3.login(token=token)
    repo = gh.repository('qutebrowser', 'qutebrowser')

    release = None  # to satisfy pylint
    for release in repo.iter_releases():
        if release.tag_name == tag:
            break
    else:
        raise Exception("No release found for {!r}!".format(tag))

    for filename, mimetype, description in artifacts:
        with open(filename, 'rb') as f:
            basename = os.path.basename(filename)
            asset = release.upload_asset(mimetype, basename, f)
        asset.edit(basename, description)


def pypi_upload(artifacts):
    """Upload the given artifacts to PyPI using twine."""
    filenames = [a[0] for a in artifacts]
    subprocess.run(['twine', 'upload'] + filenames, check=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--asciidoc', help="Full path to python and "
                        "asciidoc.py. If not given, it's searched in PATH.",
                        nargs=2, required=False,
                        metavar=('PYTHON', 'ASCIIDOC'))
    parser.add_argument('--upload', help="Tag to upload the release for",
                        nargs=1, required=False, metavar='TAG')
    args = parser.parse_args()
    utils.change_cwd()

    upload_to_pypi = False

    if args.upload is not None:
        # Fail early when trying to upload without github3 installed
        # or without API token
        import github3  # pylint: disable=unused-variable
        read_github_token()

    run_asciidoc2html(args)
    if os.name == 'nt':
        if sys.maxsize > 2**32:
            # WORKAROUND
            print("Due to a python/Windows bug, this script needs to be run ")
            print("with a 32bit Python.")
            print()
            print("See http://bugs.python.org/issue24493 and ")
            print("https://github.com/pypa/virtualenv/issues/774")
            sys.exit(1)
        artifacts = build_windows()
    elif sys.platform == 'darwin':
        artifacts = build_mac()
    else:
        artifacts = build_sdist()
        upload_to_pypi = True

    if args.upload is not None:
        utils.print_title("Press enter to release...")
        input()
        github_upload(artifacts, args.upload[0])
        if upload_to_pypi:
            pypi_upload(artifacts)
    else:
        print()
        utils.print_title("Artifacts")
        for artifact in artifacts:
            print(artifact)


if __name__ == '__main__':
    main()
