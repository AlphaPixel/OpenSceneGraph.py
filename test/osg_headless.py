import asyncio
import os
import sys

import pytest

from OpenSceneGraph import *
from OpenSceneGraph.GL import *

W, H = 160, 120
CLEAR = (0.1, 0.3, 0.2)

def add_scene(viewer):
	"""The pixel-checked test scene: a unit sphere on CLEAR, framed identically everywhere."""

	root = osg.Group()

	root.children.append(osg.ShapeDrawable(osg.Sphere(osg.Vec3(0, 0, 0), 1.0)))

	viewer.sceneData = root
	viewer.camera.viewport = (0, 0, W, H)
	viewer.camera.clearColor = osg.Vec4(*CLEAR, 1.0)
	viewer.camera.projectionMatrix = osg.Matrixd.perspective(30.0, W / H, 1.0, 100.0)
	viewer.camera.viewMatrix = osg.Matrixd.lookAt(
		osg.Vec3d(0, -8, 0), osg.Vec3d(0, 0, 0), osg.Vec3d(0, 0, 1)
	)

	return viewer

@pytest.fixture
def viewer(monkeypatch, repl_module):
	# The pbuffer path must not need an X server at all.
	monkeypatch.delenv("DISPLAY", raising=False)

	return add_scene(repl_module.headless_viewer(W, H))

def read_rgb():
	image = osg.Image()

	image.readPixels(0, 0, W, H, GL_RGB, GL_UNSIGNED_BYTE)

	return memoryview(image).tobytes()

def pixel(data, x, y):
	i = (y * W + x) * 3

	return tuple(data[i:i + 3])

def is_clear(rgb):
	return all(abs(c - round(v * 255)) <= 2 for c, v in zip(rgb, CLEAR))

def render_once(viewer):
	frames = []

	viewer.camera.finalDrawCallback = lambda ri: frames.append(read_rgb())
	viewer.frame()

	return frames[0]

def test_pbuffer_renders_scene(viewer):
	frames = []

	viewer.camera.finalDrawCallback = lambda ri: frames.append(read_rgb())

	viewer.frame()

	assert len(frames) == 1
	assert len(frames[0]) == W * H * 3
	assert is_clear(pixel(frames[0], 0, 0))
	assert not is_clear(pixel(frames[0], W // 2, H // 2))

def test_camera_draw_callback_super_call_does_not_recurse(viewer):
	calls = []

	class Final(osg.Camera.DrawCallback):
		def __call__(self, ri):
			calls.append(ri.contextID)

			super().__call__(ri)

	viewer.camera.finalDrawCallback = Final()

	viewer.frame()

	assert len(calls) == 1

# ------------------------------------------------------------------------------------------ #
# pyosg_repl's ViewerREPLController (requires the aipython package to be importable)
# ------------------------------------------------------------------------------------------ #

@pytest.fixture
def repl_module():
	sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "examples"))

	try:
		import pyosg_repl

	except ImportError as exc:
		pytest.skip(f"pyosg_repl unavailable: {exc}")

	finally:
		sys.path.pop(0)

	return pyosg_repl

def test_controller_complete_writes_capture(viewer, repl_module, tmp_path):
	ctl = repl_module.ViewerREPLController(viewer)
	path = str(tmp_path / "frame.png")

	result = ctl.complete(ctl.capture_framebuffer(path, label="sphere"))

	assert result["label"] == "sphere"
	assert result["size"] == (W, H)
	assert os.path.getsize(path) > 0

def test_controller_chains_existing_final_draw_callback(viewer, repl_module):
	calls = []

	viewer.camera.finalDrawCallback = lambda ri: calls.append(ri.contextID)

	ctl = repl_module.ViewerREPLController(viewer)

	ctl.complete(ctl.capture_framebuffer_image())

	assert len(calls) >= 1

def test_controller_rejects_replaced_capture_hook(viewer, repl_module):
	ctl = repl_module.ViewerREPLController(viewer)

	viewer.camera.finalDrawCallback = lambda ri: None

	with pytest.raises(RuntimeError, match="replaced"):
		ctl.capture_framebuffer_image()

def test_controller_await_under_kernel_raises(viewer, repl_module):
	ctl = repl_module.ViewerREPLController(viewer)
	request = ctl.capture_framebuffer_image()

	ctl.state["backend"] = "kernel"

	async def wait():
		await request

	with pytest.raises(RuntimeError, match="complete"):
		asyncio.run(wait())

def test_controller_await_resolves_under_event_loop(viewer, repl_module):
	ctl = repl_module.ViewerREPLController(viewer)

	async def awaiter(request):
		return await request

	async def wait():
		request = ctl.capture_framebuffer_image()
		# Start awaiting while the capture is still pending, as a terminal IPython cell does.
		task = asyncio.ensure_future(awaiter(request))

		await asyncio.sleep(0)

		while not task.done():
			ctl._step_once()

			await asyncio.sleep(0)

		return task.result()

	result = asyncio.run(wait())

	assert result["size"] == (W, H)
	assert "image" in result

def test_controller_preview_downscale(viewer, repl_module, tmp_path):
	ctl = repl_module.ViewerREPLController(viewer)
	path = str(tmp_path / "frame.png")

	result = ctl.complete(ctl.capture_framebuffer(path, preview_downscale=2))

	assert result["size"] == (W, H)
	assert result["preview"] == str(tmp_path / "frame.preview.png")
	assert result["preview_size"] == (W // 2, H // 2)

	preview = osgDB.readImageFile(result["preview"])
	data = memoryview(preview).tobytes()
	stride = len(data) // (preview.s * preview.t)

	def at(x, y):
		i = (y * preview.s + x) * stride

		return tuple(data[i:i + 3])

	assert (preview.s, preview.t) == (W // 2, H // 2)
	assert is_clear(at(0, 0))
	assert not is_clear(at(preview.s // 2, preview.t // 2))

def test_controller_preview_downscale_validation(viewer, repl_module):
	ctl = repl_module.ViewerREPLController(viewer)

	with pytest.raises(ValueError):
		ctl.capture_framebuffer("x.png", preview_downscale=1)

	with pytest.raises(ValueError):
		ctl.capture_framebuffer("x.png", preview_downscale=1.5)

# ------------------------------------------------------------------------------------------ #
# OSG's native per-platform pbuffer (the non-EGL fallback: WGL/Cocoa/GLX)
# ------------------------------------------------------------------------------------------ #

def test_traits_read_display(monkeypatch):
	monkeypatch.setenv("DISPLAY", ":3.1")

	traits = osg.GraphicsContext.Traits()

	traits.readDISPLAY()

	assert (traits.displayNum, traits.screenNum) == (3, 1)
	assert traits.displayName == ":3.1"

def test_headless_viewer_rejects_unknown_backend(repl_module):
	with pytest.raises(ValueError, match="backend"):
		repl_module.headless_viewer(W, H, backend="vulkan")

def test_native_pbuffer_backend_renders(repl_module):
	# On Linux this is GLX's PixelBufferX11, so it needs a real X display (unlike the EGL path).
	if not os.environ.get("DISPLAY"):
		pytest.skip("native pbuffer on Linux needs an X display")

	viewer = add_scene(repl_module.headless_viewer(W, H, backend="native"))

	assert not viewer.camera.graphicsContext.traits.doubleBuffer

	data = render_once(viewer)

	assert is_clear(pixel(data, 0, 0))
	assert not is_clear(pixel(data, W // 2, H // 2))
