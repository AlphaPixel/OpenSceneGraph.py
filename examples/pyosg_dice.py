#!/usr/bin/env python3

"""Shared polyhedral-dice mesh factory + atlas/decal shader, factored out of
`pyosg-d4.py`/`pyosg-d6-numbers.py` once both were proven working
separately -- see ai/context-todo-dice.md. Not a standalone example (no
`__main__`); imported by the per-die scripts, same relationship
`pyosg_repl.py` has to the examples that `from pyosg_repl import repl`.

Point of this module: D4/D6/D8/D10/D12/D20 all reduce to the same
``osgx.Polyhedron`` mesh construction (flat-shaded, face-unique vertices,
fan-triangulated) and the same decal mechanism (a small number of
atlas-sampled digit decals per face, placed via a per-fragment "which anchor
is this pixel nearest, what's my local position within its box" test). The
named ``osgx`` shapes own topology and UVs; this module supplies only die
numbering, decals, and roll presentation. A face shows one centered digit
except D4, which uses up to three corner digits because its rolled value is
read from the top vertex rather than the top face.

Vertex attribute layout, identical for every die built through this module:
  osg_Vertex (location 0)          -- position, via .vertexArray
  osg_Normal (location 1)          -- flat per-face normal, via .normalArray
  osg_MultiTexCoord0 (location 3)  -- canonical per-face UV, via .vertexAttrib[3]
                                       (texcoord unit 0's generic-attrib alias,
                                       confirmed against OSG source -- see
                                       pyosg-dice.py's own docstring)
  decalValues (location 13, vec3)  -- 0-based digit plus packed face ID per
                                       decal slot, -1 = unused
  anchorU/anchorV (locations 14/15, vec3 each) -- each slot's UV anchor point

MAX_DECALS is 3 -- enough for every die needed here (D4's 3 corners are the
upper bound; every other die uses exactly 1, its face center).
"""

import math
import pathlib
import time

from OpenSceneGraph import osg, osgAnimation, osgGA
from OpenSceneGraph.GL import GL_RGBA, GL_UNSIGNED_BYTE
import osgx

DECAL_VALUES_LOCATION = 13
ANCHOR_U_LOCATION = 14
ANCHOR_V_LOCATION = 15
MAX_DECALS = 3
UNUSED_DECAL = -1.0
DECAL_FACE_STRIDE = 32.0

VERTEX_SHADER = f"""
#version 330 core

in vec4 osg_Vertex;
in vec3 osg_Normal;
in vec2 osg_MultiTexCoord0;
layout(location = {DECAL_VALUES_LOCATION}) in vec3 decalValues;
layout(location = {ANCHOR_U_LOCATION}) in vec3 anchorU;
layout(location = {ANCHOR_V_LOCATION}) in vec3 anchorV;

uniform mat4 osg_ModelViewProjectionMatrix;
uniform mat3 osg_NormalMatrix;

out vec3 vNormal;
out vec2 vUV;
flat out vec3 vDecalValues;
flat out vec3 vAnchorU;
flat out vec3 vAnchorV;

void main() {{
	vNormal = normalize(osg_NormalMatrix * osg_Normal);
	vUV = osg_MultiTexCoord0;
	vDecalValues = decalValues;
	vAnchorU = anchorU;
	vAnchorV = anchorV;

	gl_Position = osg_ModelViewProjectionMatrix * osg_Vertex;
}}
"""

# One shared decal loop for every die. Anchor "up" (which way the digit's
# top points) is DERIVED, not stored: with more than one valid decal slot,
# it points from the average of all this face's anchors (== the face
# centroid, since insetting each corner toward it by the same fraction
# preserves the average -- true for any regular/symmetric face) toward this
# particular anchor -- i.e. "toward the corner it belongs to", same
# convention proven in pyosg-d4.py. With exactly one valid slot (every die
# except D4), that degenerates to a zero vector, so a fixed screen-up
# fallback is used instead -- there's no corner to point toward.
FRAGMENT_SHADER = """
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

out vec4 fragColor;

void main() {
	const vec3 L = vec3(0.4, 0.6, 0.7);
	const float DECAL_FACE_STRIDE = 32.0;

	float diffuse = max(dot(normalize(vNormal), normalize(L)), 0.0);
	float light = 0.35 + 0.65 * diffuse;

	vec2 anchorSum = vec2(0.0);
	int count = 0;

	for (int i = 0; i < 3; i++) {
		if (vDecalValues[i] >= 0.0) {
			anchorSum += vec2(vAnchorU[i], vAnchorV[i]);
			count++;
		}
	}

	vec2 avgAnchor = count > 0 ? anchorSum / float(count) : vec2(0.0);
	vec3 color = bodyColor;

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
			vec4 glyph = texture(numberAtlas, atlasUV);

			color = mix(color, glyph.rgb, glyph.a);
		}
	}

	fragColor = vec4(color * light, 1.0);
}
"""

# IBL counterpart to FRAGMENT_SHADER above: same decal-atlas logic, lit via osgx's
# PBR/IBL substrate instead of the fixed N.L term. No highlight uniforms
# (activeFaceMask/activeDecalValue) -- consumers that need those (pyosg-dice.py) fork
# their own copy the same way they already fork FRAGMENT_SHADER; consumers that just
# need picking (pyosg-match4-dice.py) add pickID the same way they already do for
# FRAGMENT_SHADER.
FRAGMENT_SHADER_IBL = """
#version 460 core

const float PI = 3.14159265359;

#pragma osgx::pbr F_MULTISCATTER, MATERIAL_STRUCT, DIRECT_LIGHTING_DECL

in vec3 vNormal;
in vec3 vViewDir;
in vec2 vUV;
flat in vec3 vDecalValues;
flat in vec3 vAnchorU;
flat in vec3 vAnchorV;

uniform mat4 osg_ViewMatrix;
uniform mat4 osg_ViewMatrixInverse;
uniform sampler2D numberAtlas;
uniform int digitCount;
uniform float decalHalf;
uniform vec3 bodyColor;

uniform samplerCube envMap;
uniform sampler2D brdfLUT;
uniform samplerCube diffuseEnv;

// Same cubemap lookup basis osgx.gltf.pbribl.PBRIBLScene.create() reads off
// PBRIBLEnvironment.iblAxis -- rotating that (in Python, on the SAME environment object)
// rotates a --scene backdrop lit through that renderer and these dice identically, since
// both end up sampling through this same remap.
uniform vec3 iblAxis[3];

// Whole-die material knobs -- no per-face roughness/metallic data yet, just a uniform
// scalar pair so the PBR/IBL response is at least visibly tunable from the CLI.
uniform float roughness;
uniform float metallic;

// Independent diffuse-irradiance/specular-reflection intensity, matching the SAME uniform names
// osgx::gltf::pbribl::PBRIBLScene::create()'s backdrop shader reads -- e.g. --ibl-diffuse/
// --ibl-specular dial these down on both the dice AND a --scene backdrop identically, so
// LIGHT_UNIFORMS' punctual lights (a torch) can be made to read more clearly against IBL.
uniform float iblDiffuseIntensity;
uniform float iblSpecularIntensity;

out vec4 fragColor;

// Ported from osgx::gltf::pbribl's own PBRIBL.cpp shader -- Z-up world direction to the
// baked cubemap's Y-up convention, then onto the (possibly rotated) lookup basis.
vec3 osgx_ZUpToGLTF(vec3 d) { return vec3(d.x, d.z, -d.y); }
vec3 osgx_OrientIBL(vec3 d) {
	return vec3(dot(d, iblAxis[0]), dot(d, iblAxis[1]), dot(d, iblAxis[2]));
}

void main() {
	const float DECAL_FACE_STRIDE = 32.0;

	vec2 anchorSum = vec2(0.0);
	int count = 0;

	for (int i = 0; i < 3; i++) {
		if (vDecalValues[i] >= 0.0) {
			anchorSum += vec2(vAnchorU[i], vAnchorV[i]);
			count++;
		}
	}

	vec2 avgAnchor = count > 0 ? anchorSum / float(count) : vec2(0.0);
	vec3 albedo = bodyColor;

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
			vec4 glyph = texture(numberAtlas, atlasUV);

			albedo = mix(albedo, glyph.rgb, glyph.a);
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
	vec3 color = diffuseIrradiance * albedo * (1.0 - Fd) * (1.0 - metallic) * iblDiffuseIntensity
		+ prefiltered * Fd * iblSpecularIntensity;

	// Direct/punctual lights, via the osgx_DirectLighting() CONTRACT (DIRECT_LIGHTING_DECL/
	// DIRECT_LIGHTING_HOOK_DEFAULT in PBR.hpp) -- worldPos comes from vViewDir's own unnormalized
	// eye-space encoding (-eyePos.xyz, see VERTEX_SHADER_IBL), so no extra varying is needed. Same
	// hook backdrop scenes use via osgx::gltf::pbribl::PBRIBLScene::create() -- share the SAME
	// osgx::pbr.LightSet (e.g. set on a common ancestor StateSet) to light dice and a --scene
	// backdrop identically. The per-light dispatch loop itself lives ONCE in
	// DIRECT_LIGHTING_HOOK_DEFAULT (added as a second FRAGMENT shader object -- see where this shader
	// is compiled into a Program), not hand-copied here, so this shader can never drift out of sync
	// with it the way it used to.
	osgx_Material mat = osgx_Material(albedo, 1.0, roughness, metallic, F0);
	vec3 worldPos = (osg_ViewMatrixInverse * vec4(-vViewDir, 1.0)).xyz;
	vec3 direct = osgx_DirectLighting(N, V, worldPos, mat);

	color += direct;

	fragColor = vec4(pow(color, vec3(1.0 / 2.2)), 1.0);
}
"""

# Vertex counterpart to VERTEX_SHADER above, adding the eye-space view direction
# FRAGMENT_SHADER_IBL needs for its N/V world-space rotation.
VERTEX_SHADER_IBL = f"""
#version 460 core

in vec4 osg_Vertex;
in vec3 osg_Normal;
in vec2 osg_MultiTexCoord0;
layout(location = {DECAL_VALUES_LOCATION}) in vec3 decalValues;
layout(location = {ANCHOR_U_LOCATION}) in vec3 anchorU;
layout(location = {ANCHOR_V_LOCATION}) in vec3 anchorV;

uniform mat4 osg_ModelViewProjectionMatrix;
uniform mat4 osg_ModelViewMatrix;
uniform mat3 osg_NormalMatrix;

out vec3 vNormal;
out vec3 vViewDir;
out vec2 vUV;
flat out vec3 vDecalValues;
flat out vec3 vAnchorU;
flat out vec3 vAnchorV;

void main() {{
	vec4 eyePos = osg_ModelViewMatrix * osg_Vertex;

	vNormal = normalize(osg_NormalMatrix * osg_Normal);
	vViewDir = -eyePos.xyz;
	vUV = osg_MultiTexCoord0;
	vDecalValues = decalValues;
	vAnchorU = anchorU;
	vAnchorV = anchorV;

	gl_Position = osg_ModelViewProjectionMatrix * osg_Vertex;
}}
"""

# --hdr/--env resolution shared by every consumer that binds FRAGMENT_SHADER_IBL --
# pyosg-dice.py's dice, pyosg-match4-dice.py's dice AND (already, separately) its
# --scene backdrop. Same contract/candidate paths as pyosg-khronos-viewer.py's own
# resolve_asset()/resolve_environment_manifest(), just generalized off of a single model
# file's directory since this module has no one asset directory of its own.
def resolve_hdr(value):
	path = pathlib.Path(value).expanduser()

	if path.is_file():
		return path

	resolved = osgx.findDataFile(value, ("glTF-Sample-Environments/{}",), "hdr")

	if resolved:
		return pathlib.Path(resolved)

	raise FileNotFoundError(f"Cannot find HDR environment {value!r}")

def resolve_environment_manifest(value):
	path = pathlib.Path(value).expanduser()

	if path.is_file():
		return path

	resolved = osgx.findDataFile(value, ("env/{}.gltf",))

	if resolved:
		return pathlib.Path(resolved)

	raise FileNotFoundError(f"Cannot find environment manifest {value!r}")

def rotate_ibl_environment(environment, degrees):
	"""Rotate `environment`'s cubemap lookup basis (iblAxis, always exactly 3 Vec3 --
	one orthonormal basis) about the world's vertical (Z) axis, in place, by an exact
	multiple of 90 degrees -- a pure axis permutation, no interpolation. `degrees` must
	be one of 0/90/180/270 (mod 360).

	This is THE rotation knob for a baked HDRI: there's no authored "this way is north"
	in an equirect environment map, so however it landed at bake time is arbitrary.
	Rotating the lookup basis (rather than resampling the cubemap itself) is exact and
	free -- both PBRIBLScene.create()'s glTF material shader and FRAGMENT_SHADER_IBL read
	iblAxis the same way, so applying this once to a shared `environment` before handing
	it to either rotates dice and backdrop identically.

	iblAxis round-trips through Python as a plain list copy (pybind11/stl.h), not a live
	view -- reassign the whole list, per-element mutation is silently a no-op.
	"""

	if degrees % 90 != 0:
		raise ValueError(f"rotate_ibl_environment: {degrees} is not a multiple of 90")

	steps = (degrees // 90) % 4

	def rotated(axis):
		x, y, z = axis.x, axis.y, axis.z

		for _ in range(steps):
			x, z = -z, x

		return osg.Vec3(x, y, z)

	environment.iblAxis = [rotated(axis) for axis in environment.iblAxis]

def prepare_environment(hdr=None, env=None, rotate=0):
	"""Resolve --hdr/--env (mutually exclusive; both optional) into a PBRIBLEnvironment,
	optionally pre-rotated -- see rotate_ibl_environment(). Returns None if neither
	hdr nor env is given."""

	if hdr:
		hdr_path = resolve_hdr(hdr)
		environment = osgx.gltf.pbribl.PBRIBLEnvironment.prepare(str(hdr_path), lutSize=1024)

	elif env:
		env_path = resolve_environment_manifest(env)
		environment = osgx.gltf.pbribl.PBRIBLEnvironment.load(str(env_path))

	else:
		return None

	if rotate:
		rotate_ibl_environment(environment, rotate)

	return environment

FLOOR_FRAGMENT_SHADER = """
#version 330 core

in vec3 vNormal;

out vec4 fragColor;

void main() {
	const vec3 L = vec3(0.4, 0.6, 0.7);
	const vec3 floorColor = vec3(0.58, 0.56, 0.50);

	float diffuse = max(dot(normalize(vNormal), normalize(L)), 0.0);
	float light = 0.35 + 0.65 * diffuse;

	fragColor = vec4(floorColor * light, 1.0);
}
"""

# Standard 5x7 pixel font -- see pyosg-d4.py's module docstring for why
# procedural (no PIL/baked font asset).
FONT_5X7 = {
	"1": ("..#..", ".##..", "..#..", "..#..", "..#..", "..#..", ".###."),
	"2": (".###.", "#...#", "....#", "...#.", "..#..", ".#...", "#####"),
	"3": ("####.", "....#", "...#.", "..##.", "....#", "....#", "####."),
	"4": ("...#.", "..##.", ".#.#.", "#..#.", "#####", "...#.", "...#."),
	"5": ("#####", "#....", "####.", "....#", "....#", "#...#", ".###."),
	"6": ("..##.", ".#...", "#....", "####.", "#...#", "#...#", ".###."),
	"7": ("#####", "....#", "...#.", "..#..", ".#...", ".#...", ".#..."),
	"8": (".###.", "#...#", "#...#", ".###.", "#...#", "#...#", ".###."),
	"9": (".###.", "#...#", "#...#", ".####", "....#", "...#.", ".##.."),
	"0": (".###.", "#...#", "#..##", "#.#.#", "##..#", "#...#", ".###."),
}
ATLAS_CELL = 64
FONT_PIXEL = 7
# Smaller per-character scale used only for 2-character cells (D12's 10/11/
# 12) so both glyphs plus a gap fit inside the same fixed ATLAS_CELL width
# as every 1-character cell -- see build_number_atlas()'s docstring.
FONT_PIXEL_MULTI = 5
INK = (0.08, 0.07, 0.07)

class FaceInfo:
	"""Stable mesh/decal basis for one numbered die face."""

	def __init__(self, index, face, positions, value=None):
		self.index = index
		self.vertices = tuple(face.vertices)
		self.normal = face.normal(positions)
		self.text_up = face.up(positions)
		self.value = value

class RollSpec:
	"""The rotation-independent data needed to roll one die shape.

	Outcomes contain (label, support_face_index, support_normal, value, active_faces)
	entries. The support face is explicit so a final roll pose is exactly flush
	with the floor even when a die's faces are not all equally distant from its
	center. active_faces lets a consumer present the chosen result without
	putting presentation policy in this module.
	"""

	def __init__(self, polyhedron, outcomes, values=()):
		self.outcomes = tuple(outcomes)
		self.polyhedron = polyhedron
		self.face_infos = tuple(
			FaceInfo(index, face, polyhedron.vertices, values[index] if values else None)
			for index, face in enumerate(polyhedron.faces)
		)

def face_roll_spec(polyhedron, values, opposite_face_indices):
	"""Builds one outcome per value-bearing face, with its opposite as support."""
	if not (len(polyhedron.faces) == len(values) == len(opposite_face_indices)):
		raise ValueError("faces, values, and opposite_face_indices must have equal lengths")

	outcomes = []

	for face_index, value in enumerate(values):
		support_face_index = opposite_face_indices[face_index]
		face_normal_ = polyhedron.faces[face_index].normal(polyhedron.vertices)
		support_normal = polyhedron.faces[support_face_index].normal(polyhedron.vertices)

		if (face_normal_ + support_normal).length() > 1e-5:
			raise ValueError(f"face {face_index}'s support face is not opposite")

		outcomes.append((f"face {face_index}", support_face_index, support_normal, value, (face_index,)))

	return RollSpec(polyhedron, outcomes, values)

def vertex_roll_spec(polyhedron, values, support_faces):
	"""Builds D4-style vertex outcomes with their opposite faces as support."""
	if not (len(polyhedron.vertices) == len(values) == len(support_faces)):
		raise ValueError("vertices, values, and support_faces must have equal lengths")

	face_indices = {tuple(face.vertices): index for index, face in enumerate(polyhedron.faces)}
	outcomes = []

	for vertex_index, (value, support_face) in enumerate(zip(values, support_faces)):
		top_axis = osg.Vec3(polyhedron.vertices[vertex_index])
		support_face_index = face_indices[tuple(support_face)]
		support_normal = polyhedron.faces[support_face_index].normal(polyhedron.vertices)

		top_axis.normalize()

		if (top_axis + support_normal).length() > 1e-5:
			raise ValueError(f"vertex {vertex_index}'s support face is not opposite")

		outcomes.append((
			f"vertex {vertex_index}",
			support_face_index,
			support_normal,
			value,
			tuple(face_index for face_index, face in enumerate(polyhedron.faces) if vertex_index in face.vertices),
		))

	return RollSpec(polyhedron, outcomes)

def support_down_quat(support_normal):
	"""Rotation that brings a support face's outward normal to world -Z."""
	quat = osg.Quat()

	quat.makeRotate(support_normal, osg.Vec3(0.0, 0.0, -1.0))

	return quat

def random_quat(rng):
	"""A visually random tumble-start orientation."""
	axis = osg.Vec3(rng.uniform(-1.0, 1.0), rng.uniform(-1.0, 1.0), rng.uniform(-1.0, 1.0))

	if axis.length() < 1e-6:
		axis = osg.Vec3(1.0, 0.0, 0.0)

	else:
		axis.normalize()

	return osg.Quat(rng.uniform(0.0, 2.0 * math.pi), axis)

def rest_position(rest_xy, polyhedron, quat):
	"""The floor-resting center position after applying quat to vertices."""
	return osg.Vec3(rest_xy.x, rest_xy.y, polyhedron.restingOffset(quat))

def support_rest_position(rest_xy, polyhedron, quat, support_face_index):
	"""Places the rotated support face's plane exactly at z=0."""
	return osg.Vec3(rest_xy.x, rest_xy.y, polyhedron.faceRestingOffset(support_face_index, quat))

class DiceRollCallback:
	"""Animates one RollSpec using bounce height and elastic tumble easing."""

	def __init__(
		self,
		mt,
		roll_spec,
		start_quat,
		target_quat,
		support_face_index,
		rest_xy,
		rolling,
		r_held,
		index,
		result_callback=None,
		result=None,
		duration=1.1,
		drop_height=3.0
	):
		self.mt = mt
		self.roll_spec = roll_spec
		self.start_quat = start_quat
		self.target_quat = target_quat
		self.support_face_index = support_face_index
		self.rest_xy = rest_xy
		self.rolling = rolling
		self.r_held = r_held
		self.index = index
		self.result_callback = result_callback
		self.result = result
		self.duration = duration
		self.drop_height = drop_height
		self.t0 = time.time()
		self.done = False
		self.was_held = False
		self.last_spin_quat = start_quat

	def set_matrix(self, quat, height, support_face_index=None):
		if support_face_index is None:
			pos = rest_position(self.rest_xy, self.roll_spec.polyhedron, quat)

		else:
			pos = support_rest_position(
				self.rest_xy,
				self.roll_spec.polyhedron,
				quat,
				support_face_index
			)

		pos.z += height
		self.mt.matrix = osg.Matrix.rotate(quat) * osg.Matrix.translate(pos)

	def __call__(self, node, nv):
		if not self.done:
			if self.r_held[0]:
				spin = osg.Quat(
					4.0 * math.pi * (time.time() - self.t0),
					osg.Vec3(0.0, 0.0, 1.0)
				)
				self.last_spin_quat = self.start_quat * spin
				self.was_held = True
				self.set_matrix(self.last_spin_quat, self.drop_height)

				return True

			if self.was_held:
				self.start_quat = self.last_spin_quat
				self.t0 = time.time()
				self.was_held = False

			t = (time.time() - self.t0) / self.duration

			if t >= 1.0:
				t = 1.0
				self.done = True
				self.rolling[self.index] = False

			if self.done:
				self.set_matrix(self.target_quat, 0.0, self.support_face_index)

				if self.result_callback is not None:
					self.result_callback(*self.result)

			else:
				quat = osg.Quat()

				quat.slerp(osgAnimation.outElastic(t), self.start_quat, self.target_quat)
				self.set_matrix(quat, self.drop_height * (1.0 - osgAnimation.outBounce(t)))

		return True

def roll_die(
	mt,
	rest_xy,
	roll_spec,
	rng,
	rolling,
	r_held,
	index,
	notice_prefix="pyosg-dice",
	result_callback=None,
	roll_started_callback=None
):
	"""Choose an outcome before starting its purely visual roll animation."""
	label, support_face_index, support_normal, value, active_faces = rng.choice(roll_spec.outcomes)
	spin = osg.Quat(rng.uniform(0.0, 2.0 * math.pi), osg.Vec3(0.0, 0.0, 1.0))
	target_quat = support_down_quat(support_normal) * spin
	start_quat = random_quat(rng)

	osg.notice(f"[{notice_prefix}] rolling die {index} -- landing on {value} ({label} up)")

	if roll_started_callback is not None:
		roll_started_callback(index)

	rolling[index] = True
	mt.updateCallback = DiceRollCallback(
		mt,
		roll_spec,
		start_quat,
		target_quat,
		support_face_index,
		rest_xy,
		rolling,
		r_held,
		index,
		result_callback,
		(index, value, active_faces),
	)

def roll_all(
	dice,
	rng,
	rolling,
	r_held,
	notice_prefix="pyosg-dice",
	result_callback=None,
	roll_started_callback=None
):
	"""Starts a simultaneous roll for (MatrixTransform, rest_xy, RollSpec) dice."""
	for index, (mt, rest_xy, roll_spec) in enumerate(dice):
		roll_die(
			mt,
			rest_xy,
			roll_spec,
			rng,
			rolling,
			r_held,
			index,
			notice_prefix,
			result_callback,
			roll_started_callback,
		)

class DiceRollKeyHandler(osgGA.GUIEventHandler):
	"""Rolls all dice on R; holding R spins them at their apex."""

	def __init__(
		self,
		dice,
		rng,
		rolling,
		r_held,
		notice_prefix="pyosg-dice",
		result_callback=None,
		roll_started_callback=None
	):
		super().__init__()
		self.dice = dice
		self.rng = rng
		self.rolling = rolling
		self.r_held = r_held
		self.notice_prefix = notice_prefix
		self.result_callback = result_callback
		self.roll_started_callback = roll_started_callback

	def handle(self, ea, aa):
		if ea.handled or ea.key != ord("r"):
			return False

		if ea.type == osgGA.GUIEventAdapter.KEYUP:
			self.r_held[0] = False

			return True

		if ea.type != osgGA.GUIEventAdapter.KEYDOWN:
			return False

		if self.r_held[0] or any(self.rolling):
			return True

		self.r_held[0] = True
		roll_all(
			self.dice,
			self.rng,
			self.rolling,
			self.r_held,
			self.notice_prefix,
			self.result_callback,
			self.roll_started_callback,
		)

		return True

def face_centroid_uv(face_uv):
	cx = sum(p.x for p in face_uv) / len(face_uv)
	cy = sum(p.y for p in face_uv) / len(face_uv)

	return osg.Vec2(cx, cy)

def center_decal_scheme(values):
	"""One decal per face, at that face's own UV centroid -- every die
	except D4. `values` is either a single 0-based digit (same value on
	every face -- not useful for a real die, mainly for quick prototyping)
	or a sequence of one 0-based digit per face, aligned with `faces`."""
	def decals_for_face(face_index, face, face_uv):
		value = values[face_index] if hasattr(values, "__getitem__") else values

		return [(face_centroid_uv(face_uv), float(value))]

	return decals_for_face

def corner_decal_scheme(vertex_values, inset=0.34):
	"""One decal per face-corner, at each vertex's own value -- D4 only.
	`vertex_values` maps a base-vertex index (into whatever `base_vertices`
	the caller built the face list from) to a number-atlas column."""
	def decals_for_face(face_index, face, face_uv):
		centroid = face_centroid_uv(face_uv)
		decals = []

		for slot, vi in enumerate(face):
			corner = face_uv[slot]
			anchor = osg.Vec2(
				corner.x + (centroid.x - corner.x) * inset,
				corner.y + (centroid.y - corner.y) * inset,
			)

			decals.append((anchor, float(vertex_values[vi])))

		return decals

	return decals_for_face

def build_number_atlas(values):
	"""A `len(values) * ATLAS_CELL` x `ATLAS_CELL` RGBA image, one VALUE
	per column -- filled via the plain buffer protocol (memoryview +
	cast-to-1D + per-row slice assignment), not PIL/numpy. `values` is a
	sequence of 1-or-2-character strings, each key(s) into FONT_5X7, e.g.
	("1", ..., "9", "0", "10", "11", "12"). A 2-character value renders
	both glyphs side by side (at FONT_PIXEL_MULTI's smaller scale, so they
	still fit the same fixed cell width as a 1-character value), centered
	as one block within the cell -- same placement math either way, just a
	different character count and per-character pixel scale."""
	atlas_w, atlas_h = ATLAS_CELL * len(values), ATLAS_CELL
	img = osg.Image()

	img.allocateImage(atlas_w, atlas_h, 1, GL_RGBA, GL_UNSIGNED_BYTE)

	view = memoryview(img)
	flat = view.cast("B")
	row_stride = view.strides[0]
	channels = view.shape[2]
	ink_bytes = bytes(int(round(c * 255)) for c in INK) + bytes([255])

	# Per-cell layout: pixel scale, one glyph's width, the gap between
	# glyphs, and the margins needed to center the whole (1 or 2 char)
	# block within ATLAS_CELL -- computed once per cell, reused per row.
	layouts = []

	for value in values:
		pixel = FONT_PIXEL if len(value) == 1 else FONT_PIXEL_MULTI
		char_w = 5 * pixel
		gap = pixel
		block_w = len(value) * char_w + (len(value) - 1) * gap
		block_h = 7 * pixel

		layouts.append((pixel, char_w, gap, (ATLAS_CELL - block_w) // 2, (ATLAS_CELL - block_h) // 2, block_w, block_h))

	for y in range(atlas_h):
		row_bytes = bytearray(atlas_w * channels)

		for cell_index, value in enumerate(values):
			pixel, char_w, gap, margin_x, margin_y, block_w, block_h = layouts[cell_index]
			row_in_block = y - margin_y
			font_row = row_in_block // pixel if 0 <= row_in_block < block_h else None

			if font_row is None:
				continue

			for x_in_cell in range(ATLAS_CELL):
				col_in_block = x_in_cell - margin_x

				if not (0 <= col_in_block < block_w):
					continue

				char_slot, col_in_char = divmod(col_in_block, char_w + gap)

				if char_slot >= len(value) or col_in_char >= char_w:
					continue

				font_col = col_in_char // pixel

				if FONT_5X7[value[char_slot]][font_row][font_col] == "#":
					offset = (cell_index * ATLAS_CELL + x_in_cell) * channels

					row_bytes[offset:offset + channels] = ink_bytes

		dest_row = atlas_h - 1 - y
		start = dest_row * row_stride

		flat[start:start + len(row_bytes)] = row_bytes

	return img

def build_polyhedron_geometry(polyhedron, decals_for_face):
	"""Add dice-decal streams to an ``osgx.Polyhedron``.

	``osgx`` owns the reusable mesh work: face-unique flat-shaded expansion,
	UVs, fan triangulation, and the conventional/core-profile vertex streams.
	This dice layer only supplies its three per-face decal attributes.
	"""
	decal_values, anchor_u, anchor_v = [], [], []

	for face_index, face in enumerate(polyhedron.faces):
		decals = decals_for_face(face_index, face.vertices, face.uv)

		if not (1 <= len(decals) <= MAX_DECALS):
			raise ValueError(f"expected 1-{MAX_DECALS} decals per face, got {len(decals)}")

		dvals = [UNUSED_DECAL] * MAX_DECALS
		au = [0.0] * MAX_DECALS
		av = [0.0] * MAX_DECALS

		for i, (anchor, value) in enumerate(decals):
			dvals[i] = value + face_index * DECAL_FACE_STRIDE
			au[i] = anchor.x
			av[i] = anchor.y

		decal_values.append(osg.Vec3(*dvals))
		anchor_u.append(osg.Vec3(*au))
		anchor_v.append(osg.Vec3(*av))

	polyhedron.setFaceAttribute(DECAL_VALUES_LOCATION, osg.Vec3Array(decal_values))
	polyhedron.setFaceAttribute(ANCHOR_U_LOCATION, osg.Vec3Array(anchor_u))
	polyhedron.setFaceAttribute(ANCHOR_V_LOCATION, osg.Vec3Array(anchor_v))

	return polyhedron

ATLAS_DIGITS = (
	"1", "2", "3", "4", "5", "6", "7", "8", "9", "0",
	"10", "11", "12", "13", "14", "15", "16", "17", "18", "19", "20",
)
DIE_SIZE = 1.1

def atlas_column(value):
	return ATLAS_DIGITS.index(str(value))

def face_orientation(face_info, view_direction, view_up):
	"""Return an orientation with `face_info` facing the viewer, text upright.

	`view_direction` points from the die toward the viewer; `view_up` is the
	viewer/screen-up direction. Both can come directly from a camera callback.
	"""
	target_normal = osg.Vec3(view_direction)

	target_normal.normalize()
	target_up = osg.Vec3(view_up) - target_normal * osg.Vec3(view_up).dot(target_normal)

	if target_up.length() < 1e-6:
		raise ValueError("view_up is parallel to view_direction")

	target_up.normalize()
	face_align = osg.Quat()

	face_align.makeRotate(face_info.normal, target_normal)
	text_spin = osg.Quat()

	text_spin.makeRotate(face_align * face_info.text_up, target_up)

	return face_align * text_spin

class DieInstance:
	"""A scene-graph die plus the stable data needed to present a chosen face."""

	def __init__(self, spec, transform, geode, roll_spec):
		self.spec = spec
		self.transform = transform
		self.geode = geode
		self.roll_spec = roll_spec

	def orient_face(self, face_index, position, view_direction, view_up):
		orientation = face_orientation(self.roll_spec.face_infos[face_index], view_direction, view_up)

		self.transform.matrix = osg.Matrix.rotate(orientation) * osg.Matrix.translate(position)

		return orientation

class DieSpec:
	"""Topology, numbering, and presentation defaults for one die family."""

	def __init__(
		self,
		name,
		shape_factory,
		values,
		opposites,
		decal_half,
		body_color,
		corner_values=None,
		display_face_values=None
	):
		self.name = name
		self.shape_factory = shape_factory
		self.values = tuple(values)
		self.opposites = tuple(opposites)
		self.decal_half = decal_half
		self.body_color = body_color
		self.corner_values = corner_values
		self.display_face_values = display_face_values

	def build_geometry(self, display_mode="normal"):
		geom = self.shape_factory()
		if display_mode == "face":
			if self.display_face_values is None:
				raise ValueError(f"{self.name} has no face-display mode")

			values = tuple(self.display_face_values)
			geom = build_polyhedron_geometry(
				geom,
				center_decal_scheme(tuple(atlas_column(value) for value in values)),
			)

			return geom, RollSpec(geom, (), values)

		if display_mode != "normal":
			raise ValueError(f"unknown display mode {display_mode!r}")

		if self.corner_values is not None:
			geom = build_polyhedron_geometry(
				geom,
				corner_decal_scheme({index: atlas_column(value) for index, value in self.corner_values.items()}),
			)

			return geom, vertex_roll_spec(geom, self.values, self.opposites)

		geom = build_polyhedron_geometry(
			geom,
			center_decal_scheme(tuple(atlas_column(value) for value in self.values)),
		)

		return geom, face_roll_spec(geom, self.values, self.opposites)

	def make_instance(self, position=None, orientation=None, name=None, display_mode="normal"):
		geom, roll_spec = self.build_geometry(display_mode)
		position = osg.Vec3() if position is None else osg.Vec3(position)
		orientation = osg.Quat() if orientation is None else orientation
		transform = osg.MatrixTransform(osg.Matrix.rotate(orientation) * osg.Matrix.translate(position))
		geode = osg.Geode(name=self.name if name is None else name)

		geode.drawables.append(geom)
		transform.children.append(geode)

		return DieInstance(self, transform, geode, roll_spec)

def _d4_spec():
	return DieSpec(
		"d4",
		lambda: osgx.Tetrahedron(radius=DIE_SIZE),
		(1, 2, 3, 4),
		((1, 2, 3), (0, 3, 2), (0, 1, 3), (0, 2, 1)),
		0.13,
		(0.12, 0.78, 0.34),
		corner_values={0: 1, 1: 2, 2: 3, 3: 4},
		display_face_values=(1, 2, 3, 4),
	)

def _d6_spec():
	return DieSpec(
		"d6",
		lambda: osgx.Cube(radius=DIE_SIZE),
		(4, 3, 5, 2, 6, 1), (1, 0, 3, 2, 5, 4), 0.38, (0.52, 0.55, 0.61),
	)

def _d8_spec():
	return DieSpec(
		"d8",
		lambda: osgx.Octahedron(radius=DIE_SIZE),
		(1, 2, 3, 4, 5, 6, 7, 8), (7, 6, 5, 4, 3, 2, 1, 0), 0.24, (0.04, 0.72, 0.90),
	)

def _d10_spec():
	return DieSpec(
		"d10", lambda: osgx.PentagonalTrapezohedron(radius=DIE_SIZE),
		(7, 0, 6, 1, 5, 2, 9, 3, 8, 4), (5, 6, 7, 8, 9, 0, 1, 2, 3, 4),
		0.18, (0.88, 0.16, 0.72),
	)

def _d20_spec():
	return DieSpec(
		"d20",
		lambda: osgx.Icosahedron(radius=DIE_SIZE),
		(1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 17, 18, 19, 20, 16, 12, 11, 15, 14, 13), (13, 12, 11, 10, 14, 17, 18, 19, 15, 16, 3, 2, 1, 0, 4, 8, 9, 5, 6, 7), 0.22, (0.90, 0.10, 0.10),
	)

def _d12_spec():
	return DieSpec(
		"d12", lambda: osgx.Dodecahedron(radius=DIE_SIZE),
		(1, 2, 3, 4, 5, 6, 9, 12, 8, 7, 10, 11),
		(7, 11, 10, 6, 8, 9, 3, 0, 4, 5, 2, 1), 0.20, (0.96, 0.78, 0.08),
	)

DIE_SPECS = {
	"d4": _d4_spec(),
	"d6": _d6_spec(),
	"d8": _d8_spec(),
	"d10": _d10_spec(),
	"d12": _d12_spec(),
	"d20": _d20_spec(),
}

def make_die(name, position=None, orientation=None, node_name=None, display_mode="normal"):
	return DIE_SPECS[name].make_instance(position, orientation, node_name, display_mode)
