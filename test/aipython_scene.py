"""Shared scene setup/verification for the aipython backend tests (not collected by pytest)."""

import os
import shutil

import pytest

from OpenSceneGraph import *

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
EXAMPLES = os.path.join(REPO, "examples")

W, H = 160, 120
CLEAR = (0.1, 0.3, 0.2)

def build_dir():
	"""The BUILD-* dir conftest.py put on sys.path, as an absolute path for a child process."""

	for name in ("BUILD-g++-13.3.0-NOASAN", "BUILD-g++-15.2.1-NOASAN"):
		path = os.path.join(REPO, name)

		if os.path.isdir(os.path.join(path, "OpenSceneGraph")):
			return path

	pytest.skip("no OpenSceneGraph.py build dir found")

def require_headless():
	"""Skip unless osgx (with EGL) and aipython are importable in this environment."""

	osgx = pytest.importorskip("osgx")

	if not hasattr(osgx.platform, "createEGLWindow"):
		pytest.skip("osgx built without OSGX_WITH_EGL")

	pytest.importorskip("aipython.integration")

def require_tmux():
	if shutil.which("tmux") is None:
		pytest.skip("tmux not installed")

def setup_source():
	"""Source that builds a headless scene and hands it to pyosg_repl.repl().

	Under ipykernel repl() returns immediately and frames run between cells; under terminal
	IPython it blocks inside the embedded prompt. Either way the session namespace ends up with
	`_osg_repl_controller`.
	"""

	return f"""
import os, sys
os.environ.pop("DISPLAY", None)
os.environ["OSG_THREADING"] = "SingleThreaded"
sys.path[:0] = [{build_dir()!r}, {EXAMPLES!r}]
from OpenSceneGraph import *
import pyosg_repl
viewer = pyosg_repl.headless_viewer({W}, {H})
root = osg.Group()
root.children.append(osg.ShapeDrawable(osg.Sphere(osg.Vec3(0, 0, 0), 1.0)))
viewer.sceneData = root
viewer.camera.clearColor = osg.Vec4({CLEAR[0]}, {CLEAR[1]}, {CLEAR[2]}, 1.0)
viewer.camera.viewMatrix = osg.Matrixd.lookAt(osg.Vec3d(0, -8, 0), osg.Vec3d(0, 0, 0), osg.Vec3d(0, 0, 1))
pyosg_repl.repl(viewer, globals())
"""

def verify_capture(path):
	"""Reload a captured PNG and check it shows the clear color at a corner and the sphere
	at the center."""

	assert os.path.getsize(path) > 0

	image = osgDB.readImageFile(path)

	assert image is not None
	assert (image.s, image.t) == (W, H)

	data = memoryview(image).tobytes()
	stride = len(data) // (W * H)

	def pixel(x, y):
		i = (y * W + x) * stride

		return tuple(data[i:i + 3])

	def is_clear(rgb):
		return all(abs(c - round(v * 255)) <= 2 for c, v in zip(rgb, CLEAR))

	assert is_clear(pixel(0, 0))
	assert not is_clear(pixel(W // 2, H // 2))
