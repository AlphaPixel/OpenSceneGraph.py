#!/usr/bin/env python3

# Procedural crosshatch/ink shading as a fullscreen-quad PoC -- three angled hatchFamily()
# layers, each keyed off a synthetic left-dark/right-light lighting field plus a soft highlight
# spot, warped/broken/dropped-out so the strokes read as hand-drawn rather than mathematically
# perfect stripes. Every constant that shaped the original one-off (angles, spacing, warp/break/
# nib thresholds, the synthetic light field itself) is now a live osgx.imgui knob, grouped into
# sections below, so the stylistic range of the technique can be explored interactively instead
# of by editing and re-running.

import random
import time

# Import side effect: fills in OSG_WINDOW/OSG_THREADING/OSG_GL_* env var defaults (see
# pyosg_example.py). Deliberately before `from OpenSceneGraph import *`, matching every other
# example -- these need to land before OSG's DisplaySettings reads them.
from pyosg_example import window_size

from OpenSceneGraph import *
from OpenSceneGraph.GL import *

import osgx

VERTEX_SHADER = """
#version 430 core
out vec2 uv;
void main() {
	vec2 base[4] = vec2[4](
		vec2(-1.0, -1.0),
		vec2(1.0, -1.0),
		vec2(1.0, 1.0),
		vec2(-1.0, 1.0)
	);
	gl_Position = vec4(base[gl_VertexID % 4], 0.0, 1.0);
	uv = vec2(gl_Position.x, gl_Position.y);
}
"""

FRAGMENT_SHADER = """
#version 430 core

in vec2 uv;
out vec4 fragColor;

uniform vec3 paperColor;
uniform vec3 inkColor;

uniform float lumDark;
uniform float lumLight;
uniform float spotX;
uniform float spotY;
uniform float spotIntensity;
uniform float spotSharpness;
uniform float darknessNoiseAmp;

uniform float warpAmount;
uniform float rowJitter;
uniform float widthJitter;
uniform float breakLow;
uniform float breakHigh;
uniform float nibLow;
uniform float nibHigh;

uniform float h1Angle, h1Spacing, h1Thickness, h1Seed, h1OnsetLow, h1OnsetHigh;
uniform float h2Angle, h2Spacing, h2Thickness, h2Seed, h2OnsetLow, h2OnsetHigh;
uniform float h3Angle, h3Spacing, h3Thickness, h3Seed, h3OnsetLow, h3OnsetHigh;

float hash21(vec2 p)
{
	p = fract(p * vec2(123.34, 456.21));
	p += dot(p, p + 45.32);
	return fract(p.x * p.y);
}

float valueNoise(vec2 p)
{
	vec2 i = floor(p);
	vec2 f = fract(p);
	f = f * f * (3.0 - 2.0 * f);

	float a = hash21(i);
	float b = hash21(i + vec2(1.0, 0.0));
	float c = hash21(i + vec2(0.0, 1.0));
	float d = hash21(i + vec2(1.0, 1.0));

	return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
}

float fbm(vec2 p)
{
	float v = 0.0;
	float a = 0.5;

	for (int i = 0; i < 4; ++i) {
		v += a * valueNoise(p);
		p = p * 2.03 + vec2(17.1, 9.2);
		a *= 0.5;
	}

	return v;
}

mat2 rot(float a)
{
	float c = cos(a);
	float s = sin(a);
	return mat2(c, -s, s, c);
}

float hatchFamily(vec2 p, float angle, float spacing, float thickness, float seed)
{
	vec2 q = rot(angle) * p;

	// Large-scale distortion: keep the strokes from looking ruler-straight.
	float warp = warpAmount * (
		(fbm(q * 0.035 + seed) - 0.5) * 5.0 +
		(fbm(q * 0.11 + seed * 2.7) - 0.5) * 1.2
	);

	q.y += warp;

	float row = floor(q.y / spacing);
	float localY = mod(q.y, spacing) - spacing * 0.5;

	// Per-stroke spacing/width variation.
	float rowRnd = hash21(vec2(row, seed));
	float width = thickness * mix(1.0 - widthJitter, 1.0 + widthJitter, rowRnd);

	localY += (hash21(vec2(row, seed + 13.0)) - 0.5) * spacing * rowJitter;

	float aa = max(fwidth(localY), 0.75);
	float line = 1.0 - smoothstep(width, width + aa, abs(localY));

	// Break strokes along their length. This is the part that keeps the
	// result from reading as mathematically perfect parallel stripes.
	float along =
		0.68 * fbm(vec2(q.x * 0.055, row * 0.37 + seed * 7.0)) +
		0.32 * fbm(vec2(q.x * 0.17 + 31.0, row * 1.91));

	float broken = smoothstep(breakLow, breakHigh, along);

	// Fine nib/dropout variation.
	float nib =
		valueNoise(vec2(q.x * 0.42, q.y * 0.31) + seed * 19.0);
	nib = smoothstep(nibLow, nibHigh, nib);

	return line * broken * nib;
}

void main()
{
	vec2 st = uv * 0.5 + 0.5;

	// Work in roughly pixel-sized units.
	vec2 p = st * vec2(800.0, 600.0);

	// Synthetic lighting field for the PoC:
	// dark on the left, bright on the right, plus a soft highlight.
	float lum = mix(lumDark, lumLight, st.x);

	vec2 d = st - vec2(spotX, spotY);
	float spot = exp(-spotSharpness * dot(d, d));
	lum = clamp(lum + spot * spotIntensity, 0.0, 1.0);

	float darkness = 1.0 - lum;

	// Broad spatial variation in ink density.
	darkness = clamp(
		darkness + (fbm(p * 0.006) - 0.5) * darknessNoiseAmp,
		0.0, 1.0);

	float h1 = hatchFamily(p, radians(h1Angle), h1Spacing, h1Thickness, h1Seed);
	float h2 = hatchFamily(p, radians(h2Angle), h2Spacing, h2Thickness, h2Seed);
	float h3 = hatchFamily(p, radians(h3Angle), h3Spacing, h3Thickness, h3Seed);

	float ink = 0.0;
	ink = max(ink, h1 * smoothstep(h1OnsetLow, h1OnsetHigh, darkness));
	ink = max(ink, h2 * smoothstep(h2OnsetLow, h2OnsetHigh, darkness));
	ink = max(ink, h3 * smoothstep(h3OnsetLow, h3OnsetHigh, darkness));

	fragColor = vec4(mix(paperColor, inkColor, ink), 1.0);
}
"""

PAPER_COLOR = (0.94, 0.91, 0.82)
INK_COLOR = (0.055, 0.045, 0.035)

LIGHT_DEFAULTS = {
	"lumDark": 0.10,
	"lumLight": 0.96,
	"spotX": 0.67,
	"spotY": 0.68,
	"spotIntensity": 0.18,
	"spotSharpness": 8.0,
	"darknessNoiseAmp": 0.12,
}
LIGHT_PARAMS = (
	("lumDark", "Dark Side Luminance", 0.0, 1.0),
	("lumLight", "Light Side Luminance", 0.0, 1.0),
	("spotX", "Highlight X", 0.0, 1.0),
	("spotY", "Highlight Y", 0.0, 1.0),
	("spotIntensity", "Highlight Intensity", 0.0, 1.0),
	("spotSharpness", "Highlight Sharpness", 1.0, 40.0),
	("darknessNoiseAmp", "Darkness Variation", 0.0, 0.5),
)

STROKE_DEFAULTS = {
	"warpAmount": 1.0,
	"rowJitter": 0.28,
	"widthJitter": 0.45,
	"breakLow": 0.36,
	"breakHigh": 0.58,
	"nibLow": 0.18,
	"nibHigh": 0.42,
}
STROKE_PARAMS = (
	("warpAmount", "Warp Amount", 0.0, 3.0),
	("rowJitter", "Row Jitter", 0.0, 1.0),
	("widthJitter", "Width Jitter", 0.0, 1.0),
	("breakLow", "Break Threshold Low", 0.0, 1.0),
	("breakHigh", "Break Threshold High", 0.0, 1.0),
	("nibLow", "Nib Threshold Low", 0.0, 1.0),
	("nibHigh", "Nib Threshold High", 0.0, 1.0),
)

# Each hatch family shares the exact same shape of knobs (angle/spacing/thickness/seed, plus the
# darkness range where it "turns on"), so the defaults/params/section-drawing are all generated
# from one shared shape rather than copy-pasted three times -- adding a fourth family later is
# one more hatch_family_defaults()/hatch_family_params() call, not three new functions.
def hatch_family_defaults(prefix, angle, spacing, thickness, seed, onset_low, onset_high):
	return {
		f"{prefix}Angle": angle,
		f"{prefix}Spacing": spacing,
		f"{prefix}Thickness": thickness,
		f"{prefix}Seed": seed,
		f"{prefix}OnsetLow": onset_low,
		f"{prefix}OnsetHigh": onset_high,
	}

def hatch_family_params(prefix, label):
	return (
		(f"{prefix}Angle", f"{label} Angle", -90.0, 90.0),
		(f"{prefix}Spacing", f"{label} Spacing", 2.0, 30.0),
		(f"{prefix}Thickness", f"{label} Thickness", 0.1, 3.0),
		(f"{prefix}Seed", f"{label} Seed", 0.0, 100.0),
		(f"{prefix}OnsetLow", f"{label} Onset Low", 0.0, 1.0),
		(f"{prefix}OnsetHigh", f"{label} Onset High", 0.0, 1.0),
	)

H1_DEFAULTS = hatch_family_defaults("h1", 24.0, 9.0, 1.05, 1.0, 0.18, 0.58)
H2_DEFAULTS = hatch_family_defaults("h2", -31.0, 10.5, 0.95, 9.0, 0.48, 0.78)
H3_DEFAULTS = hatch_family_defaults("h3", 71.0, 14.0, 0.75, 23.0, 0.72, 0.94)

H1_PARAMS = hatch_family_params("h1", "Hatch 1")
H2_PARAMS = hatch_family_params("h2", "Hatch 2")
H3_PARAMS = hatch_family_params("h3", "Hatch 3")

# The real pipeline-assembly entrypoint -- returns the root Node, no viewer/window side effects.
# Interactivity (the ImGui panel below) needs a live viewer, so it lives in configure_viewer()
# instead -- same split as pyosg-mrt.py.
def build_scene(w, h):
	g = osg.Geometry()

	g.primitiveSets.append(osg.DrawArrays(osg.PrimitiveSet.TRIANGLE_FAN, 0, 4))
	g.initialBound = osg.BoundingBox(-1, -1, -1, 1, 1, 1)

	geode = osg.Geode(name="hatch", drawables=(g,))

	geode.stateSet.attributes.append(osg.Program(name="pyosg-hatch", shaders=(
		osg.Shader(osg.Shader.VERTEX, VERTEX_SHADER),
		osg.Shader(osg.Shader.FRAGMENT, FRAGMENT_SHADER)
	)))

	geode.stateSet.uniforms.update({
		"paperColor": osg.Vec3(*PAPER_COLOR),
		"inkColor": osg.Vec3(*INK_COLOR),
		**LIGHT_DEFAULTS,
		**STROKE_DEFAULTS,
		**H1_DEFAULTS,
		**H2_DEFAULTS,
		**H3_DEFAULTS,
	})

	return geode

def configure_viewer(viewer, root):
	ss = root.stateSet

	gui_opts = osgx.imgui.Options()
	gui_opts.dock = osgx.imgui.Dock.LEFT
	gui_opts.dock_width = 340.0

	gui = osgx.imgui.Widget(viewer, options=gui_opts)

	def make_param_section(defaults, params, scope):
		def draw(ri):
			for name, label, lo, hi in params:
				changed, value = osgx.imgui.slider_float(f"{label}##{scope}", ss.uniforms[name].value, lo, hi)

				if changed: ss.uniforms[name] = value

			if osgx.imgui.button(f"Reset##{scope}"):
				for name, value in defaults.items():
					ss.uniforms[name] = value

		return draw

	def draw_paper_ink(ri):
		paper = ss.uniforms["paperColor"].value
		changed, r, g_, b = osgx.imgui.color_edit3("Paper##paperink", paper.x, paper.y, paper.z)
		if changed: ss.uniforms["paperColor"] = osg.Vec3(r, g_, b)

		ink = ss.uniforms["inkColor"].value
		changed, r, g_, b = osgx.imgui.color_edit3("Ink##paperink", ink.x, ink.y, ink.z)
		if changed: ss.uniforms["inkColor"] = osg.Vec3(r, g_, b)

		if osgx.imgui.button("Reset##paperink"):
			ss.uniforms["paperColor"] = osg.Vec3(*PAPER_COLOR)
			ss.uniforms["inkColor"] = osg.Vec3(*INK_COLOR)

	def draw_seeds(ri):
		osgx.imgui.text("Reroll all three hatch seeds for a fresh")
		osgx.imgui.text("stroke pattern without touching angle/spacing.")

		if osgx.imgui.button("Reroll Seeds##global"):
			ss.uniforms["h1Seed"] = random.uniform(0.0, 100.0)
			ss.uniforms["h2Seed"] = random.uniform(0.0, 100.0)
			ss.uniforms["h3Seed"] = random.uniform(0.0, 100.0)

	gui.addSection("Paper & Ink", draw_paper_ink, osgx.imgui.SectionOptions(default_open=True))
	gui.addSection(
		"Lighting (PoC)",
		make_param_section(LIGHT_DEFAULTS, LIGHT_PARAMS, "light"),
		osgx.imgui.SectionOptions(default_open=True)
	)
	gui.addSection(
		"Stroke Character",
		make_param_section(STROKE_DEFAULTS, STROKE_PARAMS, "stroke"),
		osgx.imgui.SectionOptions(default_open=True)
	)
	gui.addSection("Hatch 1", make_param_section(H1_DEFAULTS, H1_PARAMS, "h1"))
	gui.addSection("Hatch 2", make_param_section(H2_DEFAULTS, H2_PARAMS, "h2"))
	gui.addSection("Hatch 3", make_param_section(H3_DEFAULTS, H3_PARAMS, "h3"))
	gui.addSection("Seeds", draw_seeds)

if __name__ == "__main__":
	osg.setNotifyLevel(osg.NotifySeverity.NOTICE)

	W, H = window_size()

	v = osgViewer.Viewer()
	root = build_scene(W, H)

	v.sceneData = root
	v.cameraManipulator = osgGA.TrackballManipulator()

	configure_viewer(v, root)

	while not v.done:
		v.frame()

		time.sleep(0.01)
