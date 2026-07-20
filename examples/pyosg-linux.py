#!/usr/bin/env python3
#vimrun! python3 ../examples/pyosg-linux.py

import os
import sys
import time

os.environ.update({
	"OSG_THREADING": "SingleThreaded",
	"OSG_GL_CONTEXT_PROFILE_MASK": "1",
	"OSG_GL_VERSION": "4.6",
	"OSG_GL_CONTEXT_VERSION": "4.6"
})

from OpenSceneGraph import *

# A minimal demo of the two custom osgViewer::GraphicsWindow implementations in
# OpenSceneGraph.linux: createEGLWindow() (an ordinary X11 window, but driven by
# EGL instead of GLX) and createGBMWindow() (no X11 at all - direct DRM/KMS
# scanout). Both are skeleton/proof-of-concept implementations; see the
# docstrings on each for caveats - createGBMWindow() in particular requires
# exclusive DRM master access, so it will fail if an X server already owns the
# GPU (run it from a bare TTY instead).
#
# OSG_WINDOW is deliberately left unset: setting it would trigger OSG's normal
# windowing path, which is exactly what we're replacing here by assigning our
# own GraphicsContext directly.
if __name__ == "__main__":
	args = sys.argv[1:]
	gbm = "--gbm" in args

	if gbm:
		args.remove("--gbm")

	path = args[0] if args else "glsl_simple.osgt"
	node = osgDB.readNodeFile(path)

	if not node:
		sys.exit(f"Failed to load '{path}'")

	traits = osg.GraphicsContext.Traits()

	traits.width = 800
	traits.height = 600

	gc = linux.createGBMWindow(traits) if gbm else linux.createEGLWindow(traits)

	if not gc or not gc.valid():
		sys.exit(f"Failed to create {'GBM' if gbm else 'EGL'} window")

	v = osgViewer.Viewer()

	v.sceneData = node
	v.cameraManipulator = osgGA.TrackballManipulator()
	v.camera.graphicsContext = gc
	v.camera.viewport = (0, 0, traits.width, traits.height)
	v.camera.renderTargetImplementation = osg.Camera.FRAME_BUFFER

	while not v.done:
		v.frame()

		time.sleep(0.01)
