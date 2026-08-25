#!/usr/bin/env python3
#vimrun! python3 09-ibl-animation.py --hdr papermill

# Step 9 (animated) -- Image-Based Lighting (IBL) + glTF animation playback
#
# This is 09-ibl.py plus osgx.gltf.SimplePlayer clip playback -- nothing about the IBL/PBR/shadow
# setup below differs from that step at all (see its own header comment for why that pipeline is
# osgx.gltf.pbribl now, not hand-rolled). A much older, much larger version of this file predated
# osgx.gltf.pbribl entirely and hand-rolled its own SH projection, GGX prefilter, BRDF LUT bake,
# and shadow camera (plus an abandoned async/IPython-REPL live-rebake experiment) -- see git
# history if that archaeology is ever useful. Rewritten from scratch on top of the current
# 09-ibl.py instead of patched in place, since none of that hand-rolled machinery is worth
# carrying forward a second time.
#
# The one thing genuinely specific to animation, beyond SimplePlayer itself: GPU skinning moves
# vertices without updating OSG's CPU-side drawable bounds, so the viewer's default bounds-derived
# near/far clipping goes stale and visibly clips the model as it deforms/orbits. Fixed with
# DO_NOT_COMPUTE_NEAR_FAR plus a fixed, generously padded near/far derived from the model's own
# (bind-pose) bounding radius -- only applied when there's actually an animation to play.

import sys
import os
import pathlib
import argparse

os.environ.update({
	"OSG_WINDOW": "50 50 800 600",
	"OSG_THREADING": "SingleThreaded",
	"OSG_GL_CONTEXT_PROFILE_MASK": "1",
	"OSG_GL_VERSION": "4.6",
	"OSG_GL_CONTEXT_VERSION": "4.6",
})

from OpenSceneGraph import *
from OpenSceneGraph.GL import *

import osgx

THIS_DIR = pathlib.Path(__file__).resolve().parent
DATA_DIR = THIS_DIR / "data"

# Bare name (e.g. "Fox") -> glTF-Sample-Assets/Models/<name>/glTF/<name>.gltf via
# osgx.findDataFile(), same convention every other step in this series uses.
def resolve_model(value):
	path = pathlib.Path(value).expanduser()

	if path.is_file():
		return str(path)

	return osgx.findDataFile(value) or osgx.findDataFile(
		path.stem, ("glTF-Sample-Assets/Models/{}/glTF/{}.gltf",)
	) or None

# HDR/manifest assets for this step live locally in pyosg-lighting/data/ (papermill.hdr, etc.) --
# checked first, falling back to osgx.findDataFile() for anything found via OSG_FILE_PATH instead.
def resolve_asset(value, suffix):
	path = pathlib.Path(value).expanduser()

	if path.is_file():
		return str(path)

	local = DATA_DIR / f"{value}.{suffix}"

	if local.is_file():
		return str(local)

	return osgx.findDataFile(value, (), suffix) or None

# Same light positions as Steps 7/8/9 -- no light animation.
KEY_LIGHT_POS = osg.Vec3( 0.1, 0.1, 1.0) # front-center key (shadow caster)
FILL_LIGHT_POS_0 = osg.Vec3(-0.8, 0.3, 0.5) # cool fill, left
FILL_LIGHT_POS_1 = osg.Vec3( 0.0, -0.6, 0.2) # warm back/rim

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
# floor is just a plausible shadow receiver) -- otherwise identical shape to Step 8's floor.
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

# 1/2/3 cycle PBRIBLScene.create()'s debugMode (combined/diffuse-only/specular-only) when
# --diagnostics is passed -- isolates what IBL's two independent intensity knobs are each
# actually contributing.
class Diagnostics(osgGA.GUIEventHandler):
	MODE_NAMES = ("combined", "diffuse only", "specular only")

	def __init__(self, scene):
		super().__init__()

		self.scene = scene

	def handle(self, event, action):
		if event.handled or event.type != osgGA.GUIEventAdapter.KEYUP:
			return False

		if event.key not in (ord("1"), ord("2"), ord("3")):
			return False

		mode = event.key - ord("1")

		self.scene.debugMode.value = mode

		osg.notice(f"[diagnostic] {self.MODE_NAMES[mode]}")

		return True

# Keyboard clip playback -- always available, independent of the ImGui panel below.
# 1-9 select a clip by index, [/] step to the previous/next clip, Space toggles play/pause,
# R restarts the current clip.
class AnimationHandler(osgGA.GUIEventHandler):
	def __init__(self, player):
		super().__init__()

		self.player = player

	def select(self, index):
		if self.player.playAnimation(index):
			print(f"[animation] {index + 1}: {self.player.currentAnimationName}", flush=True)

	def handle(self, ea, aa):
		if ea.handled or ea.type != osgGA.GUIEventAdapter.KEYUP:
			return False

		if ord("1") <= ea.key <= ord("9"):
			index = ea.key - ord("1")

			if index < self.player.numAnimations:
				self.select(index)

				return True

		if ea.key in (ord("["), ord("]")):
			delta = -1 if ea.key == ord("[") else 1
			index = (self.player.currentAnimationIndex + delta) % self.player.numAnimations

			self.select(index)

			return True

		if ea.key == ord(" "):
			self.player.togglePlaying()

			print(f"[animation] {'playing' if self.player.playing else 'paused'}", flush=True)

			return True

		if ea.key in (ord("r"), ord("R")):
			self.player.restart()

			print(f"[animation] restarted {self.player.currentAnimationName}", flush=True)

			return True

		return False

if __name__ == "__main__":
	ap = argparse.ArgumentParser()
	ap.add_argument("path", nargs="?", default=None)

	env_group = ap.add_mutually_exclusive_group()
	env_group.add_argument(
		"--hdr",
		default=None,
		help="Equirectangular HDR; bakes diffuse/specular/BRDF-LUT live (default: papermill)"
	)
	env_group.add_argument(
		"--env",
		default=None,
		help="Pre-baked osgx_pbribl environment manifest"
	)

	ap.add_argument("--ibl-diffuse", type=float, default=1.0, dest="ibl_diffuse")
	ap.add_argument("--ibl-specular", type=float, default=1.0, dest="ibl_specular")
	ap.add_argument("--no-lights", dest="lights", action="store_false", default=True)
	ap.add_argument(
		"--diagnostics",
		action="store_true",
		default=False,
		help="Enable 1/2/3 combined/diffuse/specular isolation"
	)
	ap.add_argument("--floor-z", type=float, default=None)
	ap.add_argument("--floor-size", type=float, default=None)
	ap.add_argument(
		"--no-gui",
		dest="gui",
		action="store_false",
		default=True,
		help="Disable the osgx ImGui animation panel (keyboard controls still work)"
	)

	args = ap.parse_args()

	if not args.hdr and not args.env:
		args.hdr = "papermill"

	# No floor by default; passing either flag activates it.
	args.floor = args.floor_z is not None or args.floor_size is not None
	args.floor_z = -0.04 if args.floor_z is None else args.floor_z
	args.floor_size = 0.15 if args.floor_size is None else args.floor_size

	osg.setNotifyLevel(osg.NotifySeverity.NOTICE)

	# Fox has three distinct clips (Survey/Walk/Run) -- a much better default for a clip-picker
	# demo than a single-clip or unanimated model.
	path = resolve_model(args.path or "Fox")

	if not path:
		sys.exit("Cannot find model -- clone glTF-Sample-Assets into your OSG_FILE_PATH checkout")

	model = osgDB.readNodeFile(path)
	bound = model.bound

	# --- Animation -------------------------------------------------------------- #
	# Falsy (no playable clips) degrades every accessor to a harmless no-op/default -- the
	# `if animation_player:` guards below are what let this file run unmodified against a
	# non-animated model too.
	animation_player = osgx.gltf.SimplePlayer(model)

	if animation_player:
		print("[animation] available clips:", flush=True)

		for i in range(animation_player.numAnimations):
			print(f"  {i + 1}: {animation_player.getAnimationName(i)}", flush=True)

		print(
			"[animation] keys: 1-9 select, [/] previous/next, Space pause, R restart",
			flush=True
		)

	else:
		print("[animation] no animations found in this model", flush=True)

	# --- IBL environment ------------------------------------------------------ #
	if args.hdr:
		hdr_path = resolve_asset(args.hdr, "hdr")

		if not hdr_path:
			sys.exit(f"Cannot find HDR {args.hdr!r} -- check pyosg-lighting/data/ or OSG_FILE_PATH")

		environment = osgx.gltf.pbribl.PBRIBLEnvironment.prepare(hdr_path, lutSize=1024)

	else:
		env_path = resolve_asset(args.env, "gltf")

		if not env_path:
			sys.exit(f"Cannot find environment manifest {args.env!r}")

		environment = osgx.gltf.pbribl.PBRIBLEnvironment.load(env_path)

	if not environment.valid():
		sys.exit("Failed to prepare/load the PBR/IBL environment")

	# --- Lights (shared ancestor StateSet, same shape as Step 8) -------------- #
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
	# Only built when there's a light to cast it -- with --no-lights there's no direct-light term
	# for a shadow to darken, so the extra PRE_RENDER depth pass would be pure waste.
	shadow_map = None

	if args.lights:
		light_dir = (bound.center - KEY_LIGHT_POS).normalized()

		shadow_map = osgx.ShadowMap.create(light_dir, bound.center, bound.radius)

		shadow_map.camera.children.append(model)

	# --- glTF PBR/IBL scene ---------------------------------------------------- #
	# An osgx.Hook.Skinning hooks entry substitutes PBRIBLScene.create()'s default identity
	# osgx_gltf_ApplySkin() with the real joint-matrix linear-blend skin -- without this, the mesh
	# stays frozen in its bind pose no matter what AnimationCallback does to the joint transforms
	# (see osgx/TODO.md's "current animation behavior" note for why the two are independent). As
	# of osgx's 2026-08-20 HookList refactor, this is a (Hook, Shader) pair in the `hooks` list
	# rather than its own standalone `skinningHook` keyword argument.
	hooks = []

	if animation_player:
		hooks.append((
			osgx.Hook.Skinning,
			osg.Shader(
				osg.Shader.VERTEX,
				osgx.gltf.pbribl.resolveShaderLibs(osgx.gltf.shader.SKINNING_HOOK_LINEAR_BLEND)
			)
		))

	pbr = osgx.gltf.pbribl.PBRIBLScene.create(
		model,
		environment,
		iblDiffuseIntensity=args.ibl_diffuse,
		iblSpecularIntensity=args.ibl_specular,
		diagnostics=args.diagnostics,
		shadowMap=shadow_map,
		hooks=hooks
	)

	if not pbr.valid():
		sys.exit("Failed to build the PBR/IBL scene")

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

	# GPU skinning moves vertices without updating OSG's CPU-side drawable bounds -- see this
	# file's own header comment. A static model behaves fine under 09-ibl.py's plain auto near/far,
	# so this only kicks in when there's actually an animation to play.
	if animation_player:
		camera_near = max(bound.radius * 0.001, 0.001)
		camera_far = max(bound.radius * 1000.0, 1000.0)

		v.camera.computeNearFarMode = osg.Camera.DO_NOT_COMPUTE_NEAR_FAR
		v.camera.projectionMatrix = osg.Matrix.perspective(30.0, 800.0 / 600.0, camera_near, camera_far)

		v.eventHandlers.append(AnimationHandler(animation_player))

	if args.diagnostics:
		v.eventHandlers.append(Diagnostics(pbr))

		osg.notice("Diagnostics: 1=combined 2=diffuse 3=specular")

	# --- ImGui panel: one clicky button per animation clip, anchored left ------- #
	if args.gui and animation_player:
		gui_opts = osgx.imgui.Options()
		gui_opts.dock = osgx.imgui.Dock.LEFT

		gui = osgx.imgui.Widget(v, v.camera, gui_opts)

		def draw_animations(ri):
			osgx.imgui.text(f"Now playing: {animation_player.currentAnimationName or '(none)'}")
			osgx.imgui.separator()

			for i in range(animation_player.numAnimations):
				if osgx.imgui.button(animation_player.getAnimationName(i)):
					animation_player.playAnimation(i)

			osgx.imgui.separator()

			changed, playing = osgx.imgui.checkbox("Playing", animation_player.playing)

			if changed:
				animation_player.playing = playing

			if osgx.imgui.button("Restart"):
				animation_player.restart()

		gui.addSection("Animations", draw_animations, osgx.imgui.SectionOptions(default_open=True))

	while not v.done:
		v.frame()
