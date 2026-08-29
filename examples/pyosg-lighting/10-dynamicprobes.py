#!/usr/bin/env python3

# Step 10 -- Dynamic Probes
#
# Step 9 (09-ibl.py) bakes its whole environment (diffuse + specular + BRDF LUT) ONCE at startup
# via osgx.gltf.pbribl.PBRIBLEnvironment.prepare(). This step demonstrates that the specular half
# of that environment can be REBAKED LIVE: press 'r' to replace the entire reflection environment
# with a synthetic one -- each of the 6 cube faces filled with a fresh checkerboard of random/
# palette colors (see paint_random_faces()) -- and rebake the specular cubemap from it on the fly,
# swapping the result onto texture unit 5. There's no photographic content left at all after a
# repaint, so there's zero ambiguity about what's changing frame-to-frame: the whole reflection
# environment.
#
# This is sync/stalling (GGXPrefilterOptions.syncReadback, still the only mode implemented), not
# an async capture-from-live-scene mode -- per the user, "it's enough to show that it CAN change
# dynamically, even if it's not perfect or async."
#
# Diffuse (SH/Lambertian) irradiance and the BRDF LUT are intentionally left static, baked once at
# startup by PBRIBLEnvironment.prepare() -- only the specular prefiltered cubemap rebakes live.
#
# Unlike Step 9, the live-rebake mechanism itself (osgx.GGXPrefilterScene.create /
# GGXPrefilterScene.rebake() / GGXPrefilterReadback.finish()) is NOT something this pivot needed to touch -- it
# was already real osgx, not hand-rolled math, before this rewrite. What pivots here is everything
# this step has in common with Step 9: the static half of the environment bake and the whole
# glTF PBR/IBL material shader, both now osgx.gltf.pbribl exactly as in 09-ibl.py. The
# procedural checkerboard repaint (numpy) stays hand-rolled -- it's real array/image-synthesis
# work, not a reimplementation of anything osgx already does.

import sys
import os
import random
import colorsys
import pathlib
import argparse

os.environ.update({
	"OSG_WINDOW": "50 50 800 600",
	"OSG_THREADING": "SingleThreaded",
	"OSG_GL_CONTEXT_PROFILE_MASK": "1",
	"OSG_GL_VERSION": "4.6",
	"OSG_GL_CONTEXT_VERSION": "4.6",
})

import numpy as np

from OpenSceneGraph import *
from OpenSceneGraph.GL import *

import osgx

THIS_DIR = pathlib.Path(__file__).resolve().parent
DATA_DIR = THIS_DIR / "data"

# Bare name (e.g. "Corset") -> glTF-Sample-Assets/Models/<name>/glTF/<name>.gltf via
# osgx.findDataFile(), same convention every other step in this series uses.
def resolve_model(value):
	path = pathlib.Path(value).expanduser()

	if path.is_file():
		return str(path)

	return osgx.findDataFile(value) or osgx.findDataFile(
		path.stem, ("glTF-Sample-Assets/Models/{}/glTF/{}.gltf",)
	) or None

# HDR assets for this step live locally in pyosg-lighting/data/ (papermill.hdr, etc.) -- checked
# first, falling back to osgx.findDataFile() for anything found via OSG_FILE_PATH instead.
def resolve_asset(value, suffix):
	path = pathlib.Path(value).expanduser()

	if path.is_file():
		return str(path)

	local = DATA_DIR / f"{value}.{suffix}"

	if local.is_file():
		return str(local)

	return osgx.findDataFile(value, (), suffix) or None

# Same light positions as Steps 7/8/9 -- no animation.
KEY_LIGHT_POS = osg.Vec3( 0.1, 0.1, 1.0) # front-center key (shadow caster)
FILL_LIGHT_POS_0 = osg.Vec3(-0.8, 0.3, 0.5) # cool fill, left
FILL_LIGHT_POS_1 = osg.Vec3( 0.0, -0.6, 0.2) # warm back/rim

# --------------------------------------------------------------------------- #
# Dynamic probe: random cube-face repaint + live rebake
# --------------------------------------------------------------------------- #

# Order matches GGXPrefilter.cpp's faceIndex convention exactly (+X, -X, +Y, -Y,
# +Z, -Z) -- see _equirect_face_uv() below.
FACE_NAMES = ("+X", "-X", "+Y", "-Y", "+Z", "-Z")

# HDR magnitude for a fully-saturated (1.0) color channel. NOTE: PBRIBLScene.create()'s specular
# term samples envMap directly and is NOT scaled by --ibl-diffuse -- only --ibl-specular affects
# it -- so this has to sit near a real HDR's own peak magnitude (photographed HDRs like
# papermill.hdr are typically ~0.5-3), not just "however bright looks fun" -- too high and every
# face desaturates to the same white under the PBR Neutral tonemapper's highlight rolloff.
FACE_INTENSITY = 2.5
FACE_GRID_SIZE = 6 # checkerboard cells per side, per face

def _equirect_face_uv(w, h):
	"""
	For every pixel of a (h, w) equirect image, compute which of the 6 cube
	faces (matching GGXPrefilter.cpp's faceIndex convention) the corresponding
	view direction belongs to, by inverting GGXPrefilter.cpp's
	equirect_uv(dir_gl_to_zup(L)) mapping and then classifying by dominant
	axis -- the same "biggest axis wins" test any cubemap face lookup uses.
	Also returns face-local (s, t) in roughly [-1, 1], the standard gnomonic
	(gnomonic = straight-line-preserving) projection onto that face's plane
	-- the same projection a real cubemap face uses, so a checkerboard drawn
	in (s, t) reads as square cells face-on and stretches toward the edges
	exactly like a real cube face would.
	"""
	u = (np.arange(w, dtype=np.float32) + 0.5) / w
	v = (np.arange(h, dtype=np.float32) + 0.5) / h
	u, v = np.meshgrid(u, v)

	theta = (1.0 - v) * np.pi
	psi = (u - 0.5) * 2.0 * np.pi + np.pi / 2.0

	dx = np.sin(theta) * np.cos(psi)
	dy = np.cos(theta)
	dz = np.sin(theta) * np.sin(psi)

	ax, ay, az = np.abs(dx), np.abs(dy), np.abs(dz)
	x_dom = (ax >= ay) & (ax >= az)
	y_dom = ~x_dom & (ay >= az)
	z_dom = ~(x_dom | y_dom)

	face_id = np.select(
		[x_dom & (dx > 0), x_dom, y_dom & (dy > 0), y_dom, z_dom & (dz > 0), z_dom],
		[0, 1, 2, 3, 4, 5],
		default=5
	)

	# np.select evaluates every branch for every pixel even though each ratio
	# is only actually used where its own dominance mask picks it -- e.g.
	# dx/dy is computed everywhere, including pixels where dy happens to be
	# ~0, even though those pixels are always x_dom or z_dom and that value
	# gets discarded. Harmless but noisy; silence rather than chase it.
	with np.errstate(divide="ignore", invalid="ignore"):
		s = np.select([x_dom, y_dom, z_dom], [dy / dx, dx / dy, dx / dz], default=0.0)
		t = np.select([x_dom, y_dom, z_dom], [dz / dx, dz / dy, dy / dz], default=0.0)

	return face_id, s, t

def _random_vivid_rgb():
	"""A fully-saturated, full-value random hue -- as unlike a natural HDR color as possible."""
	return colorsys.hsv_to_rgb(random.random(), 1.0, 1.0)

def _hex_to_rgb(hex_color):
	hex_color = hex_color.lstrip("#")

	return tuple(int(hex_color[i:i+2], 16) / 255.0 for i in (0, 2, 4))

# Named color-scheme presets for --mode: each a list/tuple of hex strings. Add
# more here -- any key becomes a valid --mode value automatically (see
# MODE_CHOICES below). "random" (fully random hues, not a fixed palette) is
# handled separately in _make_color_source() and isn't a key in this dict.
PRESET_PALETTES = {
	"FCB": ("#923514", "#d15515", "#fc9143", "#ffc057", "#8f8854", "#474834"),
	"SMG": ("#ff400d", "#ff8c19", "#ffcc00", "#6bb359", "#008040", "#1f4d2e"),
	"OSS": ("#3d5a80", "#98c1d9", "#e0fbfc", "#e7b4a5", "#ee6c4d", "#293241"),
	"ESG": ("#264653", "#2a9d8f", "#e9c46a", "#f4a261", "#ee8959", "#e76f51"),
}

MODE_CHOICES = ("random",) + tuple(PRESET_PALETTES.keys())

def _make_color_source(mode):
	"""
	Return a zero-arg callable that produces one normalized (r, g, b) color
	per call, per the given --mode: fully random vivid hues for "random", or
	a random pick from a named PRESET_PALETTES entry otherwise.
	"""
	if mode == "random":
		return _random_vivid_rgb

	palette = PRESET_PALETTES[mode]

	return lambda: _hex_to_rgb(random.choice(palette))

def paint_random_faces(base_image, color_source):
	"""
	Return a NEW osg.Image, same size/format as base_image, with each of the
	6 cube faces filled with a FACE_GRID_SIZE x FACE_GRID_SIZE checkerboard
	of two fresh colors drawn from `color_source` (see _make_color_source()).
	Unlike an additive stamp, this replaces the ENTIRE environment -- no
	photographic content survives the repaint, so there's no mistaking it
	for anything but synthetic.
	"""
	base_arr = np.asarray(base_image)
	h, w = base_arr.shape[:2]

	img = osg.Image()
	img.allocateImage(w, h, 1, base_image.pixelFormat, base_image.dataType)

	arr = np.asarray(img)
	face_id, s, t = _equirect_face_uv(w, h)

	cell_s = np.floor((s * 0.5 + 0.5) * FACE_GRID_SIZE).astype(np.int32)
	cell_t = np.floor((t * 0.5 + 0.5) * FACE_GRID_SIZE).astype(np.int32)
	parity = (cell_s + cell_t) & 1

	color_a = np.array([color_source() for _ in FACE_NAMES], dtype=np.float32)
	color_b = np.array([color_source() for _ in FACE_NAMES], dtype=np.float32)

	checkerboard = np.where(parity[..., np.newaxis] == 0, color_a[face_id], color_b[face_id])

	arr[..., :3] = checkerboard * FACE_INTENSITY

	return img

class RebakeKeyHandler(osgGA.GUIEventHandler):
	"""Press 'r' to repaint the cube faces and rebake the specular IBL cubemap live."""

	def __init__(self, pending):
		super().__init__()
		self.pending = pending

	def handle(self, ea, aa):
		if ea.handled or ea.type != osgGA.GUIEventAdapter.KEYUP:
			return False

		if ea.key in (ord("r"), ord("R")):
			self.pending[0] = True

			return True

		return False

def do_rebake(v, root, model_ss, base_image, color_source, prefilter_size, bake_state):
	"""
	Bake a new specular prefiltered cubemap from a freshly-repainted copy of `base_image` (see
	paint_random_faces()) and swap it onto texture unit 5 of `model_ss` -- the StateSet
	PBRIBLScene.create() bound envMap to. Blocks the caller for a handful of frames (sync/stalling
	bake, see module docstring) -- safe to call from the main loop, not from inside an event
	handler callback (would re-enter viewer.frame()).
	"""
	print("[dynamicprobes] baking...", flush=True)

	baked_image = paint_random_faces(base_image, color_source)

	if bake_state["scene"] is None:
		options = osgx.GGXPrefilterOptions()
		options.prefilterSize = prefilter_size
		options.maxFrames = 8
		options.readbackFrame = 2
		bake_state["options"] = options

		bake_scene = osgx.GGXPrefilterScene.create(baked_image, options)
		bake_scene.root.nodeMask = 0
		root.children.append(bake_scene.root)
		bake_state["scene"] = bake_scene
	else:
		bake_scene = bake_state["scene"]
		options = bake_state["options"]

		if not bake_scene.rebake(baked_image):
			print("[dynamicprobes] failed to reset bake scene, keeping previous environment", flush=True)

			return

	bake_scene.root.nodeMask = 0xffffffff
	v.camera.postDrawCallback = bake_scene.readback

	frame = 0

	while frame < options.maxFrames and not bake_scene.readback.done:
		v.frame()
		frame += 1

	v.camera.postDrawCallback = None
	bake_scene.root.nodeMask = 0

	if not bake_scene.readback.done:
		print("[dynamicprobes] bake did not complete, keeping previous environment", flush=True)

		return

	cubemap = bake_scene.readback.finish()

	# GPU-baked mips are already embedded per-face (see GGXPrefilter.hpp) -- don't let OSG
	# regenerate them, same as the static-environment path in 09-ibl.py.
	cubemap.useHardwareMipMapGeneration = False

	model_ss.textureAttributes[5] = cubemap

	print(f"[dynamicprobes] rebake done after {frame} frames", flush=True)

FLOOR_VERTEX = """
#version 460 core

in vec4 osg_Vertex;
in vec3 osg_Normal;

uniform mat4 osg_ModelViewProjectionMatrix;
uniform mat4 osg_ModelViewMatrix;
uniform mat3 osg_NormalMatrix;

out vec3 vPosition;
out vec3 vNormal;

void main() {
	vec4 eyePos = osg_ModelViewMatrix * osg_Vertex;
	vPosition = eyePos.xyz;
	vNormal = normalize(osg_NormalMatrix * osg_Normal);
	gl_Position = osg_ModelViewProjectionMatrix * osg_Vertex;
}
"""

# Flat albedo, no textures, no IBL term (the glTF model is this step's IBL demonstration -- the
# floor is just a plausible shadow receiver) -- identical to Step 9's floor.
FLOOR_FRAGMENT = """
#version 460 core

#pragma osgx::pbr MATERIAL_STRUCT, DIRECT_LIGHTING_DECL

in vec3 vPosition;
in vec3 vNormal;

uniform mat4 osg_ViewMatrix;
uniform mat4 osg_ViewMatrixInverse;

out vec4 fragColor;

void main() {
	osgx_Material mat;

	mat.albedo = vec3(0.82, 0.76, 0.62); // warm light stone/concrete
	mat.ao = 1.0;
	mat.roughness = 0.9;
	mat.metallic = 0.0;
	mat.F0 = vec3(0.04);

	mat3 invViewRot = transpose(mat3(osg_ViewMatrix));
	vec3 N = invViewRot * normalize(vNormal);
	vec3 V = invViewRot * normalize(-vPosition);
	vec3 worldPos = (osg_ViewMatrixInverse * vec4(vPosition, 1.0)).xyz;

	vec3 Lo = osgx_DirectLighting(N, V, worldPos, mat);

	fragColor = vec4(vec3(0.06) * mat.albedo + Lo, 1.0);
}
"""

if __name__ == "__main__":
	ap = argparse.ArgumentParser()
	ap.add_argument("path", nargs="?", default=None)
	ap.add_argument(
		"--hdr",
		default="papermill",
		help="Equirectangular HDR -- baked once for diffuse/BRDF LUT, and as the initial specular "
			"environment before the first 'r' repaint (default: papermill)"
	)
	ap.add_argument(
		"--prefilter-size",
		type=int,
		default=64,
		help="GPU prefilter cubemap face size for live rebakes (default: 64; small keeps 'r' snappy)"
	)
	ap.add_argument("--ibl-diffuse", type=float, default=1.0, dest="ibl_diffuse")
	ap.add_argument("--ibl-specular", type=float, default=1.0, dest="ibl_specular")
	ap.add_argument("--no-lights", dest="lights", action="store_false", default=True)
	ap.add_argument("--floor-z", type=float, default=None)
	ap.add_argument("--floor-size", type=float, default=None)
	ap.add_argument(
		"--mode",
		choices=MODE_CHOICES,
		default="random",
		help="Cube-face repaint color source on 'r': 'random' for fully random vivid "
			"hues, or one of the named PRESET_PALETTES color schemes"
	)

	args = ap.parse_args()

	# No floor by default; passing either flag activates it.
	args.floor = args.floor_z is not None or args.floor_size is not None
	args.floor_z = -0.04 if args.floor_z is None else args.floor_z
	args.floor_size = 0.15 if args.floor_size is None else args.floor_size

	osg.setNotifyLevel(osg.NotifySeverity.NOTICE)

	path = resolve_model(args.path or "BoomBox")

	if not path:
		sys.exit("Cannot find model -- clone glTF-Sample-Assets into your OSG_FILE_PATH checkout")

	hdr_path = resolve_asset(args.hdr, "hdr")

	if not hdr_path:
		sys.exit(f"Cannot find HDR {args.hdr!r} -- check pyosg-lighting/data/ or OSG_FILE_PATH")

	model = osgDB.readNodeFile(path)

	# --- IBL environment: diffuse/BRDF LUT static, specular gets replaced by the live rebake ---- #
	environment = osgx.gltf.pbribl.PBRIBLEnvironment.prepare(hdr_path, lutSize=1024)

	if not environment.valid():
		sys.exit("Failed to prepare the PBR/IBL environment")

	# --- Lights (shared ancestor StateSet, same shape as Steps 8/9) ----------- #
	main_group = osg.Group()
	mg_ss = main_group.stateSet

	lights = osgx.LightSet()
	mg_ss.attributes.append(lights)

	if args.lights:
		lights.setCount(3)
		lights.setPoint(0, KEY_LIGHT_POS, osg.Vec3(1.0, 0.9, 0.7), 1.6)
		lights.setPoint(1, FILL_LIGHT_POS_0, osg.Vec3(0.3, 0.5, 1.0), 1.2)
		lights.setPoint(2, FILL_LIGHT_POS_1, osg.Vec3(1.0, 0.5, 0.2), 1.0)

	else:
		lights.setCount(0)

	# --- Shadow map (Step 8's rig, unchanged) ---------------------------------- #
	shadow_map = None

	if args.lights:
		bound = model.bound
		light_dir = (bound.center - KEY_LIGHT_POS).normalized()

		shadow_map = osgx.ShadowMap.create(light_dir, bound.center, bound.radius)

		shadow_map.camera.children.append(model)

	# --- glTF PBR/IBL scene ---------------------------------------------------- #
	pbr = osgx.gltf.pbribl.PBRIBLScene.create(
		model,
		environment,
		iblDiffuseIntensity=args.ibl_diffuse,
		iblSpecularIntensity=args.ibl_specular,
		shadowMap=shadow_map
	)

	if not pbr.valid():
		sys.exit("Failed to build the PBR/IBL scene")

	model_ss = model.stateSet

	# --- Floor (optional) ------------------------------------------------------ #
	if args.floor:
		S, Z = args.floor_size, args.floor_z
		floor_quad = osg.createTexturedQuadGeometry(
			osg.Vec3(-S / 2, -S / 2, Z),
			osg.Vec3(S, 0, 0),
			osg.Vec3(0, S, 0)
		)
		floor_geode = osg.Geode()
		floor_geode.drawables.append(floor_quad)

		hook_shader = osgx.makeShadowedDirectLightingHookShader()
		floor_p = osg.Program(name="floor_ibl", shaders=(
			osg.Shader(osg.Shader.VERTEX, FLOOR_VERTEX),
			osg.Shader(osg.Shader.FRAGMENT, osgx.resolveShaderLibs(FLOOR_FRAGMENT)),
			hook_shader
		))
		floor_geode.stateSet.attributes.append(floor_p)

	# --- Scene graph ------------------------------------------------------------ #
	# Shadow uniforms/texture live on main_group's StateSet so the hand-rolled floor shader sees
	# them by inheritance -- PBRIBLScene.create() already wired them directly onto model's own
	# StateSet above, so this is redundant (but harmless) for the model itself.
	if shadow_map is not None:
		mg_ss.textureAttributes[4] = shadow_map.depthTexture
		mg_ss.uniforms["osgx_shadowMap"] = 4
		mg_ss.uniforms.extend((
			shadow_map.shadowMatrix, shadow_map.bias, shadow_map.strength, shadow_map.casterIndex
		))

	main_group.children.append(model)

	if args.floor:
		main_group.children.append(floor_geode)

	root = osg.Group()

	if environment.root is not None:
		root.children.append(environment.root)

	if shadow_map is not None:
		root.children.append(shadow_map.camera)

	root.children.append(main_group)

	v = osgViewer.Viewer()
	v.sceneData = root
	v.cameraManipulator = osgGA.TrackballManipulator()

	# --- Dynamic IBL probe ------------------------------------------------------ #
	base_equirect = osgDB.readImageFile(hdr_path)
	color_source = _make_color_source(args.mode)

	pending_rebake = [True] # trigger the very first bake once the GL context exists
	bake_state = {"scene": None, "options": None}

	v.eventHandlers.append(RebakeKeyHandler(pending_rebake))

	print(f"[dynamicprobes] mode={args.mode!r} -- press 'r' to repaint the 6 cube faces", flush=True)

	while not v.done:
		v.frame()

		if pending_rebake[0]:
			pending_rebake[0] = None

			do_rebake(v, root, model_ss, base_equirect, color_source, args.prefilter_size, bake_state)
