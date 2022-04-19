# -*- mode: python -*-

import sys
import os
import pathlib

sys.path.insert(0, os.getcwd())
from scripts import setupcommon

from qutebrowser.extensions import loader

block_cipher = None


def get_data_files():
    data_files = [
        ('../qutebrowser/html', 'html'),
        ('../qutebrowser/img', 'img'),
        ('../qutebrowser/icons', 'icons'),
        ('../qutebrowser/javascript', 'javascript'),
        ('../qutebrowser/html/doc', 'html/doc'),
        ('../qutebrowser/git-commit-id', '.'),
        ('../qutebrowser/config/configdata.yml', 'config'),
    ]

    if os.path.exists(os.path.join('qutebrowser', '3rdparty', 'pdfjs')):
        data_files.append(('../qutebrowser/3rdparty/pdfjs', '3rdparty/pdfjs'))
    else:
        print("Warning: excluding pdfjs as it's not present!")

    return data_files


def get_hidden_imports():
    imports = ['PyQt5.QtOpenGL', 'PyQt5._QOpenGLFunctions_2_0']
    for info in loader.walk_components():
        imports.append(info.name)
    return imports


setupcommon.write_git_file()


if os.name == 'nt':
    # WORKAROUND for PyInstaller 5.0 bug:
    # https://github.com/pyinstaller/pyinstaller/issues/6759
    icons_path = pathlib.Path.cwd() / 'qutebrowser' / 'icons'
    icon = str(icons_path / 'qutebrowser.ico')
elif sys.platform == 'darwin':
    icon = '../qutebrowser/icons/qutebrowser.icns'
else:
    icon = None


DEBUG = os.environ.get('PYINSTALLER_DEBUG', '').lower() in ['1', 'true']


a = Analysis(['../qutebrowser/__main__.py'],
             pathex=['misc'],
             binaries=None,
             datas=get_data_files(),
             hiddenimports=get_hidden_imports(),
             hookspath=[],
             runtime_hooks=[],
             excludes=['tkinter'],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          exclude_binaries=True,
          name='qutebrowser',
          icon=icon,
          debug=DEBUG,
          strip=False,
          upx=False,
          console=DEBUG,
          version='../misc/file_version_info.txt')
coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               strip=False,
               upx=False,
               name='qutebrowser')

app = BUNDLE(coll,
             name='qutebrowser.app',
             icon=icon,
             # https://github.com/pyinstaller/pyinstaller/blob/b78bfe530cdc2904f65ce098bdf2de08c9037abb/PyInstaller/hooks/hook-PyQt5.QtWebEngineWidgets.py#L24
             bundle_identifier='org.qt-project.Qt.QtWebEngineCore')
