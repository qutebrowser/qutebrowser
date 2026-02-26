"""Settings for dmgbuild."""


volume_name = "qutebrowser"


files = [
    'dist/qutebrowser.app',
    'LICENSE',
]

symlinks = {
    'Applications': '/Applications',
}

badge_icon = 'qutebrowser/icons/qutebrowser.icns'

# Window position and size
window_rect = ((100, 100), (600, 400))

icon_locations = {
    'qutebrowser.app': (140, 200),
    'Applications': (460, 200),
    'LICENSE': (300, 300),
}
