#!/usr/bin/env python3
#vimrun! ../examples/pyosg-dice-procedural.py --die d4,d6,d8,d10,d12,d20

"""Combined D4/D6/D8/D10/D12/D20 procedural-number-atlas prototype -- see
ai/context-todo-dice.md. Supersedes the separate `pyosg-d4.py`/
`pyosg-d6-numbers.py` prototypes now that all these dice reduce to the same
mesh/shader mechanism via `pyosg_dice.py` (see that module's docstring for
the full writeup: one shared vertex-attribute layout, one shared decal
shader, the only real difference between die types being DATA -- which base
vertices/faces, and whether numbering is per-face-center or per-vertex-corner).

This is explicitly a separate track from `pyosg-dice.py`, which stays as the
PBR/IBL-bound D6 (pip-dot texture, real per-face material data, meant to
plug into the osgx PBR/IBL substrate later -- see that file's own docstring
and ai/context-todo-dice.md's earlier sections). This file may end up
donating pieces back to that track eventually, but for now it's purely
about proving the procedural-pixel-font/atlas-decal technique across
multiple die shapes.

Usage: `--die d4,d6,d8,d10,d12,d20` (default: all six) shows any subset of the
currently supported dice side by side, sharing one Program and one number
atlas. Press `r` to decide and animate a new outcome for every displayed die;
holding it keeps the dice spinning at their apex until release. The generic
roll support lives in `pyosg_dice.py`: it chooses each outcome first, then
uses elastic tumble/bounce interpolation only as its visualization. D8
(octahedron) needed no new mechanism at all -- centered face,
triangle UV, same as D4's TRIANGLE_UV, just its own vertex/face data (plus a
per-octant winding-parity quirk, see build_d8_geometry()'s comment). D10
(pentagonal trapezohedron, NOT a Platonic solid, irregular quadrilateral
"kite" faces) needed a real fix along the way: a hand-guessed kite UV shape
visibly stretched its digit decals, replaced by `pyosg_dice.isometric_face_uv()`
-- an exact flattening of a face's REAL 3D vertices (verified against every
pairwise distance, not just consecutive edges), rather than any more
hand-guessed canonical shapes. D12 (dodecahedron, 20 vertices/12 pentagonal
faces) is the first die needing genuinely double-digit faces (10/11/12) --
`pyosg_dice.build_number_atlas()` now renders 1 OR 2 glyphs per cell (2 at a
smaller per-character scale, so both still fit the same fixed cell width),
with the decal placement/shader completely unchanged either way -- same
decoupling between "where a decal goes" and "what's inside it" noted back
when this all started with D4. D12's 12 face vertex-lists were derived
computationally (nearest-neighbor edge graph + consistent-turn face
tracing) and verified (planarity, winding, vertex-incidence counts,
antipodal opposite-face pairing), not hand-derived -- 20 vertices/12 faces
was too large to trust by eye. D20 reuses D4/D8's TRIANGLE_UV outright
(its faces are equilateral triangles), while the existing multi-character
atlas renders its values 10-20 without any additional mechanism.
"""

import argparse
import math
import os
import random

os.environ.setdefault("OSG_WINDOW", "50 50 800 600")
os.environ.setdefault("OSG_THREADING", "SingleThreaded")
os.environ.setdefault("OSG_GL_CONTEXT_PROFILE_MASK", "1")
os.environ.setdefault("OSG_GL_VERSION", "4.6")
os.environ.setdefault("OSG_GL_CONTEXT_VERSION", "4.6")

from OpenSceneGraph import *
from OpenSceneGraph.GL import *

import pyosg_dice as dice

W, H = 800, 600
DIE_SPACING = 3.0
FLOOR_MARGIN = 1.6

# Every die is built at its own natural/arbitrary raw scale, then run
# through dice.normalize_vertices() so its CIRCUMRADIUS (centroid to
# farthest vertex) always comes out to exactly this value -- one shared
# size constant every die type agrees on, rather than independently
# eyeballed per-die-type numbers that don't actually look size-matched next
# to each other (see ai/context-todo-dice.md).
DIE_SIZE = 1.1

# All dice share one atlas sized for the widest die currently supported --
# "0" then "10"-"20" appended at the end rather than the front, so
# D4/D6/D8's existing digit-1 = column-index convention stays untouched.
# "10"-"20" are the double-digit faces introduced by D12/D20 -- pyosg_dice.py's
# build_number_atlas() renders 2 glyphs per cell for those, same cell width
# as everyone else's 1-glyph cells. Keeps one Texture2D/one digitCount
# uniform value usable by every die type.
ATLAS_DIGITS = (
	"1", "2", "3", "4", "5", "6", "7", "8", "9", "0",
	"10", "11", "12", "13", "14", "15", "16", "17", "18", "19", "20",
)

def atlas_column(digit):
	"""Which ATLAS_DIGITS column a real die digit (0-20) lives in -- looked
	up by string match rather than hand-derived arithmetic, so it stays
	correct regardless of how ATLAS_DIGITS is ordered/extended later."""
	return ATLAS_DIGITS.index(str(digit))

def build_d4_geometry():
	# Raw edge length is arbitrary -- normalize_vertices() below washes it
	# out, rescaling to DIE_SIZE regardless.
	edge = 1.0
	r = edge / math.sqrt(3.0)
	h = edge * math.sqrt(2.0 / 3.0)

	raw_verts = (
		osg.Vec3(r, 0.0, 0.0),
		osg.Vec3(-r / 2.0, r * math.sqrt(3.0) / 2.0, 0.0),
		osg.Vec3(-r / 2.0, -r / 2.0 * math.sqrt(3.0), 0.0),
		osg.Vec3(0.0, 0.0, h),
	)
	base_verts = dice.normalize_vertices(raw_verts, target_radius=DIE_SIZE)
	# Wound so each face's outward normal comes out of
	# (vB - vA).cross(vC - vA) directly -- see pyosg_dice.py's docstring.
	faces = ((0, 2, 1), (0, 1, 3), (1, 2, 3), (2, 0, 3))
	vertex_values = {
		0: atlas_column(1),
		1: atlas_column(2),
		2: atlas_column(3),
		3: atlas_column(4),
	}  # one real die value per VERTEX

	geom = dice.build_polyhedron_geometry(base_verts, faces, dice.corner_decal_scheme(vertex_values))

	return geom, dice.vertex_roll_spec(
		base_verts,
		(1, 2, 3, 4),
		(faces[2], faces[3], faces[1], faces[0]),
	)

def build_d6_geometry():
	s = 0.5  # raw unit-cube half-extent -- also washed out by normalize_vertices()
	raw_verts = (
		osg.Vec3(-s, -s, -s), osg.Vec3(s, -s, -s), osg.Vec3(s, s, -s), osg.Vec3(-s, s, -s),
		osg.Vec3(-s, -s, s), osg.Vec3(s, -s, s), osg.Vec3(s, s, s), osg.Vec3(-s, s, s),
	)
	base_verts = dice.normalize_vertices(raw_verts, target_radius=DIE_SIZE)
	faces = ((1, 2, 6, 5), (0, 4, 7, 3), (3, 7, 6, 2), (0, 1, 5, 4), (4, 5, 6, 7), (0, 3, 2, 1))
	# Opposite faces sum to 7, same convention as pyosg-dice.py:
	# +X=1/-X=6, +Y=2/-Y=5, +Z=3/-Z=4 -- one real die value per FACE.
	face_values = (1, 6, 2, 5, 3, 4)
	atlas_values = tuple(atlas_column(d) for d in face_values)

	geom = dice.build_polyhedron_geometry(base_verts, faces, dice.center_decal_scheme(atlas_values))

	return geom, dice.face_roll_spec(
		base_verts, faces, face_values, (1, 0, 3, 2, 5, 4)
	)

def build_d8_geometry():
	# +-X/+-Y/+-Z axis vertices -- the standard octahedron construction.
	raw_verts = (
		osg.Vec3(1.0, 0.0, 0.0), osg.Vec3(-1.0, 0.0, 0.0),   # 0: +X, 1: -X
		osg.Vec3(0.0, 1.0, 0.0), osg.Vec3(0.0, -1.0, 0.0),   # 2: +Y, 3: -Y
		osg.Vec3(0.0, 0.0, 1.0), osg.Vec3(0.0, 0.0, -1.0),   # 4: +Z, 5: -Z
	)
	base_verts = dice.normalize_vertices(raw_verts, target_radius=DIE_SIZE)
	# One face per octant (all 8 sign combinations of X/Y/Z), each triangle
	# built from that octant's own axis vertices. Unlike D4/D6, the winding
	# that gives an outward (vB-vA).cross(vC-vA) normal ALTERNATES by octant
	# parity here (confirmed empirically, not guessed) -- (X, Y, Z) vertex
	# order for octants where the sign product is +1, reversed to (Z, Y, X)
	# where it's -1.
	faces = (
		(0, 2, 4), (5, 2, 0), (4, 3, 0), (0, 3, 5),
		(4, 2, 1), (1, 2, 5), (1, 3, 4), (5, 3, 1),
	)
	# Opposite faces sum to 9 (n+1 for an 8-sided die), same convention as
	# pyosg-dice.py's D6 -- one real die value per FACE, aligned with faces
	# above: (+++,1)<->(---,8), (++-,2)<->(--+,7), (+-+,3)<->(-+-,6),
	# (+--,4)<->(-++,5).
	face_values = (1, 2, 3, 4, 5, 6, 7, 8)
	atlas_values = tuple(atlas_column(d) for d in face_values)

	geom = dice.build_polyhedron_geometry(base_verts, faces, dice.center_decal_scheme(atlas_values))

	return geom, dice.face_roll_spec(
		base_verts, faces, face_values, (7, 6, 5, 4, 3, 2, 1, 0)
	)

def build_d10_geometry():
	# Pentagonal trapezohedron -- NOT a Platonic solid, unlike every other
	# die here (see ai/context-todo-dice.md). 2 apex points + a 10-vertex
	# zigzag "ring" (5 up at z=+z1, 5 down at z=-z1, one every 36 degrees).
	#
	# The ring-radius-to-apex-height ratio needed to keep each 4-vertex kite
	# face perfectly flat is FIXED (apex_h = z1 * (1+cos36)/(1-cos36) =~
	# 9.47 * z1, confirmed via a coplanarity check, residual ~1e-16, not
	# guessed) and, less obviously, that ratio holds regardless of ring
	# radius. Picking z1 == ring radius (both 1.0) -- the first, "obvious"
	# guess -- satisfies that fine but forces an apex ~6.7x farther from
	# center than the ring, which normalize_vertices() then reads as the
	# die's whole circumradius, crushing the ring down to a sliver. So this
	# works BACKWARDS instead: pick apex_h as a proportion that actually
	# looks like a d10 (a fairly compact gem, per Google's dice-roller
	# widget), then derive the (much smaller) z1 that keeps the faces flat.
	ring_radius = 1.0
	apex_h = 1.35 * ring_radius
	c = math.cos(math.radians(36.0))
	z1 = apex_h * (1.0 - c) / (1.0 + c)

	def ring_vertex(i):
		angle = math.radians(i * 36.0)

		return osg.Vec3(
			ring_radius * math.cos(angle), ring_radius * math.sin(angle), z1 if i % 2 == 0 else -z1
		)

	TOP, BOTTOM = 10, 11
	raw_verts = tuple(ring_vertex(i) for i in range(10)) + (
		osg.Vec3(0.0, 0.0, apex_h),   # 10: top apex
		osg.Vec3(0.0, 0.0, -apex_h),  # 11: bottom apex
	)
	base_verts = dice.normalize_vertices(raw_verts, target_radius=DIE_SIZE)

	# Each of the 10 kite faces uses ring index i as its "middle" vertex --
	# ODD i pairs with the TOP apex (odd indices sit at z=-z1, flanked
	# upward toward the top apex), EVEN i with the BOTTOM apex. The bottom
	# half's vertex order is REVERSED relative to the top half -- confirmed
	# numerically (not guessed) that this compensates for the handedness
	# flip under reflection, same kind of parity quirk as D8's octants.
	faces = tuple(
		(TOP, (i - 1) % 10, i, (i + 1) % 10) if i % 2 == 1
		else (BOTTOM, (i + 1) % 10, i, (i - 1) % 10)
		for i in range(10)
	)
	# Opposite faces sum to 9 (real d10 dice show 0-9, not 1-10) -- one
	# digit per ring index i=0..9.
	digit_by_ring_index = (7, 0, 6, 1, 5, 2, 9, 3, 8, 4)
	atlas_values = tuple(atlas_column(d) for d in digit_by_ring_index)

	# The kite's true shape isn't a "nice" regular polygon (unlike every
	# other die here), so its UV comes from an EXACT isometric flattening
	# of one representative face's real vertices, not a hand-guessed
	# proportion -- a guessed shape visibly stretched digit decals here in
	# an earlier pass (see isometric_face_uv()'s docstring). All 10 faces
	# are congruent by construction, so any one face is representative.
	kite_uv = dice.isometric_face_uv(tuple(base_verts[i] for i in faces[0]))

	geom = dice.build_polyhedron_geometry(
		base_verts, faces, dice.center_decal_scheme(atlas_values), uv_shape=kite_uv
	)

	return geom, dice.face_roll_spec(
		base_verts, faces, digit_by_ring_index, (5, 6, 7, 8, 9, 0, 1, 2, 3, 4)
	)

def build_d12_geometry():
	# Regular dodecahedron -- 20 vertices (8 cube corners (+-1,+-1,+-1) +
	# 3 golden rectangles using phi), 12 pentagonal faces. Unlike every
	# other die here, the 12 face vertex-lists below were NOT hand-derived
	# (too error-prone for a 20-vertex/12-face solid) -- they were derived
	# computationally (nearest-neighbor edge graph + consistent-turn face
	# tracing) and verified (exact planarity, correct outward winding on
	# every face, all 20 vertices used exactly 3x) before being hardcoded
	# here; see ai/context-todo-dice.md.
	phi = (1.0 + math.sqrt(5.0)) / 2.0
	raw_verts = []

	for sx in (1.0, -1.0):
		for sy in (1.0, -1.0):
			for sz in (1.0, -1.0):
				raw_verts.append(osg.Vec3(sx, sy, sz))

	for s1 in (1.0, -1.0):
		for s2 in (1.0, -1.0):
			raw_verts.append(osg.Vec3(0.0, s1 / phi, s2 * phi))
			raw_verts.append(osg.Vec3(s1 / phi, s2 * phi, 0.0))
			raw_verts.append(osg.Vec3(s2 * phi, 0.0, s1 / phi))

	base_verts = dice.normalize_vertices(tuple(raw_verts), target_radius=DIE_SIZE)
	faces = (
		(9, 15, 4, 8, 0), (10, 16, 1, 9, 0), (8, 14, 2, 10, 0),
		(11, 5, 15, 9, 1), (16, 3, 17, 11, 1), (12, 3, 16, 10, 2),
		(14, 6, 18, 12, 2), (12, 18, 7, 17, 3), (13, 6, 14, 8, 4),
		(15, 5, 19, 13, 4), (11, 17, 7, 19, 5), (13, 19, 7, 18, 6),
	)
	# Opposite faces sum to 13 (real d12 dice show 1-12) -- face-index
	# pairs (0,7)(1,11)(2,10)(3,6)(4,8)(5,9) confirmed by matching each
	# face's vertex set against the antipode of its pair's vertex set.
	digit_by_face_index = (1, 2, 3, 4, 5, 6, 9, 12, 8, 7, 10, 11)
	atlas_values = tuple(atlas_column(d) for d in digit_by_face_index)

	# Pentagon isn't a "nice" canonical shape here either -- same exact
	# isometric flattening as D10's kite, from one representative face (all
	# 12 congruent by construction).
	pentagon_uv = dice.isometric_face_uv(tuple(base_verts[i] for i in faces[0]))

	geom = dice.build_polyhedron_geometry(
		base_verts, faces, dice.center_decal_scheme(atlas_values), uv_shape=pentagon_uv
	)

	return geom, dice.face_roll_spec(
		base_verts, faces, digit_by_face_index, (7, 11, 10, 6, 8, 9, 3, 0, 4, 5, 2, 1)
	)

def build_d20_geometry():
	# Regular icosahedron -- 12 vertices: the three coordinate permutations
	# of (0, +-1, +-phi). This standard indexing has a compact, verified
	# 20-face list below; each triangle is wound outward.
	phi = (1.0 + math.sqrt(5.0)) / 2.0
	raw_verts = (
		osg.Vec3(-1.0, phi, 0.0), osg.Vec3(1.0, phi, 0.0),
		osg.Vec3(-1.0, -phi, 0.0), osg.Vec3(1.0, -phi, 0.0),
		osg.Vec3(0.0, -1.0, phi), osg.Vec3(0.0, 1.0, phi),
		osg.Vec3(0.0, -1.0, -phi), osg.Vec3(0.0, 1.0, -phi),
		osg.Vec3(phi, 0.0, -1.0), osg.Vec3(phi, 0.0, 1.0),
		osg.Vec3(-phi, 0.0, -1.0), osg.Vec3(-phi, 0.0, 1.0),
	)
	base_verts = dice.normalize_vertices(raw_verts, target_radius=DIE_SIZE)
	faces = (
		(0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11),
		(1, 5, 9), (5, 11, 4), (11, 10, 2), (10, 7, 6), (7, 1, 8),
		(3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8), (3, 8, 9),
		(4, 9, 5), (2, 4, 11), (6, 2, 10), (8, 6, 7), (9, 8, 1),
	)
	# Opposite faces sum to 21. Face-index pairs are
	# (0,13)(1,12)(2,11)(3,10)(4,14)(5,17)(6,18)(7,19)(8,15)(9,16).
	digit_by_face_index = (
		1, 2, 3, 4, 5, 6, 7, 8, 9, 10,
		17, 18, 19, 20, 16, 12, 11, 15, 14, 13,
	)
	atlas_values = tuple(atlas_column(d) for d in digit_by_face_index)

	geom = dice.build_polyhedron_geometry(base_verts, faces, dice.center_decal_scheme(atlas_values))

	return geom, dice.face_roll_spec(
		base_verts,
		faces,
		digit_by_face_index,
		(13, 12, 11, 10, 14, 17, 18, 19, 15, 16, 3, 2, 1, 0, 4, 8, 9, 5, 6, 7),
	)

class DieSpec:
	def __init__(self, build_geometry, decal_half, body_color):
		# build_geometry() -> (osg.Geometry, dice.RollSpec). The RollSpec owns
		# the base vertices/outcomes needed to settle a rotated die on the floor.
		self.build_geometry = build_geometry
		self.decal_half = decal_half
		self.body_color = body_color

# body_color per die borrows Google's "Roll dice" widget palette (one
# distinct, saturated color per die type) rather than the earlier
# independently-eyeballed earthy tones -- nicer, more game-toy convention,
# and gives D12/D20 distinct warm colors.
DIE_SPECS = {
	"d4": DieSpec(build_d4_geometry, decal_half=0.13, body_color=(0.20, 0.66, 0.33)),  # green
	"d6": DieSpec(build_d6_geometry, decal_half=0.38, body_color=(0.10, 0.70, 0.80)),  # cyan
	# A centered decal on a triangular face (same TRIANGLE_UV as D4's
	# corners, just one decal instead of three) -- start near the D4
	# corner-decal's own scale, since both sample the same canonical
	# triangle; likely needs the same kind of one-constant tuning pass.
	"d8": DieSpec(build_d8_geometry, decal_half=0.24, body_color=(0.40, 0.23, 0.72)),  # purple
	# Centered decal on KITE_UV's (narrower than a triangle/square) kite
	# shape -- first guess, tuned smaller than D8's to clear the kite's
	# pointed top/bottom corners.
	"d10": DieSpec(build_d10_geometry, decal_half=0.18, body_color=(0.91, 0.12, 0.55)),  # magenta
	# Centered decal on the pentagon's isometric UV. D12's 10/11/12 use the
	# same smaller two-character atlas glyph as D20, so this is sized to keep
	# those values comparable rather than treating them as denser single glyphs.
	"d12": DieSpec(build_d12_geometry, decal_half=0.20, body_color=(0.85, 0.16, 0.14)),  # red
	"d20": DieSpec(build_d20_geometry, decal_half=0.22, body_color=(0.95, 0.42, 0.08)),  # orange
}

def create_scene(die_names):
	root = osg.Group(name="scene")
	vertex_shader = osg.Shader(osg.Shader.VERTEX, dice.VERTEX_SHADER)
	die_program = osg.Program(name="pyosg-dice-procedural-die", shaders=(
		vertex_shader,
		osg.Shader(osg.Shader.FRAGMENT, dice.FRAGMENT_SHADER),
	))
	atlas_tex = osg.Texture2D(
		image=dice.build_number_atlas(ATLAS_DIGITS),
		filter=(osg.Texture.NEAREST, osg.Texture.NEAREST),
		wrap=(osg.Texture.CLAMP_TO_EDGE, osg.Texture.CLAMP_TO_EDGE),
	)

	positions = [(i - (len(die_names) - 1) / 2.0) * DIE_SPACING for i in range(len(die_names))]
	# Every die's circumradius is exactly DIE_SIZE post-normalization, so
	# there's no more per-die footprint guesswork needed here.
	floor_half = (max((abs(x) for x in positions), default=0.0) + DIE_SIZE + FLOOR_MARGIN)

	floor_geode = osg.Geode(name="floor")
	floor_drawable = osg.ShapeDrawable(osg.Box(
		osg.Vec3(0.0, 0.0, -0.05), floor_half * 2.0, floor_half * 2.0, 0.1
	))

	floor_geode.drawables.append(floor_drawable)
	floor_geode.stateSet.attributes.append(osg.Program(name="pyosg-dice-procedural-floor", shaders=(
		vertex_shader,
		osg.Shader(osg.Shader.FRAGMENT, dice.FLOOR_FRAGMENT_SHADER),
	)))
	root.children.append(floor_geode)

	rollable_dice = []

	for x, name in zip(positions, die_names):
		spec = DIE_SPECS[name]
		geom, roll_spec = spec.build_geometry()
		rest_xy = osg.Vec3(x, 0.0, 0.0)
		rest_pos = dice.rest_position(rest_xy, roll_spec.vertices, osg.Quat())
		mt = osg.MatrixTransform(osg.Matrix.translate(rest_pos))
		die_geode = osg.Geode(name=name)

		die_geode.drawables.append(geom)
		mt.children.append(die_geode)
		root.children.append(mt)

		die_ss = die_geode.stateSet

		die_ss.attributes.append(die_program)
		die_ss.textureAttributes[0] = atlas_tex
		die_ss.uniforms.extend((
			osg.Uniform("numberAtlas", 0),
			osg.Uniform("digitCount", len(ATLAS_DIGITS)),
			osg.Uniform("decalHalf", spec.decal_half),
			osg.Uniform("bodyColor", osg.Vec3(*spec.body_color)),
		))
		rollable_dice.append((mt, rest_xy, roll_spec))

	return root, rollable_dice

if __name__ == "__main__":
	parser = argparse.ArgumentParser(description="Procedural polyhedral dice, number-atlas/decal prototype.")
	parser.add_argument(
		"--die",
		default="d4,d6,d8,d10,d12,d20",
		help=f"comma-separated dice to show, from {{{', '.join(sorted(DIE_SPECS))}}} (default: %(default)s)",
	)
	args = parser.parse_args()
	die_names = [d.strip() for d in args.die.split(",") if d.strip()]

	for name in die_names:
		if name not in DIE_SPECS:
			parser.error(f"unknown die {name!r} -- choose from {{{', '.join(sorted(DIE_SPECS))}}}")

	osg.setNotifyLevel(osg.NotifySeverity.NOTICE)

	viewer = osgViewer.Viewer()
	viewer.cameraManipulator = osgGA.TrackballManipulator()
	scene, rollable_dice = create_scene(die_names)
	rng = random.Random()
	rolling = [False] * len(rollable_dice)
	r_held = [False]

	viewer.sceneData = scene
	viewer.eventHandlers.append(dice.DiceRollKeyHandler(
		rollable_dice, rng, rolling, r_held, notice_prefix="pyosg-dice-procedural"
	))

	osg.notice("[pyosg-dice-procedural] press 'r' to roll; hold it to spin at the peak")

	while not viewer.done:
		viewer.frame()
