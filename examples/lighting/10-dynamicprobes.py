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
# Since specular here is ALWAYS procedural (the very first frame already fires a repaint -- see
# ProbeRebaker below), baking a real GGX-prefiltered specular cubemap from --hdr at startup would
# be pure waste: real work thrown away before a single frame ever samples it. So this step is the
# one caller of osgx.gltf.pbribl.PBRIBLEnvironment.prepareDiffuseOnly() (added alongside this
# file's conversion) -- diffuse irradiance and the BRDF LUT still bake for real, specular starts
# as an unbaked placeholder and is immediately replaced by the first procedural repaint. --env
# (a fully pre-baked manifest) has no such waste to avoid -- its specular is a cheap KTX2 load,
# not a GPU bake -- but the first repaint replaces it too, for the same reason: this step is about
# proving the environment CAN change live, not about which bytes it starts with.
#
# The procedural repaint's own template image (paint_random_faces()'s size/format source) is a
# blank synthetic equirect (see make_probe_template_image()), not a loaded --hdr file -- every
# pixel it produces gets fully overwritten by the checkerboard anyway, so there's nothing for a
# real HDR to contribute there either. This is what lets --env work stand alone, with no local
# .hdr file needed at all.
#
# This is sync/stalling (GGXPrefilterOptions.syncReadback, still the only mode implemented), not
# an async capture-from-live-scene mode -- per the user, "it's enough to show that it CAN change
# dynamically, even if it's not perfect or async."
#
# Diffuse (SH/Lambertian) irradiance and the BRDF LUT are intentionally left static, baked once at
# startup by PBRIBLEnvironment.prepareDiffuseOnly()/load() -- only the specular prefiltered
# cubemap rebakes live.

import sys
import random
import colorsys
import pathlib
import argparse

# examples/lighting/ sits one level below examples/ itself, where pyosg_example.py lives --
# unlike every flat examples/pyosg-*.py file (whose own directory IS examples/, so Python's
# automatic sys.path[0] already covers them), a standalone run of this file needs examples/
# added explicitly. Same fix pyosg-cli's own EXAMPLES_DIR insertion applies for pyosg_visitor.py.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

# Import side effect: fills in OSG_WINDOW/OSG_THREADING/OSG_GL_* env var defaults (see
# pyosg_example.py). Deliberately before `from OpenSceneGraph import *`, matching every other
# example -- these need to land before OSG's DisplaySettings reads them.
from pyosg_example import window_size

import numpy as np

from OpenSceneGraph import *
from OpenSceneGraph.GL import *

import osgx

# Bare name (e.g. "Corset") -> glTF-Sample-Assets/Models/<name>/glTF/<name>.gltf via
# osgx.findDataFile(), same convention every other step in this series uses.
def resolve_model(value):
	path = pathlib.Path(value).expanduser()

	if path.is_file():
		return str(path)

	return osgx.findDataFile(value) or osgx.findDataFile(
		path.stem, ("glTF-Sample-Assets/Models/{}/glTF/{}.gltf",)
	) or None

# HDR/manifest assets resolve via osgx.findDataFile() (OSG_FILE_PATH), same as resolve_model().
def resolve_asset(value, suffix):
	path = pathlib.Path(value).expanduser()

	if path.is_file():
		return str(path)

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

# Fixed size for make_probe_template_image() -- a plausible equirect resolution (2:1), matching
# what a real HDR probe would typically use. Purely a size/format template (see that function's
# own docstring), so this has no bearing on the baked specular cubemap's own resolution
# (--prefilter-size).
PROBE_TEMPLATE_SIZE = (1024, 512)

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

def make_probe_template_image(size=PROBE_TEMPLATE_SIZE):
	"""
	A blank equirectangular osg.Image (GL_RGB/GL_FLOAT) used only as a size/format template for
	paint_random_faces() -- every pixel it produces gets fully overwritten by the checkerboard
	repaint (see paint_random_faces()'s own docstring), so there's no need to load or bake a real
	HDR just to seed this. This is what decouples the procedural specular probe from --hdr/--env
	entirely: an --env-only invocation (a fully pre-baked environment, no local .hdr file at all)
	still gets a working 'r' repaint.
	"""
	w, h = size
	img = osg.Image()

	img.allocateImage(w, h, 1, GL_RGB, GL_FLOAT)

	return img

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

class ProbeRebaker(osgGA.GUIEventHandler):
	"""
	Owns the live dynamic-probe specular rebake. 'r' starts one (see start()); each subsequent
	FRAME event -- dispatched to every registered eventHandler once per viewer.frame() call, the
	same mechanism pyosg-taa.py's Controls and pyosg-match4.py's StepAdvancer use for their own
	per-frame state machines -- advances it by exactly one real frame, until
	GGXPrefilterReadback reports done.

	This used to be one blocking call (do_rebake()) that drove viewer.frame() itself in a tight
	inner loop to force the bake to finish before returning -- safe only while this file's own
	__main__ block owned the outer frame loop directly (do_rebake()'s own old docstring already
	warned it was NOT safe to call from inside a callback, for exactly this re-entrancy reason).
	Now that the runner (pyosg-cli/OpenSceneGraph.examples) owns that loop, this class never
	calls viewer.frame() itself -- it just advances its own state by one step per real FRAME
	event, and the bake visibly trickles in over a handful of frames instead of appearing to
	complete instantly.
	"""

	def __init__(self, camera, root, model_ss, base_image, color_source, prefilter_size):
		super().__init__()

		self.camera = camera
		self.root = root
		self.model_ss = model_ss
		self.base_image = base_image
		self.color_source = color_source
		self.prefilter_size = prefilter_size

		self.scene = None
		self.options = None
		self.elapsed = None # None = idle; int = real frames elapsed since the current bake armed

	def start(self):
		if self.elapsed is not None:
			print("[dynamicprobes] bake already in progress, ignoring", flush=True)

			return

		print("[dynamicprobes] baking...", flush=True)

		baked_image = paint_random_faces(self.base_image, self.color_source)

		if self.scene is None:
			options = osgx.GGXPrefilterOptions()
			options.prefilterSize = self.prefilter_size
			options.maxFrames = 8
			options.readbackFrame = 2
			self.options = options

			self.scene = osgx.GGXPrefilterScene.create(baked_image, options)
			self.scene.root.nodeMask = 0
			self.root.children.append(self.scene.root)

		elif not self.scene.rebake(baked_image):
			print("[dynamicprobes] failed to reset bake scene, keeping previous environment", flush=True)

			return

		self.scene.root.nodeMask = 0xffffffff
		self.camera.postDrawCallback = self.scene.readback
		self.elapsed = 0

	def _finish(self):
		self.camera.postDrawCallback = None
		self.scene.root.nodeMask = 0

		if not self.scene.readback.done:
			print("[dynamicprobes] bake did not complete, keeping previous environment", flush=True)

		else:
			cubemap = self.scene.readback.finish()

			# GPU-baked mips are already embedded per-face (see GGXPrefilter.hpp) -- don't let OSG
			# regenerate them, same as the static-environment path in 09-ibl.py.
			cubemap.useHardwareMipMapGeneration = False

			self.model_ss.textureAttributes[5] = cubemap

			print(f"[dynamicprobes] rebake done after {self.elapsed} frames", flush=True)

		self.elapsed = None

	def handle(self, ea, aa):
		if ea.type == osgGA.GUIEventAdapter.KEYUP and ea.key in (ord("r"), ord("R")):
			self.start()

			return True

		if ea.type != osgGA.GUIEventAdapter.FRAME or self.elapsed is None:
			return False

		self.elapsed += 1

		if not self.scene.readback.done and self.elapsed < self.options.maxFrames:
			return False

		self._finish()

		return False

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

# Set by build_scene(), read by configure_viewer() -- ProbeRebaker needs the live viewer.camera
# (for its postDrawCallback), which build_scene() never receives. Same "no other channel exists"
# reasoning as pyosg-khronos-viewer.py's own _args/_pbr stash.
_args = None
_probe = None

def build_scene(w, h):
	global _args, _probe

	ap = argparse.ArgumentParser()
	ap.add_argument("path", nargs="?", default=None)

	env_group = ap.add_mutually_exclusive_group()
	env_group.add_argument(
		"--hdr",
		default=None,
		help="Equirectangular HDR -- baked once for diffuse/BRDF LUT only (default: papermill); "
			"specular is always procedural (see --mode), never baked from this"
	)
	env_group.add_argument(
		"--env",
		default=None,
		help="Pre-baked osgx_pbribl environment manifest -- its specular bake is immediately "
			"replaced by the first procedural repaint, same as --hdr's"
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
	ap.add_argument("--no-floor", dest="floor", action="store_false", default=True)
	ap.add_argument(
		"--mode",
		choices=MODE_CHOICES,
		default="random",
		help="Cube-face repaint color source on 'r': 'random' for fully random vivid "
			"hues, or one of the named PRESET_PALETTES color schemes"
	)

	args = ap.parse_args()

	if not args.hdr and not args.env:
		args.hdr = "papermill"

	# On by default (tuned for BoomBox); --no-floor opts out, --floor-z/--floor-size override.
	args.floor_z = -0.01 if args.floor_z is None else args.floor_z
	args.floor_size = 0.05 if args.floor_size is None else args.floor_size

	_args = args

	osg.setNotifyLevel(osg.NotifySeverity.NOTICE)

	path = resolve_model(args.path or "BoomBox")

	if not path:
		sys.exit("Cannot find model -- clone glTF-Sample-Assets into your OSG_FILE_PATH checkout")

	model = osgDB.readNodeFile(path)

	# --- IBL environment: diffuse/BRDF LUT are the only real bake either path performs -- specular
	# is ALWAYS procedural (ProbeRebaker above), so --hdr uses prepareDiffuseOnly() rather than
	# prepare(), which would GGX-prefilter a real specular cubemap only to discard it before a
	# single frame ever samples it. --env still loads a real specular bake off disk (a cheap KTX2
	# read, not a GPU bake), which the first procedural repaint replaces regardless. ------------ #
	if args.hdr:
		hdr_path = resolve_asset(args.hdr, "hdr")

		if not hdr_path:
			sys.exit(f"Cannot find HDR {args.hdr!r} -- check OSG_FILE_PATH")

		environment = osgx.gltf.pbribl.PBRIBLEnvironment.prepareDiffuseOnly(hdr_path, lutSize=1024)

	else:
		env_path = resolve_asset(args.env, "gltf")

		if not env_path:
			sys.exit(f"Cannot find environment manifest {args.env!r}")

		environment = osgx.gltf.pbribl.PBRIBLEnvironment.load(env_path)

	if not environment.valid():
		sys.exit("Failed to prepare/load the PBR/IBL environment")

	# --- Lights ----------------------------------------------------------------- #
	main_group = osg.Group()
	mg_ss = main_group.stateSet

	# LightSet must live on the SAME StateSet as the Program that actually calls
	# osgx_DirectLighting() (model's own StateSet, wired by PBRIBLScene.create() below -- not
	# main_group, an ancestor). See [[project_osgx_lightset_maxlights_fix]] for the full root
	# cause; the floor's Program gets the same shared `lights` object attached to ITS OWN
	# StateSet below.
	lights = osgx.LightSet()
	model.stateSet.attributes.append(lights)

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
		floor_geode.stateSet.attributes.append(lights)

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

	_probe = {
		"root": root,
		"model_ss": model_ss,
		"color_source": _make_color_source(args.mode),
		"prefilter_size": args.prefilter_size,
	}

	return root

# ProbeRebaker needs the live viewer.camera, which build_scene() never receives.
def configure_viewer(viewer, root):
	probe = _probe

	rebaker = ProbeRebaker(
		viewer.camera,
		probe["root"],
		probe["model_ss"],
		make_probe_template_image(),
		probe["color_source"],
		probe["prefilter_size"]
	)

	viewer.eventHandlers.append(rebaker)

	print(f"[dynamicprobes] mode={_args.mode!r} -- press 'r' to repaint the 6 cube faces", flush=True)

	# Trigger the very first bake immediately -- no GL context is needed yet, just like every
	# other node/texture build_scene() already constructs without one; the actual GPU work only
	# happens once ProbeRebaker's FRAME polling drives real render traversals.
	rebaker.start()

if __name__ == "__main__":
	W, H = window_size()

	viewer = osgViewer.Viewer()
	root = build_scene(W, H)

	viewer.sceneData = root
	viewer.cameraManipulator = osgGA.TrackballManipulator()

	configure_viewer(viewer, root)

	while not viewer.done:
		viewer.frame()
