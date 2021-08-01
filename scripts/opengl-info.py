from PyQt5.QtGui import QOpenGLContext, QOpenGLVersionProfile, QOffscreenSurface, QGuiApplication

app = QGuiApplication([])

surface = QOffscreenSurface()
surface.create()

ctx = QOpenGLContext()
ok = ctx.create()
assert ok

ok = ctx.makeCurrent(surface)
assert ok

print("GLES: {}".format(ctx.isOpenGLES()))

vp = QOpenGLVersionProfile()
vp.setVersion(2, 0)

vf = ctx.versionFunctions(vp)
print("Vendor: {}".format(vf.glGetString(vf.GL_VENDOR)))
print("Renderer: {}".format(vf.glGetString(vf.GL_RENDERER)))
print("Version: {}".format(vf.glGetString(vf.GL_VERSION)))
print("Shading language version: {}".format(vf.glGetString(vf.GL_SHADING_LANGUAGE_VERSION)))

ctx.doneCurrent()
