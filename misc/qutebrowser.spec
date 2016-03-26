# -*- mode: python -*-

block_cipher = None


def get_data_files():
    data_files = [
        ('../qutebrowser/html', 'html'),
        ('../qutebrowser/img', 'img'),
        ('../qutebrowser/javascript', 'javascript'),
        ('../qutebrowser/html/doc', 'html/doc'),
    ]

    if os.path.exists(os.path.join('qutebrowser', '3rdparty', 'pdfjs')):
        data_files.append(('../qutebrowser/3rdparty/pdfjs', '3rdparty/pdfjs'))
    else:
        print("Warning: excluding pdfjs as it's not present!")

    return data_files


a = Analysis(['../qutebrowser.py'],
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
