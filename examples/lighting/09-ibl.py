#!/usr/bin/env python3

# Step 9 -- Image-Based Lighting (IBL)
#
# This step used to hand-roll its own SH9 diffuse projection (numpy/cv2, see git history) and its
# own GGX-prefiltered-cubemap + split-sum BRDF LUT shader math -- reasonable the first time through,
# but osgx.gltf.pbribl now exists as a real, battle-tested production pipeline (it grew out of
# exactly this example's needs -- see PBRIBL.cpp's own history comment). Re-deriving IBL by hand a
# second time here would be re-teaching a solved problem, not teaching a new one, so this step pivots
# to consuming it directly:
#
# osgx.gltf.pbribl.PBRIBLEnvironment.prepare(hdrPath) -- bakes diffuse irradiance, the BRDF LUT, and
# a GGX-prefiltered specular cubemap all LIVE from one equirectangular .hdr, via a handful of
# PRE_RENDER passes added to the scene graph (environment.root). No .ktx2 pre-bake step needed
# anymore -- that's what this step's numpy/cv2 SH compute + --ktx2 loading used to stand in for.
#
# osgx.gltf.pbribl.PBRIBLScene.create(node, environment, ..., shadowMap=...) -- wires the whole
# thing (material + IBL + optional direct lights + optional shadow) onto node's own StateSet with
# one call. Direct lights still come from osgx.LightSet exactly as Step 8 introduced; passing
# a shadowMap here is the same osgx.ShadowMap Step 8 built, just handed to PBRIBLScene.create
# instead of wired by hand.
#
# The floor is NOT glTF -- it's still a hand-rolled osgx_Material + osgx_DirectLighting() call
# (identical shape to Step 8's floor), since PBRIBLScene.create() is specifically the glTF-material
# convenience path and a flat quad has no glTF material to feed it.

import sys
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
from pyosg_example import window_size, resolve_model, resolve_asset

from OpenSceneGraph import *
from OpenSceneGraph.GL import *

import osgx

# Same light positions as Step 7/8 -- no animation.
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

# Set by build_scene(), read by configure_viewer() -- the Diagnostics eventHandler needs the live
# viewer to register on, which build_scene() never receives. Same "no other channel exists"
# reasoning as pyosg-khronos-viewer.py's own _args/_pbr stash.
_args = None
_pbr = None

def build_scene(w, h):
	global _args, _pbr

	ap = argparse.ArgumentParser()
	ap.add_argument("path", nargs="?", default=None)

	env_group = ap.add_mutually_exclusive_group()
	env_group.add_argument(
		"--hdr",
		default=None,
		help="Equirectangular HDR; bakes diffuse/specular/BRDF-LUT live"
	)
	env_group.add_argument(
		"--env",
		default=None,
		help="Pre-baked osgx_pbribl environment manifest (default: papermill)"
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
	ap.add_argument("--no-floor", dest="floor", action="store_false", default=True)

	args = ap.parse_args()

	# --env, not --hdr: only pre-baked manifests are ever bundled in the openscenegraph-
	# examples wheel (see resolve_asset()'s own comment in pyosg_example.py) -- a bare
	# invocation with neither flag must work out of the box against a plain `pip install`,
	# not require OSG_FILE_PATH pointed at a real glTF-Sample-Environments checkout.
	if not args.hdr and not args.env:
		args.env = "papermill"

	# On by default (tuned for BoomBox); --no-floor opts out, --floor-z/--floor-size override.
	args.floor_z = -0.01 if args.floor_z is None else args.floor_z
	args.floor_size = 0.05 if args.floor_size is None else args.floor_size

	_args = args

	osg.setNotifyLevel(osg.NotifySeverity.NOTICE)

	path = resolve_model(args.path or "BoomBox")

	if not path:
		sys.exit("Cannot find model -- clone glTF-Sample-Assets into your OSG_FILE_PATH checkout")

	model = osgDB.readNodeFile(path)

	# --- IBL environment ------------------------------------------------------ #
	if args.hdr:
		hdr_path = resolve_asset(args.hdr, "hdr")

		if not hdr_path:
			sys.exit(f"Cannot find HDR {args.hdr!r} -- check OSG_FILE_PATH")

		environment = osgx.gltf.pbribl.PBRIBLEnvironment.prepare(hdr_path, lutSize=1024)

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
	# main_group, an ancestor) -- osgx::LightSet::apply() pushes osgx_lightCount to whatever
	# Program is CURRENTLY bound at the moment it runs, so attaching it on an ancestor pushes to
	# whatever (stale/unrelated) program was bound before this subtree even started descending.
	# Confirmed root cause + osgx-level fix 2026-09-03 (see 08-shadows.py's own history); the
	# floor's Program gets the same shared `lights` object attached to ITS OWN StateSet below.
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
	# Only built when there's a light to cast it -- with --no-lights there's no direct-light term
	# for a shadow to darken, so the extra PRE_RENDER depth pass would be pure waste.
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
		diagnostics=args.diagnostics,
		shadowMap=shadow_map
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

	_pbr = pbr

	return root

# Diagnostics needs the live viewer, which build_scene() never receives.
def configure_viewer(viewer, root):
	if _args.diagnostics:
		viewer.eventHandlers.append(Diagnostics(_pbr))

		osg.notice("Diagnostics: 1=combined 2=diffuse 3=specular")

if __name__ == "__main__":
	W, H = window_size()

	viewer = osgViewer.Viewer()
	root = build_scene(W, H)

	viewer.sceneData = root
	viewer.cameraManipulator = osgGA.TrackballManipulator()

	configure_viewer(viewer, root)

	while not viewer.done:
		viewer.frame()
