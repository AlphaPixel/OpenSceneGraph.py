#!/usr/bin/env python3
#vimrun! ../examples/pyosg-fire.py --samples 4 --clear-color 0.02,0.02,0.03

# "Fiery explosion" prototype: a swarm of view-space-billboarded unit quads (same
# gl_InstanceID instancing trick as pyosg-instanced.py) expanding outward from the
# origin in a single burst, each one shaded by a domain-warped FBM noise fire ramp
# instead of a photographed sprite sheet.
#
# Deliberately GPU-only: every instance's position/size/life is a pure function of
# osg_SimulationTime (auto-provided by OSG every frame) and a per-instance seed
# derived from gl_InstanceID via an in-shader hash -- no SSBO, no per-frame Python.
# An earlier version of this file DID use an SSBO (mirroring pyosg-instanced-ssbo.py),
# but the per-instance data it carried (angle/radius/phase/life-offset seeds) never
# changes after upload, so a hash of gl_InstanceID produces the identical result with
# no buffer object at all -- see pyosg-instanced.py's per-instance color hash for the
# same idiom. An SSBO earns its keep once something actually WRITES per-instance state
# over time (a compute-shader velocity sim, multiple independently-triggered bursts
# with distinct origins); it's not needed just to read constants.
#
# The burst itself is one-shot, not looping: `triggerTime` is a plain uniform, and
# t = (osg_SimulationTime - triggerTime) / duration runs 0->1 exactly once per trigger.
# Call trigger() again (from Python, or the standalone loop below) to re-fire it.
#
# Try it from the aipython REPL (see build_fire()/trigger() below), or run standalone
# with `--repl` to get the same IPython prompt this file was designed to be iterated
# from.

import colorsys
import math
import os
import random
import sys
import time

os.environ.setdefault("OSG_WINDOW", "50 50 800 600")
os.environ.setdefault("OSG_THREADING", "SingleThreaded")
os.environ.setdefault("OSG_GL_CONTEXT_PROFILE_MASK", "1")
os.environ.setdefault("OSG_GL_VERSION", "4.6")
os.environ.setdefault("OSG_GL_CONTEXT_VERSION", "4.6")

from OpenSceneGraph import *
from OpenSceneGraph.GL import *

import osgx

NUM_INSTANCES = 512

VERTEX_SHADER = """
	#version 430 core

	uniform float osg_SimulationTime;
	uniform float triggerTime = -1000.0;
	uniform float duration = 1.2;
	uniform float burstRadius = 2.2;
	uniform float riseHeight = 1.2;
	uniform float baseSize = 0.5;

	out vec2 vUV;
	out float vIntensity;
	out vec3 vSeed;
	flat out int vInstanceID;

	const float TWO_PI = 6.2831853;

	// Per-instance "seed" data (emission direction, size variance) is read-once and
	// never changes after the burst starts, so it's derived straight from
	// gl_InstanceID instead of costing a buffer object round-trip.
	float hash11(float p) {
		p = fract(p * 0.1031);
		p *= p + 33.33;
		p *= p + p;

		return fract(p);
	}

	vec4 hash14(float p) {
		return vec4(
			hash11(p + 0.13),
			hash11(p + 7.71),
			hash11(p + 23.9),
			hash11(p + 91.7)
		);
	}

	void main() {
		vec2 base[4] = vec2[4](
			vec2(-0.5, -0.5),
			vec2( 0.5, -0.5),
			vec2( 0.5, 0.5),
			vec2(-0.5, 0.5)
		);

		vec2 corner = base[gl_VertexID % 4];
		vec4 seed = hash14(float(gl_InstanceID));

		// Not fract()'d -- t runs 0->1 exactly once per trigger, then the size
		// envelope below clamps to zero and stays there until re-triggered.
		float t = (osg_SimulationTime - triggerTime) / duration;

		// Random direction on a mostly-upward hemisphere (phiCos in [-0.2, 1.0]
		// keeps a little downward/outward spray instead of a perfect dome).
		float theta = seed.x * TWO_PI;
		float phiCos = mix(-0.2, 1.0, seed.y);
		float phiSin = sqrt(max(0.0, 1.0 - phiCos * phiCos));
		vec3 dir = vec3(cos(theta) * phiSin, sin(theta) * phiSin, phiCos);

		float tc = clamp(t, 0.0, 1.0);
		float expand = 1.0 - (1.0 - tc) * (1.0 - tc); // ease-out: fast, then coasts

		vec3 pos = dir * expand * burstRadius;

		pos.z += riseHeight * tc * tc; // buoyant rise kicks in after the initial punch

		float sizeEnvelope = smoothstep(0.0, 0.08, t) * (1.0 - smoothstep(0.5, 1.0, t));
		float sizeVariance = mix(0.7, 1.3, seed.z);
		float size = baseSize * sizeEnvelope * sizeVariance;

		// Billboard entirely in view space -- always faces the camera without needing
		// to extract camera right/up axes by hand.
		vec4 centerView = gl_ModelViewMatrix * vec4(pos, 1.0);

		// Per-instance quad rotation (seed.w, otherwise unused by hash14 here) -- without
		// this, every one of the ~500 quads shares the same screen-space orientation,
		// which reads as a subtle grid/uniformity once you know to look for it. vUV below
		// stays keyed to the UNROTATED corner on purpose: the noise/fireRamp pattern lives
		// in the sprite's own local frame, so rotating only the on-screen footprint spins
		// the rendered flame shape along with it instead of resampling it.
		float quadAngle = seed.w * TWO_PI;
		float ca = cos(quadAngle);
		float sa = sin(quadAngle);
		vec2 rotatedCorner = vec2(corner.x * ca - corner.y * sa, corner.x * sa + corner.y * ca);

		centerView.xy += rotatedCorner * size;

		gl_Position = gl_ProjectionMatrix * centerView;

		vUV = corner + 0.5;
		vIntensity = sizeEnvelope;
		vSeed = seed.xyz;
		vInstanceID = gl_InstanceID;
	}
"""

FRAGMENT_SHADER = """
	#version 430 core

	in vec2 vUV;
	in float vIntensity;
	in vec3 vSeed;
	flat in int vInstanceID;

	uniform float osg_SimulationTime;
	uniform float noiseScale = 3.0;
	uniform float scrollSpeed = 0.8;
	uniform float warpStrength = 0.4;
	// The ramp's two most visible stops, tunable from Python/ImGui -- everything
	// between c0 (near-black) and midColor, and between midColor's neighbor c3 and
	// coreColor, still interpolates below, so retinting these two alone reshapes the
	// whole flame's hue without needing all five stops exposed.
	uniform vec3 midColor = vec3(1.0, 0.35, 0.0);
	uniform vec3 coreColor = vec3(1.0, 1.0, 0.85);

	out vec4 fragColor;

	float hash21(vec2 p) {
		p = fract(p * vec2(123.34, 456.21));
		p += dot(p, p + 45.32);

		return fract(p.x * p.y);
	}

	float noise(vec2 p) {
		vec2 i = floor(p);
		vec2 f = fract(p);
		vec2 u = f * f * (3.0 - 2.0 * f);

		float a = hash21(i);
		float b = hash21(i + vec2(1.0, 0.0));
		float c = hash21(i + vec2(0.0, 1.0));
		float d = hash21(i + vec2(1.0, 1.0));

		return mix(mix(a, b, u.x), mix(c, d, u.x), u.y);
	}

	float fbm(vec2 p) {
		float value = 0.0;
		float amplitude = 0.5;

		for (int i = 0; i < 4; i++) {
			value += amplitude * noise(p);
			p *= 2.0;
			amplitude *= 0.5;
		}

		return value;
	}

	vec3 fireRamp(float t) {
		t = clamp(t, 0.0, 1.0);

		vec3 c0 = vec3(0.02, 0.0, 0.0);
		vec3 c1 = vec3(0.5, 0.02, 0.0);
		vec3 c2 = midColor;
		vec3 c3 = vec3(1.0, 0.8, 0.15);
		vec3 c4 = coreColor;

		if (t < 0.25) return mix(c0, c1, t / 0.25);
		if (t < 0.55) return mix(c1, c2, (t - 0.25) / 0.30);
		if (t < 0.80) return mix(c2, c3, (t - 0.55) / 0.25);

		return mix(c3, c4, (t - 0.80) / 0.20);
	}

	void main() {
		vec2 c = vUV - vec2(0.5, 0.35);

		c.y *= 0.8;

		float radial = length(c * vec2(1.6, 1.0));

		if (radial > 1.0 || vIntensity <= 0.0) discard;

		vec2 scroll = vec2(0.0, -osg_SimulationTime * scrollSpeed);
		vec2 warpUV = vUV * noiseScale + vSeed.xy * 10.0;
		vec2 q = vec2(
			fbm(warpUV + scroll),
			fbm(warpUV + scroll + vec2(5.2, 1.3))
		);
		vec2 warped = warpUV + (q - 0.5) * warpStrength;

		float n = fbm(warped + scroll * 1.5);
		float heightBias = 1.0 - clamp(vUV.y, 0.0, 1.0);

		// heightBias is a light nudge, not the dominant term -- weighting it any
		// higher than this washes the noise detail out into a flat white blob once
		// a few dozen additively-blended quads stack on the same pixels.
		float t = clamp(n * 1.0 + heightBias * 0.15, 0.0, 1.0) * vIntensity;

		float edgeMask = smoothstep(1.0, 0.4, radial);

		// The trailing 0.55 keeps a single quad's contribution below full brightness
		// so overlapping quads (additive GL_ONE, GL_ONE) still leave the c1/c2 red-
		// orange band visible instead of saturating straight to the c4 white core.
		float alpha = edgeMask * vIntensity * smoothstep(0.05, 0.35, n) * 0.55;

		vec3 color = fireRamp(t);

		fragColor = vec4(color * alpha, alpha);
	}
"""

SHOCKWAVE_VERTEX_SHADER = """
	#version 430 core

	uniform float quadSize = 4.6;

	out vec2 vLocalPos;

	void main() {
		vec2 base[4] = vec2[4](
			vec2(-1.0, -1.0),
			vec2( 1.0, -1.0),
			vec2( 1.0,  1.0),
			vec2(-1.0,  1.0)
		);

		vec2 corner = base[gl_VertexID % 4] * quadSize;

		vLocalPos = corner;

		// Flat on the ground (z=0) -- fire's z is "up" in this scene, so the shockwave
		// ring's plane is spanned by x/y, not billboarded like the fire quads.
		gl_Position = gl_ModelViewProjectionMatrix * vec4(corner.x, corner.y, 0.0, 1.0);
	}
"""

SHOCKWAVE_FRAGMENT_SHADER = """
	#version 430 core

	in vec2 vLocalPos;

	uniform float osg_SimulationTime;
	uniform float triggerTime = -1000.0;
	uniform float duration = 0.6;
	uniform float maxRadius = 4.0;
	uniform float ringWidth = 0.3;

	out vec4 fragColor;

	void main() {
		float t = (osg_SimulationTime - triggerTime) / duration;

		if (t < 0.0 || t > 1.0) discard;

		float expand = 1.0 - (1.0 - t) * (1.0 - t); // same ease-out curve as the fire

		float ringRadius = expand * maxRadius;
		float dist = length(vLocalPos);
		float ring = smoothstep(ringWidth, 0.0, abs(dist - ringRadius));

		// Fades out over the ring's own lifetime, not just at its leading edge, so it
		// reads as a dissipating wave rather than a ring that pops off abruptly.
		float fade = 1.0 - t;
		float alpha = ring * fade;

		vec3 color = mix(vec3(1.0, 0.55, 0.15), vec3(1.0, 0.95, 0.8), fade);

		fragColor = vec4(color * alpha, alpha);
	}
"""

def build_shockwave(max_radius=4.0, duration=0.6, ring_width=0.3):
	"""Return a Geode: a single flat expanding ring on the ground plane (z=0).

	Same one-shot `triggerTime`-uniform design as build_fire() -- trigger(node,
	viewer) fires this exactly the same way.
	"""

	quad_size = max_radius * 1.15

	g = osg.Geometry()

	g.primitiveSets.append(osg.DrawArrays(osg.PrimitiveSet.TRIANGLE_FAN, 0, 4))
	g.initialBound = osg.BoundingBox(-quad_size, -quad_size, -0.1, quad_size, quad_size, 0.1)

	p = osg.Program(name="pyosg-fire-shockwave", shaders=(
		osg.Shader(osg.Shader.VERTEX, SHOCKWAVE_VERTEX_SHADER),
		osg.Shader(osg.Shader.FRAGMENT, SHOCKWAVE_FRAGMENT_SHADER)
	))

	r = osg.Geode()

	r.drawables.append(g)

	ss = r.stateSet

	ss.attributes.append(p)
	ss.attributes[osg.StateAttribute.BLENDFUNC] = (osg.BlendFunc(GL_ONE, GL_ONE), osg.StateAttribute.ON)
	ss.attributes[osg.StateAttribute.DEPTH] = (
		osg.Depth(osg.Depth.LESS, 0.0, 1.0, False), osg.StateAttribute.ON
	)
	ss.modes[GL_CULL_FACE] = osg.StateAttribute.OFF
	ss.renderingHint = osg.StateSet.TRANSPARENT_BIN

	ss.uniforms["quadSize"] = quad_size
	ss.uniforms["duration"] = duration
	ss.uniforms["maxRadius"] = max_radius
	ss.uniforms["ringWidth"] = ring_width

	return r

SMOKE_VERTEX_SHADER = """
	#version 430 core

	uniform float osg_SimulationTime;
	uniform float triggerTime = -1000.0;
	uniform float startDelay = 0.15;
	uniform float duration = 3.0;
	uniform float spreadRadius = 3.2;
	uniform float riseHeight = 3.5;
	uniform float baseSize = 0.7;
	uniform float growAmount = 3.0;

	out vec2 vUV;
	out float vIntensity;
	out vec3 vSeed;

	const float TWO_PI = 6.2831853;

	float hash11(float p) {
		p = fract(p * 0.1031);
		p *= p + 33.33;
		p *= p + p;

		return fract(p);
	}

	vec4 hash14(float p) {
		return vec4(
			hash11(p + 0.13),
			hash11(p + 7.71),
			hash11(p + 23.9),
			hash11(p + 91.7)
		);
	}

	void main() {
		vec2 base[4] = vec2[4](
			vec2(-0.5, -0.5),
			vec2( 0.5, -0.5),
			vec2( 0.5, 0.5),
			vec2(-0.5, 0.5)
		);

		vec2 corner = base[gl_VertexID % 4];
		vec4 seed = hash14(float(gl_InstanceID) + 1000.0); // offset from fire's own hash domain

		// Smoke starts a beat after the fire (startDelay), then runs much longer -- this
		// is what makes it read as lingering AFTER the fire quads have already faded.
		float t = (osg_SimulationTime - triggerTime - startDelay) / duration;
		float tc = clamp(t, 0.0, 1.0);

		// Mostly-vertical cone, but wide enough that individual puffs actually separate
		// from each other as they rise instead of coasting up as one overlapping mass
		// (0.55 was too narrow -- every puff traveled nearly straight up together).
		float theta = seed.x * TWO_PI;
		float phiCos = mix(0.15, 1.0, seed.y);
		float phiSin = sqrt(max(0.0, 1.0 - phiCos * phiCos));
		vec3 dir = vec3(cos(theta) * phiSin, sin(theta) * phiSin, phiCos);

		float expand = 1.0 - (1.0 - tc) * (1.0 - tc);
		vec3 pos = dir * expand * spreadRadius;

		// Continued climb for the whole lifetime, not just the initial punch -- smoke
		// keeps rising as it dissipates instead of coasting like the fire's rise term.
		pos.z += riseHeight * tc;

		// Puffs GROW over their lifetime instead of shrinking -- opposite envelope shape
		// from build_fire()'s baseSize * sizeEnvelope, since real smoke expands as it
		// dissipates rather than shrinking away. The smoothstep factor grows puffs in
		// from zero at spawn instead of popping in at full baseSize immediately -- without
		// it, every puff starts stacked at the same origin point at its eventual minimum
		// size, which reads as one solid overlapping blob for the first instant.
		float sizeVariance = mix(0.7, 1.3, seed.z);
		float growIn = smoothstep(0.0, 0.15, t);
		float size = baseSize * mix(1.0, growAmount, tc) * sizeVariance * growIn;

		vec4 centerView = gl_ModelViewMatrix * vec4(pos, 1.0);

		// Same per-instance rotation trick as build_fire()'s vertex shader (seed.w) --
		// see that shader's comment for why vUV stays keyed to the unrotated corner.
		float quadAngle = seed.w * TWO_PI;
		float ca = cos(quadAngle);
		float sa = sin(quadAngle);
		vec2 rotatedCorner = vec2(corner.x * ca - corner.y * sa, corner.x * sa + corner.y * ca);

		centerView.xy += rotatedCorner * size;

		gl_Position = gl_ProjectionMatrix * centerView;

		vUV = corner + 0.5;
		// Fades in quickly after startDelay, then fades out slowly over the rest of the
		// (much longer) duration -- this is the "lingers" part of the effect.
		vIntensity = smoothstep(0.0, 0.1, t) * (1.0 - tc);
		vSeed = seed.xyz;
	}
"""

SMOKE_FRAGMENT_SHADER = """
	#version 430 core

	in vec2 vUV;
	in float vIntensity;
	in vec3 vSeed;

	uniform float osg_SimulationTime;
	uniform float noiseScale = 2.0;
	uniform float scrollSpeed = 0.3;
	uniform float warpStrength = 0.5;
	uniform float maxAlpha = 0.35;

	out vec4 fragColor;

	float hash21(vec2 p) {
		p = fract(p * vec2(123.34, 456.21));
		p += dot(p, p + 45.32);

		return fract(p.x * p.y);
	}

	float noise(vec2 p) {
		vec2 i = floor(p);
		vec2 f = fract(p);
		vec2 u = f * f * (3.0 - 2.0 * f);

		float a = hash21(i);
		float b = hash21(i + vec2(1.0, 0.0));
		float c = hash21(i + vec2(0.0, 1.0));
		float d = hash21(i + vec2(1.0, 1.0));

		return mix(mix(a, b, u.x), mix(c, d, u.x), u.y);
	}

	float fbm(vec2 p) {
		float value = 0.0;
		float amplitude = 0.5;

		for (int i = 0; i < 4; i++) {
			value += amplitude * noise(p);
			p *= 2.0;
			amplitude *= 0.5;
		}

		return value;
	}

	void main() {
		vec2 c = vUV - vec2(0.5);
		float radial = length(c) * 2.0;

		if (radial > 1.0 || vIntensity <= 0.0) discard;

		vec2 scroll = vec2(0.0, -osg_SimulationTime * scrollSpeed);
		vec2 warpUV = vUV * noiseScale + vSeed.xy * 10.0;
		vec2 q = vec2(
			fbm(warpUV + scroll),
			fbm(warpUV + scroll + vec2(5.2, 1.3))
		);
		vec2 warped = warpUV + (q - 0.5) * warpStrength;

		float density = fbm(warped + scroll * 0.5);
		float edgeMask = smoothstep(1.0, 0.3, radial);

		// Grey ramp, near-black core to a pale highlight -- explicitly NOT the fire's
		// warm ramp, so the two layers read as physically distinct materials even
		// though they share the same instanced-quad/fbm-turbulence machinery.
		vec3 c0 = vec3(0.03, 0.03, 0.035);
		vec3 c1 = vec3(0.18, 0.18, 0.2);
		vec3 c2 = vec3(0.45, 0.45, 0.47);
		vec3 color = mix(c0, mix(c1, c2, density), density);

		float alpha = edgeMask * vIntensity * smoothstep(0.1, 0.5, density) * maxAlpha;

		fragColor = vec4(color, alpha);
	}
"""

def build_smoke(
	num_instances=256,
	start_delay=0.15,
	duration=3.0,
	spread_radius=3.2,
	rise_height=3.5,
	base_size=0.7,
	grow_amount=3.0,
):
	"""Return a Geode of instanced smoke puffs -- same GPU-only one-shot design as
	build_fire(), meant to be triggered alongside it (same triggerTime) so it starts
	a beat later and lingers after the fire quads have already faded out.

	Normal alpha blending (not additive like the fire/shockwave) -- smoke should read
	as translucent grey mass, not glow, which is also what visually separates it from
	everything else in this file at a glance.
	"""

	g = osg.Geometry()

	g.primitiveSets.append(osg.DrawArrays(osg.PrimitiveSet.TRIANGLE_FAN, 0, 4, num_instances))
	g.initialBound = osg.BoundingBox(-7, -7, -0.5, 7, 7, 8)

	p = osg.Program(name="pyosg-fire-smoke", shaders=(
		osg.Shader(osg.Shader.VERTEX, SMOKE_VERTEX_SHADER),
		osg.Shader(osg.Shader.FRAGMENT, SMOKE_FRAGMENT_SHADER)
	))

	r = osg.Geode()

	r.drawables.append(g)

	ss = r.stateSet

	ss.attributes.append(p)
	ss.attributes[osg.StateAttribute.BLENDFUNC] = (
		osg.BlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA), osg.StateAttribute.ON
	)
	ss.attributes[osg.StateAttribute.DEPTH] = (
		osg.Depth(osg.Depth.LESS, 0.0, 1.0, False), osg.StateAttribute.ON
	)
	ss.modes[GL_CULL_FACE] = osg.StateAttribute.OFF
	ss.renderingHint = osg.StateSet.TRANSPARENT_BIN

	ss.uniforms["startDelay"] = start_delay
	ss.uniforms["duration"] = duration
	ss.uniforms["spreadRadius"] = spread_radius
	ss.uniforms["riseHeight"] = rise_height
	ss.uniforms["baseSize"] = base_size
	ss.uniforms["growAmount"] = grow_amount

	return r

# --------------------------------------------------------------------------- #
# Embers/sparks: real GL_POINTS, not billboarded quads -- per pyosg-points.py, a
# point sprite's footprint (gl_PointCoord in the fragment shader) is far cheaper per-
# particle than a quad when the particle never needs to face-camera via explicit
# corner geometry, which is exactly the case for small fast debris like this. No
# vertex array is bound (same as build_fire()/build_smoke()) -- gl_VertexID alone
# seeds every point's trajectory.
# --------------------------------------------------------------------------- #

EMBER_VERTEX_SHADER = """
	#version 430 core

	uniform float osg_SimulationTime;
	uniform float triggerTime = -1000.0;
	uniform float duration = 1.6;
	uniform float launchSpeed = 4.0;
	uniform float gravity = 6.0;
	uniform float basePointSize = 14.0;

	out float vCool;
	out float vIntensity;

	const float TWO_PI = 6.2831853;

	float hash11(float p) {
		p = fract(p * 0.1031);
		p *= p + 33.33;
		p *= p + p;

		return fract(p);
	}

	vec4 hash14(float p) {
		return vec4(
			hash11(p + 0.13),
			hash11(p + 7.71),
			hash11(p + 23.9),
			hash11(p + 91.7)
		);
	}

	void main() {
		vec4 seed = hash14(float(gl_VertexID));

		// Per-instance life variance (0.6x-1.3x duration) so embers fizzle out staggered
		// instead of all vanishing on the same frame.
		float life = duration * mix(0.6, 1.3, seed.w);
		float t = (osg_SimulationTime - triggerTime) / life;
		float tc = clamp(t, 0.0, 1.0);

		// Full hemisphere spray (phiCos down to -0.1, unlike the fire's tighter dome) with
		// per-instance speed variance -- sparks launch chaotically, not as a smooth front.
		float theta = seed.x * TWO_PI;
		float phiCos = mix(-0.1, 1.0, seed.y);
		float phiSin = sqrt(max(0.0, 1.0 - phiCos * phiCos));
		vec3 dir = vec3(cos(theta) * phiSin, sin(theta) * phiSin, phiCos);
		float speed = launchSpeed * mix(0.5, 1.5, seed.z);

		// Ballistic arc: launched at `speed` along `dir`, then gravity pulls straight down
		// -- a genuinely different trajectory shape from the fire's ease-out punch and the
		// smoke's continuous buoyant climb, which is most of why this layer reads as
		// distinct debris rather than more fire.
		vec3 pos = dir * speed * tc;

		pos.z -= 0.5 * gravity * tc * tc;

		vec4 centerView = gl_ModelViewMatrix * vec4(pos, 1.0);

		gl_Position = gl_ProjectionMatrix * centerView;

		// Shrinks to nothing as the ember dies (tc -> 1); before the first trigger,
		// triggerTime's -1000 default puts t (and therefore tc) permanently at 1, so
		// gl_PointSize/vIntensity are already zero with no separate visibility toggle
		// needed -- same trick build_fire()'s sizeEnvelope uses.
		float sizeEnvelope = 1.0 - tc;

		// Cheap stepped sparkle -- distinct per point (gl_VertexID) and re-rolled roughly
		// 24 times/sec (floor(time * 24)), not a smooth flicker. Good enough at this scale;
		// not worth a smoother curve for something this small on screen.
		float flicker = 0.6 + 0.4 * hash11(float(gl_VertexID) * 17.0 + floor(osg_SimulationTime * 24.0));

		// No distance falloff -- confirmed live that this scene's auto-fit camera distance
		// (trackball sizes home position off the WHOLE scene bound, and the smoke/ember
		// layers pushed that bound out considerably) made a `basePointSize / dist` term
		// collapse to sub-pixel. Flat size, same convention pyosg-points.py itself uses.
		gl_PointSize = max(1.0, basePointSize * sizeEnvelope);

		vIntensity = sizeEnvelope * flicker;
		vCool = tc;
	}
"""

EMBER_FRAGMENT_SHADER = """
	#version 430 core

	in float vCool;
	in float vIntensity;

	out vec4 fragColor;

	// Same dot-glow + thin-ring "bling" trick as pyosg-points.py's fragment shader --
	// gl_PointCoord alone, no extra geometry needed to carry it.
	void main() {
		vec2 p = gl_PointCoord * 2.0 - 1.0;
		float r2 = dot(p, p);

		if (r2 > 1.0 || vIntensity <= 0.0) discard;

		float dotGlow = exp(-r2 * 2.5);
		float r = sqrt(r2);
		float ring = smoothstep(0.12, 0.0, abs(r - 0.85));
		float glow = max(dotGlow, ring * 0.6);

		// Cools from white-hot to a dull red ember as vCool (the spark's own age, 0->1)
		// increases -- distinct from build_fire()'s fireRamp(), which ramps on turbulence
		// density rather than a single spark's elapsed lifetime.
		// Deliberately over-1.0 -- with additive blending this blows out toward a
		// white-hot core instead of just capping at plain white, which reads as much
		// hotter than a literal (1,1,1) would.
		vec3 hot = vec3(1.6, 1.55, 1.4);
		vec3 mid = vec3(1.0, 0.55, 0.1);
		vec3 cool = vec3(0.5, 0.08, 0.0);
		vec3 color = vCool < 0.4
			? mix(hot, mid, vCool / 0.4)
			: mix(mid, cool, (vCool - 0.4) / 0.6);

		float alpha = glow * vIntensity;

		fragColor = vec4(color * alpha, alpha);
	}
"""

def build_embers(num_points=220, duration=1.6, launch_speed=4.0, gravity=6.0, base_point_size=14.0):
	"""Return a Geode of `num_points` GL_POINTS embers -- same one-shot `triggerTime`
	design as build_fire()/build_smoke(), fired the same way via trigger(node, viewer).

	Real point sprites, not billboarded quads (see the module comment above) -- cheaper
	per-particle, and the ballistic-arc trajectory (launch + gravity) reads as flying
	debris rather than more fire, which is the point of this layer existing at all.
	"""

	g = osg.Geometry()

	g.primitiveSets.append(osg.DrawArrays(osg.PrimitiveSet.POINTS, 0, num_points))
	g.initialBound = osg.BoundingBox(-8, -8, -4, 8, 8, 8)

	p = osg.Program(name="pyosg-fire-embers", shaders=(
		osg.Shader(osg.Shader.VERTEX, EMBER_VERTEX_SHADER),
		osg.Shader(osg.Shader.FRAGMENT, EMBER_FRAGMENT_SHADER)
	))

	r = osg.Geode()

	r.drawables.append(g)

	ss = r.stateSet

	ss.attributes.append(p)
	ss.modes[GL_PROGRAM_POINT_SIZE] = osg.StateAttribute.ON
	ss.modes[GL_VERTEX_PROGRAM_POINT_SIZE] = osg.StateAttribute.ON
	ss.attributes[osg.StateAttribute.BLENDFUNC] = (osg.BlendFunc(GL_ONE, GL_ONE), osg.StateAttribute.ON)
	ss.attributes[osg.StateAttribute.DEPTH] = (
		osg.Depth(osg.Depth.LESS, 0.0, 1.0, False), osg.StateAttribute.ON
	)
	ss.renderingHint = osg.StateSet.TRANSPARENT_BIN

	ss.uniforms["duration"] = duration
	ss.uniforms["launchSpeed"] = launch_speed
	ss.uniforms["gravity"] = gravity
	ss.uniforms["basePointSize"] = base_point_size

	return r

def build_fire(
	num_instances=NUM_INSTANCES,
	duration=1.2,
	burst_radius=2.2,
	rise_height=1.2,
	base_size=0.5,
	mid_color=(1.0, 0.35, 0.0),
	core_color=(1.0, 1.0, 0.85),
):
	"""Return a Geode of `num_instances` GPU-simulated fire quads, centered at the origin.

	Everything after this call is driven by osg_SimulationTime alone -- there's no
	per-frame Python work, so it's safe to build once and drop straight into a live
	REPL scene: `viewer.sceneData = build_fire()`. The burst is one-shot; call
	trigger(node, viewer) to fire it (or re-fire it).

	`mid_color`/`core_color` retint fireRamp()'s two most visible stops (default:
	orange ember / pale-hot core) -- pass any RGB triple to get flame colors besides
	fire's own, e.g. for build_multiburst()'s per-burst hue variation.
	"""

	g = osg.Geometry()

	g.primitiveSets.append(osg.DrawArrays(osg.PrimitiveSet.TRIANGLE_FAN, 0, 4, num_instances))
	g.initialBound = osg.BoundingBox(-3, -3, -0.5, 3, 3, 3)

	p = osg.Program(name="pyosg-fire", shaders=(
		osg.Shader(osg.Shader.VERTEX, VERTEX_SHADER),
		osg.Shader(osg.Shader.FRAGMENT, FRAGMENT_SHADER)
	))

	r = osg.Geode()

	r.drawables.append(g)

	ss = r.stateSet

	ss.attributes.append(p)
	ss.attributes[osg.StateAttribute.BLENDFUNC] = (osg.BlendFunc(GL_ONE, GL_ONE), osg.StateAttribute.ON)
	ss.attributes[osg.StateAttribute.DEPTH] = (
		osg.Depth(osg.Depth.LESS, 0.0, 1.0, False), osg.StateAttribute.ON
	)
	ss.modes[GL_CULL_FACE] = osg.StateAttribute.OFF
	ss.renderingHint = osg.StateSet.TRANSPARENT_BIN

	ss.uniforms["duration"] = duration
	ss.uniforms["burstRadius"] = burst_radius
	ss.uniforms["riseHeight"] = rise_height
	ss.uniforms["baseSize"] = base_size
	ss.uniforms["midColor"] = osg.Vec3(*mid_color)
	ss.uniforms["coreColor"] = osg.Vec3(*core_color)

	return r

def build_explosion(include_smoke=False, include_embers=False):
	"""Return a Group combining a fire burst with a ground shockwave ring (and,
	optionally, a lingering smoke layer and/or a flying-debris ember layer).

	Each child gets its own `triggerTime` uniform; trigger(group, viewer) fires all
	of them at once (see trigger() below).
	"""

	group = osg.Group()

	group.children.append(build_fire())
	group.children.append(build_shockwave())

	if include_smoke:
		group.children.append(build_smoke())

	if include_embers:
		group.children.append(build_embers())

	return group

def build_multiburst(num_bursts=4, spread_radius=9.0, include_smoke=True, include_embers=True):
	"""Return a Group of `num_bursts` full explosions, each in its own MatrixTransform
	offset around a ring of `spread_radius` -- several distinct, non-identical blasts
	firing together, rather than one bigger one.

	Unlike build_explosion(), each burst's fire/shockwave/smoke/ember parameters are
	independently randomized (duration, radius, size, etc, each jittered within a sane
	range of build_*()'s own defaults) so the bursts read as genuinely different
	explosions side by side, not identical copies at different positions -- including
	a randomized flame hue (build_fire()'s mid_color/core_color), so some bursts read
	as ordinary fire and others as blue/green/violet "sci-fi" flame. Plain
	`random.uniform()`/`colorsys.hsv_to_rgb()` -- no numpy (see
	[[feedback_avoid_numpy_crutch]]).

	Each burst gets its own Program/Geometry (same build_fire()/build_shockwave()/etc.
	as everywhere else in this file) instead of sharing one draw call via a
	per-instance origin uniform array -- explosions are inherently few-at-a-time here,
	so the extra draw calls cost nothing, and this reuses every already-tested shader
	completely unchanged. See ai/context-todo-particles.md's "Open questions" for the
	uniform-array/SSBO alternative that was considered and set aside in favor of this.
	"""

	group = osg.Group()

	for i in range(num_bursts):
		angle = math.tau * i / num_bursts
		x = math.cos(angle) * spread_radius
		y = math.sin(angle) * spread_radius

		xform = osg.MatrixTransform(osg.Matrix.translate(osg.Vec3(x, y, 0.0)))
		burst = osg.Group()

		# Hue randomized per burst; core stays near-white but tinted by the same hue
		# rather than pure white, so a blue/green burst still reads as "hot at the
		# center" instead of the core looking like a mismatched leftover default.
		hue = random.random()
		mid_color = colorsys.hsv_to_rgb(hue, 0.9, 1.0)
		core_color = colorsys.hsv_to_rgb(hue, 0.25, 1.0)

		burst.children.append(build_fire(
			duration=random.uniform(0.8, 1.6),
			burst_radius=random.uniform(1.5, 3.2),
			rise_height=random.uniform(0.6, 2.0),
			base_size=random.uniform(0.35, 0.75),
			mid_color=mid_color,
			core_color=core_color,
		))
		burst.children.append(build_shockwave(
			max_radius=random.uniform(2.5, 5.5),
			duration=random.uniform(0.4, 0.9),
			ring_width=random.uniform(0.2, 0.45),
		))

		if include_smoke:
			burst.children.append(build_smoke(
				start_delay=random.uniform(0.05, 0.3),
				duration=random.uniform(2.0, 4.5),
				spread_radius=random.uniform(2.0, 4.5),
				rise_height=random.uniform(2.0, 5.0),
				base_size=random.uniform(0.5, 1.0),
				grow_amount=random.uniform(2.0, 4.5),
			))

		if include_embers:
			burst.children.append(build_embers(
				duration=random.uniform(1.0, 2.2),
				launch_speed=random.uniform(2.5, 6.0),
				gravity=random.uniform(3.0, 9.0),
				base_point_size=random.uniform(8.0, 20.0),
			))

		xform.children.append(burst)
		group.children.append(xform)

	return group

# --------------------------------------------------------------------------- #
# Camera kick: a screen-space white flash (POST_RENDER HUD camera, same shape
# as pyosg-blur.py's make_composite_hud()) plus a brief eye-space shake, now via
# osgx.CameraManipulator/osgx.ShakeCallback (osgx/CameraIntents.hpp) instead of
# the EffectManipulator Python decorator this file carried as a documented dead
# end for a while -- see aipython/06-camera-effects.md for that investigation.
# osgx.CameraManipulator<TrackballManipulator> genuinely IS a TrackballManipulator
# (real C++ CRTP inheritance, not a Python-side wrapper forwarding events through
# pybind11), so the GUIActionAdapter-casting crash that made EffectManipulator
# unusable for real interaction simply doesn't exist here -- normal orbiting/
# panning keeps working underneath a shake because there's no decorator layer
# left to break in the first place.
# --------------------------------------------------------------------------- #

FLASH_VERTEX_SHADER = """
	#version 430 core

	void main() {
		vec2 base[4] = vec2[4](
			vec2(-1.0, -1.0),
			vec2( 1.0, -1.0),
			vec2( 1.0,  1.0),
			vec2(-1.0,  1.0)
		);

		gl_Position = vec4(base[gl_VertexID % 4], 0.0, 1.0);
	}
"""

FLASH_FRAGMENT_SHADER = """
	#version 430 core

	uniform float osg_SimulationTime;
	uniform float triggerTime = -1000.0;
	uniform float duration = 0.25;

	out vec4 fragColor;

	void main() {
		float t = (osg_SimulationTime - triggerTime) / duration;

		if (t < 0.0 || t > 1.0) discard;

		// Squared falloff -- most of the brightness is gone within the first third
		// of `duration`, reading as a sharp punch rather than a slow fade.
		float alpha = (1.0 - t) * (1.0 - t) * 0.8;

		fragColor = vec4(1.0, 1.0, 1.0, alpha);
	}
"""

def build_flash_camera(width, height, duration=0.25):
	"""Return a POST_RENDER HUD Camera: a fullscreen white flash, one-shot like
	build_fire(). trigger(cam, viewer) fires it the same way as any other node.
	"""

	cam = osg.Camera()

	cam.name = "pyosg-fire flash HUD"
	cam.renderOrder = osg.Camera.POST_RENDER
	cam.clearMask = 0  # overlay only -- don't clear the already-rendered scene
	cam.viewport = osg.Viewport(0, 0, width, height)
	cam.projectionMatrix = osg.Matrix.identity()
	cam.viewMatrix = osg.Matrix.identity()
	cam.referenceFrame = osg.Transform.ABSOLUTE_RF
	cam.allowEventFocus = False

	g = osg.Geometry()

	g.primitiveSets.append(osg.DrawArrays(osg.PrimitiveSet.TRIANGLE_FAN, 0, 4))
	g.initialBound = osg.BoundingBox(-1, -1, -1, 1, 1, 1)

	p = osg.Program(name="pyosg-fire-flash", shaders=(
		osg.Shader(osg.Shader.VERTEX, FLASH_VERTEX_SHADER),
		osg.Shader(osg.Shader.FRAGMENT, FLASH_FRAGMENT_SHADER)
	))

	ss = cam.stateSet

	ss.attributes.append(p)
	ss.attributes[osg.StateAttribute.BLENDFUNC] = (
		osg.BlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA), osg.StateAttribute.ON
	)
	ss.modes[GL_DEPTH_TEST] = osg.StateAttribute.OFF
	ss.uniforms["duration"] = duration

	cam.children.append(g)

	return cam

# The dead-end EffectManipulator decorator + make_shake_effect() that used to live here
# (a Python CameraManipulator subclass wrapping an `inner` manipulator, confirmed to
# crash the moment the user dragged the mouse -- forwarding handle()'s live
# GUIActionAdapter through to another bound method requires an osgViewer::View ->
# GUIActionAdapter upcast pybind11 can't do) are gone. osgx.CameraManipulator<Base>
# solves the actual problem this was working around: real C++ CRTP inheritance means
# there's no Python-side decorator forwarding events at all, so that whole class of
# crash doesn't exist to work around. Full history of the dead end:
# aipython/06-camera-effects.md.
def camera_kick(viewer, flash_cam, shake_magnitude=3.0, shake_duration=0.3):
	"""Fire the screen flash and a brief camera shake, both starting right now.

	`shake_magnitude` is degrees (osgx.ShakeCallback's own units -- max jitter
	angle, not a translation offset like the old make_shake_effect() used).
	Requires `viewer.cameraManipulator` to be an osgx.CameraManipulator (see
	__main__ below) -- .shake() is only bound on that subclass.
	"""

	flash_cam.stateSet.uniforms["triggerTime"] = float(viewer.frameStamp.simulationTime)
	viewer.cameraManipulator.shake(shake_magnitude, shake_duration)

def trigger(node, viewer):
	"""(Re-)fire every burst under `node` -- a single Geode, or an arbitrarily nested
	tree of Groups/MatrixTransforms containing them (e.g. build_multiburst()'s
	per-burst MatrixTransform wrappers). Recurses through every Group level and sets
	triggerTime on the first non-Group node found down each branch.
	"""

	now = float(viewer.frameStamp.simulationTime)

	def walk(n):
		if isinstance(n, osg.Group):
			for child in n.children:
				walk(child)

		else:
			# No existence check needed -- uniforms[key] = value creates-or-updates on
			# its own (see UniformsTag::apply() in pyosg/osg/State.hpp). An earlier
			# version guarded this on "if already present," which meant a node's very
			# FIRST trigger() call silently did nothing (build_fire() never pre-creates
			# triggerTime, only the GLSL default exists until something assigns it) --
			# confirmed live via a diagnostic handler that surfaced the resulting
			# KeyError instead of silently no-op'ing.
			n.stateSet.uniforms["triggerTime"] = now

	walk(node)

class ExplosionKeyHandler(osgGA.GUIEventHandler):
	"""Bind number keys to different explosion nodes/presets.

	`bindings` maps ord(<digit>) -> either a node (Geode or Group), fired via
	trigger(), or a zero-arg callable (e.g. camera_kick partially applied),
	called directly -- camera effects act on the viewer/camera, not a scene
	node, so they don't fit trigger()'s node-walking shape. Numeric keys rather
	than a single key so each preset gets its own key without redesigning the
	handler.
	"""

	def __init__(self, bindings, viewer):
		super().__init__()

		self.bindings = bindings
		self.viewer = viewer

	def handle(self, ea, aa):
		if ea.type != osgGA.GUIEventAdapter.KEYDOWN:
			return False

		target = self.bindings.get(ea.key)

		if target is None:
			return False

		if callable(target):
			target()

		else:
			trigger(target, self.viewer)

		osg.notice(f"[pyosg-fire] triggered (key {chr(ea.key)})")

		return True

if __name__ == "__main__":
	osg.setNotifyLevel(osg.NotifySeverity.NOTICE)

	fire_only = build_fire()
	explosion = build_explosion()
	explosion_smoke = build_explosion(include_smoke=True)
	explosion_smoke_embers = build_explosion(include_smoke=True, include_embers=True)
	multiburst = build_multiburst()

	v = osgViewer.Viewer(osg.ArgumentParser("pyosg-fire.py", sys.argv))
	viewport = v.camera.viewport

	flash_cam = build_flash_camera(
		int(viewport.width) if viewport else 800,
		int(viewport.height) if viewport else 600,
	)

	root = osg.Group()

	root.children.append(fire_only)
	root.children.append(explosion)
	root.children.append(explosion_smoke)
	root.children.append(explosion_smoke_embers)
	root.children.append(multiburst)
	root.children.append(flash_cam)

	v.sceneData = root
	# osgx.CameraManipulator<TrackballManipulator> genuinely IS a TrackballManipulator
	# (see the module comment above camera_kick()) -- normal orbit/pan/zoom works exactly
	# like plain osgGA.TrackballManipulator(), and camera_kick()'s shake composes on top.
	v.cameraManipulator = osgx.CameraManipulator()

	def with_kick(node):
		"""Return a zero-arg callable: trigger `node`'s bursts plus the camera kick,
		both starting right now. Each successive key (3, 4, ...) reuses this instead
		of repeating the trigger()+camera_kick() pair inline.
		"""

		return lambda: (trigger(node, v), camera_kick(v, flash_cam))

	bindings = {
		ord("1"): fire_only,
		ord("2"): explosion,
		ord("3"): with_kick(explosion),
		ord("4"): with_kick(explosion_smoke),
		ord("5"): with_kick(explosion_smoke_embers),
		ord("6"): with_kick(multiburst),
	}

	v.eventHandlers.append(ExplosionKeyHandler(bindings, v))

	# --- Docked ImGui panel: enabled by default; --no-gui removes it. The -- #
	# --- panel exposes every build_fire()/build_shockwave()/build_smoke()/ -- #
	# --- build_embers() kwarg as a live slider, written to -- #
	# --- every key (1-5) that carries that layer at once, so tuning a -- #
	# --- knob and pressing plain "1" shows that layer alone with no -- #
	# --- shockwave/smoke/ember "noise" mixed in. Key 6 (multiburst) is -- #
	# --- deliberately excluded -- it randomizes each burst's params for -- #
	# --- variety (see build_multiburst()'s docstring), and forcing the -- #
	# --- shared sliders onto it would erase that. Buttons still fire the -- #
	# --- exact same bindings as the number keys (osgx.imgui -- "knobs, -- #
	# --- not frameworks", see aipython/17-particles.md). --------------- #
	if "--no-gui" not in sys.argv:
		# No deferred/compositing pipeline in this file (unlike 11-sketchfab.py) --
		# flash_cam is POST_RENDER but discard()s every pixel except during its brief
		# 0.25s flash, so the default master-camera draw hook is fine; no drawCamera
		# override needed (contrast [[project_osgdebug_imgui_python]]'s final_cam fix).
		# Pinned to the left edge like 11-sketchfab.py: osgx's ImGui build does not
		# include interactive docking, so this fixed sidebar keeps the controls out
		# of the explosion's way.
		gui_opts = osgx.imgui.Options()
		gui_opts.dock = osgx.imgui.Dock.LEFT
		gui_opts.dock_width = 320.0
		gui = osgx.imgui.Widget(v, v.camera, gui_opts)

		# Each key binding below (1/2/3/4/5) holds its OWN build_fire()/build_shockwave()/
		# etc. instances -- they can't share a single node across keys, since every preset
		# sits permanently in the scene graph and OSG draws a multi-parented node once per
		# parent path, which would double/triple/quadruple-render the same particles the
		# instant one got triggered. So instead these lists collect every same-layer node
		# across keys 1-5, and the sliders below write each change to all of them at once.
		fire_nodes = [
			fire_only,
			explosion.children[0],
			explosion_smoke.children[0],
			explosion_smoke_embers.children[0],
		]
		shockwave_nodes = [
			explosion.children[1],
			explosion_smoke.children[1],
			explosion_smoke_embers.children[1],
		]
		smoke_nodes = [explosion_smoke.children[2], explosion_smoke_embers.children[2]]
		embers_nodes = [explosion_smoke_embers.children[3]] # only key 5 carries embers

		def add_uniform_sliders(section_label, nodes, sliders, default_open=False):
			"""Add one ImGui section with a slider_float_nudge per (uniform_name,
			label, min, max, default) in `sliders`, reading/writing straight through
			each node in `nodes` (every same-layer instance across keys 1-5) --
			no rebuild needed, matches [[feedback_uniform_value_property]] (.value,
			not .getFloat()/[0]).

			The slider's displayed value is read from nodes[0] alone; every change
			is then written to ALL of them, which is what keeps every key's copy
			of this layer in lockstep with the panel instead of only key 5's.

			Every uniform is (re-)seeded to its listed default right here, once,
			before the section is added -- covers the fragment-shader-only uniforms
			(noiseScale/scrollSpeed/warpStrength/maxAlpha) that build_fire()/
			build_smoke() never explicitly set, which would otherwise raise on the
			first `.value` read. Labels are prefixed per layer ("Fire Duration", not
			"Duration") so two sliders in different sections never share an ImGui ID
			-- see [[feedback_imgui_section_label_collision]].
			"""

			stateSets = [n.stateSet for n in nodes]

			for name, label, lo, hi, default in sliders:
				for ss in stateSets:
					ss.uniforms[name] = default

			def draw(ri):
				for name, label, lo, hi, _ in sliders:
					changed, value = osgx.imgui.slider_float_nudge(
						label, stateSets[0].uniforms[name].value, lo, hi
					)

					if changed:
						for ss in stateSets:
							ss.uniforms[name] = value

			gui.addSection(
				section_label, draw, osgx.imgui.SectionOptions(default_open=default_open)
			)

		add_uniform_sliders("Fire", fire_nodes, [
			("duration", "Fire Duration", 0.3, 3.0, 1.2),
			("burstRadius", "Fire Burst Radius", 0.5, 6.0, 2.2),
			("riseHeight", "Fire Rise Height", 0.0, 4.0, 1.2),
			("baseSize", "Fire Base Size", 0.1, 1.5, 0.5),
			("noiseScale", "Fire Noise Scale", 0.5, 8.0, 3.0),
			("scrollSpeed", "Fire Scroll Speed", 0.0, 3.0, 0.8),
			("warpStrength", "Fire Warp Strength", 0.0, 1.5, 0.4),
		], default_open=True)

		def draw_fire_colors(ri):
			# Same read-nodes[0]/write-all pattern as add_uniform_sliders() above,
			# just inlined here since color_edit3() isn't a plain float slider.
			mid = fire_nodes[0].stateSet.uniforms["midColor"].value
			changed, r, g, b = osgx.imgui.color_edit3("Fire Mid Color", mid.x, mid.y, mid.z)

			if changed:
				for n in fire_nodes:
					n.stateSet.uniforms["midColor"] = osg.Vec3(r, g, b)

			core = fire_nodes[0].stateSet.uniforms["coreColor"].value
			changed, r, g, b = osgx.imgui.color_edit3("Fire Core Color", core.x, core.y, core.z)

			if changed:
				for n in fire_nodes:
					n.stateSet.uniforms["coreColor"] = osg.Vec3(r, g, b)

		gui.addSection("Fire Color", draw_fire_colors, osgx.imgui.SectionOptions(default_open=True))

		add_uniform_sliders("Shockwave", shockwave_nodes, [
			("duration", "Shockwave Duration", 0.1, 2.0, 0.6),
			("maxRadius", "Shockwave Max Radius", 1.0, 8.0, 4.0),
			("ringWidth", "Shockwave Ring Width", 0.05, 1.0, 0.3),
		])

		add_uniform_sliders("Smoke", smoke_nodes, [
			("startDelay", "Smoke Start Delay", 0.0, 1.0, 0.15),
			("duration", "Smoke Duration", 0.5, 8.0, 3.0),
			("spreadRadius", "Smoke Spread Radius", 0.5, 8.0, 3.2),
			("riseHeight", "Smoke Rise Height", 0.0, 8.0, 3.5),
			("baseSize", "Smoke Base Size", 0.1, 2.0, 0.7),
			("growAmount", "Smoke Grow Amount", 1.0, 6.0, 3.0),
			("noiseScale", "Smoke Noise Scale", 0.5, 6.0, 2.0),
			("scrollSpeed", "Smoke Scroll Speed", 0.0, 2.0, 0.3),
			("warpStrength", "Smoke Warp Strength", 0.0, 1.5, 0.5),
			("maxAlpha", "Smoke Max Alpha", 0.0, 1.0, 0.35),
		])

		add_uniform_sliders("Embers", embers_nodes, [
			("duration", "Ember Duration", 0.3, 4.0, 1.6),
			("launchSpeed", "Ember Launch Speed", 0.5, 10.0, 4.0),
			("gravity", "Ember Gravity", 0.0, 15.0, 6.0),
			("basePointSize", "Ember Base Point Size", 2.0, 40.0, 14.0),
		])

		def draw_triggers(ri):
			# Same bindings dict ExplosionKeyHandler uses -- a button fires the exact
			# preset its number key does, never a parallel/divergent copy. bindings'
			# values are already either a node (needs trigger()) or a zero-arg
			# callable (with_kick()'s closures, called directly) -- ExplosionKeyHandler
			# .handle() branches on callable() the same way.
			for key, label in (
				("1", "1: Fire"),
				("2", "2: +Shockwave"),
				("3", "3: +Camera Kick"),
				("4", "4: +Smoke"),
				("5", "5: +Embers (tuned above)"),
				("6", "6: Multi-Burst (random)"),
			):
				if osgx.imgui.button(label):
					target = bindings[ord(key)]

					target() if callable(target) else trigger(target, v)

		gui.addSection("Triggers", draw_triggers, osgx.imgui.SectionOptions(default_open=True))

	trigger(fire_only, v)

	if "--repl" in sys.argv:
		from pyosg_repl import repl

		repl(v, globals())

	else:
		while not v.done:
			v.frame()

			time.sleep(1.0 / 60.0)
