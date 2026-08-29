#!/usr/bin/env python3

"""A pure-GL take on the Unity "Shapes" library's Voronoi-construction demo:
a field of points where a diagram of cells sweeps into existence left-to-right,
each cell popping in with a little red/pink flourish right as the front passes
it, while everything ahead of the front is still just bare dots.

No vector-line library involved -- one fullscreen quad, one fragment shader.
Points are uploaded once as a flat uniform array; the shader does a brute-force
nearest/second-nearest search per pixel (this is the classic "Worley noise"
cell-boundary trick: d2 - d1 goes to zero exactly on a Voronoi edge). The only
non-obvious bit is how "reveal" is decided: a cell is drawn (edges + fat seed
dot) once ITS SEED's x coordinate falls behind the sweeping frontierX, so the
boundary between a revealed and an unrevealed cell -- which is just wherever
two neighboring cells disagree on being revealed -- automatically traces the
real Voronoi edge between them. That's what makes the front wavy/organic
instead of a plain vertical wipe, with no extra geometry work required.

`--vband N` switches to a second mode: instead of revealing-and-keeping cells
as a frontier sweeps by, only cells whose SEED currently falls within an N-pixel-
wide vertical band are drawn at all -- nothing outside that band renders, not
even the "not yet revealed" dots -- and the band itself just travels left-to-
right on a loop (no ping-pong). Same nearest/second-nearest search, same
per-cell membership test, just windowed instead of accumulating. The leading
(right) edge of the band is a hard clip on the FRAGMENT's own position (the
shockwave's outer rim -- straight, not wavy); the trailing (left) edge stays a
seed-position test, which is what gives it its natural wavy cell-boundary look.

Two more --vband-mode-only options: `--density N` sets the cell count (default
90) -- point generation and the shader's array size both key off this, so it's
threaded through at build time rather than baked in at import. `--fill` paints
each cell's whole interior instead of just its edges+seed dot, for a solid
"energy goo clinging to the rim" mass instead of a wireframe diagram.
"""

import os
import random
import sys

os.environ.setdefault("OSG_WINDOW", "50 50 900 650")

# Import side effect: fills in OSG_THREADING/OSG_GL_* env var defaults (see pyosg_example.py).
# Deliberately after the OSG_WINDOW override above (setdefault() means order between these
# doesn't actually matter, but matching pyosg-khronos-viewer.py's style) and before
# `from OpenSceneGraph import *` -- these need to land before OSG's DisplaySettings reads them.
from pyosg_example import window_size

from OpenSceneGraph import *
from OpenSceneGraph.GL import *

POINT_COUNT = 90 # default cell count; overridden by --density N
SWEEP_PERIOD = 5.0 # seconds for one left->right pass; the sweep then ping-pongs back

FULLSCREEN_VERT = """
#version 330 core

in vec4 osg_Vertex;
in vec2 osg_MultiTexCoord0;

out vec2 uv;

void main() {
	uv = osg_MultiTexCoord0;
	gl_Position = osg_Vertex;
}
"""

# __POINT_COUNT__ is substituted in build_voronoi_hud() with the actual point count
# (so --density threads through) -- GLSL needs a compile-time array size, and the
# shader has no other reason to be a template.
VORONOI_FRAG = """
#version 330 core

#define POINT_COUNT __POINT_COUNT__

uniform vec2 points[POINT_COUNT];
uniform float aspect;
uniform float pixelSize; // world-space size of one output pixel (1.0 / H)
uniform float sweepPeriod;
uniform float sweepMargin;
uniform float osg_SimulationTime;
uniform int bandMode;
uniform float bandWidth; // world-space band width (vband pixels * pixelSize), bandMode only
uniform int fillMode; // bandMode only: paint each cell's whole interior, not just edges+dot

in vec2 uv;

out vec4 fragColor;

float hash21(vec2 p) {
	p = fract(p * vec2(123.34, 456.21));
	p += dot(p, p + 45.32);

	return fract(p.x * p.y);
}

void main() {
	vec2 p = vec2(uv.x * aspect, uv.y);

	float d1 = 1e9;
	float d2 = 1e9;
	int i1 = 0;
	int i2 = 0;

	for (int i = 0; i < POINT_COUNT; i++) {
		float d = distance(p, points[i]);

		if (d < d1) {
			d2 = d1;
			i2 = i1;
			d1 = d;
			i1 = i;
		}
		else if (d < d2) {
			d2 = d;
			i2 = i;
		}
	}

	vec3 col = vec3(1.0);

	if (bandMode != 0) {
		// Single left->right sweep (no ping-pong) of a fixed-width window, membership
		// decided purely by seed x -- nothing persists once the band moves past it.
		float halfBand = bandWidth * 0.5;
		float travelStart = -sweepMargin - halfBand;
		float travelEnd = aspect + sweepMargin + halfBand;
		float bandCenterX = mix(travelStart, travelEnd, fract(osg_SimulationTime / sweepPeriod));

		// Seed-based test gives the trailing (left) edge its natural wavy cell-
		// boundary look -- but it's ONE-SIDED: it only asks "has this cell's seed
		// not yet been left behind", with no upper bound. An upper bound (excluding
		// any cell whose seed is still ahead of the rim) sounds right but isn't --
		// a cell just past the rim can still own a sliver of territory dipping back
		// inside it, and excluding the whole cell left that sliver unpainted (visible
		// as small notches eaten into the fill right at the rim). The rim itself is
		// handled entirely by the fragment's OWN position, independent of seed.
		bool seedPastTrail = points[i1].x > bandCenterX - halfBand;
		bool pastRim = p.x > bandCenterX + halfBand;

		if (seedPastTrail && !pastRim) {
			if (fillMode != 0) {
				// Solid mass instead of a wireframe: every pixel in-cell gets painted,
				// not just the edge/dot -- a per-cell hash gives each patch a slightly
				// different shade (mottled, organic) and a thin darker seam along
				// d2-d1 still separates neighboring cells, like fused tissue.
				float cellShade = hash21(points[i1]);
				vec3 fillColor = mix(vec3(0.55, 0.06, 0.10), vec3(0.85, 0.20, 0.22), cellShade);

				float edgeDist = d2 - d1;
				float lineW = pixelSize * 1.2;
				float seam = 1.0 - smoothstep(0.0, lineW, edgeDist);

				col = mix(fillColor, fillColor * 0.5, seam);
			}
			else {
				float edgeDist = d2 - d1;
				float lineW = pixelSize * 1.4;
				float edge = 1.0 - smoothstep(0.0, lineW, edgeDist);

				col = mix(col, vec3(0.55), edge * 0.85);

				float dotR = pixelSize * 4.0;
				float dot = 1.0 - smoothstep(dotR - pixelSize, dotR, distance(p, points[i1]));

				col = mix(col, vec3(0.15, 0.05, 0.06), dot);
			}
		}

		fragColor = vec4(col, 1.0);

		return;
	}

	float cycle = mod(osg_SimulationTime, sweepPeriod * 2.0);
	float t = cycle < sweepPeriod ? cycle / sweepPeriod : 2.0 - cycle / sweepPeriod;
	float frontierX = mix(-sweepMargin, aspect + sweepMargin, t);

	bool revealedA = points[i1].x < frontierX;
	bool revealedB = points[i2].x < frontierX;

	if (revealedA) {
		// How close this cell's seed is to the sweeping front -- 1 right at the
		// front, fading to 0 for cells that were revealed long ago.
		float sinceReveal = frontierX - points[i1].x;
		float revealT = clamp(1.0 - sinceReveal / 0.10, 0.0, 1.0);

		// Pink wash trailing the front, keyed off screen-space distance so it
		// reads correctly no matter which direction the sweep is moving.
		float wash = 1.0 - clamp(abs(frontierX - p.x) / 0.14, 0.0, 1.0);
		wash *= step(0.0, frontierX - p.x);
		col = mix(col, vec3(1.0, 0.85, 0.86), wash * 0.35);

		// Soft halo around freshly-revealed seeds.
		float haloR = mix(0.0, pixelSize * 26.0, revealT);
		float halo = 1.0 - smoothstep(0.0, haloR, distance(p, points[i1]));
		col = mix(col, vec3(1.0, 0.72, 0.76), halo * revealT * 0.6);

		float edgeDist = d2 - d1;

		if (revealedB) {
			// Interior edge between two revealed cells.
			float lineW = pixelSize * 1.4;
			float edge = 1.0 - smoothstep(0.0, lineW, edgeDist);

			col = mix(col, vec3(0.55), edge * 0.85);
		}
		else {
			// The sweep front itself.
			float lineW = pixelSize * 3.5;
			float edge = 1.0 - smoothstep(0.0, lineW, edgeDist);

			col = mix(col, vec3(0.88, 0.10, 0.16), edge);
		}

		// Seed dot, growing/reddening right as the front passes over it.
		float dotR = mix(pixelSize * 3.0, pixelSize * 8.0, revealT);
		float dot = 1.0 - smoothstep(dotR - pixelSize, dotR, distance(p, points[i1]));
		vec3 dotColor = mix(vec3(0.22, 0.05, 0.06), vec3(0.78, 0.06, 0.09), revealT);

		col = mix(col, dotColor, dot);
	}
	else {
		float dotR = pixelSize * 3.0;
		float dot = 1.0 - smoothstep(dotR - pixelSize, dotR, distance(p, points[i1]));

		col = mix(col, vec3(0.08), dot);
	}

	fragColor = vec4(col, 1.0);
}
"""

def generate_points(count, aspect, margin, max_attempts=50):
	"""Rejection-sample `count` points, spaced apart just enough (relative to the
	resulting typical cell size) to stop near-coincident points from forming
	degenerate sliver cells thinner than the edge lines -- scaled to `count` so
	--density still looks right whether that's 20 cells or 400.
	"""

	area = (aspect + 2.0 * margin) * (1.0 + 2.0 * margin)
	min_dist = 0.5 * (area / count) ** 0.5

	points = []

	for _ in range(count):
		for _ in range(max_attempts):
			x = random.uniform(-margin, aspect + margin)
			y = random.uniform(-margin, 1.0 + margin)

			if all((x - px) ** 2 + (y - py) ** 2 >= min_dist ** 2 for px, py in points):
				break

		points.append((x, y))

	return points

def make_fullscreen_quad():
	geode = osg.Geode(name="fullscreen-quad")

	geode.drawables.append(osg.createTexturedQuadGeometry(
		osg.Vec3(-1.0, -1.0, -1.0),
		osg.Vec3(2.0, 0.0, 0.0),
		osg.Vec3(0.0, 2.0, 0.0),
	))

	return geode

def parse_arg(argv, flag, default):
	"""Return the value following `flag` in argv (cast to type(default)), or default."""

	if flag not in argv:
		return default

	return type(default)(argv[argv.index(flag) + 1])

def parse_vband(argv):
	"""Return the --vband N pixel width from argv, or None if the flag isn't present."""

	if "--vband" not in argv:
		return None

	return float(argv[argv.index("--vband") + 1])

def build_voronoi_hud(points, w, h, vband_px=None, fill=False):
	aspect = w / float(h)

	cam = osg.Camera(name="Voronoi Reveal HUD")

	cam.renderOrder = osg.Camera.POST_RENDER
	cam.clearMask = GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT
	cam.clearColor = osg.Vec4(1.0, 1.0, 1.0, 1.0)
	cam.viewport = osg.Viewport(0, 0, w, h)
	cam.projectionMatrix = osg.Matrix.identity()
	cam.viewMatrix = osg.Matrix.identity()
	cam.referenceFrame = osg.Transform.ABSOLUTE_RF
	cam.allowEventFocus = False

	# POINT_COUNT is baked in here (build time, keyed off the actual point count) rather
	# than at import time, so --density threads through to the shader's array size.
	frag = VORONOI_FRAG.replace("__POINT_COUNT__", str(len(points)))
	prog = osg.Program(name="voronoi_reveal_program", shaders=(
		osg.Shader(osg.Shader.VERTEX, FULLSCREEN_VERT),
		osg.Shader(osg.Shader.FRAGMENT, frag),
	))

	cam.stateSet.attributes[osg.StateAttribute.PROGRAM] = (
		prog, osg.StateAttribute.ON | osg.StateAttribute.OVERRIDE
	)

	points_u = osg.Uniform(osg.Uniform.Type.FLOAT_VEC2, "points", tuple(
		osg.Vec2(x, y) for x, y in points
	))

	cam.stateSet.uniforms.extend((points_u,))
	cam.stateSet.uniforms["aspect"] = aspect
	cam.stateSet.uniforms["pixelSize"] = 1.0 / float(h)
	cam.stateSet.uniforms["sweepPeriod"] = SWEEP_PERIOD
	cam.stateSet.uniforms["sweepMargin"] = 0.08
	cam.stateSet.uniforms["bandMode"] = 1 if vband_px is not None else 0
	cam.stateSet.uniforms["bandWidth"] = (vband_px / float(h)) if vband_px is not None else 0.0
	cam.stateSet.uniforms["fillMode"] = 1 if fill else 0

	cam.children.append(make_fullscreen_quad())

	return cam

# The real pipeline-assembly entrypoint -- returns the root Node, no viewer/window side effects.
# Reads --density/--vband/--fill straight from sys.argv (matching parse_arg()/parse_vband()'s
# existing shape) rather than switching to argparse, so both a standalone run and a runner-driven
# one (which forwards `-- --density N ...` straight into sys.argv[1:], see pyosg-khronos-viewer.py)
# pick these up identically.
def build_scene(w, h):
	aspect = w / float(h)
	margin = 0.05
	density = int(parse_arg(sys.argv, "--density", POINT_COUNT))

	points = generate_points(density, aspect, margin)

	hud = build_voronoi_hud(
		points, w, h,
		vband_px=parse_vband(sys.argv),
		fill="--fill" in sys.argv,
	)

	root = osg.Group()
	root.children.append(hud)

	return root

# The HUD camera clears white and covers the whole viewport every frame -- viewer-level, so it
# needs the live viewer build_scene() never receives.
def configure_viewer(viewer, root):
	viewer.camera.clearColor = osg.Vec4(1.0, 0.0, 1.0, 1.0)

	if "--repl" in sys.argv:
		from pyosg_repl import repl

		repl(viewer, globals())

if __name__ == "__main__":
	W, H = window_size()

	v = osgViewer.Viewer()
	root = build_scene(W, H)

	v.sceneData = root
	v.cameraManipulator = osgGA.TrackballManipulator()

	configure_viewer(v, root)

	while not v.done:
		v.frame()
