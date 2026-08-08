#!/usr/bin/env python3
#vimrun! ../examples/pyosg-flame.py --samples 4 --clear-color 0.008,0.008,0.012

"""A continuously burning, procedurally deformed low-poly flame mesh.

This deliberately has no particle state, texture, SSBO, or per-frame Python.
The CPU builds one small tapered ring mesh once.  One instanced draw turns it
into several flame tongues; gl_InstanceID derives each tongue's placement,
scale, and turbulence phase.  The vertex shader keeps the base still and
increasingly displaces/twists the mesh toward its tip.

It is an art-directed flame silhouette, not a fluid simulation.  The two
draws are nested shells: a broad orange envelope and a smaller bright core.
For many independently placed torches, an SSBO with one emitter record per
torch would be the natural next step; this example keeps one emitter entirely
uniform- and gl_InstanceID-driven on purpose.
"""

import math
import os
import sys

os.environ.setdefault("OSG_WINDOW", "50 50 800 600")
os.environ.setdefault("OSG_THREADING", "SingleThreaded")
os.environ.setdefault("OSG_GL_CONTEXT_PROFILE_MASK", "1")
os.environ.setdefault("OSG_GL_VERSION", "4.6")
os.environ.setdefault("OSG_GL_CONTEXT_VERSION", "4.6")

from OpenSceneGraph import *
from OpenSceneGraph.GL import *

import osgx

RINGS = 12
SIDES = 8

VERTEX_SHADER = """
	#version 430 core

	layout(location=0) in vec3 aPosition;

	uniform float osg_SimulationTime;
	uniform float flameHeight = 2.4;
	uniform float shellScale = 1.0;
	uniform float motionSpeed = 1.25;
	uniform float turbulence = 0.26;
	uniform float windStrength = 0.18;
	uniform float instanceSpread = 0.23;

	out float vHeight;
	out float vNoise;
	flat out float vSeed;

	float hash11(float p) {
		p = fract(p * 0.1031);
		p *= p + 33.33;
		p *= p + p;

		return fract(p);
	}

	float noise(vec3 p) {
		vec3 i = floor(p);
		vec3 f = fract(p);
		f = f * f * (3.0 - 2.0 * f);

		float a = hash11(dot(i, vec3(127.1, 311.7, 74.7)));
		float b = hash11(dot(i + vec3(1.0, 0.0, 0.0), vec3(127.1, 311.7, 74.7)));
		float c = hash11(dot(i + vec3(0.0, 1.0, 0.0), vec3(127.1, 311.7, 74.7)));
		float d = hash11(dot(i + vec3(1.0, 1.0, 0.0), vec3(127.1, 311.7, 74.7)));
		float e = hash11(dot(i + vec3(0.0, 0.0, 1.0), vec3(127.1, 311.7, 74.7)));
		float f0 = hash11(dot(i + vec3(1.0, 0.0, 1.0), vec3(127.1, 311.7, 74.7)));
		float g = hash11(dot(i + vec3(0.0, 1.0, 1.0), vec3(127.1, 311.7, 74.7)));
		float h = hash11(dot(i + vec3(1.0, 1.0, 1.0), vec3(127.1, 311.7, 74.7)));

		return mix(mix(mix(a, b, f.x), mix(c, d, f.x), f.y), mix(mix(e, f0, f.x), mix(g, h, f.x), f.y), f.z);
	}

	void main() {
		float seed = hash11(float(gl_InstanceID) + 17.0);
		float h = clamp(aPosition.z / flameHeight, 0.0, 1.0);
		float tipMotion = h * h;
		float time = osg_SimulationTime * motionSpeed;

		// Every instance is an independently animated tongue clustered around the wick.
		float angle = seed * 6.2831853;
		float radius = instanceSpread * sqrt(hash11(float(gl_InstanceID) + 31.0));
		vec2 instanceOffset = vec2(cos(angle), sin(angle)) * radius;

		vec3 p = aPosition * shellScale;
		vec3 npos = vec3(p.xy * 2.4 + instanceOffset * 5.0, h * 2.0 - time + seed * 9.0);
		float n0 = noise(npos);
		float n1 = noise(npos + vec3(13.7, 4.1, 0.0));
		vec2 turbulentOffset = (vec2(n0, n1) - 0.5) * turbulence * tipMotion;

		// Slow whole-flame bend plus faster small turbulent motion.  Both disappear at
		// the base, so the mesh really is visually attached to the wick/log.
		vec2 wind = vec2(sin(time * 0.73 + seed * 8.0), cos(time * 0.51 + seed * 5.0));
		p.xy += instanceOffset + turbulentOffset + wind * windStrength * tipMotion;
		p.z += (n0 - 0.5) * 0.18 * tipMotion;

		gl_Position = gl_ModelViewProjectionMatrix * vec4(p, 1.0);
		vHeight = h;
		vNoise = n0;
		vSeed = seed;
	}
"""

FRAGMENT_SHADER = """
	#version 430 core

	in float vHeight;
	in float vNoise;
	flat in float vSeed;

	uniform vec3 lowColor = vec3(1.0, 0.045, 0.0);
	uniform vec3 highColor = vec3(1.0, 0.72, 0.08);
	uniform float opacity = 0.62;

	out vec4 fragColor;

	void main() {
		// Break the mechanically smooth cone silhouette.  The threshold rises toward
		// the tip, leaving intermittent tongues instead of a plastic-looking point.
		float breakup = vNoise - mix(0.18, 0.56, vHeight);
		if (breakup < 0.0) discard;

		float fade = 1.0 - smoothstep(0.72, 1.0, vHeight);
		float hot = clamp(0.2 + (1.0 - vHeight) * 0.95 + (vNoise - 0.5) * 0.2, 0.0, 1.0);
		vec3 color = mix(lowColor, highColor, hot);
		float alpha = smoothstep(0.0, 0.22, breakup) * fade * opacity;

		// Premultiplied output, used with additive blending below.
		fragColor = vec4(color * alpha, alpha);
	}
"""

def make_flame_mesh(rings=RINGS, sides=SIDES, height=2.4, base_radius=0.45):
	"""Make a triangle-list tapered shell; shaders supply all motion afterward."""

	vertices = []

	def point(ring, side):
		h = ring / (rings - 1)
		angle = math.tau * side / sides
		# A real candle flame does not start as a wide, flat cone.  Pinch it at the
		# wick, swell through the first few rings into a rounded lower bulb, then use
		# the concave taper that gives the upper silhouette its flame-like shape.
		u = min(h / 0.18, 1.0)
		base_bulb = 0.28 + 0.72 * u * u * (3.0 - 2.0 * u)
		radius = base_radius * base_bulb * (1.0 - h) ** 0.62

		return osg.Vec3(math.cos(angle) * radius, math.sin(angle) * radius, h * height)

	for ring in range(rings - 1):
		for side in range(sides):
			next_side = (side + 1) % sides
			p00 = point(ring, side)
			p01 = point(ring, next_side)
			p10 = point(ring + 1, side)
			p11 = point(ring + 1, next_side)

			vertices.extend((p00, p10, p11, p00, p11, p01))

	g = osg.Geometry()
	g.vertexArray = osg.Vec3Array(vertices)
	g.primitiveSets.append(osg.DrawArrays(osg.PrimitiveSet.TRIANGLES, 0, len(vertices)))
	g.initialBound = osg.BoundingBox(-1, -1, 0, 1, 1, height)

	return g

def build_flame(
	num_instances=7,
	height=2.4,
	base_radius=0.45,
	motion_speed=1.25,
	turbulence=0.96,
	wind_strength=0.18,
	instance_spread=0.23,
):
	"""Return nested, instanced low-poly flame shells centered on the origin.

	`num_instances` is the number of individually seeded tongues in each shell, not
	the number of CPU meshes.  A single static triangle list is instanced twice.
	"""

	mesh = make_flame_mesh(height=height, base_radius=base_radius)
	group = osg.Group()

	for name, shell_scale, low_color, high_color, opacity in (
		("outer", 1.0, (1.0, 0.035, 0.0), (1.0, 0.48, 0.025), 0.48),
		("core", 0.55, (1.0, 0.20, 0.0), (1.7, 1.25, 0.55), 0.70),
	):
		g = osg.Geometry()
		g.vertexArray = mesh.vertexArray
		g.primitiveSets.append(osg.DrawArrays(
			osg.PrimitiveSet.TRIANGLES,
			0,
			len(mesh.vertexArray),
			num_instances,
		))
		g.initialBound = mesh.initialBound

		p = osg.Program(name=f"pyosg-flame-{name}", shaders=(
			osg.Shader(osg.Shader.VERTEX, VERTEX_SHADER),
			osg.Shader(osg.Shader.FRAGMENT, FRAGMENT_SHADER),
		))
		r = osg.Geode()
		r.drawables.append(g)

		ss = r.stateSet
		ss.attributes.append(p)
		ss.attributes[osg.StateAttribute.BLENDFUNC] = (osg.BlendFunc(GL_ONE, GL_ONE), osg.StateAttribute.ON)
		ss.attributes[osg.StateAttribute.DEPTH] = (
			osg.Depth(osg.Depth.LESS, 0.0, 1.0, False), osg.StateAttribute.ON
		)
		ss.setMode(GL_CULL_FACE, osg.StateAttribute.OFF)
		ss.renderingHint = osg.StateSet.TRANSPARENT_BIN
		ss.uniforms["flameHeight"] = height
		ss.uniforms["shellScale"] = shell_scale
		ss.uniforms["motionSpeed"] = motion_speed
		ss.uniforms["turbulence"] = turbulence
		ss.uniforms["windStrength"] = wind_strength
		ss.uniforms["instanceSpread"] = instance_spread
		ss.uniforms["lowColor"] = osg.Vec3(*low_color)
		ss.uniforms["highColor"] = osg.Vec3(*high_color)
		ss.uniforms["opacity"] = opacity

		group.children.append(r)

	return group

if __name__ == "__main__":
	osg.setNotifyLevel(osg.NotifySeverity.NOTICE)

	v = osgViewer.Viewer(osg.ArgumentParser("pyosg-flame.py", sys.argv))
	v.sceneData = build_flame()
	v.cameraManipulator = osgGA.TrackballManipulator()
	v.camera.clearColor = osg.Vec4(0.008, 0.008, 0.012, 1.0)

	if "--no-gui" not in sys.argv:
		# Match 11-sketchfab.py's fixed left sidebar. The ImGui package is not built
		# with interactive docking, so this reserves a stable panel instead.
		gui_opts = osgx.imgui.Options()
		gui_opts.dock = osgx.imgui.Dock.LEFT
		gui_opts.dock_width = 320.0
		gui = osgx.imgui.Widget(v, v.camera, gui_opts)
		shell_state_sets = [child.stateSet for child in v.sceneData.children]

		def draw_motion(ri):
			for name, label, lo, hi in (
				("motionSpeed", "Motion Speed", 0.0, 4.0),
				("turbulence", "Turbulence", 0.0, 2.0),
				("windStrength", "Wind Strength", 0.0, 1.0),
				("instanceSpread", "Tongue Spread", 0.0, 0.8),
			):
				changed, value = osgx.imgui.slider_float_nudge(
					label, shell_state_sets[0].uniforms[name].value, lo, hi
				)

				if changed:
					for ss in shell_state_sets:
						ss.uniforms[name] = value

		gui.addSection("Motion", draw_motion, osgx.imgui.SectionOptions(default_open=True))

		def draw_colors(ri):
			for name, label in (
				("lowColor", "Outer Low Color"),
				("highColor", "Outer High Color"),
			):
				color = shell_state_sets[0].uniforms[name].value
				changed, r, g, b = osgx.imgui.color_edit3(label, color.x, color.y, color.z)

				if changed:
					shell_state_sets[0].uniforms[name] = osg.Vec3(r, g, b)

			for name, label in (
				("lowColor", "Core Low Color"),
				("highColor", "Core High Color"),
			):
				color = shell_state_sets[1].uniforms[name].value
				changed, r, g, b = osgx.imgui.color_edit3(label, color.x, color.y, color.z)

				if changed:
					shell_state_sets[1].uniforms[name] = osg.Vec3(r, g, b)

			for ss, label in zip(shell_state_sets, ("Outer Opacity", "Core Opacity")):
				changed, value = osgx.imgui.slider_float_nudge(
					label, ss.uniforms["opacity"].value, 0.0, 1.0
				)

				if changed:
					ss.uniforms["opacity"] = value

		gui.addSection("Color", draw_colors, osgx.imgui.SectionOptions(default_open=True))

	while not v.done:
		v.frame()
