#!/usr/bin/env python3

"""Combined D4/D6/D8/D10/D12/D20 procedural-number-atlas prototype -- see
ai/context-todo-dice.md. Supersedes the separate `pyosg-d4.py`/
`pyosg-d6-numbers.py` prototypes now that all these dice reduce to the same
mesh/shader mechanism via `pyosg_dice.py` (see that module's docstring for
the full writeup: one shared vertex-attribute layout, one shared decal
shader, the only real difference between die types being DATA -- which base
vertices/faces, and whether numbering is per-face-center or per-vertex-corner).

Usage: `--die d4,d6,d8,d10,d12,d20` (default: all six) shows any subset of the
currently supported dice side by side, sharing one Program and one number
atlas. Press `r` to decide and animate a new outcome for every displayed die;
holding it keeps the dice spinning at their apex until release. The generic
roll support lives in `pyosg_dice.py`: it chooses each outcome first, then
uses elastic tumble/bounce interpolation only as its visualization. The
shape topology, face UVs, and support geometry now come from the named
`osgx` polyhedra. This example remains responsible only for the procedural
number atlas, dice-specific shader, scene assembly, and result highlight.

`--hdr PATH`/`--env MANIFEST` (mutually exclusive, both optional -- same
contract as `pyosg-khronos-viewer.py`) swap the dice's lighting from the
fixed N.L term to real PBR/IBL: the atlas-decal fragment logic is unchanged,
only the term the decal-composited albedo is lit by. Dice are treated as a
fixed dielectric plastic (metallic=0, a constant roughness) for now -- no
per-face material data yet, that's still future work. The floor stays on
the plain N.L shader either way; this is a first proof that the procedural
dice mesh/shader can sit under osgx's PBR/IBL substrate at all.
"""

import argparse
import os
import random

os.environ.setdefault("OSG_WINDOW", "50 50 800 600")
os.environ.setdefault(
	"OSG_LIBRARY_PATH", ":".join((
		"/home/cubicool/dev/osgx/BUILD-g++-13.3.0-NOASAN/plugins/ktx2",
		"/home/cubicool/dev/osgx/BUILD-g++-13.3.0-NOASAN/plugins/gltf"
	))
)

# Import side effect: fills in OSG_THREADING/OSG_GL_* env var defaults (see pyosg_example.py).
# Deliberately after the OSG_WINDOW/OSG_LIBRARY_PATH overrides above (setdefault() means order
# between these doesn't actually matter, but matching pyosg-khronos-viewer.py's style) and before
# `from OpenSceneGraph import *` -- these need to land before OSG's DisplaySettings reads them.
from pyosg_example import label, window_size

from OpenSceneGraph import *
from OpenSceneGraph.GL import *

import osgx
import pyosg_dice as dice

DIE_SPACING = 3.0
FLOOR_MARGIN = 1.6

DIE_SIZE = dice.DIE_SIZE
ATLAS_DIGITS = dice.ATLAS_DIGITS

DIE_FRAGMENT_SHADER = """
#version 330 core

in vec3 vNormal;
in vec2 vUV;
flat in vec3 vDecalValues;
flat in vec3 vAnchorU;
flat in vec3 vAnchorV;

uniform sampler2D numberAtlas;
uniform int digitCount;
uniform float decalHalf;
uniform vec3 bodyColor;
uniform vec3 ink;
uniform int activeFaceMask;
uniform int activeDecalValue;

out vec4 fragColor;

void main() {
	const vec3 L = vec3(0.4, 0.6, 0.7);
	const float DECAL_FACE_STRIDE = 32.0;

	float diffuse = max(dot(normalize(vNormal), normalize(L)), 0.0);
	float light = 0.35 + 0.65 * diffuse;
	int faceBit = 1 << int(vDecalValues[0] / DECAL_FACE_STRIDE);
	bool activeFace = (activeFaceMask & faceBit) != 0;

	vec2 anchorSum = vec2(0.0);
	int count = 0;

	for (int i = 0; i < 3; i++) {
		if (vDecalValues[i] >= 0.0) {
			anchorSum += vec2(vAnchorU[i], vAnchorV[i]);
			count++;
		}
	}

	vec2 avgAnchor = count > 0 ? anchorSum / float(count) : vec2(0.0);
	vec3 color = activeFace ? bodyColor * 0.55 : bodyColor;

	for (int i = 0; i < 3; i++) {
		if (vDecalValues[i] < 0.0) continue;

		float decalValue = mod(vDecalValues[i], DECAL_FACE_STRIDE);
		vec2 anchor = vec2(vAnchorU[i], vAnchorV[i]);
		vec2 up = count > 1 ? normalize(anchor - avgAnchor) : vec2(0.0, 1.0);
		vec2 right = vec2(up.y, -up.x);

		vec2 local = vUV - anchor;
		float lu = dot(local, right) / decalHalf;
		float lv = dot(local, up) / decalHalf;

		if (abs(lu) <= 1.0 && abs(lv) <= 1.0) {
			vec2 atlasUV = vec2(
				(decalValue + (lu * 0.5 + 0.5)) / float(digitCount),
				lv * 0.5 + 0.5
			);
			// osgx.PixelText.createAtlas() is a coverage-only (single-channel) atlas -- the
			// ink color is no longer baked into the image, so it comes from the ink uniform.
			float coverage = texture(numberAtlas, atlasUV).r;
			bool activeDecal = activeFace && int(decalValue + 0.5) == activeDecalValue;
			vec3 glyphColor = activeDecal ? vec3(0.95, 0.92, 0.82) : ink;

			color = mix(color, glyphColor, coverage);
		}
	}

	fragColor = vec4(color * light, 1.0);
}
"""

# IBL variant of the fragment shader above: same decal-atlas logic, lit via osgx's
# PBR/IBL substrate instead of the fixed N.L term. Forked from dice.FRAGMENT_SHADER_IBL
# to add the activeFaceMask/activeDecalValue highlight uniforms, same relationship
# DIE_FRAGMENT_SHADER has to dice.FRAGMENT_SHADER. The vertex side needs no such fork --
# dice.VERTEX_SHADER_IBL carries no highlight data, so it's used directly below.
DIE_FRAGMENT_SHADER_IBL = """
#version 460 core

#pragma osgx::pbr F_MULTISCATTER

in vec3 vNormal;
in vec3 vViewDir;
in vec2 vUV;
flat in vec3 vDecalValues;
flat in vec3 vAnchorU;
flat in vec3 vAnchorV;

uniform mat4 osg_ViewMatrix;
uniform sampler2D numberAtlas;
uniform int digitCount;
uniform float decalHalf;
uniform vec3 bodyColor;
uniform vec3 ink;
uniform int activeFaceMask;
uniform int activeDecalValue;

uniform samplerCube envMap;
uniform sampler2D brdfLUT;
uniform samplerCube diffuseEnv;

// Same cubemap lookup basis osgx.gltf.pbribl.PBRIBLScene.create() reads off
// PBRIBLEnvironment.iblAxis -- see dice.rotate_ibl_environment().
uniform vec3 iblAxis[3];

// Whole-die material knobs -- no per-face roughness/metallic data yet, just a uniform
// scalar pair so the PBR/IBL response is at least visibly tunable from the CLI.
uniform float roughness;
uniform float metallic;

out vec4 fragColor;

// Ported from osgx::gltf::pbribl's own PBRIBL.cpp shader -- Z-up world direction to the
// baked cubemap's Y-up convention, then onto the (possibly rotated) lookup basis.
vec3 osgx_ZUpToGLTF(vec3 d) { return vec3(d.x, d.z, -d.y); }
vec3 osgx_OrientIBL(vec3 d) {
	return vec3(dot(d, iblAxis[0]), dot(d, iblAxis[1]), dot(d, iblAxis[2]));
}

void main() {
	const float DECAL_FACE_STRIDE = 32.0;

	int faceBit = 1 << int(vDecalValues[0] / DECAL_FACE_STRIDE);
	bool activeFace = (activeFaceMask & faceBit) != 0;

	vec2 anchorSum = vec2(0.0);
	int count = 0;

	for (int i = 0; i < 3; i++) {
		if (vDecalValues[i] >= 0.0) {
			anchorSum += vec2(vAnchorU[i], vAnchorV[i]);
			count++;
		}
	}

	vec2 avgAnchor = count > 0 ? anchorSum / float(count) : vec2(0.0);
	vec3 albedo = activeFace ? bodyColor * 0.55 : bodyColor;

	for (int i = 0; i < 3; i++) {
		if (vDecalValues[i] < 0.0) continue;

		float decalValue = mod(vDecalValues[i], DECAL_FACE_STRIDE);
		vec2 anchor = vec2(vAnchorU[i], vAnchorV[i]);
		vec2 up = count > 1 ? normalize(anchor - avgAnchor) : vec2(0.0, 1.0);
		vec2 right = vec2(up.y, -up.x);

		vec2 local = vUV - anchor;
		float lu = dot(local, right) / decalHalf;
		float lv = dot(local, up) / decalHalf;

		if (abs(lu) <= 1.0 && abs(lv) <= 1.0) {
			vec2 atlasUV = vec2(
				(decalValue + (lu * 0.5 + 0.5)) / float(digitCount),
				lv * 0.5 + 0.5
			);
			// osgx.PixelText.createAtlas() is a coverage-only (single-channel) atlas -- the
			// ink color is no longer baked into the image, so it comes from the ink uniform.
			float coverage = texture(numberAtlas, atlasUV).r;
			bool activeDecal = activeFace && int(decalValue + 0.5) == activeDecalValue;
			vec3 glyphColor = activeDecal ? vec3(0.95, 0.92, 0.82) : ink;

			albedo = mix(albedo, glyphColor, coverage);
		}
	}

	// Eye-space N/V, rotated into world space the same way pyosg-khronos-viewer.py's
	// underlying shader does -- transpose(mat3(osg_ViewMatrix)) is the view rotation's
	// inverse, since it's orthonormal.
	mat3 invView = transpose(mat3(osg_ViewMatrix));
	vec3 N = invView * normalize(vNormal);
	vec3 V = invView * normalize(vViewDir);
	vec3 F0 = mix(vec3(0.04), albedo, metallic);

	vec3 diffuseIrradiance = texture(diffuseEnv, osgx_OrientIBL(osgx_ZUpToGLTF(N))).rgb;
	vec3 R = reflect(-V, N);
	float maxMip = float(max(textureQueryLevels(envMap) - 2, 0));
	vec3 prefiltered = textureLod(envMap, osgx_OrientIBL(osgx_ZUpToGLTF(R)), roughness * maxMip).rgb;
	vec3 Fd = osgx_F_MultiScatter(N, V, roughness, F0, brdfLUT);
	vec3 color = diffuseIrradiance * albedo * (1.0 - Fd) * (1.0 - metallic) + prefiltered * Fd;

	fragColor = vec4(pow(color, vec3(1.0 / 2.2)), 1.0);
}
"""

# The shared module owns topology, values, and presentation defaults.
DIE_SPECS = dice.DIE_SPECS

def create_scene(die_names, environment=None, roughness=0.45, metallic=0.0):
	root = osg.Group(name="scene")
	vertex_shader = osg.Shader(osg.Shader.VERTEX, dice.VERTEX_SHADER)

	if environment is not None:
		die_program = osg.Program(name="pyosg-dice-ibl", shaders=(
			osg.Shader(osg.Shader.VERTEX, dice.VERTEX_SHADER_IBL),
			osg.Shader(osg.Shader.FRAGMENT, osgx.resolveShaderLibs(DIE_FRAGMENT_SHADER_IBL)),
		))
		root.stateSet.uniforms.extend((
			osg.Uniform("roughness", roughness),
			osg.Uniform("metallic", metallic),
			osg.Uniform(osg.Uniform.Type.FLOAT_VEC3, "iblAxis", tuple(environment.iblAxis)),
		))

	else:
		die_program = osg.Program(name="pyosg-dice", shaders=(
			vertex_shader,
			osg.Shader(osg.Shader.FRAGMENT, DIE_FRAGMENT_SHADER),
		))

	atlas_tex = osg.Texture2D(
		image=osgx.PixelText.createAtlas(ATLAS_DIGITS),
		filter=(osg.Texture.NEAREST, osg.Texture.NEAREST),
		wrap=(osg.Texture.CLAMP_TO_EDGE, osg.Texture.CLAMP_TO_EDGE),
	)

	positions = [(i - (len(die_names) - 1) / 2.0) * DIE_SPACING for i in range(len(die_names))]
	# Every die has this shared circumradius, so no per-die footprint estimates are needed.
	floor_half = (max((abs(x) for x in positions), default=0.0) + DIE_SIZE + FLOOR_MARGIN)

	floor_geode = osg.Geode(name="floor")
	floor_drawable = osg.ShapeDrawable(osg.Box(
		osg.Vec3(0.0, 0.0, -0.05), floor_half * 2.0, floor_half * 2.0, 0.1
	))

	floor_geode.drawables.append(floor_drawable)
	floor_geode.stateSet.attributes.append(osg.Program(name="pyosg-dice-floor", shaders=(
		vertex_shader,
		osg.Shader(osg.Shader.FRAGMENT, dice.FLOOR_FRAGMENT_SHADER),
	)))
	root.children.append(floor_geode)

	rollable_dice = []
	active_face_uniforms = []
	active_decal_uniforms = []

	for x, name in zip(positions, die_names):
		spec = DIE_SPECS[name]
		geom, roll_spec = spec.build_geometry()
		rest_xy = osg.Vec3(x, 0.0, 0.0)
		rest_pos = dice.rest_position(rest_xy, roll_spec.polyhedron, osg.Quat())
		mt = osg.MatrixTransform(osg.Matrix.translate(rest_pos))
		die_geode = osg.Geode(name=name)

		die_geode.drawables.append(geom)
		mt.children.append(die_geode)
		root.children.append(mt)

		die_ss = die_geode.stateSet
		active_face_uniform = osg.Uniform("activeFaceMask", 0)
		active_decal_uniform = osg.Uniform("activeDecalValue", -1)

		die_ss.attributes.append(die_program)
		die_ss.textureAttributes[0] = atlas_tex
		die_ss.uniforms.extend((
			osg.Uniform("numberAtlas", 0),
			osg.Uniform("digitCount", len(ATLAS_DIGITS)),
			osg.Uniform("decalHalf", spec.decal_half),
			osg.Uniform("bodyColor", osg.Vec3(*spec.body_color)),
			osg.Uniform("ink", osg.Vec3(*dice.INK)),
			active_face_uniform,
			active_decal_uniform,
		))

		if environment is not None:
			die_ss.textureAttributes[5] = environment.envMap
			die_ss.textureAttributes[6] = environment.brdfLUT
			die_ss.textureAttributes[7] = environment.diffuseEnv
			die_ss.uniforms.extend((
				osg.Uniform("envMap", 5),
				osg.Uniform("brdfLUT", 6),
				osg.Uniform("diffuseEnv", 7),
			))

		rollable_dice.append((mt, rest_xy, roll_spec))
		active_face_uniforms.append(active_face_uniform)
		active_decal_uniforms.append(active_decal_uniform)

	return root, rollable_dice, active_face_uniforms, active_decal_uniforms

# Set by build_scene(), read by configure_viewer() -- rollable_dice/active_face_uniforms/
# active_decal_uniforms/roll_totals/total_label are plain Python state (roll_spec data, uniform
# lists, running-total bookkeeping) with no single natural home in the returned Node the way
# pyosg-mrt.py pulls a lone Uniform back out of a StateSet -- same shape/reason as
# pyosg-khronos-viewer.py's _args/_pbr.
_args = None
_rollable_dice = None
_active_face_uniforms = None
_active_decal_uniforms = None
_roll_totals = None
_total_label = None

# The real pipeline-assembly entrypoint -- returns the root Node, no viewer/window side effects.
def build_scene(w, h):
	global _args, _rollable_dice, _active_face_uniforms, _active_decal_uniforms
	global _roll_totals, _total_label

	parser = argparse.ArgumentParser(description="Procedural polyhedral dice, number-atlas/decal prototype.")
	parser.add_argument(
		"--die",
		default="d4,d6,d8,d10,d12,d20",
		help=f"comma-separated dice to show, from {{{', '.join(sorted(DIE_SPECS))}}} (default: %(default)s)",
	)
	environment_group = parser.add_mutually_exclusive_group()
	environment_group.add_argument(
		"--hdr",
		metavar="PATH",
		help="source HDR environment; bakes diffuse, BRDF LUT, and GGX-prefiltered specular live, "
			"and switches the dice from N.L shading to PBR/IBL"
	)
	environment_group.add_argument(
		"--env",
		metavar="MANIFEST",
		help="fully pre-baked osgx_pbribl environment manifest (see pyosg-khronos-viewer.py)"
	)
	parser.add_argument(
		"--roughness",
		type=float,
		default=0.45,
		help="whole-die PBR/IBL roughness, only used with --hdr/--env (default: %(default)s)"
	)
	parser.add_argument(
		"--metallic",
		type=float,
		default=0.0,
		help="whole-die PBR/IBL metallic, only used with --hdr/--env (default: %(default)s)"
	)
	parser.add_argument(
		"--ibl-rotate",
		type=int,
		default=0,
		choices=(0, 90, 180, 270),
		help="rotate the environment about the vertical axis by this many degrees before "
			"sampling it, only used with --hdr/--env (default: %(default)s)"
	)
	_args = args = parser.parse_args()
	die_names = [d.strip() for d in args.die.split(",") if d.strip()]

	for name in die_names:
		if name not in DIE_SPECS:
			parser.error(f"unknown die {name!r} -- choose from {{{', '.join(sorted(DIE_SPECS))}}}")

	environment = dice.prepare_environment(args.hdr, args.env, args.ibl_rotate)

	if environment is not None and not environment.valid():
		parser.error("failed to prepare PBR/IBL environment resources")

	scene, rollable_dice, active_face_uniforms, active_decal_uniforms = create_scene(
		die_names, environment, args.roughness, args.metallic
	)

	if environment is not None and environment.root is not None:
		scene.children.append(environment.root)

	# 0 until a die's first roll completes, so the total is always the sum of whatever's
	# currently showing -- populated by highlight_result() below, same per-die "which value did
	# THIS die land on" data DiceRollCallback already threads through result_callback for the
	# highlight uniforms above; this was already tracked, just not summed/displayed anywhere.
	roll_totals = [0] * len(rollable_dice)

	# A screen-aligned running-total HUD, top-left -- same POST_RENDER/ABSOLUTE_RF overlay-camera
	# shape pyosg_async.Progress already uses for a screen-space indicator, just a pixel-space
	# ortho (0..w, 0..h) projection instead of Progress' identity/clip-space one, since
	# osgx.PixelText expects local-space units in screen pixels, not NDC. w/h are fixed for this
	# script (no window-resize handling elsewhere), so the projection is set once, not tracked
	# live the way examples/osgx-pixel-text.cpp's makeHudLabel() has to for a resizable window.
	hud_margin = 12.0
	hud_cell_size = osgx.PixelText.GLYPH_ROWS * 3.0
	total_label = osgx.PixelText("TOTAL: 0", hud_cell_size)
	total_geode = osg.Geode(name="roll-total-label")

	total_label.ink = osg.Vec4(1.0, 1.0, 1.0, 1.0)

	total_geode.drawables.append(total_label)

	total_transform = osg.MatrixTransform(
		osg.Matrix.translate(hud_margin, h - hud_margin - hud_cell_size, 0.0)
	)

	total_transform.children.append(total_geode)

	hud_camera = osg.Camera(name="roll-total-camera", children=[total_transform])

	hud_camera.referenceFrame = osg.Transform.ABSOLUTE_RF
	hud_camera.renderOrder = osg.Camera.POST_RENDER
	hud_camera.clearMask = 0
	hud_camera.viewMatrix = osg.Matrix.identity()
	hud_camera.projectionMatrix = osg.Matrix.ortho2D(0, w, 0, h)
	hud_camera.allowEventFocus = False
	hud_camera.stateSet.modes[GL_DEPTH_TEST] = osg.StateAttribute.OFF

	scene.children.append(hud_camera)
	scene.children.append(label("R to reroll", w, h))

	_rollable_dice = rollable_dice
	_active_face_uniforms = active_face_uniforms
	_active_decal_uniforms = active_decal_uniforms
	_roll_totals = roll_totals
	_total_label = total_label

	return scene

# DiceRollKeyHandler needs the live viewer (event handler registration), which build_scene()
# never receives.
def configure_viewer(viewer, root):
	rollable_dice = _rollable_dice
	active_face_uniforms = _active_face_uniforms
	active_decal_uniforms = _active_decal_uniforms
	roll_totals = _roll_totals
	total_label = _total_label

	rng = random.Random()
	rolling = [False] * len(rollable_dice)
	r_held = [False]

	def highlight_result(index, value, active_faces):
		active_face_uniforms[index].value = sum(1 << face_index for face_index in active_faces)
		active_decal_uniforms[index].value = dice.atlas_column(value)
		roll_totals[index] = value
		total_label.text = f"TOTAL: {sum(roll_totals)}"

	def clear_result(index):
		active_face_uniforms[index].value = 0
		active_decal_uniforms[index].value = -1

	viewer.eventHandlers.append(dice.DiceRollKeyHandler(
		rollable_dice,
		rng,
		rolling,
		r_held,
		notice_prefix="pyosg-dice",
		result_callback=highlight_result,
		roll_started_callback=clear_result,
	))

	osg.notice("[pyosg-dice] press 'r' to roll; hold it to spin at the peak")

if __name__ == "__main__":
	osg.setNotifyLevel(osg.NotifySeverity.NOTICE)

	W, H = window_size()

	viewer = osgViewer.Viewer()
	root = build_scene(W, H)

	viewer.sceneData = root
	viewer.cameraManipulator = osgGA.TrackballManipulator()

	configure_viewer(viewer, root)

	while not viewer.done:
		viewer.frame()
