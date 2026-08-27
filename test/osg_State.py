#vimrun! pytest -sv ../test/osg_State.py

from OpenSceneGraph import osgGA, osgViewer
from OpenSceneGraph.osg import GLExtensions

def _realized_state():
	# osg.State has no Python constructor -- the only way to reach one is through a real
	# GraphicsContext, and GLExtensions only reports real values (glVersion, isXxxSupported,
	# ...) once that context has actually been made current at least once; before that it's
	# GLExtensions's own documented "no valid context" fallback (glVersion == 0.0, everything
	# else False). realize() alone typically already triggers this -- GraphicsContext.
	# makeCurrent() calls State.initializeExtensionProcs() internally -- but a frame() is cheap
	# insurance against relying on that being realize()'s behavior specifically.
	viewer = osgViewer.Viewer()

	viewer.cameraManipulator = osgGA.TrackballManipulator()
	viewer.realize()
	viewer.frame()

	return viewer.camera.graphicsContext.state

def test_gl_extensions_reports_real_context_info():
	state = _realized_state()
	ext = state.glExtensions

	assert isinstance(ext, GLExtensions)
	assert ext.contextID == state.contextID

	# 0.0 is GLExtensions's fallback for "no valid context" -- realize()+frame() above should
	# rule that out here.
	assert ext.glVersion > 0.0

	# This project's baseline: GL3/CORE, GLSL required (see README "Key Features").
	assert ext.glVersion >= 3.0
	assert ext.isGlslSupported

def test_gl_extensions_identity_is_stable():
	# GLExtensions::Get() is OSG's OWN per-contextID cache (a static registry) -- State.
	# glExtensions deliberately does NOT layer a pyx::PropertySlot identity cache on top of it
	# (see the comment in State.cpp). This confirms pybind11's own instance registry alone is
	# enough to keep repeated access to the SAME underlying C++ object returning the SAME
	# Python wrapper.
	state = _realized_state()

	assert state.glExtensions is state.glExtensions
