#!/usr/bin/env python3

"""Procedural "celestial body" sketch: a single sphere shaded entirely by 3D noise keyed on its
own object-space normal (no UV, no displacement - the vessel this is meant for never lands), plus
a second, slightly larger sphere for clouds. Three layers:

1. Surface - a low-octave 3D FBM (simplex13/fbm13 below, lifted from pyosg-noise.py's own 3D noise
   block, same MIT-licensed hash33/simplex13) evaluated at the fragment's normalized object-space
   position. Habitable preset thresholds it into ocean/land; gas giant preset turns the same FBM
   value into a latitude-band warp instead.
2. Detail - a second, higher-frequency FBM added at low amplitude on top of layer 1, in the SAME
   fragment shader and on the SAME geometry - it is a second octave group, not a second mesh.
3. Clouds - a separate sphere (radius * CLOUD_RADIUS_SCALE), its own Program, alpha-blended over
   layer 1+2 from its own independent FBM. This is the only layer that needs its own geometry,
   since it needs independent alpha compositing above the surface.

Keying noise off the object-space normal instead of a lat/long UV means pole-pinching is never a
concern for the shading itself, regardless of mesh topology - a lat/long UV-mapped sphere (like
osgSlug's SphereDrawable) would still need real UVs for texture/decal content, but this file never
samples a 2D UV at all. The geometry comes from build_sphere_geometry() below, an icosphere (see
its own comment) built specifically to avoid two separate failure modes a lat/long
osg.ShapeDrawable(osg.Sphere(...)) has: its GL_QUAD_STRIP latitude rings (removed from core-profile
GL 3.2+; this example runs GL 4.6 core) and its pole singularity (degenerate triangles converging
at 2 points). An icosphere has neither.

Run standalone:

	./pyosg-planet.py

Run through the Qt-free example runner (build_scene(w, h) is this file's runnable contract - see
../pyosg-cli and examples/pyosg-blur.py's own build_scene() for the convention):

	../pyosg-cli planet
"""

import math
import os
import time

os.environ.setdefault("OSG_WINDOW", "50 50 800 600")

# Shared example defaults: SingleThreaded, the GL 4.6 core-profile context, and the osgx.Library.
import pyosg_example

from OpenSceneGraph import *
from OpenSceneGraph.GL import *

import osgx

# World-space radius of the surface sphere; the cloud shell sits CLOUD_RADIUS_SCALE times
# farther out, just enough to clear the surface without a visible gap at any zoom this example's
# TrackballManipulator can reach.
SURFACE_RADIUS = 2.0
CLOUD_RADIUS_SCALE = 1.03

# How many times to recursively split each icosahedron triangle into 4 - see
# build_sphere_geometry() below. Face count is 20 * 4^n (n=5 -> 20480 triangles, ~10242 vertices).
# A sphere built from a small fixed number of independently-parameterized flat patches (e.g. 6
# cube faces, each with its own (right, up) basis) has a fold at every patch boundary whose angle
# is set by the patch count, not by how finely each patch is subdivided internally - more triangles
# per patch shrinks facet size there but never the fold itself. An icosphere instead produces every
# vertex (past the initial 12) via the same shared-midpoint split applied uniformly to every edge
# in the mesh, so the fold angle at EVERY edge - there is no separate "patch boundary" category -
# shrinks together with facet size as subdivision level increases.
ICOSPHERE_SUBDIVISIONS = 5

_PHI = (1.0 + 5.0 ** 0.5) / 2.0

# The 12 vertices of a regular icosahedron (unnormalized - build_sphere_geometry() normalizes
# everything onto the unit sphere before scaling by radius) and its 20 triangular faces, CCW
# winding when viewed from outside.
_ICOSAHEDRON_VERTICES = (
	(-1, _PHI, 0), (1, _PHI, 0), (-1, -_PHI, 0), (1, -_PHI, 0),
	(0, -1, _PHI), (0, 1, _PHI), (0, -1, -_PHI), (0, 1, -_PHI),
	(_PHI, 0, -1), (_PHI, 0, 1), (-_PHI, 0, -1), (-_PHI, 0, 1),
)

_ICOSAHEDRON_FACES = (
	(0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11),
	(1, 5, 9), (5, 11, 4), (11, 10, 2), (10, 7, 6), (7, 1, 8),
	(3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8), (3, 8, 9),
	(4, 9, 5), (2, 4, 11), (6, 2, 10), (8, 6, 7), (9, 8, 1),
)

# Builds an icosphere (recursive 4-way triangle split of a regular icosahedron, each new edge
# midpoint normalized onto the unit sphere and cached so the two triangles sharing an edge
# reference the exact SAME vertex, not two independently-computed-but-equal ones) instead of a
# cube-sphere. Replaces the earlier cube-sphere entirely rather than warping it further - no
# per-face basis, so there is no boundary between independently-parameterized patches for a fold
# to form at in the first place. Also replaces the original osg.ShapeDrawable(osg.Sphere(...)),
# whose lat/long tessellation closes each latitude ring as a GL_QUAD_STRIP (see
# BuildShapeGeometryVisitor::apply(const Sphere&) in OSG's own src/osg/Shape.cpp), a primitive
# removed from core-profile GL 3.2+; this example runs GL 4.6 core. Plain GL_TRIANGLES throughout,
# no closing seam, no pole singularity (an icosphere has no poles at all).
def build_sphere_geometry(radius, subdivisions=ICOSPHERE_SUBDIVISIONS):
	vertices = [osg.Vec3(*v).normalized() for v in _ICOSAHEDRON_VERTICES]
	faces = list(_ICOSAHEDRON_FACES)
	# Which of the 20 base icosahedron faces each current face descended from - carried through
	# subdivision purely for the uDebugMode==3 "Face ID" debug view below; not used for shading.
	face_origin = list(range(len(_ICOSAHEDRON_FACES)))

	midpoint_cache = {}

	def midpoint(i0, i1):
		key = (i0, i1) if i0 < i1 else (i1, i0)
		index = midpoint_cache.get(key)

		if index is None:
			index = len(vertices)
			vertices.append(((vertices[i0] + vertices[i1]) * 0.5).normalized())
			midpoint_cache[key] = index

		return index

	for _ in range(subdivisions):
		new_faces = []
		new_origin = []

		for (a, b, c), origin in zip(faces, face_origin):
			ab, bc, ca = midpoint(a, b), midpoint(b, c), midpoint(c, a)

			new_faces.extend(((a, ab, ca), (b, bc, ab), (c, ca, bc), (ab, bc, ca)))
			new_origin.extend((origin, origin, origin, origin))

		faces = new_faces
		face_origin = new_origin

	# First triangle to touch a given vertex decides its debug face id - approximate at shared
	# vertices (most vertices border several triangles, possibly from different base faces), good
	# enough for the debug coloring it's used for.
	vertex_origin = [None] * len(vertices)

	for (a, b, c), origin in zip(faces, face_origin):
		for i in (a, b, c):
			if vertex_origin[i] is None:
				vertex_origin[i] = origin

	geom = osg.Geometry(
		vertexArray=osg.Vec3Array([v * radius for v in vertices]),
		primitiveSets=(osg.DrawElementsUInt(osg.PrimitiveSet.TRIANGLES, [i for f in faces for i in f]),),
	)

	# faceID (location 1) - which base icosahedron face a vertex first appeared on, read back in
	# the surface fragment shader's uDebugMode==3 view.
	face_id_array = osg.FloatArray([float(o) for o in vertex_origin])
	face_id_array.binding = osg.Array.BIND_PER_VERTEX
	geom.vertexAttrib[1] = face_id_array

	return geom

VERTEX_SHADER = """
#version 430 core

in vec4 osg_Vertex;
in float faceID;

uniform mat4 osg_ModelViewProjectionMatrix;

// Object-space position - for a Sphere centered at its own local origin (both geodes below are),
// normalize(vPos) IS the surface normal, so no separate osg_Normal attribute is needed at all.
out vec3 vPos;
out float vFaceID;

void main() {
	vPos = osg_Vertex.xyz;
	vFaceID = faceID;

	gl_Position = osg_ModelViewProjectionMatrix * osg_Vertex;
}
"""

# SPDX-License-Identifier: MIT
# Copyright (c) 2026 @lumiey
# hash33/simplex13 lifted verbatim from pyosg-noise.py's own 3D noise block (same license header
# there) - fbm13 is a 3-argument-parameterized version of that file's fbm12, extended to 3D.
#
# perlin13 (pyosg-noise.py's other 3D option) was tried first and dropped: its gradient is
# normalize(hash33(...) - 0.5), which goes numerically unstable whenever hash33() lands near
# exactly (0.5, 0.5, 0.5) - normalizing a near-zero vector. That's rare per-lattice-corner, but a
# sphere's surface sweeps through enough lattice cells that it reliably hits one, and the bad
# gradient doesn't stay a single-pixel glitch - bilinear interpolation spreads it across that
# whole cell, which confirmed live as a sharp-edged, flatter-than-everything-around-it patch (not
# a geometry hole: same artifact, same screen position, independent of mesh tessellation density,
# see this session's own investigation). simplex13 reads hash33() output directly in a dot()
# instead of normalizing it, so the same near-(0.5,0.5,0.5) case just contributes ~0 to that
# corner - degrades smoothly instead of blowing up.
NOISE_GLSL = """
vec3 hash33(vec3 p) {
	uvec3 u = floatBitsToUint(p * vec3(141421356, 2718281828, 1618033988));
	return vec3((u.x ^ u.y ^ u.z) * uvec3(1732050807, 2645751311, 3316624790)) / float(~0u);
}

float simplex13(vec3 p) {
	vec3 s = floor(p + dot(p, vec3(1.0 / 3.0)));
	vec3 x = p - s + dot(s, vec3(1.0 / 6.0));
	vec3 e = step(vec3(0), x - x.yzx);
	vec3 i1 = e * (1.0 - e.zxy);
	vec3 i2 = 1.0 - e.zxy * (1.0 - e);
	vec3 x1 = x - i1 + 1.0 / 6.0;
	vec3 x2 = x - i2 + 1.0 / 3.0;
	vec3 x3 = x - 0.5;
	vec4 w = vec4(dot(x, x), dot(x1, x1), dot(x2, x2), dot(x3, x3));
	w = max(0.6 - w, 0.0);
	vec4 d = vec4(
		dot(hash33(s) - 0.5, x),
		dot(hash33(s + i1) - 0.5, x1),
		dot(hash33(s + i2) - 0.5, x2),
		dot(hash33(s + 1.0) - 0.5, x3)
	);
	w *= w;
	w *= w;
	d *= w;
	return dot(d, vec4(26)) + 0.5;
}

float fbm13(vec3 p, int octaves, float lacunarity, float gain) {
	float s = 0.0, m = 0.0, a = 1.0;

	for (int i = 0; i < octaves; i++) {
		s += a * simplex13(p);
		m += a;
		a *= gain;
		p *= lacunarity;
	}

	return s / m;
}
"""

# Object-space gradient of fbm13 at p (forward difference, NOT dFdx/dFdy - a screen-space
# quantity that would make bump strength vary with zoom/resolution instead of being a fixed
# property of the noise field itself), projected onto the tangent plane around N - the
# component along N isn't a "slope" in any direction a surface could actually tilt toward.
# Surface-shader-only (clouds don't use it), kept separate from NOISE_GLSL for that reason.
BUMP_GLSL = """
vec3 perturbNormal(vec3 N, vec3 p, float center, float strength) {
	float eps = 0.01;
	float dx = fbm13(p + vec3(eps, 0.0, 0.0), 4, 2.0, 0.5) - center;
	float dy = fbm13(p + vec3(0.0, eps, 0.0), 4, 2.0, 0.5) - center;
	float dz = fbm13(p + vec3(0.0, 0.0, eps), 4, 2.0, 0.5) - center;
	vec3 grad = vec3(dx, dy, dz) / eps;
	vec3 tangentGrad = grad - dot(grad, N) * N;

	return normalize(N - tangentGrad * strength);
}
"""

SURFACE_FRAGMENT_SHADER = "#version 430 core\n" + NOISE_GLSL + BUMP_GLSL + """
in vec3 vPos;
in float vFaceID;

// 0 = shaded body (normal rendering below), 1 = raw layer-1 FBM as grayscale, 2 = screen-space
// derivative of that FBM as a heatmap (crease artifacts show up as a bright line independent of
// the color/threshold logic below), 3 = flat color per base icosahedron face (see
// build_sphere_geometry()'s vertex_origin - mesh-construction debugging, not shading).
uniform int uDebugMode;

// 0 = habitable (elevation thresholded into ocean/land), 1 = gas giant (latitude-band warp).
uniform int uBodyType;
uniform float uScale;
uniform int uOctaves;
uniform float uLacunarity;
uniform float uGain;
uniform float uDetailScale;
uniform float uDetailStrength;
uniform float uBumpStrength;
uniform float uSeaLevel;
uniform vec3 uColorDeep;
uniform vec3 uColorShallow;
uniform vec3 uColorLand;
uniform vec3 uColorHigh;
uniform vec3 uBandColorA;
uniform vec3 uBandColorB;
uniform float uBandFrequency;
uniform float uBandWarp;
uniform vec3 uLightDir;

out vec4 fragColor;

void main() {
	vec3 N = normalize(vPos);

	// Layer 1: surface FBM, same value feeds both presets below.
	float elevation = fbm13(N * uScale, uOctaves, uLacunarity, uGain);

	// Layer 2: a second, higher-frequency octave group blended in at low amplitude - same
	// geometry, same fragment, just a different (scale, octaves) pair fed through fbm13 again.
	float detail = fbm13(N * uDetailScale, 4, 2.0, 0.5) - 0.5;

	if (uDebugMode == 1) {
		fragColor = vec4(vec3(elevation), 1.0);
		return;
	}

	if (uDebugMode == 2) {
		// A flat `grad * k` saturates to solid white across a wide range of real discontinuity
		// magnitudes, hiding exactly the differences this view exists to show (a linear scale that
		// separates small residual seams clips large ones to the same white as small ones). This
		// exponential tonemap keeps mid-range values visually distinct instead of all-or-nothing.
		float grad = length(vec2(dFdx(elevation), dFdy(elevation)));

		fragColor = vec4(vec3(1.0 - exp(-grad * 2.0)), 1.0);
		return;
	}

	if (uDebugMode == 3) {
		float hue = vFaceID / 20.0;

		fragColor = vec4(0.5 + 0.5 * cos(6.28318 * (hue + vec3(0.0, 0.33, 0.67))), 1.0);
		return;
	}

	vec3 color;
	// Scales uBumpStrength below - 1 where the bump should show (land), 0 where it shouldn't
	// (open ocean reads as smooth/reflective at this scale, not rocky). Gas giant has no such
	// split, so it stays at full strength throughout its own branch.
	float bumpMask = 1.0;

	if (uBodyType == 0) {
		float e = elevation + detail * uDetailStrength;

		// Same elevation/uSeaLevel test the color mix below already uses, reused as a material
		// mask instead of a second procedural system - this IS what "land vs. ocean" already
		// means here.
		bumpMask = smoothstep(uSeaLevel - 0.02, uSeaLevel + 0.02, e);

		if (e < uSeaLevel) {
			color = mix(uColorDeep, uColorShallow, smoothstep(uSeaLevel - 0.15, uSeaLevel, e));
		} else {
			color = mix(uColorLand, uColorHigh, smoothstep(uSeaLevel, uSeaLevel + 0.35, e));
		}
	} else {
		// N.z is the latitude axis - Z is this scene's pole axis (see build_sphere_geometry()'s
		// cube-face table) - the FBM warp term is what breaks the bands into turbulent
		// storm-like boundaries.
		float band = N.z * uBandFrequency + (elevation - 0.5) * uBandWarp;

		color = mix(uBandColorA, uBandColorB, sin(band * 3.14159265) * 0.5 + 0.5);
		color += detail * uDetailStrength;
	}

	// The detail layer above only perturbs COLOR - without this, lighting still sees the raw
	// smooth geometric normal, so all that high-frequency noise can only ever read as a flat
	// tint, never as relief. Reuses the same detail-layer fbm13 call (same uDetailScale), not a
	// third noise system. bumpMask keeps it off open ocean.
	vec3 shadingN = perturbNormal(N, N * uDetailScale, detail + 0.5, uBumpStrength * bumpMask);

	float diffuse = max(dot(shadingN, normalize(uLightDir)), 0.0);

	fragColor = vec4(color * (0.25 + 0.75 * diffuse), 1.0);
}
"""

CLOUD_FRAGMENT_SHADER = "#version 430 core\n" + NOISE_GLSL + """
in vec3 vPos;

uniform float uScale;
uniform int uOctaves;
uniform float uLacunarity;
uniform float uGain;
uniform float uCoverage;
uniform float uSoftness;
uniform float uTime;
uniform float uSpeed;
uniform vec3 uColor;
uniform vec3 uLightDir;

out vec4 fragColor;

void main() {
	vec3 N = normalize(vPos);

	// Domain scroll over time stands in for planetary rotation relative to the cloud deck -
	// cheaper than actually spinning the geometry, and exactly as convincing from a vessel's
	// flyby distance.
	vec3 p = N * uScale + vec3(uTime * uSpeed, 0.0, 0.0);
	float n = fbm13(p, uOctaves, uLacunarity, uGain);
	float alpha = smoothstep(uCoverage - uSoftness, uCoverage + uSoftness, n);
	float diffuse = max(dot(N, normalize(uLightDir)), 0.0);

	fragColor = vec4(uColor * (0.4 + 0.6 * diffuse), alpha);
}
"""

# DEFAULTS double as the preset data AND the "Reset"/preset-switch source of truth - same shape
# as pyosg-noise.py's GLOBAL_DEFAULTS/WAVELET_DEFAULTS. Every key exists in BOTH presets (even the
# ones only one body type's shader branch reads) so switching presets never leaves a stale value
# from the other branch behind.
HABITABLE_DEFAULTS = {
	"uBodyType": 0,
	"uScale": 2.0,
	"uOctaves": 6,
	"uLacunarity": 2.0,
	"uGain": 0.5,
	"uDetailScale": 14.0,
	"uDetailStrength": 0.12,
	"uBumpStrength": 0.35,
	"uSeaLevel": 0.52,
	"uColorDeep": osg.Vec3(0.02, 0.08, 0.28),
	"uColorShallow": osg.Vec3(0.06, 0.35, 0.55),
	"uColorLand": osg.Vec3(0.30, 0.42, 0.16),
	"uColorHigh": osg.Vec3(0.55, 0.52, 0.45),
	"uBandColorA": osg.Vec3(0.82, 0.68, 0.48),
	"uBandColorB": osg.Vec3(0.55, 0.35, 0.22),
	"uBandFrequency": 6.0,
	"uBandWarp": 1.0,
	"uLightDir": osg.Vec3(0.4, 0.6, 0.7),
}

GAS_GIANT_DEFAULTS = {
	"uBodyType": 1,
	"uScale": 1.5,
	"uOctaves": 5,
	"uLacunarity": 2.0,
	"uGain": 0.55,
	"uDetailScale": 10.0,
	"uDetailStrength": 0.18,
	"uBumpStrength": 0.35,
	"uSeaLevel": 0.52,
	"uColorDeep": osg.Vec3(0.02, 0.08, 0.28),
	"uColorShallow": osg.Vec3(0.06, 0.35, 0.55),
	"uColorLand": osg.Vec3(0.30, 0.42, 0.16),
	"uColorHigh": osg.Vec3(0.55, 0.52, 0.45),
	"uBandColorA": osg.Vec3(0.86, 0.72, 0.52),
	"uBandColorB": osg.Vec3(0.55, 0.33, 0.20),
	"uBandFrequency": 7.0,
	"uBandWarp": 1.4,
	"uLightDir": osg.Vec3(0.4, 0.6, 0.7),
}

CLOUD_DEFAULTS = {
	"uScale": 3.0,
	"uOctaves": 5,
	"uLacunarity": 2.0,
	"uGain": 0.5,
	"uCoverage": 0.55,
	"uSoftness": 0.08,
	"uTime": 0.0,
	"uSpeed": 0.03,
	"uColor": osg.Vec3(1.0, 1.0, 1.0),
	"uLightDir": osg.Vec3(0.4, 0.6, 0.7),
}

# The real pipeline-assembly entrypoint - returns the root Node, no viewer/window side effects.
# See pyosg-blur.py's own build_scene() for the convention. Returns a Group of [surface, clouds] -
# configure_viewer() below unpacks root.children in that order to recover both geodes.
def build_scene(w, h):
	surface_program = osg.Program(name="pyosg-planet-surface", shaders=(
		osg.Shader(osg.Shader.VERTEX, VERTEX_SHADER),
		osg.Shader(osg.Shader.FRAGMENT, SURFACE_FRAGMENT_SHADER),
	))
	surface_program.bindAttribLocation["faceID"] = 1

	cloud_program = osg.Program(name="pyosg-planet-clouds", shaders=(
		osg.Shader(osg.Shader.VERTEX, VERTEX_SHADER),
		osg.Shader(osg.Shader.FRAGMENT, CLOUD_FRAGMENT_SHADER),
	))
	cloud_program.bindAttribLocation["faceID"] = 1

	surface_geode = osg.Geode(name="Surface", drawables=(
		build_sphere_geometry(SURFACE_RADIUS),
	))
	ss = surface_geode.stateSet

	ss.attributes.append(surface_program)
	ss.modes[GL_CULL_FACE] = osg.StateAttribute.ON

	for name, value in HABITABLE_DEFAULTS.items():
		ss.uniforms[name] = value

	# Not part of HABITABLE_DEFAULTS/GAS_GIANT_DEFAULTS - apply_preset() only loops over those, so
	# a body-type switch never resets the debug view.
	ss.uniforms["uDebugMode"] = 0

	cloud_geode = osg.Geode(name="Clouds", drawables=(
		build_sphere_geometry(SURFACE_RADIUS * CLOUD_RADIUS_SCALE),
	))
	css = cloud_geode.stateSet

	css.attributes.append(cloud_program)
	css.modes[GL_CULL_FACE] = osg.StateAttribute.ON
	css.modes[GL_BLEND] = osg.StateAttribute.ON
	css.attributes.append(osg.BlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA))
	# writeMask=False - clouds never occlude anything behind them in depth, only the surface's
	# own color; avoids depth-fighting the surface sphere it sits just outside of.
	css.attributes.append(osg.Depth(osg.Depth.LESS, 0.0, 1.0, False))
	css.renderingHint = osg.StateSet.TRANSPARENT_BIN

	for name, value in CLOUD_DEFAULTS.items():
		css.uniforms[name] = value

	root = osg.Group(name="pyosg-planet")

	root.children.append(surface_geode)
	root.children.append(cloud_geode)

	return root

# ImGui/time-update are viewer-level concerns, kept out of build_scene() - same split as
# pyosg-noise.py's build_scene()/configure_viewer().
def configure_viewer(viewer, root):
	surface_geode, cloud_geode = root.children

	gui = osgx.imgui.Widget(viewer)

	body_index = [0]

	def apply_preset(defaults):
		for name, value in defaults.items():
			surface_geode.stateSet.uniforms[name] = value

	def draw_body(ri):
		changed, idx = osgx.imgui.radio_group(body_index[0], ["Habitable", "Gas Giant"])

		if changed:
			body_index[0] = idx

			apply_preset(HABITABLE_DEFAULTS if idx == 0 else GAS_GIANT_DEFAULTS)

		osgx.imgui.separator()

		uniforms = surface_geode.stateSet.uniforms

		changed, value = osgx.imgui.slider_float("Scale", uniforms["uScale"].value, 0.5, 6.0)
		if changed: uniforms["uScale"] = value

		changed, value = osgx.imgui.slider_float(
			"Octaves", float(uniforms["uOctaves"].value), 1.0, 8.0, "%.0f"
		)
		if changed: uniforms["uOctaves"] = int(round(value))

		changed, value = osgx.imgui.slider_float(
			"Detail Strength", uniforms["uDetailStrength"].value, 0.0, 0.5
		)
		if changed: uniforms["uDetailStrength"] = value

		changed, value = osgx.imgui.slider_float(
			"Bump Strength", uniforms["uBumpStrength"].value, 0.0, 1.5
		)
		if changed: uniforms["uBumpStrength"] = value

		osgx.imgui.separator()

		changed, value = osgx.imgui.slider_float(
			"Sea Level##habitable", uniforms["uSeaLevel"].value, 0.2, 0.8
		)
		if changed: uniforms["uSeaLevel"] = value

		changed, value = osgx.imgui.slider_float(
			"Band Frequency##gasgiant", uniforms["uBandFrequency"].value, 1.0, 16.0
		)
		if changed: uniforms["uBandFrequency"] = value

		changed, value = osgx.imgui.slider_float(
			"Band Warp##gasgiant", uniforms["uBandWarp"].value, 0.0, 3.0
		)
		if changed: uniforms["uBandWarp"] = value

	gui.addSection("Body", draw_body, osgx.imgui.SectionOptions(default_open=True))

	debug_mode = [0]
	debug_labels = ["Normal", "Raw Noise", "Derivative", "Face ID"]

	def draw_debug(ri):
		changed, idx = osgx.imgui.radio_group(debug_mode[0], debug_labels)

		if changed:
			debug_mode[0] = idx

			surface_geode.stateSet.uniforms["uDebugMode"] = idx

	gui.addSection("Debug", draw_debug, osgx.imgui.SectionOptions(default_open=False))

	def draw_clouds(ri):
		uniforms = cloud_geode.stateSet.uniforms

		changed, value = osgx.imgui.slider_float("Coverage", uniforms["uCoverage"].value, 0.0, 1.0)
		if changed: uniforms["uCoverage"] = value

		changed, value = osgx.imgui.slider_float("Softness", uniforms["uSoftness"].value, 0.01, 0.3)
		if changed: uniforms["uSoftness"] = value

		changed, value = osgx.imgui.slider_float(
			"Scroll Speed", uniforms["uSpeed"].value, 0.0, 0.2
		)
		if changed: uniforms["uSpeed"] = value

		color = uniforms["uColor"].value
		changed, r, g, b = osgx.imgui.color_edit3("Color##clouds", color.x, color.y, color.z)
		if changed: uniforms["uColor"] = osg.Vec3(r, g, b)

	gui.addSection("Clouds", draw_clouds, osgx.imgui.SectionOptions(default_open=True))

	# Cloud time advance only - an update callback instead of a Python-side loop, so this runs
	# correctly under any frame-loop driver (../pyosg-cli, this file's own __main__, or a future
	# Qt-embedded host). Same shape as pyosg-noise.py's own u_time update callback.
	elapsed = [0.0]
	last_time = [time.time()]

	def update(node, nv):
		now = time.time()

		elapsed[0] += now - last_time[0]
		last_time[0] = now

		cloud_geode.stateSet.uniforms["uTime"] = float(elapsed[0])

		return True

	cloud_geode.updateCallback = update

if __name__ == "__main__":
	osg.setNotifyLevel(osg.NotifySeverity.NOTICE)

	viewer = osgViewer.Viewer()
	root = build_scene(*pyosg_example.window_size())

	viewer.sceneData = root
	viewer.cameraManipulator = osgGA.TrackballManipulator()
	viewer.camera.clearColor = osg.Vec4(0.02, 0.02, 0.04, 1.0)

	configure_viewer(viewer, root)

	while not viewer.done:
		viewer.frame()
