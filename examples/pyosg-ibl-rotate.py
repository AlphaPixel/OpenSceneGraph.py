#!/usr/bin/env python3

"""Sanity check for pyosg_dice.rotate_ibl_environment()'s osgx.Environment rotation --
NOT a real IBL bake. Builds a synthetic 6-face osg.TextureCubeMap by hand - a smooth
per-texel vertical (cubemap-space Y, i.e. OSG world Z/up) gradient, black at the bottom
to white at the top, the SAME on all 6 faces, plus a soft cosine-power "spotlight"
centered on world +X, ADDED ON EVERY FACE as a continuous function of direction (not a
flag on one discrete face) - and mirror-reflects it off an osgx.Cube - 6 flat faces,
easy to eyeball 1:1 against the 6 cubemap faces (unlike a higher-face-count shape, where a
visible facet's reflection is never exactly its own face-normal direction and is harder
to reason about at a glance).

A discrete "this ONE cubemap face is red, the other five aren't" flag was tried first and
rejected: each physical cube face has an exactly constant normal, so at ordinary camera
distances the reflected direction rarely sweeps far enough across ONE face to cross into
a neighboring cubemap face's bucket - you'd see the accent fully on one face and NEVER
bleeding onto its neighbor, even viewed corner-on, which is confusing to read. The smooth
falloff blends continuously across every edge/corner instead, so an edge-on or corner-on
view naturally splits it across the visible faces the way you'd intuitively expect.

The gradient depends only on cubemap Y (world up), and rotate_ibl_environment() only ever
rotates about world Z (see its own docstring) - so the gradient should stay COMPLETELY
STATIONARY as you press 'r', while only the red spotlight sweeps to a new compass position. If
the gradient itself visibly shifts too, that's a real bug in the "rotation never touches
up/down" invariant, not a rendering quirk.

Deliberately bypasses osgx's real bake pipeline (computeLambertianCubeMap/
GGXPrefilterScene.create both take an equirectangular osg.Image, not a cubemap already
in face-space) - this hand-fills 6 gradient faces directly (see direction_for_face(),
the standard per-face inverse-cubemap-projection formulas), wraps it in an osgx.Environment
(as both specular and diffuse map), and samples it with a plain mirror reflection (no
roughness/BRDF/Fresnel), since the only thing under test is osgx::Environment's lookup
direction (osgx_EnvironmentDirection()) under rotation.

Press 'r' to step live through 0/90/180/270 degree rotations.
"""

import argparse

# Also applies the shared example defaults (see pyosg_example.py): OSG_WINDOW/SingleThreaded,
# the GL 4.6 core-profile context, and the osgx.Library.
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
# one face to cross into a neighboring cubemap face's bucket - see the conversation this
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
# per-face (u, v) -> direction convention - they agree. s=t=0 is the image's first
# (lowest-address) row/column, which osg.Image stores bottom-to-top by default, so t=0
# below means cubemap-space v=-1 (bottom), matching GL's own texture origin.
def direction_for_face(face_name, s, t):
	u, v = 2.0 * s - 1.0, 2.0 * t - 1.0

	return {
		"+x": osg.Vec3(1.0, -v, -u), "-x": osg.Vec3(-1.0, -v, u),
		"+y": osg.Vec3(u, 1.0, v), "-y": osg.Vec3(u, -1.0, -v),
		"+z": osg.Vec3(u, -v, 1.0), "-z": osg.Vec3(-u, -v, -1.0),
	}[face_name]

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

# Same eye-space-to-world-space N/V trick as pyosg_dice.py's FRAGMENT_SHADER_IBL, just a plain
# mirror reflection instead of the diffuse+specular PBR combine (nothing here needs roughness/
# metallic/brdfLUT - this is purely a "which direction am I looking" test).
FRAGMENT_SHADER = """
#version 460 core

#pragma osgx::environment ENVIRONMENT_INPUTS, ENVIRONMENT_SAMPLE

in vec3 vNormal;
in vec3 vViewDir;

uniform mat4 osg_ViewMatrix;
// Debug mode: show the raw per-face world-space normal as color instead of the cubemap
// reflection - proves (or disproves) that flat per-face shading survives this shader,
// independent of the cubemap's own 6-color quantization. Press 'n' to toggle.
uniform int debugNormals;
// Diffuse-style mode: sample the SAME cubemap by N instead of the view-dependent
// reflection vector R - exactly how real diffuse IBL differs from specular IBL
// (osgx_EnvironmentIrradiance samples by N too). No view-dependence at all: whichever
// face's normal points closest to the accent direction shows the most accent color,
// full stop, regardless of camera angle. Press 'd' to toggle.
uniform int diffuseView;

out vec4 fragColor;

void main() {
	mat3 invView = transpose(mat3(osg_ViewMatrix));
	vec3 N = invView * normalize(vNormal);
	vec3 V = invView * normalize(vViewDir);

	if (debugNormals != 0) {
		fragColor = vec4(N * 0.5 + 0.5, 1.0);

		return;
	}

	vec3 color = diffuseView != 0
		? osgx_EnvironmentIrradiance(N)
		: osgx_EnvironmentSpecular(reflect(-V, N), 0.0)
	;

	fragColor = vec4(pow(color, vec3(1.0 / 2.2)), 1.0);
}
"""

def gradient_face_image(face_name, size):
	"""An RGBA osg.Image for one cubemap face: per-texel color from the REAL 3D
	direction that texel represents (direction_for_face()) - black at direction.y = -1
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

def set_rotation(environment, degrees):
	"""The same Khronos-viewer starting orientation every glTF consumer uses, then
	rotate_ibl_environment() on top - so `degrees` is always relative to that default."""
	environment.rotation = osgx.gltf.KHRONOS_ENVIRONMENT_ROTATION

	dice.rotate_ibl_environment(environment, degrees)

class RotateKeyHandler(osgGA.GUIEventHandler):
	def __init__(self, environment, degrees):
		super().__init__()

		self.environment = environment
		self.degrees = degrees

	def handle(self, event, action):
		if event.handled or event.type != osgGA.GUIEventAdapter.KEYUP:
			return False

		if event.key not in (ord("r"), ord("R")):
			return False

		self.degrees = (self.degrees + 90) % 360

		set_rotation(self.environment, self.degrees)
		osg.notice(f"[pyosg-ibl-rotate-test] --ibl-rotate {self.degrees}")

		return True

class ToggleUniformKeyHandler(osgGA.GUIEventHandler):
	"""Flips an int 0/1 uniform on a given keypress - shared by 'n' (debugNormals) and
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

# Set by build_scene(), read by configure_viewer() - args.ibl_rotate and the Environment have
# no natural home in the returned Node the way the two uniforms below do (recovered straight
# back out of the geode's own StateSet). Same reason/shape as pyosg-khronos-viewer.py's _args.
_args = None
_environment = None

def build_scene(w, h):
	global _args, _environment

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

	cubemap = build_test_cubemap()

	_environment = osgx.Environment(cubemap, cubemap)

	set_rotation(_environment, _args.ibl_rotate)

	debug_normals_uniform = osg.Uniform("debugNormals", 0)
	diffuse_view_uniform = osg.Uniform("diffuseView", 0)
	ss = geode.stateSet

	ss.attributes.append(osg.Program(name="pyosg-ibl-rotate-test", shaders=(
		osg.Shader(osg.Shader.VERTEX, VERTEX_SHADER),
		osg.Shader(osg.Shader.FRAGMENT, osgx.resolveShaderLibs(FRAGMENT_SHADER)),
	)))
	ss.attributes.append(_environment)
	ss.uniforms.extend((
		debug_normals_uniform,
		diffuse_view_uniform,
	))

	# The shared BRDF LUT's one-time bake pass, if this is the first Environment in the process.
	if _environment.bakeRoot is not None:
		root.children.append(_environment.bakeRoot)
	root.children.append(label("R to rotate", w, h))

	return root

def configure_viewer(viewer, root):
	geode = root.children[0]
	ss = geode.stateSet
	debug_normals_uniform = ss.uniforms["debugNormals"]
	diffuse_view_uniform = ss.uniforms["diffuseView"]

	viewer.eventHandlers.append(RotateKeyHandler(_environment, _args.ibl_rotate))
	viewer.eventHandlers.append(ToggleUniformKeyHandler(debug_normals_uniform, "n", "debugNormals"))
	viewer.eventHandlers.append(ToggleUniformKeyHandler(diffuse_view_uniform, "d", "diffuseView"))

	osg.notice(
		f"[pyosg-ibl-rotate-test] black-to-white vertical gradient on all 6 faces, plus a "
		f"soft red spotlight centered on +X that blends across every edge/corner - "
		f"starting rotation = {_args.ibl_rotate} - "
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
