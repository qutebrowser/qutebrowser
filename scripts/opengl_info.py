#!/usr/bin/env python3

# SPDX-FileCopyrightText: Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later


"""Show information about the OpenGL setup."""

from PyQt6.QtGui import QOpenGLContext, QOffscreenSurface, QGuiApplication
from PyQt6.QtOpenGL import QOpenGLVersionProfile, QOpenGLVersionFunctionsFactory

app = QGuiApplication([])

surface = QOffscreenSurface()
surface.create()

ctx = QOpenGLContext()
ok = ctx.create()
assert ok

ok = ctx.makeCurrent(surface)
assert ok

print(f"GLES: {ctx.isOpenGLES()}")

vp = QOpenGLVersionProfile()
vp.setVersion(2, 0)

vf = QOpenGLVersionFunctionsFactory.get(vp, ctx)
print(f"Vendor: {vf.glGetString(vf.GL_VENDOR)}")
print(f"Renderer: {vf.glGetString(vf.GL_RENDERER)}")
print(f"Version: {vf.glGetString(vf.GL_VERSION)}")
print(f"Shading language version: {vf.glGetString(vf.GL_SHADING_LANGUAGE_VERSION)}")

ctx.doneCurrent()
