#!/usr/bin/env python3
"""Thin Python viewer for osgx.gltf.pbribl.PBRIBLScene.create().

This is the Python counterpart to osgx/utils/osgx-gltf-viewer.cpp. It loads the model, selects
optional diagnostics, and drives an osgViewer.Viewer.
"""

import argparse
import json
import math
import os
import pathlib
import time

# os.environ.setdefault("OSG_WINDOW", "50 50 800 600")
os.environ.setdefault("OSG_WINDOW", "50 50 1420 933") # Default on cubicool's machine
os.environ.setdefault(
	"OSG_LIBRARY_PATH", ":".join((
		"/home/cubicool/dev/osgx/BUILD-g++-13.3.0-NOASAN/plugins/ktx2",
		"/home/cubicool/dev/osgx/BUILD-g++-13.3.0-NOASAN/plugins/gltf"
	))
)

# Import side effect: fills in OSG_THREADING/OSG_GL_* env var defaults (see pyosg_example.py),
# same reason as every other example -- these need to land before OSG's DisplaySettings reads
# them. Deliberately after the OSG_WINDOW/OSG_LIBRARY_PATH overrides above (setdefault() means
# order between these doesn't actually matter, but matching the rest of this file's style).
from pyosg_example import window_size

from OpenSceneGraph import *
from OpenSceneGraph.GL import *

import osgx

THIS_DIR = pathlib.Path(__file__).resolve().parent
PACKAGE_ASSET_DIR = THIS_DIR / "assets"
CLEAR_COLOR = (48.0 / 255.0, 53.0 / 255.0, 66.0 / 255.0, 1.0)
DEBUG_MODES = {
	"combined": 0,
	"diffuse": 1,
	"specular": 2,
	"base-color": 3,
	"roughness": 4,
	"metallic": 5,
	"normal-texture": 6,
	"normal-texture-raw": 7,
	"geometry-normal": 8,
	"shading-normal": 9,
	"geometry-tangent": 10,
	"bitangent": 11,
	"linear-diffuse": 12,
	"linear-specular": 13,
	"linear-combined": 14
}

def resolve_asset(value, suffix, candidates=()):
	path = pathlib.Path(value).expanduser()

	if path.is_file():
		return path

	resolved = osgx.findDataFile(value, list(candidates), suffix)

	if resolved:
		return pathlib.Path(resolved)

	path = PACKAGE_ASSET_DIR / f"{value}.{suffix}"

	if path.is_file():
		return path

	raise FileNotFoundError(f"Cannot find {value!r} in configured data paths")

def resolve_model(value):
	path = pathlib.Path(value).expanduser()

	if path.is_file():
		return path

	resolved = osgx.findDataFile(value)

	if resolved:
		return pathlib.Path(resolved)

	path = PACKAGE_ASSET_DIR / "models" / path.stem / f"{path.stem}.gltf"

	if path.is_file():
		return path

	resolved = osgx.findDataFile(
		path.stem,
		("glTF-Sample-Assets/Models/{}/glTF/{}.gltf",)
	)

	if resolved:
		return pathlib.Path(resolved)

	raise FileNotFoundError(f"Cannot find glTF model {value!r}")

def resolve_environment_manifest(value):
	path = pathlib.Path(value).expanduser()
	name = path.stem

	if path.is_file():
		return path

	resolved = osgx.findDataFile(value)

	if resolved:
		return pathlib.Path(resolved)

	resolved = osgx.findDataFile(path.stem, ("env/{}.gltf",))

	if resolved:
		return pathlib.Path(resolved)

	path = PACKAGE_ASSET_DIR / "env" / f"{name}.gltf"

	if path.is_file():
		return path

	raise FileNotFoundError(f"Cannot find environment manifest {value!r} in configured data paths")

def load_camera(path):
	"""Read a Khronos Sample Viewer camera export into OSG's Z-up basis."""

	with open(path, encoding="utf-8") as stream:
		document = json.load(stream)

	perspective = document["cameras"][0]["perspective"]
	node = next(node for node in document["nodes"] if "camera" in node)
	matrix = node["matrix"]

	def z_up(value):
		return osg.Vec3(value[0], -value[2], value[1])

	eye = z_up(matrix[12:15])
	forward = z_up((-matrix[8], -matrix[9], -matrix[10]))
	up = z_up(matrix[4:7])

	return (
		osg.Matrix.lookAt(eye, eye + forward, up),
		osg.Matrix.perspective(
			math.degrees(perspective["yfov"]),
			perspective["aspectRatio"],
			perspective["znear"], perspective["zfar"]
		)
	)

class FramebufferPNG(osg.Camera.DrawCallback):
	"""Write the current default framebuffer once after the complete scene draw."""

	def __init__(self, viewer, filename):
		super().__init__()

		self.viewer, self.filename, self.done = viewer, filename, False

	def __call__(self, render_info):
		if self.done:
			return

		viewport = self.viewer.camera.viewport

		if viewport is None or not viewport.valid:
			raise RuntimeError("capture camera has no valid viewport")

		image = osg.Image()

		image.readPixels(
			int(viewport.x),
			int(viewport.y),
			int(viewport.width),
			int(viewport.height),
			GL_RGB,
			GL_UNSIGNED_BYTE
		)

		if not osgDB.writeImageFile(image, self.filename):
			raise RuntimeError(f"failed to write screenshot {self.filename!r}")

		self.done = True

		# Standard runner loops just do `while not viewer.done: viewer.frame()` -- they don't
		# know about `capture.done`. Setting this here (rather than main()'s old special-cased
		# `if capture is not None and capture.done: break`) means the same standard loop exits
		# on its own after the screenshot, standalone or via a runner, no custom exit condition
		# needed anywhere else.
		self.viewer.done = True

		osg.notice(f"Wrote framebuffer screenshot: {self.filename}")

class Diagnostics(osgGA.GUIEventHandler):
	def __init__(self, scene):
		super().__init__()

		self.scene = scene

	def handle(self, event, action):
		if event.handled or event.type != osgGA.GUIEventAdapter.KEYUP:
			return False

		if event.key in (ord("1"), ord("2"), ord("3")):
			mode = event.key - ord("1")

			self.scene.debugMode.value = mode

			osg.notice(f"[diagnostic] {('combined', 'diffuse', 'specular')[mode]}")

		elif event.key in (ord("n"), ord("N")):
			self.scene.disableNormalMap.value = 1 - self.scene.disableNormalMap.value

		elif event.key in (ord("r"), ord("R")):
			self.scene.disableRoughnessMap.value = 1 - self.scene.disableRoughnessMap.value

		elif event.key in (ord("d"), ord("D")):
			self.scene.diffuseIBLMode.value = 1 - self.scene.diffuseIBLMode.value

		else: return False

		return True

# Set by build_scene(), read by configure_viewer() -- args.camera/args.debug/args.screenshot and
# the PBRIBLScene object aren't retrievable from the returned root (build_scene()'s contract is
# just "return a Node"), and args in particular has no natural home in the graph the way e.g.
# pyosg-mrt.py pulls a Uniform back out of a StateSet. A same-module variable is the simpler
# channel; both runners and every __main__ block call build_scene() before configure_viewer().
_args = None
_pbr = None

def build_scene(w, h):
	global _args, _pbr

	parser = argparse.ArgumentParser(description=__doc__)

	parser.add_argument("model", help="glTF model path")
	environment_group = parser.add_mutually_exclusive_group(required=True)

	environment_group.add_argument(
		"--hdr",
		metavar="PATH",
		help="source HDR environment; bakes diffuse, BRDF LUT, and GGX-prefiltered specular live"
	)
	environment_group.add_argument(
		"--env",
		metavar="MANIFEST",
		help="fully pre-baked osgx_pbribl environment manifest"
	)
	parser.add_argument("--camera", help="Khronos camera-export glTF")
	parser.add_argument(
		"--debug",
		nargs="?",
		const="combined",
		choices=tuple(DEBUG_MODES),
		help="opt into diagnostics, optionally selecting the initial channel (default: combined)"
	)
	parser.add_argument(
		"--screenshot",
		"--capture",
		dest="screenshot",
		metavar="PNG",
		help="write one raw framebuffer PNG"
	)

	_args = parser.parse_args()

	# Must happen before any GraphicsContext exists -- build_scene() runs before either runner's
	# viewer.setUpViewInWindow(), and before a standalone __main__ constructs its GraphicsContext
	# at first realize()/frame(), so this ordering holds either way.
	osg.DisplaySettings.instance.numMultiSamples = 8

	model_path = resolve_model(_args.model)
	t0 = time.time()
	model = osgDB.readNodeFile(str(model_path))

	print(f"readNodeFile({model_path.name}): {time.time() - t0:.3f}s", flush=True)

	if model is None:
		raise RuntimeError(f"failed to load model {model_path}")

	diagnostics = _args.debug is not None

	if _args.hdr:
		hdr_path = resolve_asset(
			_args.hdr,
			"hdr",
			("glTF-Sample-Environments/{}",)
		)
		environment = osgx.gltf.pbribl.PBRIBLEnvironment.prepare(str(hdr_path), lutSize=1024)
		environment_description = str(hdr_path)

	else:
		env_path = resolve_environment_manifest(_args.env)
		environment = osgx.gltf.pbribl.PBRIBLEnvironment.load(str(env_path))
		environment_description = str(env_path)

	pbr = osgx.gltf.pbribl.PBRIBLScene.create(
		model,
		environment,
		iblDiffuseIntensity=1.0,
		iblSpecularIntensity=1.0,
		diagnostics=diagnostics
	)

	if not environment.valid() or not pbr.valid():
		raise RuntimeError(f"failed to prepare PBR IBL resources for {environment_description}")

	if diagnostics:
		pbr.debugMode.value = DEBUG_MODES[_args.debug]

	_pbr = pbr

	root = osg.Group()

	if environment.root is not None:
		root.children.append(environment.root)

	root.children.append(pbr.node)

	return root

# Camera/diagnostics/screenshot setup all need the live viewer, which build_scene() never
# receives.
def configure_viewer(viewer, root):
	args = _args
	pbr = _pbr

	viewer.camera.clearColor = osg.Vec4(*CLEAR_COLOR)

	if args.debug is not None:
		viewer.eventHandlers.append(Diagnostics(pbr))

		osg.notice("Diagnostics: 1=combined 2=diffuse 3=specular N=normal R=roughness D=diffuse IBL")

	if args.camera:
		camera_path = pathlib.Path(args.camera).expanduser()
		viewer.cameraManipulator = None
		viewer.camera.viewMatrix, viewer.camera.projectionMatrix = load_camera(camera_path)

	else:
		viewer.cameraManipulator = osgGA.TrackballManipulator()

	if args.screenshot:
		path = pathlib.Path(args.screenshot).expanduser()

		if path.suffix.lower() != ".png":
			raise ValueError("--screenshot must name a .png file")

		capture = FramebufferPNG(viewer, str(path))
		viewer.camera.finalDrawCallback = capture

if __name__ == "__main__":
	W, H = window_size()

	viewer = osgViewer.Viewer()
	root = build_scene(W, H)

	viewer.sceneData = root

	configure_viewer(viewer, root)

	while not viewer.done:
		viewer.frame()
