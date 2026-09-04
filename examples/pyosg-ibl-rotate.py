#!/usr/bin/env python3

"""Sanity check for pyosg_dice.rotate_ibl_environment()'s 90-degree axis permutation --
NOT a real IBL bake. Builds a synthetic 6-face osg.TextureCubeMap by hand -- a smooth
per-texel vertical (cubemap-space Y, i.e. OSG world Z/up) gradient, black at the bottom
to white at the top, the SAME on all 6 faces, plus a soft cosine-power "spotlight"
centered on world +X, ADDED ON EVERY FACE as a continuous function of direction (not a
flag on one discrete face) -- and mirror-reflects it off an osgx.Cube -- 6 flat faces,
easy to eyeball 1:1 against the 6 cubemap faces (unlike a higher-face-count shape, where a
visible facet's reflection is never exactly its own face-normal direction and is harder
to reason about at a glance).

A discrete "this ONE cubemap face is red, the other five aren't" flag was tried first and
rejected: each physical cube face has an exactly constant normal, so at ordinary camera
distances the reflected direction rarely sweeps far enough across ONE face to cross into
a neighboring cubemap face's bucket -- you'd see the accent fully on one face and NEVER
bleeding onto its neighbor, even viewed corner-on, which is confusing to read. The smooth
falloff blends continuously across every edge/corner instead, so an edge-on or corner-on
view naturally splits it across the visible faces the way you'd intuitively expect.

The gradient depends only on cubemap Y, and rotate_ibl_environment()'s 90-degree steps
only ever permute iblAxis's X/Z rows -- Y is untouched at every step (see its own
docstring) -- so the gradient should stay COMPLETELY STATIONARY as you press 'r', while
only the red spotlight sweeps to a new compass position. If the gradient itself visibly
shifts too, that's a real bug in the "rotation never touches up/down" invariant, not a
rendering quirk.

Deliberately bypasses osgx's real bake pipeline (computeLambertianCubeMap/
GGXPrefilterScene.create both take an equirectangular osg.Image, not a cubemap already
in face-space) -- this hand-fills 6 gradient faces directly (see direction_for_face(),
the standard per-face inverse-cubemap-projection formulas) and samples with a plain
mirror reflection (no roughness/BRDF/Fresnel), since the only thing under test is the
osgx_ZUpToGLTF/osgx_OrientIBL remap itself, ported verbatim from pyosg_dice.py's
FRAGMENT_SHADER_IBL (and osgx::gltf::pbribl's own PBRIBL.cpp shader).

Press 'r' to step live through 0/90/180/270 degree rotations.
"""

import argparse

# Import side effect: fills in OSG_WINDOW/OSG_THREADING/OSG_GL_* env var defaults (see
# pyosg_example.py). Deliberately before `from OpenSceneGraph import *`, matching every other
# example -- these need to land before OSG's DisplaySettings reads them.
from pyosg_example import label, window_size

from OpenSceneGraph import *
from OpenSceneGraph.GL import *

import osgx
import pyosg_dice as dice

RADIUS = 2.0
FACE_SIZE = 32
# A soft, continuous "spotlight" centered on world +X, NOT a discrete cubemap-face flag --
# a flag only ever shows fully on or fully off per physical cube face (each face has an
# exactly constant normal, and the reflected direction rarely sweeps far enough across
# one face to cross into a neighboring cubemap face's bucket -- see the conversation this
# came out of). A smooth cosine-power falloff blends continuously across every face and
# every cubemap seam, so a corner/edge-on view naturally shows it split across neighbors.
ACCENT_DIRECTION = osg.Vec3(1.0, 0.0, 0.0)
ACCENT_COLOR = (0.75, 0.0, 0.0)
ACCENT_POWER = 4.0 # lower = broader/softer spot, higher = tighter/sharper

FACES = {
	"+x": osg.TextureCubeMap.POSITIVE_X, "-x": osg.TextureCubeMap.NEGATIVE_X,
	"+y": osg.TextureCubeMap.POSITIVE_Y, "-y": osg.TextureCubeMap.NEGATIVE_Y,
	"+z": osg.TextureCubeMap.POSITIVE_Z, "-z": osg.TextureCubeMap.NEGATIVE_Z,
}

# Standard inverse cubemap-face projection: texel (s, t), each in [0, 1], to the 3D
# direction on the unit cube that face/texel represents. Cross-checked against both the
# OpenGL spec's direction-to-face table (inverted) and the common LearnOpenGL-style
# per-face (u, v) -> direction convention -- they agree. s=t=0 is the image's first
# (lowest-address) row/column, which osg.Image stores bottom-to-top by default, so t=0
# below means cubemap-space v=-1 (bottom), matching GL's own texture origin.
def direction_for_face(face_name, s, t):
	u, v = 2.0 * s - 1.0, 2.0 * t - 1.0

	return {
		"+x": osg.Vec3(1.0, -v, -u), "-x": osg.Vec3(-1.0, -v, u),
		"+y": osg.Vec3(u, 1.0, v), "-y": osg.Vec3(u, -1.0, -v),
		"+z": osg.Vec3(u, -v, 1.0), "-z": osg.Vec3(-u, -v, -1.0),
	}[face_name]

# The one orthonormal basis every consumer (PBRIBLScene.create()'s glTF shader,
# FRAGMENT_SHADER_IBL, and this test's own shader below) rotates identically via
# dice.rotate_ibl_environment() -- same default osgx::gltf::pbribl ships.
DEFAULT_IBL_AXIS = (
	osg.Vec3(0.0, 0.0, 1.0),
	osg.Vec3(0.0, 1.0, 0.0),
	osg.Vec3(-1.0, 0.0, 0.0),
)

VERTEX_SHADER = """
#version 460 core

in vec4 osg_Vertex;
in vec3 osg_Normal;

uniform mat4 osg_ModelViewProjectionMatrix;
uniform mat4 osg_ModelViewMatrix;
uniform mat3 osg_NormalMatrix;

out vec3 vNormal;
out vec3 vViewDir;

void main() {
	vec4 eyePos = osg_ModelViewMatrix * osg_Vertex;

	vNormal = normalize(osg_NormalMatrix * osg_Normal);
	vViewDir = -eyePos.xyz;

	gl_Position = osg_ModelViewProjectionMatrix * osg_Vertex;
}
"""

# Ported verbatim from pyosg_dice.py's FRAGMENT_SHADER_IBL -- same osgx_ZUpToGLTF/
# osgx_OrientIBL remap, same eye-space-to-world-space N/V trick, just a plain mirror
# reflection instead of the diffuse+specular PBR combine (nothing here needs roughness/
# metallic/brdfLUT -- this is purely a "which direction am I looking" test).
FRAGMENT_SHADER = """
#version 460 core

in vec3 vNormal;
in vec3 vViewDir;

uniform mat4 osg_ViewMatrix;
uniform samplerCube envMap;
uniform vec3 iblAxis[3];
// Debug mode: show the raw per-face world-space normal as color instead of the cubemap
// reflection -- proves (or disproves) that flat per-face shading survives this shader,
// independent of the cubemap's own 6-color quantization. Press 'n' to toggle.
uniform int debugNormals;
// Diffuse-style mode: sample the SAME cubemap by N instead of the view-dependent
// reflection vector R -- exactly how real diffuse IBL differs from specular IBL
// (osgx_LambertianIrradiance samples by N too). No view-dependence at all: whichever
// face's normal points closest to the accent direction shows the most accent color,
// full stop, regardless of camera angle. Press 'd' to toggle.
uniform int diffuseView;

out vec4 fragColor;

vec3 osgx_ZUpToGLTF(vec3 d) { return vec3(d.x, d.z, -d.y); }
vec3 osgx_OrientIBL(vec3 d) {
	return vec3(dot(d, iblAxis[0]), dot(d, iblAxis[1]), dot(d, iblAxis[2]));
}

void main() {
	mat3 invView = transpose(mat3(osg_ViewMatrix));
	vec3 N = invView * normalize(vNormal);
	vec3 V = invView * normalize(vViewDir);

	if (debugNormals != 0) {
		fragColor = vec4(N * 0.5 + 0.5, 1.0);

		return;
	}

	vec3 sampleDir = diffuseView != 0 ? N : reflect(-V, N);
	vec3 color = texture(envMap, osgx_OrientIBL(osgx_ZUpToGLTF(sampleDir))).rgb;

	fragColor = vec4(pow(color, vec3(1.0 / 2.2)), 1.0);
}
"""

def gradient_face_image(face_name, size):
	"""An RGBA osg.Image for one cubemap face: per-texel color from the REAL 3D
	direction that texel represents (direction_for_face()) -- black at direction.y = -1
	(cubemap-space bottom) to white at +1 (top), plus a smooth cosine-power "spotlight"
	centered on ACCENT_DIRECTION, added on EVERY face (not one discrete face) so it blends
	continuously across cube edges/corners. Plain buffer protocol, same technique as
	pyosg_dice.py's build_number_atlas()."""
	img = osg.Image()

	img.allocateImage(size, size, 1, GL_RGBA, GL_UNSIGNED_BYTE)

	view = memoryview(img)
	flat = view.cast("B")
	accent_axis = ACCENT_DIRECTION

	for row in range(size):
		t = (row + 0.5) / size

		for col in range(size):
			s = (col + 0.5) / size
			direction = direction_for_face(face_name, s, t)
			length = (direction.x**2 + direction.y**2 + direction.z**2) ** 0.5
			unit = osg.Vec3(direction.x / length, direction.y / length, direction.z / length)
			gradient = unit.y * 0.5 + 0.5
			cos_angle = max(
				unit.x * accent_axis.x + unit.y * accent_axis.y + unit.z * accent_axis.z, 0.0
			)
			intensity = cos_angle ** ACCENT_POWER
			pixel = bytes(
				int(round(min(gradient + accent * intensity, 1.0) * 255))
				for accent in ACCENT_COLOR
			)
			i = (row * size + col) * 4

			flat[i:i + 3] = pixel
			flat[i + 3] = 255

	return img

def build_test_cubemap():
	cubemap = osg.TextureCubeMap()

	for name, face in FACES.items():
		cubemap.setFace(face, gradient_face_image(name, FACE_SIZE))

	cubemap.filter = (osg.Texture.LINEAR, osg.Texture.LINEAR)
	cubemap.wrap = (osg.Texture.CLAMP_TO_EDGE, osg.Texture.CLAMP_TO_EDGE)

	return cubemap

class Basis:
	"""Just enough of a PBRIBLEnvironment's shape (a single `.iblAxis` list of 3 Vec3)
	for dice.rotate_ibl_environment() to operate on -- this test has no other
	environment resources (envMap/brdfLUT/diffuseEnv/root) to speak of."""

	def __init__(self, axis):
		self.iblAxis = list(axis)

def set_ibl_axis_uniform(uniform, axis):
	"""Update a live FLOAT_VEC3[3] uniform in place -- .array is the flat 9-float
	backing store (no per-Vec3 __setitem__), so write 3 floats per axis and dirty()
	to flag it for re-upload."""
	array = uniform.array

	for i, vec in enumerate(axis):
		array[i * 3 + 0] = vec.x
		array[i * 3 + 1] = vec.y
		array[i * 3 + 2] = vec.z

	uniform.dirty()

class RotateKeyHandler(osgGA.GUIEventHandler):
	def __init__(self, uniform, degrees):
		super().__init__()

		self.uniform = uniform
		self.degrees = degrees

	def handle(self, event, action):
		if event.handled or event.type != osgGA.GUIEventAdapter.KEYUP:
			return False

		if event.key not in (ord("r"), ord("R")):
			return False

		self.degrees = (self.degrees + 90) % 360
		basis = Basis(DEFAULT_IBL_AXIS)

		dice.rotate_ibl_environment(basis, self.degrees)
		set_ibl_axis_uniform(self.uniform, basis.iblAxis)
		osg.notice(f"[pyosg-ibl-rotate-test] --ibl-rotate {self.degrees}")

		return True

class ToggleUniformKeyHandler(osgGA.GUIEventHandler):
	"""Flips an int 0/1 uniform on a given keypress -- shared by 'n' (debugNormals) and
	'd' (diffuseView)."""

	def __init__(self, uniform, key, label):
		super().__init__()

		self.uniform = uniform
		self.key = ord(key)
		self.label = label

	def handle(self, event, action):
		if event.handled or event.type != osgGA.GUIEventAdapter.KEYUP:
			return False

		if event.key not in (self.key, self.key - 32): # also accept the uppercase form
			return False

		self.uniform.value = 1 - self.uniform.value
		osg.notice(f"[pyosg-ibl-rotate-test] {self.label} = {bool(self.uniform.value)}")

		return True

# Set by build_scene(), read by configure_viewer() -- args.ibl_rotate has no natural home in
# the returned Node the way the three uniforms below do (recovered straight back out of the
# geode's own StateSet instead of needing a second stash). Same reason/shape as
# pyosg-khronos-viewer.py's _args.
_args = None

def build_scene(w, h):
	global _args

	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument(
		"--ibl-rotate", type=int, default=0, choices=(0, 90, 180, 270),
		help="initial rotation in degrees (default: %(default)s); press 'r' to step live"
	)
	_args = parser.parse_args()

	root = osg.Group(name="scene")
	geode = osg.Geode(name="test-cube")
	shape = osgx.Cube(radius=RADIUS)

	geode.drawables.append(shape)
	root.children.append(geode)

	basis = Basis(DEFAULT_IBL_AXIS)

	dice.rotate_ibl_environment(basis, _args.ibl_rotate)

	ibl_axis_uniform = osg.Uniform(osg.Uniform.Type.FLOAT_VEC3, "iblAxis", tuple(basis.iblAxis))
	debug_normals_uniform = osg.Uniform("debugNormals", 0)
	diffuse_view_uniform = osg.Uniform("diffuseView", 0)
	ss = geode.stateSet

	ss.attributes.append(osg.Program(name="pyosg-ibl-rotate-test", shaders=(
		osg.Shader(osg.Shader.VERTEX, VERTEX_SHADER),
		osg.Shader(osg.Shader.FRAGMENT, FRAGMENT_SHADER),
	)))
	ss.textureAttributes[0] = build_test_cubemap()
	ss.uniforms.extend((
		osg.Uniform("envMap", 0),
		ibl_axis_uniform,
		debug_normals_uniform,
		diffuse_view_uniform,
	))
	root.children.append(label("R to rotate", w, h))

	return root

def configure_viewer(viewer, root):
	geode = root.children[0]
	ss = geode.stateSet
	ibl_axis_uniform = ss.uniforms["iblAxis"]
	debug_normals_uniform = ss.uniforms["debugNormals"]
	diffuse_view_uniform = ss.uniforms["diffuseView"]

	viewer.eventHandlers.append(RotateKeyHandler(ibl_axis_uniform, _args.ibl_rotate))
	viewer.eventHandlers.append(ToggleUniformKeyHandler(debug_normals_uniform, "n", "debugNormals"))
	viewer.eventHandlers.append(ToggleUniformKeyHandler(diffuse_view_uniform, "d", "diffuseView"))

	osg.notice(
		f"[pyosg-ibl-rotate-test] black-to-white vertical gradient on all 6 faces, plus a "
		f"soft red spotlight centered on +X that blends across every edge/corner -- "
		f"starting rotation = {_args.ibl_rotate} -- "
		f"'r' steps 90 degrees (gradient should stay put, only the red spot should sweep), "
		f"'n' toggles a per-face-normal debug view, "
		f"'d' toggles diffuse-style (view-independent, sampled by N not R) shading"
	)

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
