# -*- mode: python -*-

import sys
import os

sys.path.insert(0, os.getcwd())
from scripts import setupcommon

import qutebrowser
from qutebrowser.extensions import loader

block_cipher = None


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
    }, {
        "CFBundleTypeExtensions": ["mhtml"],
        "CFBundleTypeMIMETypes": ["multipart/related", "application/x-mimearchive", "message/rfc822"],
        "CFBundleTypeName": "MHTML document",
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
    imports = [] if "PYINSTALLER_QT6" in os.environ else ['PyQt5.QtOpenGL']
    for info in loader.walk_components():
        imports.append(info.name)
    return imports


setupcommon.write_git_file()


if os.name == 'nt':
    icon = '../qutebrowser/icons/qutebrowser.ico'
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
             info_plist=INFO_PLIST_UPDATES,
             # https://github.com/pyinstaller/pyinstaller/blob/b78bfe530cdc2904f65ce098bdf2de08c9037abb/PyInstaller/hooks/hook-PyQt5.QtWebEngineWidgets.py#L24
             bundle_identifier='org.qt-project.Qt.QtWebEngineCore')
