"""examples/pyosg-gbuffer.py run unmodified and headless (EGL pbuffer), both modes.

Each run is a subprocess, as a real example run would be: the example imports pyosg_example,
which sets GL 4.6 core-profile defaults on the process-wide DisplaySettings singleton; inside the
pytest process every later DisplaySettings-seeded context would become core profile, where the
fixed-function drawables other tests render draw nothing.
"""

import json
import os
import subprocess
import sys

import pytest

from OpenSceneGraph import *

from .aipython_scene import EXAMPLES, build_dir

osgx = pytest.importorskip("osgx")

if not hasattr(osgx.platform, "createEGLWindow"):
	pytest.skip("osgx built without OSGX_WITH_EGL", allow_module_level=True)

W, H = 800, 600

RUNNER = """
import importlib.util, json, os, sys

os.environ.pop("DISPLAY", None)

build, examples, out, mode = sys.argv[1:5]
sys.path[:0] = [build, examples]

import pyosg_example

from OpenSceneGraph import *
import pyosg_repl

spec = importlib.util.spec_from_file_location("pyosg_gbuffer", os.path.join(examples, "pyosg-gbuffer.py"))
example = importlib.util.module_from_spec(spec)
spec.loader.exec_module(example)

sys.argv = ["pyosg-gbuffer.py"] + sys.argv[5:]

viewer = pyosg_repl.headless_viewer({W}, {H})
root = example.build_scene({W}, {H})
viewer.sceneData = root

example.configure_viewer(viewer, root)

ctl = pyosg_repl.ViewerREPLController(viewer)
paths = {{"backbuffer": os.path.join(out, mode + ".png")}}

ctl.complete(ctl.capture_framebuffer(paths["backbuffer"]))

if mode == "generic":
	paths["color0"] = os.path.join(out, mode + "-color0.png")
	color = root.children[1].stateSet.textureAttributes[0]
	ctl.complete(ctl.capture_texture(color, paths["color0"]))

paths["glVersion"] = viewer.camera.graphicsContext.state.glExtensions.glVersion

print("RESULT " + json.dumps(paths))
""".format(W=W, H=H)

def run_example(tmp_path, mode, *args):
	script = tmp_path / "runner.py"

	script.write_text(RUNNER)

	env = dict(os.environ, OSG_NOTIFY_LEVEL="WARN")

	proc = subprocess.run(
		[sys.executable, str(script), build_dir(), EXAMPLES, str(tmp_path), mode, *args],
		env=env,
		capture_output=True,
		text=True,
		timeout=120,
	)

	lines = [line for line in proc.stdout.splitlines() if line.startswith("RESULT ")]

	assert proc.returncode == 0 and lines, proc.stdout + proc.stderr

	return json.loads(lines[-1][len("RESULT "):])

def load(path):
	image = osgDB.readImageFile(path)

	assert image is not None
	assert (image.s, image.t) == (W, H)

	data = memoryview(image).tobytes()
	stride = len(data) // (W * H)

	def pixel(x, y):
		i = (y * W + x) * stride

		return tuple(data[i:i + stride])

	return pixel

def test_generic_gbuffer_headless(tmp_path):
	result = run_example(tmp_path, "generic")

	# pyosg_example requests 4.6 core; the headless context honors it.
	assert result["glVersion"] >= 4.5

	backbuffer = load(result["backbuffer"])

	assert backbuffer(0, 0) == (0, 0, 0)

	box = backbuffer(220, 300)
	sphere = backbuffer(540, 300)

	assert box[0] > 200 and box[2] < 80 # flat red box (0.95, 0.2, 0.15)
	assert sphere[2] > 200 and sphere[0] < 80 # flat blue sphere (0.15, 0.55, 1.0)

	# The raw RGBA8 attachment: transparent black where no geometry was written.
	color0 = load(result["color0"])

	assert color0(0, 0) == (0, 0, 0, 0)
	assert color0(540, 300)[:3] == sphere and color0(540, 300)[3] == 255

def test_deferred_pbr_gbuffer_headless(tmp_path):
	hdr = osgx.findDataFile("glTF-Sample-Environments/footprint_court.hdr")

	if not hdr:
		pytest.skip("footprint_court.hdr not found on OSG_FILE_PATH")

	result = run_example(tmp_path, "pbr", "--hdr", hdr)

	backbuffer = load(result["backbuffer"])

	# No skybox: pixels outside the sphere keep OSG's default clear color (0.2, 0.2, 0.4).
	assert all(abs(a - b) <= 2 for a, b in zip(backbuffer(0, 0), (51, 51, 102)))

	# Metallic orange (0.9, 0.35, 0.08) reflecting the environment: warm, and NOT flat.
	center = backbuffer(400, 300)

	assert center[0] > center[2]

	colors = {backbuffer(x, y) for x in range(330, 470, 4) for y in range(230, 370, 4)}

	assert len(colors) > 100
