#!/usr/bin/env python3

"""Shared polyhedral-dice mesh factory + atlas/decal shader, factored out of
`pyosg-d4.py`/`pyosg-d6-numbers.py` once both were proven working
separately -- see ai/context-todo-dice.md. Not a standalone example (no
`__main__`); imported by the per-die scripts, same relationship
`pyosg_repl.py` has to the examples that `from pyosg_repl import repl`.

Point of this module: D4/D6/D8/D10/D12/D20 all reduce to the SAME mesh
construction (flat-shaded, per-face-unique vertices, fan-triangulated) and
the SAME decal mechanism (a small number of atlas-sampled digit decals per
face, placed via a per-fragment "which anchor is this pixel nearest, what's
my local position within its box" test) -- see `pyosg-d4.py`'s module
docstring for the derivation. The only real difference between die types is
DATA: which base vertices/faces define the shape, what each face's canonical
(fixed, shared-across-all-its-faces) UV layout looks like, and whether a
face shows one CENTERED digit (every die except D4) or up to three CORNER
digits, one per vertex (D4 only, because a d4's rolled value is read from
the top vertex, not the top face).

Vertex attribute layout, identical for every die built through this module:
  osg_Vertex (location 0)          -- position, via .vertexArray
  osg_Normal (location 1)          -- flat per-face normal, via .normalArray
  osg_MultiTexCoord0 (location 3)  -- canonical per-face UV, via .vertexAttrib[3]
                                       (texcoord unit 0's generic-attrib alias,
                                       confirmed against OSG source -- see
                                       pyosg-dice.py's own docstring)
  decalValues (location 13, vec3)  -- 0-based digit per decal slot, -1 = unused
  anchorU/anchorV (locations 14/15, vec3 each) -- each slot's UV anchor point

MAX_DECALS is 3 -- enough for every die needed here (D4's 3 corners are the
upper bound; every other die uses exactly 1, its face center).
"""

import math
import time

from OpenSceneGraph import osg, osgAnimation, osgGA
from OpenSceneGraph.GL import GL_RGBA, GL_UNSIGNED_BYTE

DECAL_VALUES_LOCATION = 13
ANCHOR_U_LOCATION = 14
ANCHOR_V_LOCATION = 15
MAX_DECALS = 3
UNUSED_DECAL = -1.0

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

		vec2 anchor = vec2(vAnchorU[i], vAnchorV[i]);
		vec2 up = count > 1 ? normalize(anchor - avgAnchor) : vec2(0.0, 1.0);
		vec2 right = vec2(up.y, -up.x);

		vec2 local = vUV - anchor;
		float lu = dot(local, right) / decalHalf;
		float lv = dot(local, up) / decalHalf;

		if (abs(lu) <= 1.0 && abs(lv) <= 1.0) {
			vec2 atlasUV = vec2(
				(vDecalValues[i] + (lu * 0.5 + 0.5)) / float(digitCount),
				lv * 0.5 + 0.5
			);
			vec4 glyph = texture(numberAtlas, atlasUV);

			color = mix(color, glyph.rgb, glyph.a);
		}
	}

	fragColor = vec4(color * light, 1.0);
}
"""

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

# Canonical, fixed UV shape per face vertex-count -- identical for every
# face of a given die, since a Platonic solid's faces are all congruent.
# Both exact isometries of the real 3D face (equilateral triangle, unit
# square) -- for anything less "nice" (D10's kite, D12's pentagon later),
# use isometric_face_uv() below instead of guessing proportions by eye; see
# its docstring for why a guessed shape visibly stretches whatever gets
# decaled onto it.
TRIANGLE_UV = (osg.Vec2(0.0, 0.0), osg.Vec2(1.0, 0.0), osg.Vec2(0.5, 3.0 ** 0.5 / 2.0))
SQUARE_UV = (osg.Vec2(0.0, 0.0), osg.Vec2(1.0, 0.0), osg.Vec2(1.0, 1.0), osg.Vec2(0.0, 1.0))

def canonical_uv(face):
	if len(face) == 3:
		return TRIANGLE_UV

	if len(face) == 4:
		return SQUARE_UV

	raise ValueError(f"no canonical UV defined yet for a {len(face)}-vertex face")

def isometric_face_uv(vertices):
	"""Flattens a planar polygon's REAL 3D vertices into 2D UV coordinates
	that exactly preserve every true distance between them (a rigid
	projection onto the face's own plane -- confirmed by cross-checking
	every pairwise distance, not just consecutive edges, not just an
	approximation). Use this instead of a hand-picked canonical UV table
	whenever a face's true proportions aren't a "nice" regular polygon
	(first needed for D10's kite, since a hand-guessed KITE_UV visibly
	stretched its digit decals -- a "square" region in a non-isometric UV
	space does not correspond to a square region on the real 3D face)."""
	v0 = vertices[0]
	right = (vertices[1] - v0)

	right.normalize()

	normal = right.cross(vertices[2] - v0)

	normal.normalize()

	up = normal.cross(right)

	return tuple(osg.Vec2((v - v0).dot(right), (v - v0).dot(up)) for v in vertices)

def normalize_vertices(vertices, target_radius=1.0):
	"""Recenter `vertices` (any sequence of osg.Vec3) on their own centroid,
	then scale uniformly so the farthest vertex sits exactly `target_radius`
	away -- i.e. every die built through this factory agrees on its
	CIRCUMRADIUS, regardless of its own raw edge-length math. Lets every
	caller share ONE size constant (DIE_SIZE = target_radius) instead of
	hand-tuned, not-necessarily-comparable per-die-type constants -- see
	ai/context-todo-dice.md."""
	count = len(vertices)
	centroid = osg.Vec3(
		sum(v.x for v in vertices) / count,
		sum(v.y for v in vertices) / count,
		sum(v.z for v in vertices) / count,
	)
	centered = [v - centroid for v in vertices]
	radius = max(v.length() for v in centered)
	scale = target_radius / radius

	return [v * scale for v in centered]

def resting_offset(vertices):
	"""Z shift needed to put `vertices`' LOWEST point at z=0. Deliberately a
	separate step from normalize_vertices(): the centroid is the right
	origin for consistent SIZE and for rotating a die naturally (e.g. a
	roll animation), but the centroid-to-resting-face distance differs per
	shape (a cube's centroid sits exactly between opposite faces; a
	tetrahedron's sits only 1/4 of the way from base to apex) -- so two
	dice normalized to the same circumradius and placed at the same z=0 via
	a plain translate do NOT actually rest on the same floor level. Apply
	this to whichever face/vertex is currently "down" (post any rotation)
	at placement time to make every die actually sit flush, regardless of
	shape -- see ai/context-todo-dice.md."""
	return -min(v.z for v in vertices)

def face_normal(vertices, face):
	"""Returns the normalized outward normal of an already outward-wound face."""
	v0, v1, v2 = (vertices[i] for i in face[:3])
	normal = (v1 - v0).cross(v2 - v0)

	normal.normalize()

	return normal

class RollSpec:
	"""The rotation-independent data needed to roll one die shape.

	Outcomes contain (label, support_face, support_normal, value) entries. The
	support face is explicit so a final roll pose is exactly flush with the
	floor even when a die's faces are not all equally distant from its center.
	"""

	def __init__(self, vertices, outcomes):
		self.vertices = tuple(vertices)
		self.outcomes = tuple(outcomes)

def face_roll_spec(vertices, faces, values, opposite_face_indices):
	"""Builds one outcome per value-bearing face, with its opposite as support."""
	if not (len(faces) == len(values) == len(opposite_face_indices)):
		raise ValueError("faces, values, and opposite_face_indices must have equal lengths")

	outcomes = []

	for face_index, value in enumerate(values):
		face = faces[face_index]
		support_face = faces[opposite_face_indices[face_index]]
		face_normal_ = face_normal(vertices, face)
		support_normal = face_normal(vertices, support_face)

		if (face_normal_ + support_normal).length() > 1e-5:
			raise ValueError(f"face {face_index}'s support face is not opposite")

		outcomes.append((f"face {face_index}", support_face, support_normal, value))

	return RollSpec(vertices, outcomes)

def vertex_roll_spec(vertices, values, support_faces):
	"""Builds D4-style vertex outcomes with their opposite faces as support."""
	if not (len(vertices) == len(values) == len(support_faces)):
		raise ValueError("vertices, values, and support_faces must have equal lengths")

	outcomes = []

	for vertex_index, (value, support_face) in enumerate(zip(values, support_faces)):
		top_axis = osg.Vec3(vertices[vertex_index])
		support_normal = face_normal(vertices, support_face)

		top_axis.normalize()

		if (top_axis + support_normal).length() > 1e-5:
			raise ValueError(f"vertex {vertex_index}'s support face is not opposite")

		outcomes.append((
			f"vertex {vertex_index}",
			support_face,
			support_normal,
			value,
		))

	return RollSpec(vertices, outcomes)

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

def rest_position(rest_xy, vertices, quat):
	"""The floor-resting center position after applying quat to vertices."""
	rotated_vertices = tuple(quat * vertex for vertex in vertices)

	return osg.Vec3(rest_xy.x, rest_xy.y, resting_offset(rotated_vertices))

def support_rest_position(rest_xy, vertices, quat, support_face):
	"""Places the rotated support face's plane exactly at z=0."""
	support_z = sum((quat * vertices[i]).z for i in support_face) / len(support_face)

	return osg.Vec3(rest_xy.x, rest_xy.y, -support_z)

class DiceRollCallback:
	"""Animates one RollSpec using bounce height and elastic tumble easing."""

	def __init__(
		self,
		mt,
		roll_spec,
		start_quat,
		target_quat,
		support_face,
		rest_xy,
		rolling,
		r_held,
		index,
		duration=1.1,
		drop_height=3.0
	):
		self.mt = mt
		self.roll_spec = roll_spec
		self.start_quat = start_quat
		self.target_quat = target_quat
		self.support_face = support_face
		self.rest_xy = rest_xy
		self.rolling = rolling
		self.r_held = r_held
		self.index = index
		self.duration = duration
		self.drop_height = drop_height
		self.t0 = time.time()
		self.done = False
		self.was_held = False
		self.last_spin_quat = start_quat

	def set_matrix(self, quat, height, support_face=None):
		if support_face is None:
			pos = rest_position(self.rest_xy, self.roll_spec.vertices, quat)

		else:
			pos = support_rest_position(self.rest_xy, self.roll_spec.vertices, quat, support_face)

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
				self.set_matrix(self.target_quat, 0.0, self.support_face)

			else:
				quat = osg.Quat()

				quat.slerp(osgAnimation.outElastic(t), self.start_quat, self.target_quat)
				self.set_matrix(quat, self.drop_height * (1.0 - osgAnimation.outBounce(t)))

		return True

def roll_die(mt, rest_xy, roll_spec, rng, rolling, r_held, index, notice_prefix="pyosg-dice"):
	"""Choose an outcome before starting its purely visual roll animation."""
	label, support_face, support_normal, value = rng.choice(roll_spec.outcomes)
	spin = osg.Quat(rng.uniform(0.0, 2.0 * math.pi), osg.Vec3(0.0, 0.0, 1.0))
	target_quat = support_down_quat(support_normal) * spin
	start_quat = random_quat(rng)

	osg.notice(f"[{notice_prefix}] rolling die {index} -- landing on {value} ({label} up)")

	rolling[index] = True
	mt.updateCallback = DiceRollCallback(
		mt, roll_spec, start_quat, target_quat, support_face, rest_xy, rolling, r_held, index
	)

def roll_all(dice, rng, rolling, r_held, notice_prefix="pyosg-dice"):
	"""Starts a simultaneous roll for (MatrixTransform, rest_xy, RollSpec) dice."""
	for index, (mt, rest_xy, roll_spec) in enumerate(dice):
		roll_die(mt, rest_xy, roll_spec, rng, rolling, r_held, index, notice_prefix)

class DiceRollKeyHandler(osgGA.GUIEventHandler):
	"""Rolls all dice on R; holding R spins them at their apex."""

	def __init__(self, dice, rng, rolling, r_held, notice_prefix="pyosg-dice"):
		super().__init__()
		self.dice = dice
		self.rng = rng
		self.rolling = rolling
		self.r_held = r_held
		self.notice_prefix = notice_prefix

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
		roll_all(self.dice, self.rng, self.rolling, self.r_held, self.notice_prefix)

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

def build_polyhedron_geometry(base_vertices, faces, decals_for_face, uv_shape=None):
	"""The shared factory. `base_vertices` is a sequence of osg.Vec3 (the
	polyhedron's raw corners); `faces` is a sequence of vertex-index tuples
	(any length >= 3), wound so `(v[1]-v[0]).cross(v[2]-v[0])` gives the
	face's OUTWARD normal. `decals_for_face(face, face_uv)` is one of
	center_decal_scheme(...)/corner_decal_scheme(...) above. `uv_shape`
	overrides canonical_uv()'s vertex-count-based dispatch -- needed
	whenever two different die types share a face vertex-count but not a
	face SHAPE (e.g. D6's square vs D10's kite, both 4 vertices).

	Each face gets its own unique vertices (never shared with another face,
	even across a shared edge/corner) so every vertex can carry one flat
	per-face normal -- same reason osg.ShapeDrawable(osg.Box()) builds 24
	vertices rather than 8. Faces with more than 3 vertices are
	fan-triangulated from slot 0.
	"""
	positions, normals, uvs = [], [], []
	decal_values, anchor_u, anchor_v = [], [], []

	for face_index, face in enumerate(faces):
		face_uv = uv_shape if uv_shape is not None else canonical_uv(face)
		v0, v1, v2 = (base_vertices[i] for i in face[:3])
		normal = (v1 - v0).cross(v2 - v0)

		normal.normalize()

		decals = decals_for_face(face_index, face, face_uv)

		if not (1 <= len(decals) <= MAX_DECALS):
			raise ValueError(f"expected 1-{MAX_DECALS} decals per face, got {len(decals)}")

		dvals = [UNUSED_DECAL] * MAX_DECALS
		au = [0.0] * MAX_DECALS
		av = [0.0] * MAX_DECALS

		for i, (anchor, value) in enumerate(decals):
			dvals[i] = value
			au[i] = anchor.x
			av[i] = anchor.y

		decal_vec = osg.Vec3(*dvals)
		anchor_u_vec = osg.Vec3(*au)
		anchor_v_vec = osg.Vec3(*av)

		def emit(slot):
			positions.append(base_vertices[face[slot]])
			normals.append(normal)
			uvs.append(face_uv[slot])
			decal_values.append(decal_vec)
			anchor_u.append(anchor_u_vec)
			anchor_v.append(anchor_v_vec)

		for t in range(1, len(face) - 1):
			emit(0)
			emit(t)
			emit(t + 1)

	def per_vertex(array):
		array.binding = osg.Array.Binding.BIND_PER_VERTEX

		return array

	geom = osg.Geometry()
	geom.vertexArray = per_vertex(osg.Vec3Array(positions))
	geom.normalArray = per_vertex(osg.Vec3Array(normals))
	geom.vertexAttrib[3] = per_vertex(osg.Vec2Array(uvs))
	geom.vertexAttrib[DECAL_VALUES_LOCATION] = per_vertex(osg.Vec3Array(decal_values))
	geom.vertexAttrib[ANCHOR_U_LOCATION] = per_vertex(osg.Vec3Array(anchor_u))
	geom.vertexAttrib[ANCHOR_V_LOCATION] = per_vertex(osg.Vec3Array(anchor_v))
	geom.primitiveSets.append(osg.DrawArrays(osg.PrimitiveSet.TRIANGLES, 0, len(positions)))

	return geom
