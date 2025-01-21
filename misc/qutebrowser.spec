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
    'CFBundleDocumentTypes': [
        {
            "CFBundleTypeIconFile": "document.icns",
            "CFBundleTypeName": name,
            "CFBundleTypeRole": "Viewer",
            "LSItemContentTypes": [content_type],
        }
        for name, content_type in [
            ("GIF image", "com.compuserve.gif"),
            ("HTML document", "public.html"),
            ("XHTML document", "public.xhtml"),
            ("JavaScript script", "com.netscape.javascript-source"),
            ("JPEG image", "public.jpeg"),
            ("MHTML document", "org.ietf.mhtml"),
            ("HTML5 Audio (Ogg)", "org.xiph.ogg-audio"),
            ("HTML5 Video (Ogg)", "org.xiph.oggv"),
            ("PNG image", "public.png"),
            ("SVG document", "public.svg-image"),
            ("Plain text document", "public.text"),
            ("HTML5 Video (WebM)", "org.webmproject.webm"),
            ("WebP image", "org.webmproject.webp"),
            ("PDF Document", "com.adobe.pdf"),
        ]
    ],
    'UTImportedTypeDeclarations': [
        {
            "UTTypeConformsTo": ["public.data", "public.content"],
            "UTTypeDescription": "MIME HTML document",
            "UTTypeIconFile": "document.icns",
            "UTTypeIdentifier": "org.ietf.mhtml",
            "UTTypeReferenceURL": "https://www.ietf.org/rfc/rfc2557",
            "UTTypeTagSpecification": {
                "com.apple.ostype": "MHTM",
                "public.filename-extension": ["mht", "mhtml"],
                "public.mime-type": ["multipart/related", "application/x-mimearchive"],
            },
        },
        {
            "UTTypeConformsTo": ["public.audio"],
            "UTTypeDescription": "Ogg Audio",
            "UTTypeIconFile": "document.icns",
            "UTTypeIdentifier": "org.xiph.ogg-audio",
            "UTTypeReferenceURL": "https://xiph.org/ogg/",
            "UTTypeTagSpecification": {
                "public.filename-extension": ["ogg", "oga"],
                "public.mime-type": ["audio/ogg"],
            },
        },
        {
            "UTTypeConformsTo": ["public.movie"],
            "UTTypeDescription": "Ogg Video",
            "UTTypeIconFile": "document.icns",
            "UTTypeIdentifier": "org.xiph.ogv",
            "UTTypeReferenceURL": "https://xiph.org/ogg/",
            "UTTypeTagSpecification": {
                "public.filename-extension": ["ogm", "ogv"],
                "public.mime-type": ["video/ogg"],
            },
        },
    ],
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
        ('../qutebrowser/html', 'qutebrowser/html'),
        ('../qutebrowser/img', 'qutebrowser/img'),
        ('../qutebrowser/icons', 'qutebrowser/icons'),
        ('../qutebrowser/javascript', 'qutebrowser/javascript'),
        ('../qutebrowser/html/doc', 'qutebrowser/html/doc'),
        ('../qutebrowser/git-commit-id', 'qutebrowser/git-commit-id'),
        ('../qutebrowser/config/configdata.yml', 'qutebrowser/config'),
    ]

    if os.path.exists(os.path.join('qutebrowser', '3rdparty', 'pdfjs')):
        data_files.append(('../qutebrowser/3rdparty/pdfjs', 'qutebrowser/3rdparty/pdfjs'))
    else:
        print("Warning: excluding pdfjs as it's not present!")

    return data_files


def get_hidden_imports():
    imports = ["PyQt5.QtOpenGL"] if "PYINSTALLER_QT5" in os.environ else []
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
if DEBUG:
  options = options = [('v', None, 'OPTION')]
else:
  options = []



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
          options,
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
             bundle_identifier='org.qutebrowser.qutebrowser')
