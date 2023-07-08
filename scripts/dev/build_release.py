#!/usr/bin/env python3
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
import sys
import time
import shutil
import pathlib
import subprocess
import argparse
import tarfile
import tempfile
import collections
import dataclasses
import re
from typing import Iterable, List, Optional

try:
    import winreg
except ImportError:
    pass

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

import qutebrowser
from scripts import utils
from scripts.dev import update_3rdparty, misc_checks


IS_MACOS = sys.platform == 'darwin'
IS_WINDOWS = os.name == 'nt'


@dataclasses.dataclass
class Artifact:

    """A single file being uploaded to GitHub."""

    path: pathlib.Path
    mimetype: str
    description: str

    def __str__(self):
        return f"{self.path} ({self.mimetype}): {self.description}"


def call_script(name: str, *args: str, python: str = sys.executable) -> None:
    """Call a given shell script.

    Args:
        name: The script to call.
        *args: The arguments to pass.
        python: The python interpreter to use.
    """
    subprocess.run([python, REPO_ROOT / "scripts" / name, *args], check=True)


def call_tox(
    toxenv: str,
    *args: str,
    python: pathlib.Path = pathlib.Path(sys.executable),
    debug: bool = False,
) -> None:
    """Call tox.

    Args:
        toxenv: Which tox environment to use
        *args: The arguments to pass.
        python: The python interpreter to use.
        debug: Turn on pyinstaller debugging
    """
    env = os.environ.copy()
    env['PYTHON'] = str(python)
    env['PATH'] = os.environ['PATH'] + os.pathsep + str(python.parent)
    if debug:
        env['PYINSTALLER_DEBUG'] = '1'
    subprocess.run(
        [sys.executable, '-m', 'tox', '-vv', '-e', toxenv, *args],
        env=env, check=True)


def run_asciidoc2html() -> None:
    """Run the asciidoc2html script."""
    utils.print_title("Running asciidoc2html.py")
    call_script('asciidoc2html.py')


def _maybe_remove(path: pathlib.Path) -> None:
    """Remove a path if it exists."""
    try:
        shutil.rmtree(path)
    except FileNotFoundError:
        pass


def _filter_whitelisted(output: bytes, patterns: Iterable[str]) -> Iterable[str]:
    """Get all lines not matching any of the given regex patterns."""
    for line in output.decode('utf-8').splitlines():
        if not any(re.fullmatch(pattern, line) for pattern in patterns):
            yield line


def _smoke_test_run(
    executable: pathlib.Path,
    *args: str,
) -> subprocess.CompletedProcess:
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


def smoke_test(executable: pathlib.Path, debug: bool, qt6: bool) -> None:
    """Try starting the given qutebrowser executable."""
    stdout_whitelist = []
    stderr_whitelist = [
        # PyInstaller debug output
        r'\[.*\] PyInstaller Bootloader .*',
        r'\[.*\] LOADER: .*',
    ]
    if IS_MACOS:
        stderr_whitelist.extend([
            # macOS on Qt 5.15
            # https://github.com/qutebrowser/qutebrowser/issues/4919
            (r'objc\[.*\]: .* One of the two will be used\. '
            r'Which one is undefined\.'),
            (r'QCoreApplication::applicationDirPath: Please instantiate the '
            r'QApplication object first'),
            (r'\[.*:ERROR:mach_port_broker.mm\(48\)\] bootstrap_look_up '
            r'org\.chromium\.Chromium\.rohitfork\.1: Permission denied \(1100\)'),
            (r'\[.*:ERROR:mach_port_broker.mm\(43\)\] bootstrap_look_up: '
            r'Unknown service name \(1102\)'),

            # macOS on Qt 5.15
            (r'[0-9:]* WARNING: The available OpenGL surface format was either not '
            r'version 3\.2 or higher or not a Core Profile\.'),
            r'Chromium on macOS will fall back to software rendering in this case\.',
            r'Hardware acceleration and features such as WebGL will not be available\.',
            r'Unable to create basic Accelerated OpenGL renderer\.',
            r'Core Image is now using the software OpenGL renderer\. This will be slow\.',

            # https://github.com/qutebrowser/qutebrowser/issues/3719
            '[0-9:]* ERROR: Load error: ERR_FILE_NOT_FOUND',

            # macOS 11
            (r'[0-9:]* WARNING: Failed to load libssl/libcrypto\.'),

            # macOS?
            (r'\[.*:ERROR:command_buffer_proxy_impl.cc\([0-9]*\)\] '
            r'ContextResult::kTransientFailure: Failed to send '
            r'.*CreateCommandBuffer\.'),
        ])
        if qt6:
            stderr_whitelist.extend([
                # FIXME:qt6 Qt 6.3 on macOS
                r'[0-9:]* WARNING: Incompatible version of OpenSSL',
                r'[0-9:]* WARNING: Qt WebEngine resources not found at .*',
                (r'[0-9:]* WARNING: Installed Qt WebEngine locales directory not found at '
                r'location /qtwebengine_locales\. Trying application directory\.\.\.'),

                # https://github.com/pyinstaller/pyinstaller/pull/6903
                r"[0-9:]* INFO: Sandboxing disabled by user\.",
            ])
    elif IS_WINDOWS:
        stderr_whitelist.extend([
            # Windows N:
            # https://github.com/microsoft/playwright/issues/2901
            (r'\[.*:ERROR:dxva_video_decode_accelerator_win.cc\(\d+\)\] '
            r'DXVAVDA fatal error: could not LoadLibrary: .*: The specified '
            r'module could not be found. \(0x7E\)'),
        ])

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

        raise Exception("\n".join(lines))  # pylint: disable=broad-exception-raised


def verify_windows_exe(exe_path: pathlib.Path) -> None:
    """Make sure the Windows .exe has a correct checksum."""
    import pefile
    pe = pefile.PE(exe_path)
    assert pe.verify_checksum()


def patch_mac_app(qt6: bool) -> None:
    """Patch .app to save some space and make it signable."""
    dist_path = pathlib.Path('dist')
    ver = '6' if qt6 else '5'
    app_path = dist_path / 'qutebrowser.app'

    contents_path = app_path / 'Contents'
    macos_path = contents_path / 'MacOS'
    resources_path = contents_path / 'Resources'
    pyqt_path = macos_path / f'PyQt{ver}'

    # Replace some duplicate files by symlinks
    framework_path = pyqt_path / f'Qt{ver}' / 'lib' / 'QtWebEngineCore.framework'

    framework_resource_path = framework_path / 'Resources'
    for file_path in framework_resource_path.iterdir():
        target = pathlib.Path(*[os.pardir] * 5, file_path.name)
        if file_path.is_dir():
            shutil.rmtree(file_path)
        else:
            file_path.unlink()
        file_path.symlink_to(target)

    if qt6:
        # Symlinking QtWebEngineCore.framework does not seem to work with Qt 6.
        # Also, the symlinking/moving before signing doesn't seem to be required.
        return

    core_lib = framework_path / 'Versions' / '5' / 'QtWebEngineCore'
    core_lib.unlink()
    core_target = pathlib.Path(*[os.pardir] * 7, 'MacOS', 'QtWebEngineCore')
    core_lib.symlink_to(core_target)

    # Move stuff around to make things signable on macOS
    # See https://github.com/pyinstaller/pyinstaller/issues/6612
    pyqt_path_dest = resources_path / pyqt_path.name
    shutil.move(pyqt_path, pyqt_path_dest)
    pyqt_path_target = pathlib.Path("..") / pyqt_path_dest.relative_to(contents_path)
    pyqt_path.symlink_to(pyqt_path_target)

    for path in macos_path.glob("Qt*"):
        link_path = resources_path / path.name
        target_path = pathlib.Path("..") / path.relative_to(contents_path)
        link_path.symlink_to(target_path)


def sign_mac_app() -> None:
    """Re-sign and verify the Mac .app."""
    app_path = pathlib.Path('dist') / 'qutebrowser.app'
    subprocess.run([
        'codesign',
        '-s', '-',
        '--force',
        '--timestamp',
        '--deep',
        '--verbose',
        app_path,
    ], check=True)
    subprocess.run([
        'codesign',
        '--verify',
        '--strict',
        '--deep',
        '--verbose',
        app_path,
    ], check=True)


def _mac_bin_path(base: pathlib.Path) -> pathlib.Path:
    """Get the macOS qutebrowser binary path."""
    return pathlib.Path(base, 'qutebrowser.app', 'Contents', 'MacOS', 'qutebrowser')


def build_mac(
    *,
    gh_token: Optional[str],
    qt6: bool,
    skip_packaging: bool,
    debug: bool,
) -> List[Artifact]:
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
    update_3rdparty.run(ace=False, pdfjs=True, legacy_pdfjs=not qt6, fancy_dmg=False,
                        gh_token=gh_token)

    utils.print_title("Building .app via pyinstaller")
    call_tox(f'pyinstaller-64bit{"-qt6" if qt6 else ""}', '-r', debug=debug)
    utils.print_title("Patching .app")
    patch_mac_app(qt6=qt6)
    utils.print_title("Re-signing .app")
    sign_mac_app()

    dist_path = pathlib.Path("dist")

    utils.print_title("Running pre-dmg smoke test")
    smoke_test(_mac_bin_path(dist_path), debug=debug, qt6=qt6)

    if skip_packaging:
        return []

    utils.print_title("Building .dmg")
    dmg_makefile_path = REPO_ROOT / "scripts" / "dev" / "Makefile-dmg"
    subprocess.run(['make', '-f', dmg_makefile_path], check=True)

    suffix = "-debug" if debug else ""
    suffix += "-qt6" if qt6 else ""
    dmg_path = dist_path / f'qutebrowser-{qutebrowser.__version__}{suffix}.dmg'
    pathlib.Path('qutebrowser.dmg').rename(dmg_path)

    utils.print_title("Running smoke test")

    try:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = pathlib.Path(tmp)
            subprocess.run(['hdiutil', 'attach', dmg_path,
                            '-mountpoint', tmp_path], check=True)
            try:
                smoke_test(_mac_bin_path(tmp_path), debug=debug, qt6=qt6)
            finally:
                print("Waiting 10s for dmg to be detachable...")
                time.sleep(10)
                subprocess.run(['hdiutil', 'detach', tmp_path], check=False)
    except PermissionError as e:
        print(f"Failed to remove tempdir: {e}")

    return [
        Artifact(
            path=dmg_path,
            mimetype='application/x-apple-diskimage',
            description='macOS .dmg'
        )
    ]


def _get_windows_python_path(x64: bool) -> pathlib.Path:
    """Get the path to Python.exe on Windows."""
    parts = str(sys.version_info.major), str(sys.version_info.minor)
    ver = ''.join(parts)
    dot_ver = '.'.join(parts)

    if x64:
        path = rf'SOFTWARE\Python\PythonCore\{dot_ver}\InstallPath'
        fallback = pathlib.Path('C:', f'Python{ver}', 'python.exe')
    else:
        path = rf'SOFTWARE\WOW6432Node\Python\PythonCore\{dot_ver}-32\InstallPath'
        fallback = pathlib.Path('C:', f'Python{ver}-32', 'python.exe')

    try:
        key = winreg.OpenKeyEx(winreg.HKEY_LOCAL_MACHINE, path)
        return pathlib.Path(winreg.QueryValueEx(key, 'ExecutablePath')[0])
    except FileNotFoundError:
        return fallback


def _build_windows_single(
    *, x64: bool,
    qt6: bool,
    skip_packaging: bool,
    debug: bool,
) -> List[Artifact]:
    """Build on Windows for a single architecture."""
    human_arch = '64-bit' if x64 else '32-bit'
    utils.print_title(f"Running pyinstaller {human_arch}")
    dist_path = pathlib.Path("dist")

    arch = "x64" if x64 else "x86"
    out_path = dist_path / f'qutebrowser-{qutebrowser.__version__}-{arch}'
    _maybe_remove(out_path)

    python = _get_windows_python_path(x64=x64)
    suffix = "64bit" if x64 else "32bit"
    if qt6:
        # FIXME:qt6 does this regress 391623d5ec983ecfc4512c7305c4b7a293ac3872?
        suffix += "-qt6"
    call_tox(f'pyinstaller-{suffix}', '-r', python=python, debug=debug)

    out_pyinstaller = dist_path / "qutebrowser"
    shutil.move(out_pyinstaller, out_path)
    exe_path = out_path / 'qutebrowser.exe'

    utils.print_title(f"Verifying {human_arch} exe")
    verify_windows_exe(exe_path)

    utils.print_title(f"Running {human_arch} smoke test")
    smoke_test(exe_path, debug=debug, qt6=qt6)

    if skip_packaging:
        return []

    utils.print_title(f"Packaging {human_arch}")
    return _package_windows_single(
        nsis_flags=[] if x64 else ['/DX86'],
        out_path=out_path,
        filename_arch='amd64' if x64 else 'win32',
        desc_arch=human_arch,
        desc_suffix='' if x64 else ' (only for 32-bit Windows!)',
        debug=debug,
        qt6=qt6,
    )


def build_windows(
    *, gh_token: str,
    skip_packaging: bool,
    only_32bit: bool,
    only_64bit: bool,
    qt6: bool,
    debug: bool,
) -> List[Artifact]:
    """Build windows executables/setups."""
    utils.print_title("Updating 3rdparty content")
    update_3rdparty.run(nsis=True, ace=False, pdfjs=True, legacy_pdfjs=not qt6,
                        fancy_dmg=False, gh_token=gh_token)

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
            qt6=qt6,
        )
    if not only_64bit and not qt6:
        artifacts += _build_windows_single(
            x64=False,
            skip_packaging=skip_packaging,
            debug=debug,
            qt6=qt6,
        )

    return artifacts


def _package_windows_single(
    *,
    nsis_flags: List[str],
    out_path: pathlib.Path,
    desc_arch: str,
    desc_suffix: str,
    filename_arch: str,
    debug: bool,
    qt6: bool,
) -> List[Artifact]:
    """Build the given installer/zip for windows."""
    artifacts = []

    dist_path = pathlib.Path("dist")
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
    if qt6:
        name_parts.append('qt6')
    name = '-'.join(name_parts) + '.exe'

    artifacts.append(Artifact(
        path=dist_path / name,
        mimetype='application/vnd.microsoft.portable-executable',
        description=f'Windows {desc_arch} installer{desc_suffix}',
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
    if qt6:
        zip_name_parts.append('qt6')
    zip_name = '-'.join(zip_name_parts) + '.zip'

    zip_path = dist_path / zip_name
    shutil.make_archive(str(zip_path.with_suffix('')), 'zip', 'dist', out_path.name)
    artifacts.append(Artifact(
        path=zip_path,
        mimetype='application/zip',
        description=f'Windows {desc_arch} standalone{desc_suffix}',
    ))

    return artifacts


def build_sdist() -> List[Artifact]:
    """Build an sdist and list the contents."""
    utils.print_title("Building sdist")

    dist_path = pathlib.Path('dist')
    _maybe_remove(dist_path)

    subprocess.run([sys.executable, '-m', 'build'], check=True)

    dist_files = list(dist_path.glob('*.tar.gz'))
    filename = f'qutebrowser-{qutebrowser.__version__}.tar.gz'
    assert dist_files == [dist_path / filename], dist_files
    dist_file = dist_files[0]

    subprocess.run(['gpg', '--detach-sign', '-a', str(dist_file)], check=True)

    by_ext = collections.defaultdict(list)

    with tarfile.open(dist_file) as tar:
        for tarinfo in tar.getmembers():
            if not tarinfo.isfile():
                continue
            path = pathlib.Path(*pathlib.Path(tarinfo.name).parts[1:])
            by_ext[path.suffix].append(path)

    assert '.pyc' not in by_ext

    utils.print_title("sdist contents")

    for ext, paths in sorted(by_ext.items()):
        utils.print_subtitle(ext)
        print('\n'.join(str(p) for p in paths))

    artifacts = [
        Artifact(
            path=dist_file,
            mimetype='application/gzip',
            description='Source release',
        ),
        Artifact(
            path=dist_file.with_suffix(dist_file.suffix + '.asc'),
            mimetype='application/pgp-signature',
            description='Source release - PGP signature',
        ),
    ]

    return artifacts


def test_makefile() -> None:
    """Make sure the Makefile works correctly."""
    utils.print_title("Testing makefile")
    with tempfile.TemporaryDirectory() as tmpdir:
        subprocess.run(['make', '-f', 'misc/Makefile',
                        f'DESTDIR={tmpdir}', 'install'], check=True)


def read_github_token(
    arg_token: Optional[str], *,
    optional: bool = False,
) -> Optional[str]:
    """Read the GitHub API token from disk."""
    if arg_token is not None:
        return arg_token

    token_path = pathlib.Path.home() / '.gh_token'
    if not token_path.exists():
        if optional:
            return None
        else:
            raise Exception(  # pylint: disable=broad-exception-raised
                "GitHub token needed, but ~/.gh_token not found, "
                "and --gh-token not given.")

    token = token_path.read_text(encoding="ascii").strip()
    return token


def github_upload(artifacts: List[Artifact], tag: str, gh_token: str) -> None:
    """Upload the given artifacts to GitHub.

    Args:
        artifacts: A list of Artifacts to upload.
        tag: The name of the release tag
        gh_token: The GitHub token to use
    """
    # pylint: disable=broad-exception-raised
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
        raise Exception(f"No release found for {tag!r}!")

    for artifact in artifacts:
        while True:
            print(f"Uploading {artifact.path}")

            assets = [asset for asset in release.assets()
                      if asset.name == artifact.path.name]
            if assets:
                print(f"Assets already exist: {assets}")
                print("Press enter to continue anyways or Ctrl-C to abort.")
                input()

            try:
                with artifact.path.open('rb') as f:
                    release.upload_asset(
                        artifact.mimetype,
                        artifact.path.name,
                        f,
                        artifact.description,
                    )
            except github3.exceptions.ConnectionError as e:
                utils.print_error(f'Failed to upload: {e}')
                print("Press Enter to retry...", file=sys.stderr)
                input()
                print("Retrying!")

                assets = [asset for asset in release.assets()
                          if asset.name == artifact.path.name]
                if assets:
                    stray_asset = assets[0]
                    print(f"Deleting stray asset {stray_asset.name}")
                    stray_asset.delete()
            else:
                break


def pypi_upload(artifacts: List[Artifact]) -> None:
    """Upload the given artifacts to PyPI using twine."""
    utils.print_title("Uploading to PyPI...")
    run_twine('upload', artifacts)


def twine_check(artifacts: List[Artifact]) -> None:
    """Check packages using 'twine check'."""
    utils.print_title("Running twine check...")
    run_twine('check', artifacts, '--strict')


def run_twine(command: str, artifacts: List[Artifact], *args: str) -> None:
    paths = [a.path for a in artifacts]
    subprocess.run([sys.executable, '-m', 'twine', command, *args, *paths], check=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--skip-docs', action='store_true',
                        help="Don't generate docs")
    parser.add_argument('--gh-token', help="GitHub token to use.",
                        nargs='?')
    parser.add_argument('--upload', action='store_true', required=False,
                        help="Toggle to upload the release to GitHub.")
    parser.add_argument('--no-confirm', action='store_true', required=False,
                        help="Skip confirmation before uploading.")
    parser.add_argument('--skip-packaging', action='store_true', required=False,
                        help="Skip Windows installer/zip generation or macOS DMG.")
    parser.add_argument('--32bit', action='store_true', required=False,
                        help="Skip Windows 64 bit build.", dest='only_32bit')
    parser.add_argument('--64bit', action='store_true', required=False,
                        help="Skip Windows 32 bit build.", dest='only_64bit')
    parser.add_argument('--debug', action='store_true', required=False,
                        help="Build a debug build.")
    parser.add_argument('--qt6', action='store_true', required=False,
                        help="Build against PyQt6")
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
        pathlib.Path("qutebrowser", "html", "doc").mkdir(parents=True, exist_ok=True)
    else:
        run_asciidoc2html()

    if IS_WINDOWS:
        artifacts = build_windows(
            gh_token=gh_token,
            skip_packaging=args.skip_packaging,
            only_32bit=args.only_32bit,
            only_64bit=args.only_64bit,
            qt6=args.qt6,
            debug=args.debug,
        )
    elif IS_MACOS:
        artifacts = build_mac(
            gh_token=gh_token,
            skip_packaging=args.skip_packaging,
            qt6=args.qt6,
            debug=args.debug,
        )
    else:
        test_makefile()
        artifacts = build_sdist()
        twine_check(artifacts)
        upload_to_pypi = True

    if args.upload:
        version_tag = f"v{qutebrowser.__version__}"

        if not args.no_confirm:
            utils.print_title(f"Press enter to release {version_tag}...")
            input()

        assert gh_token is not None
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
