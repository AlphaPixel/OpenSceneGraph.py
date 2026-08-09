#!/usr/bin/env python3
#vimrun! ../examples/pyosg-dice.py

"""Procedural dice -- see ai/context-todo-dice.md for the full staged plan
this came out of (match4's colored spheres are a placeholder for real
polyhedral dice; this is the start of the real thing). Scope of THIS file,
per the plan's own staging:

  1. A plain D6 -- osg.ShapeDrawable(osg.Box()), same minimal core-profile
     Lambertian shader as pyosg-picking.py/pyosg-hover.py/pyosg-match4.py.
  2. A predetermined faux-physics roll: press 'r' to roll. The outcome (which
     of the die's 6 faces lands up) is decided FIRST, then animated toward --
     never the other way around. This is the same governing principle as
     pyosg-match4.py's ShrinkCallback/FallCallback (board state is
     authoritative, animation is pure visualization on top), and the SAME
     wall-clock-timer-as-updateCallback mechanism.
  3. A real per-face texture (this step) -- a small 6-cell "earthy/neutral"
     color atlas, one cell per die value, sampled in the die's own fragment
     shader. Deliberately a real osg.Texture2D (not just ShapeDrawable.color)
     so a later step can layer noise/PBR data into the same atlas cells
     without changing how faces are selected. Pip/dot layout is still the
     next step after this, not here.

The animation itself uses tier 1 from the plan's faux-physics section --
pure eased interpolation, zero hand-rolled physics: `osgAnimation.outBounce`
(already-bound pyosgAnimation easing, 28 functions total) drives the drop
height, since its curve already looks exactly like a decaying bounce-to-rest
without any spring/gravity math, and `osgAnimation.outElastic` drives the
slerp parameter from a random tumble-start orientation to the known target
orientation, giving a bit of overshoot-and-settle wobble for free. Tiers 2
(spring-damper) and 3 (decaying noise) from the plan are NOT here -- this is
deliberately the cheapest tier first.

Die values are assigned to local box-face directions the same way a real D6
does (opposite faces sum to 7): +X=1/-X=6, +Y=2/-Y=5, +Z=3/-Z=4 -- see
FACES below. roll() uses that to pick a target orientation and osg.notice()
the predetermined outcome up front; the fragment shader uses the SAME table
(baked into a per-vertex `faceValue` attribute, see FACE_ATTRIB_LOCATION) to
pick which atlas cell each face samples.

Per-face texturing deliberately does NOT hand-author a replacement Geometry,
and does NOT touch osg.Geometry's legacy TexCoordArray path either (not even
bound in Python yet -- see `pyosg/osg/Geometry.cpp`'s TODO comment).
osg.ShapeDrawable(osg.Box()) already builds correct per-face 0..1 UVs in C++
at construction (24 unique vertices, 4 per face -- verified empirically by
inspecting .vertexArray/.normalArray directly, no shared/welded corners),
which reach the shader for free as `osg_MultiTexCoord0` via OSG's
core-profile vertex-attrib aliasing -- same mechanism this project already
leans on for osg_Vertex/osg_Normal/osg_Color. The only genuinely new
per-vertex data needed is `faceValue` (which atlas column, 0-5), added as
one extra generic `vertexAttrib` array -- the same already-proven mechanism
pyosg-polyhaven.py's `faceDir` attribute uses -- at a location confirmed
free by reading `osg::State::resetVertexAttributeAlias()`'s default compact
numbering directly (`~/dev/OpenSceneGraph-3.6.5/src/osg/State.cpp`, not
guessed): osg_Vertex=0, osg_Normal=1, osg_Color=2, osg_MultiTexCoord0-7=3-10,
osg_SecondaryColor=11, osg_FogCoord=12 -- so 13 is the first free slot,
confirmed against this project's own setup (`pyosg/pyosgViewer.cpp` calls
`state->setUseVertexAttributeAliasing(true)` but never overrides the default
compact/8-texcoord-unit numbering).

The atlas image itself is filled via the plain buffer protocol
(`memoryview(img).cast("B")` + per-row 1-D slice assignment), not numpy --
multi-dimensional `memoryview` slice ASSIGNMENT is a general CPython
restriction to ndim==1 (confirmed: reproduces identically on a bare numpy
array's memoryview, nothing project-specific), so a cast-to-1D + per-row
approach is the real fix, not a numpy workaround.
"""

import argparse
import math
import os
import random
import time

os.environ.setdefault("OSG_WINDOW", "50 50 800 600")
os.environ.setdefault("OSG_THREADING", "SingleThreaded")
os.environ.setdefault("OSG_GL_CONTEXT_PROFILE_MASK", "1")
os.environ.setdefault("OSG_GL_VERSION", "4.6")
os.environ.setdefault("OSG_GL_CONTEXT_VERSION", "4.6")

from OpenSceneGraph import *
from OpenSceneGraph.GL import *

# First generic vertex-attrib location confirmed free of OSG's own default aliases --
# see module docstring for how this was verified (not guessed).
FACE_ATTRIB_LOCATION = 13

# Shared by both the floor and the die -- forwards everything either fragment shader
# might need. `faceValue` is unused/zero for the floor (its Program below never declares
# it as an active input -- see FLOOR_FRAGMENT_SHADER), harmless per GL's default generic
# vertex attribute value.
SCENE_VERTEX_SHADER = f"""
#version 330 core

in vec4 osg_Vertex;
in vec3 osg_Normal;
in vec4 osg_Color;
in vec2 osg_MultiTexCoord0;
layout(location = {FACE_ATTRIB_LOCATION}) in float faceValue;

uniform mat4 osg_ModelViewProjectionMatrix;
uniform mat3 osg_NormalMatrix;

out vec3 vNormal;
out vec4 vColor;
out vec2 vUV;
flat out float vFaceValue;

void main() {{
	vNormal = normalize(osg_NormalMatrix * osg_Normal);
	vColor = osg_Color;
	vUV = osg_MultiTexCoord0;
	vFaceValue = faceValue;

	gl_Position = osg_ModelViewProjectionMatrix * osg_Vertex;
}}
"""

# Floor: same flat-lit vColor path as step 1/2 -- no texture.
FLOOR_FRAGMENT_SHADER = """
#version 330 core

in vec3 vNormal;
in vec4 vColor;

out vec4 fragColor;

void main() {
	const vec3 L = vec3(0.4, 0.6, 0.7);

	float diffuse = max(dot(normalize(vNormal), normalize(L)), 0.0);
	float light = 0.35 + 0.65 * diffuse;

	fragColor = vec4(vColor.rgb * light, vColor.a);
}
"""

# Die: samples the 6-cell face-color atlas -- `vFaceValue` (0-5) picks the column,
# `vUV` (the box's own per-face 0..1 UV) picks position within that column's cell --
# then draws the standard 7-slot pip layout procedurally on top, purely from `vUV`
# and the die value, as a cheap placeholder for the later slughorn/osgSlug
# MSDF-engraved-numeral upgrade (see module docstring / ai/context-todo-dice.md).
DIE_FRAGMENT_SHADER = """
#version 330 core

in vec3 vNormal;
in vec2 vUV;
flat in float vFaceValue;

uniform sampler2D diceAtlas;

out vec4 fragColor;

// Standard 7-slot pip grid (TL, TR, ML, MM, MR, BL, BR) -- every die value 1-6 lights
// some subset of these same 7 positions, so one shared layout covers all of them.
const vec2 PIP_POS[7] = vec2[7](
	vec2(0.24, 0.76), vec2(0.76, 0.76), // TL, TR
	vec2(0.24, 0.50), vec2(0.50, 0.50), vec2(0.76, 0.50), // ML, MM, MR
	vec2(0.24, 0.24), vec2(0.76, 0.24) // BL, BR
);

// One bit per PIP_POS slot above, indexed by die value (index 0 unused/never hit).
const int PIP_MASKS[7] = int[7](0, 0x08, 0x41, 0x49, 0x63, 0x6B, 0x77);

const float PIP_RADIUS = 0.11;
const float PIP_AA = 0.02;

void main() {
	const vec3 L = vec3(0.4, 0.6, 0.7);

	float diffuse = max(dot(normalize(vNormal), normalize(L)), 0.0);
	float light = 0.35 + 0.65 * diffuse;

	vec2 atlasUV = vec2((vFaceValue + vUV.x) / 6.0, vUV.y);
	vec4 texColor = texture(diceAtlas, atlasUV);

	int value = int(vFaceValue + 0.5) + 1;
	int mask = PIP_MASKS[value];
	float pip = 0.0;

	for (int i = 0; i < 7; i++) {
		if ((mask & (1 << i)) != 0) {
			float d = distance(vUV, PIP_POS[i]);

			pip = max(pip, 1.0 - smoothstep(PIP_RADIUS - PIP_AA, PIP_RADIUS + PIP_AA, d));
		}
	}

	// Contrast-adaptive pip ink -- dark on light faces, light on dark faces -- rather than
	// one fixed color that would wash out against faces like walnut/slate.
	float luminance = dot(texColor.rgb, vec3(0.299, 0.587, 0.114));
	vec3 pipColor = luminance > 0.45 ? vec3(0.12, 0.10, 0.09) : vec3(0.92, 0.88, 0.80);
	vec3 baseColor = mix(texColor.rgb, pipColor, pip);

	fragColor = vec4(baseColor * light, texColor.a);
}
"""

W, H = 800, 600
DIE_SIZE = 1.4
DICE_COUNT = 3
PIP_SPACING = 3.5
DROP_HEIGHT = 3.0
ROLL_DURATION = 1.1

ATLAS_CELL = 64
ATLAS_SIZE = (ATLAS_CELL * 6, ATLAS_CELL)

# (label, local face-normal, die value) -- opposite faces sum to 7, same as a real D6.
FACES = (
	("+X", osg.Vec3(1.0, 0.0, 0.0), 1),
	("-X", osg.Vec3(-1.0, 0.0, 0.0), 6),
	("+Y", osg.Vec3(0.0, 1.0, 0.0), 2),
	("-Y", osg.Vec3(0.0, -1.0, 0.0), 5),
	("+Z", osg.Vec3(0.0, 0.0, 1.0), 3),
	("-Z", osg.Vec3(0.0, 0.0, -1.0), 4),
)

# Earthy/neutral per-value atlas colors -- keeping the same palette family as the
# floor/die flat colors from steps 1/2, one shade per die value.
FACE_COLORS = {
	1: (0.82, 0.76, 0.66), # bone
	2: (0.70, 0.42, 0.28), # terracotta
	3: (0.45, 0.47, 0.33), # moss
	4: (0.36, 0.40, 0.44), # slate
	5: (0.42, 0.29, 0.20), # walnut
	6: (0.76, 0.64, 0.44), # sand
}

# Die centers arranged exactly like the pips for the corresponding D6 value.
# The center die for 1/3/5 is shared deliberately, just as it is on a die face.
DICE_LAYOUTS = {
	1: ((0.0, 0.0),),
	2: ((-0.5, 0.5), (0.5, -0.5)),
	3: ((-0.5, 0.5), (0.0, 0.0), (0.5, -0.5)),
	4: ((-0.5, 0.5), (0.5, 0.5), (-0.5, -0.5), (0.5, -0.5)),
	5: ((-0.5, 0.5), (0.5, 0.5), (0.0, 0.0), (-0.5, -0.5), (0.5, -0.5)),
	6: ((-0.5, 0.5), (0.5, 0.5), (-0.5, 0.0), (0.5, 0.0), (-0.5, -0.5), (0.5, -0.5)),
}

def dice_positions(dice_count):
	return tuple(
		osg.Vec3(x * PIP_SPACING, y * PIP_SPACING, DIE_SIZE / 2.0)
		for x, y in DICE_LAYOUTS[dice_count]
	)

def floor_size(positions):
	max_extent = max(max(abs(pos.x), abs(pos.y)) for pos in positions)

	return 2.0 * (max_extent + DIE_SIZE / 2.0 + 0.4)

def build_face_atlas():
	"""A `6 * ATLAS_CELL` x `ATLAS_CELL` RGB image, one flat-colored cell per die
	value (column = value - 1) -- see FACE_COLORS. Filled via the plain buffer
	protocol (memoryview + cast-to-1D + per-row slice assignment), not numpy --
	see module docstring for why cast-to-1D specifically is needed.
	"""
	img = osg.Image()

	img.allocateImage(ATLAS_SIZE[0], ATLAS_SIZE[1], 1, GL_RGB, GL_UNSIGNED_BYTE)

	view = memoryview(img)
	flat = view.cast("B")
	row_stride = view.strides[0]
	channels = view.shape[2]

	for value, color in FACE_COLORS.items():
		col0 = (value - 1) * ATLAS_CELL
		rgb = bytes(int(round(c * 255)) for c in color)
		row_bytes = rgb * ATLAS_CELL

		for row in range(ATLAS_SIZE[1]):
			start = row * row_stride + col0 * channels

			flat[start:start + len(row_bytes)] = row_bytes

	return img

def face_value_array(drawable):
	"""Per-vertex `faceValue` (0-5) for `drawable`'s existing vertex/normal arrays --
	looked up per-vertex from its own normalArray against FACES, rather than assumed
	from ShapeDrawable(Box)'s known face-group order, so this keeps working even if
	that internal tessellation order ever changes.
	"""
	normals = drawable.normalArray
	values = []

	for i in range(len(normals)):
		n = normals[i]
		_, axis, value = min(FACES, key=lambda face: (face[1] - n).length2())

		values.append(float(value - 1))

	array = osg.FloatArray(values)
	array.binding = osg.Array.Binding.BIND_PER_VERTEX

	return array

def face_up_quat(local_axis):
	"""Rotation that brings a die-local face normal to point along world +Z --
	this codebase's world is Z-up (see 08-shadows.py's floor-plane comment)."""
	q = osg.Quat()

	q.makeRotate(local_axis, osg.Vec3(0.0, 0.0, 1.0))

	return q

def random_quat(rng):
	"""A random tumble-start orientation -- only ever used as slerp's FROM
	endpoint, so it just needs to look random, not be a perfectly uniform
	SO(3) sample."""
	axis = osg.Vec3(rng.uniform(-1.0, 1.0), rng.uniform(-1.0, 1.0), rng.uniform(-1.0, 1.0))

	if axis.length() < 1e-6:
		axis = osg.Vec3(1.0, 0.0, 0.0)

	else:
		axis.normalize()

	return osg.Quat(rng.uniform(0.0, 2.0 * math.pi), axis)

class DiceRollCallback:
	"""Animates `mt` from a random tumble-start orientation to `target_quat`
	(already decided by roll(), below, before this callback ever exists) over
	`duration` seconds -- same wall-clock-timer/no-self-detach pattern as
	ShrinkCallback/FallCallback in pyosg-match4.py. Height follows
	osgAnimation.outBounce (decaying-bounce shape, for free); rotation slerps
	along osgAnimation.outElastic (slight overshoot wobble, for free) -- no
	physics simulation of any kind, see module docstring.

	`rolling` is the shared per-die flag list (one entry per die in `dice`,
	see create_scene()) and `index` is this die's own slot in it -- lets N
	independent dice roll/settle on their own schedules while DiceKeyHandler
	still only needs one `any(rolling)` check to know if the whole row is
	still moving.
	"""

	def __init__(
		self,
		mt,
		start_quat,
		target_quat,
		rest_pos,
		rolling,
		r_held,
		index,
		duration=ROLL_DURATION
	):
		self.mt = mt
		self.start_quat = start_quat
		self.target_quat = target_quat
		self.rest_pos = rest_pos
		self.rolling = rolling
		self.r_held = r_held
		self.index = index
		self.duration = duration
		self.t0 = time.time()
		self.done = False
		self.was_held = False
		self.last_spin_quat = start_quat

	def __call__(self, node, nv):
		if not self.done:
			if self.r_held[0]:
				# A held roll remains at its highest point while rotating. On release,
				# the normal drop starts from this exact orientation.
				spin = osg.Quat(
					4.0 * math.pi * (time.time() - self.t0),
					osg.Vec3(0.0, 0.0, 1.0)
				)
				self.last_spin_quat = self.start_quat * spin
				self.was_held = True
				self.mt.matrix = osg.Matrix.rotate(self.last_spin_quat) * osg.Matrix.translate(
					osg.Vec3(self.rest_pos.x, self.rest_pos.y, self.rest_pos.z + DROP_HEIGHT)
				)

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

			z = self.rest_pos.z + DROP_HEIGHT * (1.0 - osgAnimation.outBounce(t))
			pos = osg.Vec3(self.rest_pos.x, self.rest_pos.y, z)

			quat = osg.Quat()

			quat.slerp(osgAnimation.outElastic(t), self.start_quat, self.target_quat)

			self.mt.matrix = osg.Matrix.rotate(quat) * osg.Matrix.translate(pos)

		return True

def roll(mt, rest_pos, rng, rolling, r_held, index):
	"""Decide the roll's outcome FIRST -- a random die value (and a random
	multiple-of-90-degree spin around the vertical axis, so repeated rolls
	on the same value don't look identical) -- THEN kick off the animation
	toward it. Never the other way around; see module docstring.
	"""
	label, axis, value = rng.choice(FACES)
	spin = osg.Quat(rng.choice((0, 1, 2, 3)) * (math.pi / 2.0), osg.Vec3(0.0, 0.0, 1.0))
	target_quat = face_up_quat(axis) * spin
	start_quat = random_quat(rng)

	osg.notice(f"[pyosg-dice] rolling die {index} -- landing on {value} (local {label} face up)")

	rolling[index] = True
	mt.updateCallback = DiceRollCallback(
		mt,
		start_quat,
		target_quat,
		rest_pos,
		rolling,
		r_held,
		index
	)

def roll_all(dice, rng, rolling, r_held):
	"""Rolls every die in `dice` (see create_scene()) at once."""
	for index, (mt, rest_pos) in enumerate(dice):
		roll(mt, rest_pos, rng, rolling, r_held, index)

def create_scene(dice_count):
	positions = dice_positions(dice_count)
	root = osg.Group(name="scene")
	vertex_shader = osg.Shader(osg.Shader.VERTEX, SCENE_VERTEX_SHADER)

	floor_geode = osg.Geode(name="floor")
	floor_drawable = osg.ShapeDrawable(osg.Box(
		osg.Vec3(0.0, 0.0, -0.05),
		floor_size(positions),
		floor_size(positions),
		0.1
	))

	# TODO: Add `color` to `kwargs_init`!
	floor_drawable.color = osg.Vec4(0.88, 0.86, 0.80, 1.0)

	floor_geode.drawables.append(floor_drawable)
	floor_geode.stateSet.attributes.append(osg.Program(name="pyosg-dice-floor", shaders=(
		vertex_shader,
		osg.Shader(osg.Shader.FRAGMENT, FLOOR_FRAGMENT_SHADER),
	)))
	root.children.append(floor_geode)

	# Program/texture/uniform are each built ONCE and shared across every die below --
	# only the geometry (and its per-vertex faceValue attribute) is genuinely per-instance.
	die_prog = osg.Program(name="pyosg-dice-die", shaders=(
		vertex_shader,
		osg.Shader(osg.Shader.FRAGMENT, DIE_FRAGMENT_SHADER),
	))
	die_tex = osg.Texture2D(
		image=build_face_atlas(),
		filter=(osg.Texture.NEAREST, osg.Texture.NEAREST),
		wrap=(osg.Texture.CLAMP_TO_EDGE, osg.Texture.CLAMP_TO_EDGE),
	)
	die_atlas_uniform = osg.Uniform("diceAtlas", 0)

	dice = []

	for i, rest_pos in enumerate(positions):
		mt = osg.MatrixTransform(osg.Matrix.translate(rest_pos))
		die_geode = osg.Geode(name=f"die{i}")
		die_drawable = osg.ShapeDrawable(osg.Box(osg.Vec3(), DIE_SIZE))

		die_drawable.vertexAttrib[FACE_ATTRIB_LOCATION] = face_value_array(die_drawable)

		die_geode.drawables.append(die_drawable)
		mt.children.append(die_geode)
		root.children.append(mt)

		die_ss = die_geode.stateSet

		die_ss.attributes.append(die_prog)
		die_ss.textureAttributes[0] = die_tex
		die_ss.uniforms.extend((die_atlas_uniform,))

		dice.append((mt, rest_pos))

	return root, dice

class DiceKeyHandler(osgGA.GUIEventHandler):
	"""Rolls every die on 'r'; holding it spins them at the drop's peak."""

	def __init__(self, dice, rng, rolling, r_held):
		super().__init__()

		self.dice = dice
		self.rng = rng
		self.rolling = rolling
		self.r_held = r_held

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
		roll_all(self.dice, self.rng, self.rolling, self.r_held)

		return True

if __name__ == "__main__":
	parser = argparse.ArgumentParser(description="Roll one to six procedural D6 dice.")
	parser.add_argument(
		"--dice-count",
		type=int,
		choices=range(1, 7),
		default=DICE_COUNT,
		help="number of dice to show (default: %(default)s)",
	)
	args = parser.parse_args()

	osg.setNotifyLevel(osg.NotifySeverity.NOTICE)

	viewer = osgViewer.Viewer()
	viewer.cameraManipulator = osgGA.TrackballManipulator()

	scene, dice = create_scene(args.dice_count)
	rng = random.Random()
	rolling = [False] * len(dice)
	r_held = [False]

	viewer.sceneData = scene
	viewer.eventHandlers.append(DiceKeyHandler(dice, rng, rolling, r_held))

	osg.notice("[pyosg-dice] press 'r' to roll; hold it to spin at the peak")

	roll_all(dice, rng, rolling, r_held)

	while not viewer.done:
		viewer.frame()
