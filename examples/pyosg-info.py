#!/usr/bin/env python3

# Quick diagnostic dump, not an interactive viewer: build_info() from OpenSceneGraph (and osgx,
# if installed), the REQUESTED GL context (DisplaySettings, sourced from the OSG_GL_VERSION/
# OSG_GL_CONTEXT_VERSION/OSG_GL_CONTEXT_PROFILE_MASK env vars set below), what a realized
# GraphicsContext's own Traits resolved that request to, and what the driver ACTUALLY granted
# (State.glExtensions). Realizes just long enough to populate that last part, then exits.
# Edit the env vars below (or unset them) to see how the three stages diverge -- e.g. request a
# GL version the driver doesn't support and watch Traits echo the request back while
# GLExtensions reports what was actually negotiated instead.

import os
import sys

os.environ.update({
	"OSG_WINDOW": "50 50 100 100",
	"OSG_THREADING": "SingleThreaded",
	"OSG_GL_CONTEXT_PROFILE_MASK": "1",
	"OSG_GL_VERSION": "4.6",
	"OSG_GL_CONTEXT_VERSION": "4.6",
})

from OpenSceneGraph import *

GL_EXTENSION_FIELDS = (
	"contextID",
	"glVersion",
	"glslLanguageVersion",
	"isGlslSupported",
	"isShaderObjectsSupported",
	"isVertexShaderSupported",
	"isFragmentShaderSupported",
	"isLanguage100Supported",
	"isGeometryShader4Supported",
	"areTessellationShadersSupported",
	"isGpuShader4Supported",
	"isUniformBufferObjectSupported",
	"isGetProgramBinarySupported",
	"isGpuShaderFp64Supported",
	"isShaderAtomicCountersSupported",
	"isRectangleSupported",
	"isCubeMapSupported",
	"isClipControlSupported",
)

def section(title):
	print(f"\n== {title} ==")

def dump(label, value):
	# Display-only rounding: glVersion/glslLanguageVersion are C++ `float` (32-bit), so e.g.
	# 4.6's nearest float32 widens to 4.599999904632568 once pybind11 hands it back as a
	# Python (64-bit) float -- a real, if slightly lossy, binary representation, not corrupted
	# data. Round here for a readable dump only; anything doing a real comparison against
	# these values should still read the unrounded field directly.
	if isinstance(value, float):
		value = round(value, 4)

	print(f"  {label:<32} {value}")

def main(viewer):
	section("build_info()")

	for key, value in build_info().items():
		dump(key, value)

	try:
		import osgx

		section("build_info() [osgx]")

		for key, value in osgx.build_info().items():
			dump(key, value)

	except ImportError:
		section("osgx")
		dump("status", "not installed")

	section("DisplaySettings (requested)")

	ds = osg.DisplaySettings.instance

	dump("glContextVersion", repr(ds.glContextVersion))
	dump("glContextProfileMask", ds.glContextProfileMask)
	dump("glContextFlags", ds.glContextFlags)
	dump("numMultiSamples", ds.numMultiSamples)

	# viewer = osgViewer.Viewer()
	#
	# viewer.cameraManipulator = osgGA.TrackballManipulator()
	viewer.realize()
	viewer.frame()

	gc = viewer.camera.graphicsContext

	if not gc or not gc.valid():
		sys.exit("error: failed to realize a GraphicsContext")

	traits = gc.traits

	section("GraphicsContext.Traits (resolved)")

	dump("x, y", f"{traits.x}, {traits.y}")
	dump("width, height", f"{traits.width}, {traits.height}")
	dump("glContextVersion", repr(traits.glContextVersion))
	dump("glContextProfileMask", traits.glContextProfileMask)
	dump("glContextFlags", traits.glContextFlags)

	section("GLExtensions (actual, from the driver)")

	ext = gc.state.glExtensions

	for field in GL_EXTENSION_FIELDS:
		dump(field, getattr(ext, field))

	print()

	viewer.close()

def build_scene(*args):
	return None

def configure_viewer(viewer, root):
	main(viewer)

if __name__ == "__main__":
	main(osgViewer.Viewer())
