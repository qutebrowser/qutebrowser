# -*- mode: python -*-

import sys
import os

sys.path.insert(0, os.getcwd())
from scripts import setupcommon

block_cipher = None


def get_data_files():
    data_files = [
        ('../qutebrowser/html', 'html'),
        ('../qutebrowser/img', 'img'),
        ('../qutebrowser/javascript', 'javascript'),
        ('../qutebrowser/html/doc', 'html/doc'),
        ('../qutebrowser/git-commit-id', '')
    ]

    if os.path.exists(os.path.join('qutebrowser', '3rdparty', 'pdfjs')):
        data_files.append(('../qutebrowser/3rdparty/pdfjs', '3rdparty/pdfjs'))
    else:
        print("Warning: excluding pdfjs as it's not present!")

    return data_files


setupcommon.write_git_file()


if os.name == 'nt':
    icon = 'icons/qutebrowser.ico'
elif sys.platform == 'darwin':
    icon = 'icons/qutebrowser.icns'
else:
    icon = None


a = Analysis(['../qutebrowser/__main__.py'],
             pathex=['misc'],
             binaries=None,
             datas=get_data_files(),
             hiddenimports=[],
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
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
          debug=False,
          strip=False,
          upx=True,
          console=False )
coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               strip=False,
               upx=True,
               name='qutebrowser')

app = BUNDLE(coll,
             name='qutebrowser.app',
             icon=icon,
             info_plist={'NSHighResolutionCapable': 'True'},
             bundle_identifier=None)
