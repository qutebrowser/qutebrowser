#!/usr/bin/env python3
# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2014-2021 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
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
# along with qutebrowser.  If not, see <https://www.gnu.org/licenses/>.

"""Build a new release."""


import os
import os.path
import sys
import time
import shutil
import pathlib
import plistlib
import subprocess
import argparse
import tarfile
import tempfile
import collections
import re

try:
    import winreg
except ImportError:
    pass

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir,
                                os.pardir))

import qutebrowser
from scripts import utils
from scripts.dev import update_3rdparty, misc_checks


def call_script(name, *args, python=sys.executable):
    """Call a given shell script.

    Args:
        name: The script to call.
        *args: The arguments to pass.
        python: The python interpreter to use.
    """
    path = os.path.join(os.path.dirname(__file__), os.pardir, name)
    subprocess.run([python, path] + list(args), check=True)


def call_tox(toxenv, *args, python=sys.executable, debug=False):
    """Call tox.

    Args:
        toxenv: Which tox environment to use
        *args: The arguments to pass.
        python: The python interpreter to use.
        debug: Turn on pyinstaller debugging
    """
    env = os.environ.copy()
    env['PYTHON'] = python
    env['PATH'] = os.environ['PATH'] + os.pathsep + os.path.dirname(python)
    if debug:
        env['PYINSTALLER_DEBUG'] = '1'
    subprocess.run(
        [sys.executable, '-m', 'tox', '-vv', '-e', toxenv] + list(args),
        env=env, check=True)


def run_asciidoc2html(args):
    """Common buildsteps used for all OS'."""
    utils.print_title("Running asciidoc2html.py")
    a2h_args = []
    if args.asciidoc is not None:
        a2h_args += ['--asciidoc', args.asciidoc]
    if args.asciidoc_python is not None:
        a2h_args += ['--asciidoc-python', args.asciidoc_python]
    call_script('asciidoc2html.py', *a2h_args)


def _maybe_remove(path):
    """Remove a path if it exists."""
    try:
        shutil.rmtree(path)
    except FileNotFoundError:
        pass


def _filter_whitelisted(output, patterns):
    for line in output.decode('utf-8').splitlines():
        if not any(re.fullmatch(pattern, line) for pattern in patterns):
            yield line


def _smoke_test_run(executable, *args):
    """Get a subprocess to run a smoke test."""
    argv = [
        executable,
        '--no-err-windows',
        '--nowindow',
        '--temp-basedir',
        *args,
        'about:blank',
        ':later 500 quit',
    ]
    return subprocess.run(argv, check=True, capture_output=True)


def smoke_test(executable, debug):
    """Try starting the given qutebrowser executable."""
    stdout_whitelist = []
    stderr_whitelist = [
        # PyInstaller debug output
        r'\[.*\] PyInstaller Bootloader .*',
        r'\[.*\] LOADER: .*',

        # https://github.com/qutebrowser/qutebrowser/issues/4919
        (r'objc\[.*\]: .* One of the two will be used\. '
         r'Which one is undefined\.'),
        (r'QCoreApplication::applicationDirPath: Please instantiate the '
         r'QApplication object first'),
        (r'\[.*:ERROR:mach_port_broker.mm\(48\)\] bootstrap_look_up '
         r'org\.chromium\.Chromium\.rohitfork\.1: Permission denied \(1100\)'),
        (r'\[.*:ERROR:mach_port_broker.mm\(43\)\] bootstrap_look_up: '
         r'Unknown service name \(1102\)'),

        (r'[0-9:]* WARNING: The available OpenGL surface format was either not '
         r'version 3\.2 or higher or not a Core Profile\.'),
        r'Chromium on macOS will fall back to software rendering in this case\.',
        r'Hardware acceleration and features such as WebGL will not be available\.',
        r'Unable to create basic Accelerated OpenGL renderer\.',
        r'Core Image is now using the software OpenGL renderer\. This will be slow\.',

        # Windows N:
        # https://github.com/microsoft/playwright/issues/2901
        (r'\[.*:ERROR:dxva_video_decode_accelerator_win.cc\(\d+\)\] '
         r'DXVAVDA fatal error: could not LoadLibrary: .*: The specified '
         r'module could not be found. \(0x7E\)'),

        # https://github.com/qutebrowser/qutebrowser/issues/3719
        '[0-9:]* ERROR: Load error: ERR_FILE_NOT_FOUND',
    ]

    proc = _smoke_test_run(executable)
    if debug:
        print("Skipping output check for debug build")
        return

    stdout = '\n'.join(_filter_whitelisted(proc.stdout, stdout_whitelist))
    stderr = '\n'.join(_filter_whitelisted(proc.stderr, stderr_whitelist))

    if stdout or stderr:
        print("Unexpected output, running with --debug")
        proc = _smoke_test_run(executable, '--debug')
        debug_stdout = proc.stdout.decode('utf-8')
        debug_stderr = proc.stderr.decode('utf-8')

        lines = [
            "Unexpected output!",
            "",
        ]
        if stdout:
            lines += [
                "stdout",
                "------",
                "",
                stdout,
                "",
            ]
        if stderr:
            lines += [
                "stderr",
                "------",
                "",
                stderr,
                "",
            ]
        if debug_stdout:
            lines += [
                "debug rerun stdout",
                "------------------",
                "",
                debug_stdout,
                "",
            ]
        if debug_stderr:
            lines += [
                "debug rerun stderr",
                "------------------",
                "",
                debug_stderr,
                "",
            ]

        raise Exception("\n".join(lines))


def verify_windows_exe(exe_path):
    """Make sure the Windows .exe has a correct checksum."""
    import pefile
    pe = pefile.PE(exe_path)
    assert pe.verify_checksum()


def patch_mac_app():
    """Patch .app to use our Info.plist and save some space."""
    app_path = os.path.join('dist', 'qutebrowser.app')

    # Patch Info.plist - pyinstaller's options are too limiting
    plist_path = os.path.join(app_path, 'Contents', 'Info.plist')
    with open(plist_path, "rb") as f:
        plist_data = plistlib.load(f)
    plist_data.update(INFO_PLIST_UPDATES)
    with open(plist_path, "wb") as f:
        plistlib.dump(plist_data, f)

    # Replace some duplicate files by symlinks
    framework_path = os.path.join(app_path, 'Contents', 'MacOS', 'PyQt5',
                                  'Qt5', 'lib', 'QtWebEngineCore.framework')

    core_lib = os.path.join(framework_path, 'Versions', '5', 'QtWebEngineCore')
    os.remove(core_lib)
    core_target = os.path.join(*[os.pardir] * 7, 'MacOS', 'QtWebEngineCore')
    os.symlink(core_target, core_lib)

    framework_resource_path = os.path.join(framework_path, 'Resources')
    for name in os.listdir(framework_resource_path):
        file_path = os.path.join(framework_resource_path, name)
        target = os.path.join(*[os.pardir] * 5, name)
        if os.path.isdir(file_path):
            shutil.rmtree(file_path)
        else:
            os.remove(file_path)
        os.symlink(target, file_path)


INFO_PLIST_UPDATES = {
    'CFBundleVersion': qutebrowser.__version__,
    'CFBundleShortVersionString': qutebrowser.__version__,
    'NSSupportsAutomaticGraphicsSwitching': True,
    'NSHighResolutionCapable': True,
    'NSRequiresAquaSystemAppearance': False,
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
    }],

    # https://developer.apple.com/documentation/avfoundation/cameras_and_media_capture/requesting_authorization_for_media_capture_on_macos
    #
    # Keys based on Google Chrome's .app, except Bluetooth keys which seem to
    # be iOS-only.
    #
    # If we don't do this, we get a SIGABRT from macOS when those permissions
    # are used, and even in some other situations (like logging into Google
    # accounts)...
    'NSCameraUsageDescription':
        'A website in qutebrowser wants to use the camera.',
    'NSLocationUsageDescription':
        'A website in qutebrowser wants to use your location information.',
    'NSMicrophoneUsageDescription':
        'A website in qutebrowser wants to use your microphone.',
    'NSBluetoothAlwaysUsageDescription':
        'A website in qutebrowser wants to access Bluetooth.',
}


def build_mac(*, gh_token, debug):
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
    update_3rdparty.run(ace=False, pdfjs=True, fancy_dmg=False, gh_token=gh_token)
    utils.print_title("Building .app via pyinstaller")
    call_tox('pyinstaller-64', '-r', debug=debug)
    utils.print_title("Patching .app")
    patch_mac_app()
    utils.print_title("Building .dmg")
    subprocess.run(['make', '-f', 'scripts/dev/Makefile-dmg'], check=True)

    suffix = "-debug" if debug else ""
    dmg_path = f'dist/qutebrowser-{qutebrowser.__version__}{suffix}.dmg'
    os.rename('qutebrowser.dmg', dmg_path)

    utils.print_title("Running smoke test")

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            subprocess.run(['hdiutil', 'attach', dmg_path,
                            '-mountpoint', tmpdir], check=True)
            try:
                binary = os.path.join(tmpdir, 'qutebrowser.app', 'Contents',
                                      'MacOS', 'qutebrowser')
                smoke_test(binary, debug=debug)
            finally:
                print("Waiting 10s for dmg to be detachable...")
                time.sleep(10)
                subprocess.run(['hdiutil', 'detach', tmpdir], check=False)
    except PermissionError as e:
        print("Failed to remove tempdir: {}".format(e))

    return [(dmg_path, 'application/x-apple-diskimage', 'macOS .dmg')]


def _get_windows_python_path(x64):
    """Get the path to Python.exe on Windows."""
    parts = str(sys.version_info.major), str(sys.version_info.minor)
    ver = ''.join(parts)
    dot_ver = '.'.join(parts)

    if x64:
        path = (r'SOFTWARE\Python\PythonCore\{}\InstallPath'
                .format(dot_ver))
        fallback = r'C:\Python{}\python.exe'.format(ver)
    else:
        path = (r'SOFTWARE\WOW6432Node\Python\PythonCore\{}-32\InstallPath'
                .format(dot_ver))
        fallback = r'C:\Python{}-32\python.exe'.format(ver)

    try:
        key = winreg.OpenKeyEx(winreg.HKEY_LOCAL_MACHINE, path)
        return winreg.QueryValueEx(key, 'ExecutablePath')[0]
    except FileNotFoundError:
        return fallback


def _build_windows_single(*, x64, skip_packaging, debug):
    """Build on Windows for a single architecture."""
    human_arch = '64-bit' if x64 else '32-bit'
    utils.print_title(f"Running pyinstaller {human_arch}")

    outdir = os.path.join(
        'dist', f'qutebrowser-{qutebrowser.__version__}-{"x64" if x64 else "x86"}')
    _maybe_remove(outdir)

    python = _get_windows_python_path(x64=x64)
    call_tox(f'pyinstaller-{"64" if x64 else "32"}', '-r', python=python, debug=debug)

    out_pyinstaller = os.path.join('dist', 'qutebrowser')
    shutil.move(out_pyinstaller, outdir)
    exe_path = os.path.join(outdir, 'qutebrowser.exe')

    utils.print_title(f"Verifying {human_arch} exe")
    verify_windows_exe(exe_path)

    utils.print_title(f"Running {human_arch} smoke test")
    smoke_test(exe_path, debug=debug)

    if skip_packaging:
        return []

    utils.print_title(f"Packaging {human_arch}")
    return _package_windows_single(
        nsis_flags=[] if x64 else ['/DX86'],
        outdir=outdir,
        filename_arch='amd64' if x64 else 'win32',
        desc_arch=human_arch,
        desc_suffix='' if x64 else ' (only for 32-bit Windows!)',
        debug=debug,
    )


def build_windows(*, gh_token, skip_packaging, only_32bit, only_64bit, debug):
    """Build windows executables/setups."""
    utils.print_title("Updating 3rdparty content")
    update_3rdparty.run(nsis=True, ace=False, pdfjs=True, fancy_dmg=False,
                        gh_token=gh_token)

    utils.print_title("Building Windows binaries")

    artifacts = []

    from scripts.dev import gen_versioninfo
    utils.print_title("Updating VersionInfo file")
    gen_versioninfo.main()

    if not only_32bit:
        artifacts += _build_windows_single(
            x64=True,
            skip_packaging=skip_packaging,
            debug=debug,
        )
    if not only_64bit:
        artifacts += _build_windows_single(
            x64=False,
            skip_packaging=skip_packaging,
            debug=debug,
        )

    return artifacts


def _package_windows_single(
    *,
    nsis_flags,
    outdir,
    desc_arch,
    desc_suffix,
    filename_arch,
    debug,
):
    """Build the given installer/zip for windows."""
    artifacts = []

    utils.print_subtitle(f"Building {desc_arch} installer...")
    subprocess.run(['makensis.exe',
                    f'/DVERSION={qutebrowser.__version__}', *nsis_flags,
                    'misc/nsis/qutebrowser.nsi'], check=True)

    name_parts = [
        'qutebrowser',
        str(qutebrowser.__version__),
        filename_arch,
    ]
    if debug:
        name_parts.append('debug')
    name = '-'.join(name_parts) + '.exe'

    artifacts.append((
        os.path.join('dist', name),
        'application/vnd.microsoft.portable-executable',
        f'Windows {desc_arch} installer{desc_suffix}',
    ))

    utils.print_subtitle(f"Zipping {desc_arch} standalone...")
    zip_name_parts = [
        'qutebrowser',
        str(qutebrowser.__version__),
        'windows',
        'standalone',
        filename_arch,
    ]
    if debug:
        zip_name_parts.append('debug')
    zip_name = '-'.join(zip_name_parts)

    zip_path = os.path.join('dist', zip_name)
    shutil.make_archive(zip_path, 'zip', 'dist', os.path.basename(outdir))
    artifacts.append((
        f'{zip_path}.zip',
        'application/zip',
        f'Windows {desc_arch} standalone{desc_suffix}'
    ))

    return artifacts


def build_sdist():
    """Build an sdist and list the contents."""
    utils.print_title("Building sdist")

    dist_path = pathlib.Path('dist')
    _maybe_remove(dist_path)

    subprocess.run([sys.executable, '-m', 'build'], check=True)

    dist_files = list(dist_path.glob('*.tar.gz'))
    filename = 'qutebrowser-{}.tar.gz'.format(qutebrowser.__version__)
    assert dist_files == [dist_path / filename], dist_files
    dist_file = dist_files[0]

    subprocess.run(['gpg', '--detach-sign', '-a', str(dist_file)], check=True)

    by_ext = collections.defaultdict(list)

    with tarfile.open(dist_file) as tar:
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

    artifacts = [
        (str(dist_file), 'application/gzip', 'Source release'),
        (
            str(dist_file.with_suffix(dist_file.suffix + '.asc')),
            'application/pgp-signature',
            'Source release - PGP signature',
        ),
    ]

    return artifacts


def test_makefile():
    """Make sure the Makefile works correctly."""
    utils.print_title("Testing makefile")
    with tempfile.TemporaryDirectory() as tmpdir:
        subprocess.run(['make', '-f', 'misc/Makefile',
                        'DESTDIR={}'.format(tmpdir), 'install'], check=True)


def read_github_token(arg_token, *, optional=False):
    """Read the GitHub API token from disk."""
    if arg_token is not None:
        return arg_token

    token_file = os.path.join(os.path.expanduser('~'), '.gh_token')
    if not os.path.exists(token_file):
        if optional:
            return None
        else:
            raise Exception(
                "GitHub token needed, but ~/.gh_token not found, "
                "and --gh-token not given.")

    with open(token_file, encoding='ascii') as f:
        token = f.read().strip()
    return token


def github_upload(artifacts, tag, gh_token):
    """Upload the given artifacts to GitHub.

    Args:
        artifacts: A list of (filename, mimetype, description) tuples
        tag: The name of the release tag
        gh_token: The GitHub token to use
    """
    import github3
    import github3.exceptions
    utils.print_title("Uploading to github...")

    gh = github3.login(token=gh_token)
    repo = gh.repository('qutebrowser', 'qutebrowser')

    release = None  # to satisfy pylint
    for release in repo.releases():
        if release.tag_name == tag:
            break
    else:
        raise Exception("No release found for {!r}!".format(tag))

    for filename, mimetype, description in artifacts:
        while True:
            print("Uploading {}".format(filename))

            basename = os.path.basename(filename)
            assets = [asset for asset in release.assets()
                      if asset.name == basename]
            if assets:
                print("Assets already exist: {}".format(assets))
                print("Press enter to continue anyways or Ctrl-C to abort.")
                input()

            try:
                with open(filename, 'rb') as f:
                    release.upload_asset(mimetype, basename, f, description)
            except github3.exceptions.ConnectionError as e:
                utils.print_error('Failed to upload: {}'.format(e))
                print("Press Enter to retry...", file=sys.stderr)
                input()
                print("Retrying!")

                assets = [asset for asset in release.assets()
                          if asset.name == basename]
                if assets:
                    stray_asset = assets[0]
                    print("Deleting stray asset {}".format(stray_asset.name))
                    stray_asset.delete()
            else:
                break


def pypi_upload(artifacts):
    """Upload the given artifacts to PyPI using twine."""
    utils.print_title("Uploading to PyPI...")
    run_twine('upload', artifacts)


def twine_check(artifacts):
    """Check packages using 'twine check'."""
    utils.print_title("Running twine check...")
    run_twine('check', artifacts, '--strict')


def run_twine(command, artifacts, *args):
    filenames = [a[0] for a in artifacts]
    subprocess.run([sys.executable, '-m', 'twine', command] + list(args) + filenames,
                   check=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--skip-docs', action='store_true',
                        help="Don't generate docs")
    parser.add_argument('--asciidoc', help="Full path to asciidoc.py. "
                        "If not given, it's searched in PATH.",
                        nargs='?')
    parser.add_argument('--asciidoc-python', help="Python to use for asciidoc."
                        "If not given, the current Python interpreter is used.",
                        nargs='?')
    parser.add_argument('--gh-token', help="GitHub token to use.",
                        nargs='?')
    parser.add_argument('--upload', action='store_true', required=False,
                        help="Toggle to upload the release to GitHub.")
    parser.add_argument('--no-confirm', action='store_true', required=False,
                        help="Skip confirmation before uploading.")
    parser.add_argument('--skip-packaging', action='store_true', required=False,
                        help="Skip Windows installer/zip generation.")
    parser.add_argument('--32bit', action='store_true', required=False,
                        help="Skip Windows 64 bit build.", dest='only_32bit')
    parser.add_argument('--64bit', action='store_true', required=False,
                        help="Skip Windows 32 bit build.", dest='only_64bit')
    parser.add_argument('--debug', action='store_true', required=False,
                        help="Build a debug build.")
    args = parser.parse_args()
    utils.change_cwd()

    upload_to_pypi = False

    if args.upload:
        # Fail early when trying to upload without github3 installed
        # or without API token
        import github3  # pylint: disable=unused-import
        gh_token = read_github_token(args.gh_token)
    else:
        gh_token = read_github_token(args.gh_token, optional=True)

    if not misc_checks.check_git():
        utils.print_error("Refusing to do a release with a dirty git tree")
        sys.exit(1)

    if args.skip_docs:
        os.makedirs(os.path.join('qutebrowser', 'html', 'doc'), exist_ok=True)
    else:
        run_asciidoc2html(args)

    if os.name == 'nt':
        artifacts = build_windows(
            gh_token=gh_token,
            skip_packaging=args.skip_packaging,
            only_32bit=args.only_32bit,
            only_64bit=args.only_64bit,
            debug=args.debug,
        )
    elif sys.platform == 'darwin':
        artifacts = build_mac(gh_token=gh_token, debug=args.debug)
    else:
        test_makefile()
        artifacts = build_sdist()
        twine_check(artifacts)
        upload_to_pypi = True

    if args.upload:
        version_tag = "v" + qutebrowser.__version__

        if not args.no_confirm:
            utils.print_title("Press enter to release {}...".format(version_tag))
            input()

        github_upload(artifacts, version_tag, gh_token=gh_token)
        if upload_to_pypi:
            pypi_upload(artifacts)
    else:
        print()
        utils.print_title("Artifacts")
        for artifact in artifacts:
            print(artifact)


if __name__ == '__main__':
    main()
