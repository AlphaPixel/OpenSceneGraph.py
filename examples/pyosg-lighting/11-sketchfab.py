#!/usr/bin/env python3

# Step 11 -- Sketchfab-parity capstone: deferred G-buffer + SSAO/bloom/tonemap post-fx chain
#
# This step used to hand-build its OWN deferred G-buffer + composite lighting pass (the same PBR/
# IBL/shadow math 09-ibl.py's single-pass shader had, just split across two passes) -- osgx's
# header for PBRIBLGBuffer.create()/PBRIBLLightingScene.create() says outright that split was
# "hand-built and validated pixel-for-pixel against Sketchfab's own renderer" against THIS file,
# so re-deriving it by hand a second time here would just be re-teaching a solved problem. This
# step pivots the G-buffer + lighting-pass math to those two calls, exactly like 09/10 pivoted the
# single-pass shader to PBRIBLScene.create() -- everything downstream of the lighting pass (bloom,
# the tonemap-comparison/post-fx final pass) stays 100% hand-rolled Python, since osgx deliberately
# does NOT standardize bloom generation (too taste-dependent) and this step's whole teaching point
# is comparing tonemap curves live, which doesn't fit the (link-time-only) osgx_Tonemap() hook. SSAO
# itself is a SECOND, smaller pivot (2026-08-21, after osgx.SSAO shipped, ported straight
# from this file's own proven-live hand-rolled version) -- no longer hand-rolled Python either, see
# the "--- SSAO ---" section below and PBRIBLLightingPassOptions.aoTexture's own doc comment.
#
# Real, human-visible tradeoffs from this pivot, called out up front rather than discovered later:
# - The 0-9 raw-channel/lighting-term debug views are gone, replaced by a smaller 0-6 set (see
#   "Visualize Mode" below). PBRIBLLightingScene.create()'s own diagnostics option exists but isn't
#   wired up to anything in its shader yet (a real osgx gap, not something this file works around
#   by hand-rolling a second lighting shader) -- direct-only/IBL-only/shadow-only isolation would
#   need that ported first. What's left (albedo/normal/material/emissive/depth/AO) is exactly what
#   a raw texture blit CAN show without any new shader math.
# - --msaa and the "Debug Tint (red)" shadow-strength aid are both gone -- PBRIBLGBuffer.create()
#   doesn't expose a G-buffer MSAA knob, and there's no hook to tint the shared lighting shader's
#   output. The room/grid backdrop is a much clearer way to judge shadow softness/strength anyway.
# - The light rig is a single directional key light via osgx.LightSet (unchanged from what
#   this file already simplified to on 2026-07-11 -- fill lights were dropped THEN, not by this
#   pivot). It's now interactively draggable via the SAME ShadowMap.reposition()
#   this session's osgx-shadow.cpp/osgx-gbuffer.cpp proofs already validated live.
#
# Pipeline shape:
# shadow_map.camera -> gbuffer.camera (MRT: albedo+ao/normal/material/emissive/position) ->
# ssao.rawCamera -> ssao.blurCamera (osgx.SSAO -- generic hemisphere-kernel SSAO, not
# hand-rolled here anymore, see the "--- SSAO ---" section below) -> lighting.node (re-targeted to
# PRE_RENDER, writes LINEAR HDR, no tonemap) -> bloom_threshold_cam -> bloom_blur_h_cam ->
# bloom_blur_v_cam -> final_cam (bloom add, tonemap, gamma, vignette/grain/CA/sharpen/color-balance
# -> window) -> debug_cam (raw G-buffer blit, only visible when Visualize Mode != 0) -> gizmo
# overlay (always on top).

import sys
import os
import math
import argparse
import asyncio
import pathlib

os.environ.update({
	"OSG_WINDOW": "50 50 1169 768",
	"OSG_THREADING": "SingleThreaded",
	"OSG_GL_CONTEXT_PROFILE_MASK": "1",
	"OSG_GL_VERSION": "4.6",
	"OSG_GL_CONTEXT_VERSION": "4.6",
})

from OpenSceneGraph import *
from OpenSceneGraph.GL import *

import osgx

W, H = 1169, 768

THIS_DIR = pathlib.Path(__file__).resolve().parent
DATA_DIR = THIS_DIR / "data"

# Initial light direction only -- interactively draggable from here via the "Light Direction"
# ImGui section (LightOrbit below), unlike 08/09/10's fixed key light.
KEY_LIGHT_DIR = osg.Vec3(0.6, 0.4, -0.6).normalized()
KEY_LIGHT_COLOR = osg.Vec3(1.0, 0.95, 0.85)
KEY_LIGHT_INTENSITY = 3.0

# Bare name (e.g. "Corset") -> glTF-Sample-Assets/Models/<name>/glTF/<name>.gltf via
# osgx.findDataFile(), same convention every other step in this series uses.
def resolve_model(value):
	path = pathlib.Path(value).expanduser()

	if path.is_file():
		return str(path)

	return osgx.findDataFile(value) or osgx.findDataFile(
		path.stem, ("glTF-Sample-Assets/Models/{}/glTF/{}.gltf",)
	) or None

# HDR/manifest assets for this step live locally in pyosg-lighting/data/ -- checked first, falling
# back to osgx.findDataFile() for anything found via OSG_FILE_PATH instead.
def resolve_asset(value, suffix):
	path = pathlib.Path(value).expanduser()

	if path.is_file():
		return str(path)

	local = DATA_DIR / f"{value}.{suffix}"

	if local.is_file():
		return str(local)

	return osgx.findDataFile(value, (), suffix) or None

# --------------------------------------------------------------------------- #
# Shaders
# --------------------------------------------------------------------------- #

# Shared G-buffer vertex stage for the room/frame's simple unlit-material geometry.
UNLIT_GBUFFER_VERTEX = """
#version 460 core

in vec4 osg_Vertex;
in vec3 osg_Normal;

uniform mat4 osg_ModelViewProjectionMatrix;
uniform mat4 osg_ModelViewMatrix;
uniform mat3 osg_NormalMatrix;

out vec3 vNormal;
out vec3 vPosition;

void main() {
	vNormal = normalize(osg_NormalMatrix * osg_Normal);
	vPosition = (osg_ModelViewMatrix * osg_Vertex).xyz;

	gl_Position = osg_ModelViewProjectionMatrix * osg_Vertex;
}
"""

# The grid room writes a complete G-buffer record (NOT PBRIBLGBuffer.create()'s glTF-material
# shader -- a procedural grid has none of that data) so it shares the model's real depth buffer
# and receives its shadow, added as an extra child of the geometry pass's own camera -- same
# pattern osgx-gbuffer.cpp's own floor addition already proved out. Channel layout matches
# PBRIBLGBuffer exactly (see PBRIBL.cpp's GBUFFER_FRAGMENT_SHADER_SRC): gAlbedo.a = ambient
# occlusion (1.0 = none baked in), gMaterial = (roughness, metallic, unused, unused).
GRID_ROOM_VERTEX = """
#version 460 core

#pragma osgx::grid INPUTS

in vec4 osg_Vertex;
in vec3 osg_Normal;
in vec2 osg_MultiTexCoord0;

uniform mat4 osg_ModelViewProjectionMatrix;
uniform mat4 osg_ModelViewMatrix;
uniform mat3 osg_NormalMatrix;
out vec2 vGridPos;
out vec3 vNormal;
out vec3 vPosition;

void main() {
	vGridPos = osg_MultiTexCoord0 * u_grid.canvasSize;
	vNormal = normalize(osg_NormalMatrix * osg_Normal);
	vPosition = (osg_ModelViewMatrix * osg_Vertex).xyz;
	gl_Position = osg_ModelViewProjectionMatrix * osg_Vertex;
}
"""

GRID_ROOM_FRAGMENT = """
#version 460 core

#pragma osgx::grid GRID

in vec2 vGridPos;
in vec3 vNormal;
in vec3 vPosition;

uniform float roomRoughness;
uniform float roomMetallic;

layout(location = 0) out vec4 gAlbedo;
layout(location = 1) out vec4 gNormal;
layout(location = 2) out vec4 gMaterial;
layout(location = 3) out vec4 gEmissive;
layout(location = 4) out vec4 gPosition;

void main() {
	vec3 albedo = osgx_GridColor(vGridPos).rgb;

	gAlbedo = vec4(albedo, 1.0); // a = ambient occlusion (none baked in)
	gNormal = vec4(normalize(vNormal), 0.0);
	gMaterial = vec4(roomRoughness, roomMetallic, 0.0, 0.0);
	gEmissive = vec4(0.0, 0.0, 0.0, 1.0);
	gPosition = vec4(vPosition, 1.0);
}
"""

FRAME_GBUFFER_FRAGMENT = """
#version 460 core

in vec3 vNormal;
in vec3 vPosition;

uniform vec3 frameColor;

layout(location = 0) out vec4 gAlbedo;
layout(location = 1) out vec4 gNormal;
layout(location = 2) out vec4 gMaterial;
layout(location = 3) out vec4 gEmissive;
layout(location = 4) out vec4 gPosition;

void main() {
	gAlbedo = vec4(0.0, 0.0, 0.0, 1.0); // black, unoccluded -- all its color is emissive below
	gNormal = vec4(normalize(vNormal), 0.0);
	gMaterial = vec4(1.0, 0.0, 0.0, 0.0);
	gEmissive = vec4(frameColor, 1.0);
	gPosition = vec4(vPosition, 1.0);
}
"""

# Bloom bright-pass extract -- soft-knee smoothstep rather than a hard cutoff, so bloom doesn't
# flicker as luminance crosses the threshold frame to frame.
BLOOM_THRESHOLD_FRAGMENT_SHADER = """
#version 460 core

uniform sampler2D hdrColorTex;
uniform float bloomThreshold;

in vec2 vUV;

out vec4 fragColor;

void main() {
	vec3 c = texture(hdrColorTex, vUV).rgb;
	float lum = dot(c, vec3(0.2126, 0.7152, 0.0722));

	fragColor = vec4(c * smoothstep(bloomThreshold, bloomThreshold + 0.5, lum), 1.0);
}
"""

# Generic separable-Gaussian blur pass -- same 9-tap weights as examples/pyosg-blur.py, duplicated
# here rather than imported (every examples/pyosg-lighting/*.py file is self-contained). Used
# twice for bloom (horizontal then vertical, each into its own texture -- not ping-ponged).
BLUR_FRAGMENT_SHADER = """
#version 460 core

uniform sampler2D inputTex;
uniform vec2 texelStep;

in vec2 vUV;

out vec4 fragColor;

void main() {
	vec4 sum = vec4(0.0);

	sum += texture(inputTex, vUV - 4.0 * texelStep) * 0.0162162162;
	sum += texture(inputTex, vUV - 3.0 * texelStep) * 0.0540540541;
	sum += texture(inputTex, vUV - 2.0 * texelStep) * 0.1216216216;
	sum += texture(inputTex, vUV - 1.0 * texelStep) * 0.1945945946;
	sum += texture(inputTex, vUV) * 0.2270270270;
	sum += texture(inputTex, vUV + 1.0 * texelStep) * 0.1945945946;
	sum += texture(inputTex, vUV + 2.0 * texelStep) * 0.1216216216;
	sum += texture(inputTex, vUV + 3.0 * texelStep) * 0.0540540541;
	sum += texture(inputTex, vUV + 4.0 * texelStep) * 0.0162162162;

	fragColor = sum;
}
"""

# Debug blit: samples one raw G-buffer/AO texture into a fullscreen quad, with a small per-channel
# remap. NOT part of osgx -- purely an example-level diagnostic aid, same role pyosg-mrt.py's own
# visualizeMode branches and osgx-gbuffer.cpp's DEBUG_BLIT_FRAGMENT_SHADER play. See the module
# docstring for why this is a smaller mode set than the old hand-rolled composite shader's 0-9.
DEBUG_BLIT_FRAGMENT_SHADER = """
#version 460 core

uniform sampler2D blitTex;
uniform int channelMode; // 0=passthrough 1=signed-normal 2=scalar-red 3=gamma-color 4=view-space-depth
uniform float depthScale;

in vec2 vUV;

out vec4 fragColor;

void main() {
	vec4 s = texture(blitTex, vUV);

	if (channelMode == 1) {
		fragColor = vec4(s.rgb * 0.5 + 0.5, 1.0);

		return;
	}

	if (channelMode == 2) {
		fragColor = vec4(vec3(s.r), 1.0);

		return;
	}

	if (channelMode == 3) {
		fragColor = vec4(pow(max(s.rgb, 0.0), vec3(1.0 / 2.2)), 1.0);

		return;
	}

	if (channelMode == 4) {
		float t = clamp(-s.z / depthScale, 0.0, 1.0);

		fragColor = vec4(vec3(t), 1.0);

		return;
	}

	fragColor = vec4(s.rgb, 1.0);
}
"""

# Final LDR pass: additively composites bloom into the HDR color, tonemaps, gamma-encodes, then
# applies vignette/grain/chromatic-aberration/sharpening/color-balance -- all cheap single-pass
# color-only effects, so they share one shader rather than a pass each. No visualizeMode branch
# here anymore -- debug views bypass this whole chain via debug_cam's own nodeMask toggle instead
# (see select_visualize_mode() below), the same mechanism osgx-gbuffer.cpp's VisualizeModeHandler
# already proved out, rather than this pass having to know about debug modes at all.
FINAL_FRAGMENT_SHADER = """
#version 460 core

uniform sampler2D hdrColorTex; // unit 0
uniform sampler2D bloomTex;    // unit 1
uniform sampler2D aoTex;       // unit 2: same blurred SSAO the lighting pass already reads

uniform bool postEnabled;

uniform int tonemapMode; // 0=PBR Neutral 1=ACES(Narkowicz) 2=Reinhard 3=None(clamped linear)
uniform float exposure; // stops (EV); multiplies linear HDR as exp2(exposure) before tonemap
uniform float bloomStrength;
uniform float caStrength;
uniform float sharpenStrength;
uniform float vignetteStrength;
uniform float grainStrength;
uniform float grainSize;      // pixels per grain cell; 1.0 = original per-pixel noise
uniform bool grainAnimated;   // false = same noise pattern every frame (no osg_SimulationTime)
uniform float grainAOBoost;   // 0 = grain everywhere equally; 1 = grain only where aoTex is dark
uniform float colorLift;
uniform float colorGamma;
uniform float colorGain;
uniform float osg_SimulationTime;

in vec2 vUV;

out vec4 fragColor;

// Khronos PBR Neutral tonemapping.
vec3 tonemapPBRNeutral(vec3 color) {
	const float startCompression = 0.8 - 0.04;
	const float desaturation = 0.15;
	float x = min(color.r, min(color.g, color.b));
	float offset = x < 0.08 ? x - 6.25 * x * x : 0.04;
	color -= offset;
	float peak = max(color.r, max(color.g, color.b));
	if (peak >= startCompression) {
		float d = 1.0 - startCompression;
		float newPeak = 1.0 - d * d / (peak + d - startCompression);
		color *= newPeak / peak;
		float g = 1.0 - 1.0 / (desaturation * (peak - newPeak) + 1.0);
		color = mix(color, vec3(newPeak), g);
	}
	return clamp(color, 0.0, 1.0);
}

// Narkowicz 2015 fit to the ACES reference rendering transform -- the common "ACES-style" filmic
// curve most game engines actually ship (the real ACES RRT+ODT is a 3D LUT, not a closed-form
// curve). More contrast/saturation falloff in the highlights than PBR Neutral, which is the point
// of comparing them side by side.
vec3 tonemapACES(vec3 x) {
	const float a = 2.51;
	const float b = 0.03;
	const float c = 2.43;
	const float d = 0.59;
	const float e = 0.14;

	return clamp((x * (a * x + b)) / (x * (c * x + d) + e), 0.0, 1.0);
}

// Simple Reinhard (x / (1+x)) -- the baseline every other curve gets judged against.
vec3 tonemapReinhard(vec3 x) {
	return x / (1.0 + x);
}

void main() {
	vec3 hdr;

	if (postEnabled) {
		// Chromatic aberration has to happen WHILE assembling color, not after -- you can't
		// offset one channel of an already-combined vec3. Each offset sample includes its own
		// bloom contribution so CA and bloom don't visibly separate.
		vec2 caDir = (vUV - 0.5) * caStrength;

		float r = texture(hdrColorTex, vUV - caDir).r + texture(bloomTex, vUV - caDir).r * bloomStrength;
		float g = texture(hdrColorTex, vUV).g          + texture(bloomTex, vUV).g          * bloomStrength;
		float b = texture(hdrColorTex, vUV + caDir).b + texture(bloomTex, vUV + caDir).b * bloomStrength;

		hdr = vec3(r, g, b);

		// Sharpen (unsharp mask), in linear HDR, on the un-aberrated center sample.
		vec2 texel = 1.0 / vec2(textureSize(hdrColorTex, 0));
		vec3 center = texture(hdrColorTex, vUV).rgb;
		vec3 blurred = (
			texture(hdrColorTex, vUV + vec2(texel.x, 0.0)).rgb +
			texture(hdrColorTex, vUV - vec2(texel.x, 0.0)).rgb +
			texture(hdrColorTex, vUV + vec2(0.0, texel.y)).rgb +
			texture(hdrColorTex, vUV - vec2(0.0, texel.y)).rgb
		) * 0.25;

		hdr += (center - blurred) * sharpenStrength;

	} else {
		hdr = texture(hdrColorTex, vUV).rgb;
	}

	// Exposure applies regardless of postEnabled -- core linear-HDR-to-tonemap step, not a
	// stylistic extra like CA/sharpen/vignette/grain below.
	hdr *= exp2(exposure);

	vec3 color;

	if (tonemapMode == 1) color = tonemapACES(hdr);
	else if (tonemapMode == 2) color = tonemapReinhard(hdr);
	else if (tonemapMode == 3) color = clamp(hdr, 0.0, 1.0);
	else color = tonemapPBRNeutral(hdr);

	color = pow(color, vec3(1.0 / 2.2));

	if (postEnabled) {
		color = pow(max(color + colorLift, 0.0), vec3(1.0 / colorGamma)) * colorGain;

		float d = distance(vUV, vec2(0.5));
		float vig = smoothstep(0.8, 0.2, d);
		color *= mix(1.0 - vignetteStrength, 1.0, vig);

		vec2 grainCell = floor(gl_FragCoord.xy / max(grainSize, 1.0));

		if (grainAnimated) grainCell += osg_SimulationTime;

		float g = fract(sin(dot(grainCell, vec2(12.9898, 78.233))) * 43758.5453);

		float aoMask = mix(1.0, 1.0 - texture(aoTex, vUV).r, grainAOBoost);

		color += (g - 0.5) * grainStrength * aoMask;
	}

	fragColor = vec4(clamp(color, 0.0, 1.0), 1.0);
}
"""

# --------------------------------------------------------------------------- #
# G-buffer + post-processing camera builders
# --------------------------------------------------------------------------- #

# Generic fullscreen post-process RTT camera factory. `textures` is {unit: (texture, uniform_name)}.
def make_fullscreen_rtt_pass(textures, output_tex, frag_shader, w, h, name="Post RTT", order=1, extra_uniforms=None):
	cam = osg.Camera()

	cam.name = name
	cam.renderOrder = (osg.Camera.PRE_RENDER, order)
	cam.dataVariance = osg.Object.DYNAMIC
	cam.renderTargetImplementation = osg.Camera.FRAME_BUFFER_OBJECT
	cam.clearMask = GL_COLOR_BUFFER_BIT
	cam.clearColor = osg.Vec4(0.0, 0.0, 0.0, 0.0)
	cam.viewport = osg.Viewport(0, 0, w, h)
	cam.projectionMatrix = osg.Matrix.identity()
	cam.viewMatrix = osg.Matrix.identity()
	cam.referenceFrame = osg.Transform.ABSOLUTE_RF
	cam.allowEventFocus = False

	cam.attach(osg.Camera.COLOR_BUFFER0, output_tex)

	ss = cam.stateSet
	# Fullscreen passes have no depth relationship. OSG gives this FBO an implicit depth
	# renderbuffer; if depth testing is inherited while only color is cleared, frame 0 writes
	# depth and identical frame-1 fragments all fail GL_LESS.
	ss.modes[GL_DEPTH_TEST] = osg.StateAttribute.OFF | osg.StateAttribute.OVERRIDE

	for unit, (tex, uniform_name) in textures.items():
		ss.textureAttributes[unit] = tex
		ss.uniforms[uniform_name] = unit

	if extra_uniforms:
		for k, val in extra_uniforms.items():
			ss.uniforms[k] = val

	p = osg.Program(name=f"{name}_program", shaders=(
		osg.Shader(osg.Shader.VERTEX, osgx.FULLSCREEN_VERT),
		osg.Shader(osg.Shader.FRAGMENT, frag_shader),
	))

	ss.attributes.append(p)

	g = osg.Geode()
	g.drawables.append(osg.createTexturedQuadGeometry(
		osg.Vec3(-1.0, -1.0, -1.0),
		osg.Vec3(2.0, 0.0, 0.0),
		osg.Vec3(0.0, 2.0, 0.0)
	))

	cam.children.append(g)

	return cam

# Bloom: threshold-extract -> horizontal blur -> vertical blur. Single-scale two-pass blur, not a
# downsample/upsample mip pyramid -- the sanctioned simplification for a teaching example.
def create_bloom_cameras(hdr_color_tex, w=W, h=H):
	bright_tex = osg.Texture2D(
		size=(w, h),
		internalFormat=GL_RGB16F,
		filter=(osg.Texture.LINEAR, osg.Texture.LINEAR),
	)

	blur_a_tex = osg.Texture2D(
		size=(w, h),
		internalFormat=GL_RGB16F,
		filter=(osg.Texture.LINEAR, osg.Texture.LINEAR),
	)

	blur_b_tex = osg.Texture2D(
		size=(w, h),
		internalFormat=GL_RGB16F,
		filter=(osg.Texture.LINEAR, osg.Texture.LINEAR),
	)

	for tex in (bright_tex, blur_a_tex, blur_b_tex):
		tex.dataVariance = osg.Object.DYNAMIC

	threshold_cam = make_fullscreen_rtt_pass(
		textures={0: (hdr_color_tex, "hdrColorTex")},
		output_tex=bright_tex,
		frag_shader=BLOOM_THRESHOLD_FRAGMENT_SHADER,
		w=w, h=h,
		name="BloomThreshold",
		order=5,
		extra_uniforms={"bloomThreshold": 1.0},
	)

	blur_h_cam = make_fullscreen_rtt_pass(
		textures={0: (bright_tex, "inputTex")},
		output_tex=blur_a_tex,
		frag_shader=BLUR_FRAGMENT_SHADER,
		w=w, h=h,
		name="BloomBlurH",
		order=6,
		extra_uniforms={"texelStep": osg.Vec2(1.0 / float(w), 0.0)},
	)

	blur_v_cam = make_fullscreen_rtt_pass(
		textures={0: (blur_a_tex, "inputTex")},
		output_tex=blur_b_tex,
		frag_shader=BLUR_FRAGMENT_SHADER,
		w=w, h=h,
		name="BloomBlurV",
		order=7,
		extra_uniforms={"texelStep": osg.Vec2(0.0, 1.0 / float(h))},
	)

	return threshold_cam, blur_h_cam, blur_v_cam, blur_b_tex

# Final LDR pass -- draws straight to the window (no renderTargetImplementation set).
def create_final_camera(hdr_color_tex, bloom_tex, ssao_tex, w=W, h=H):
	cam = osg.Camera(
		referenceFrame=osg.Transform.ABSOLUTE_RF,
		renderOrder=osg.Camera.POST_RENDER,
		clearMask=0,
		allowEventFocus=False,
		projectionMatrix=osg.Matrix.identity(),
		viewMatrix=osg.Matrix.identity(),
		name="Final",
	)

	g = osg.Geode()
	g.drawables.append(osg.createTexturedQuadGeometry(
		osg.Vec3(-1.0, -1.0, -1.0),
		osg.Vec3(2.0, 0.0, 0.0),
		osg.Vec3(0.0, 2.0, 0.0)
	))

	cam.children.append(g)

	ss = cam.stateSet
	ss.modes[GL_DEPTH_TEST] = osg.StateAttribute.OFF | osg.StateAttribute.OVERRIDE
	ss.textureAttributes[0] = hdr_color_tex
	ss.textureAttributes[1] = bloom_tex
	ss.textureAttributes[2] = ssao_tex
	ss.uniforms["hdrColorTex"] = 0
	ss.uniforms["bloomTex"] = 1
	ss.uniforms["aoTex"] = 2

	p = osg.Program(name="final_post", shaders=(
		osg.Shader(osg.Shader.VERTEX, osgx.FULLSCREEN_VERT),
		osg.Shader(osg.Shader.FRAGMENT, FINAL_FRAGMENT_SHADER),
	))

	g.stateSet.attributes.append(p)

	return cam

# Debug blit camera -- only visible when Visualize Mode != 0 (see select_visualize_mode()).
def create_debug_camera(depth_scale, w=W, h=H):
	cam = osg.Camera(
		name="DebugBlit",
		referenceFrame=osg.Transform.ABSOLUTE_RF,
		renderOrder=(osg.Camera.POST_RENDER, 1),
		clearMask=0,
		allowEventFocus=False,
		projectionMatrix=osg.Matrix.identity(),
		viewMatrix=osg.Matrix.identity(),
		nodeMask=0,
	)

	g = osg.Geode()
	g.drawables.append(osg.createTexturedQuadGeometry(
		osg.Vec3(-1.0, -1.0, -1.0),
		osg.Vec3(2.0, 0.0, 0.0),
		osg.Vec3(0.0, 2.0, 0.0)
	))

	cam.children.append(g)

	ss = cam.stateSet

	ss.modes[GL_DEPTH_TEST] = osg.StateAttribute.OFF | osg.StateAttribute.OVERRIDE

	p = osg.Program(name="debug_blit", shaders=(
		osg.Shader(osg.Shader.VERTEX, osgx.FULLSCREEN_VERT),
		osg.Shader(osg.Shader.FRAGMENT, DEBUG_BLIT_FRAGMENT_SHADER),
	))

	ss.attributes.append(p)
	ss.uniforms["blitTex"] = 0
	ss.uniforms["depthScale"] = depth_scale

	channel_mode_u = osg.Uniform("channelMode", 0)

	ss.uniforms.extend((channel_mode_u,))

	return cam, channel_mode_u

def create_grid_room(bound_center, bound_radius, floor_z, room_size):
	"""Create the optional Z-up model guide room.

	`room_size` is the full floor width/depth. The room is centered on the asset's horizontal
	bound center, while its floor is explicitly positioned so callers can place it at the model's
	conservative base.
	"""
	half_width = room_size * 0.5
	room_height = max(
		bound_center.z + bound_radius - floor_z + bound_radius * 0.5,
		room_size * 0.75
	)
	center_x, center_y = bound_center.x, bound_center.y
	frame_width = max(bound_radius * 0.035, room_size * 0.008)

	grid_settings = osgx.GridSettings()
	grid_program = osg.Program(name="grid_room_gbuffer", shaders=(
		osg.Shader(osg.Shader.VERTEX, osgx.resolveShaderLibs(GRID_ROOM_VERTEX)),
		osg.Shader(osg.Shader.FRAGMENT, osgx.resolveShaderLibs(GRID_ROOM_FRAGMENT)),
	))
	grid_settings.canvasSize = osg.Vec2(500.0, 500.0)
	grid_settings.gridInterval = 50.0
	grid_settings.gridIntervalStrong = 250.0
	grid_settings.lineWidthPx = 1.0
	grid_settings.colorBg = osg.Vec4(0.055, 0.070, 0.110, 1.0)
	grid_settings.colorLine = osg.Vec4(0.20, 0.30, 0.48, 1.0)
	grid_settings.colorLineStrong = osg.Vec4(0.52, 0.68, 0.90, 1.0)
	frame_program = osg.Program(name="grid_room_frame_gbuffer", shaders=(
		osg.Shader(osg.Shader.VERTEX, UNLIT_GBUFFER_VERTEX),
		osg.Shader(osg.Shader.FRAGMENT, FRAME_GBUFFER_FRAGMENT),
	))

	def make_grid(corner, width, height):
		grid = osgx.Grid(corner, width, height)
		grid.settings = grid_settings
		grid.stateSet.uniforms["roomRoughness"] = 0.85
		grid.stateSet.uniforms["roomMetallic"] = 0.0
		grid.stateSet.attributes[osg.StateAttribute.PROGRAM] = (
			grid_program,
			osg.StateAttribute.ON | osg.StateAttribute.OVERRIDE
		)
		# The G-buffer must write every attachment without blending, including the grid's opaque
		# background, rather than blending normals with the cleared targets.
		grid.stateSet.modes[GL_BLEND] = osg.StateAttribute.OFF | osg.StateAttribute.OVERRIDE

		return grid

	floor = make_grid(
		osg.Vec3(center_x - half_width, center_y - half_width, floor_z),
		osg.Vec3(room_size, 0.0, 0.0),
		osg.Vec3(0.0, room_size, 0.0)
	)
	back_wall = make_grid(
		osg.Vec3(center_x - half_width, center_y + half_width, floor_z),
		osg.Vec3(room_size, 0.0, 0.0),
		osg.Vec3(0.0, 0.0, room_height)
	)
	right_wall = make_grid(
		osg.Vec3(center_x + half_width, center_y - half_width, floor_z),
		osg.Vec3(0.0, 0.0, room_height),
		osg.Vec3(0.0, room_size, 0.0)
	)

	panels = osg.Geode()
	panels.drawables.extend((floor, back_wall, right_wall))

	front_left = osg.Vec3(center_x - half_width, center_y - half_width, floor_z)
	front_right = osg.Vec3(center_x + half_width, center_y - half_width, floor_z)
	back_left = osg.Vec3(center_x - half_width, center_y + half_width, floor_z)
	back_right = osg.Vec3(center_x + half_width, center_y + half_width, floor_z)
	back_left_top = back_left + osg.Vec3(0.0, 0.0, room_height)
	back_right_top = back_right + osg.Vec3(0.0, 0.0, room_height)
	front_right_top = front_right + osg.Vec3(0.0, 0.0, room_height)

	frame = osg.Geode()

	def add_frame_rod(start, end):
		delta = end - start
		midpoint = (start + end) * 0.5
		size = osg.Vec3(
			max(abs(delta.x), frame_width),
			max(abs(delta.y), frame_width),
			max(abs(delta.z), frame_width)
		)
		frame.drawables.append(osg.ShapeDrawable(osg.Box(midpoint, size.x, size.y, size.z)))

	for start, end in (
		(front_left, front_right), (front_left, back_left),
		(back_left, back_right), (front_right, back_right), (back_right, back_right_top),
		(back_left, back_left_top), (back_left_top, back_right_top),
		(front_right, front_right_top), (front_right_top, back_right_top),
	):
		add_frame_rod(start, end)

	for position in (
		front_left, front_right, back_left, back_right,
		back_left_top, back_right_top, front_right_top,
	):
		frame.drawables.append(osg.ShapeDrawable(osg.Sphere(position, frame_width * 0.75)))

	frame.stateSet.attributes[osg.StateAttribute.PROGRAM] = (
		frame_program,
		osg.StateAttribute.ON | osg.StateAttribute.OVERRIDE
	)
	frame.stateSet.uniforms["frameColor"] = osg.Vec3(0.55, 0.60, 0.70)

	room = osg.Group()
	room.children.extend((panels, frame))

	return room, (floor, back_wall, right_wall)

# --------------------------------------------------------------------------- #
# Light orbit -- drives BOTH osgx.LightSet and the shadow map now (was a
# raw uniform + a per-frame shadow_cam.viewMatrix recompute in update_uniforms())
# --------------------------------------------------------------------------- #

class LightOrbit:
	"""The key light's DIRECTION, as the two angles a direction actually has.

	Azimuth (around Z) and elevation (up from the XY plane), both in radians here and shown in
	degrees by the ImGui section. A directional light has no position and no distance -- osgx
	discards magnitude at both consumers (PBR.hpp's osgx_DirectionalLightRadiance() does
	`L = -normalize(direction)`, and Shadow.cpp's ShadowMap::reposition() normalizes
	before building its frustum), so only the direction's ORIENTATION can ever have an effect.

	This deliberately replaces an earlier cylindrical (azimuth / orbit-radius / height)
	parameterization inherited from when this file drove a positional light. Those three knobs
	fed the same normalized direction, which made them a genuinely misleading set of controls:
	"Orbit Radius" and "Height" were not a radius and a height at all -- only their RATIO did
	anything (it set elevation), and scaling both together did nothing whatsoever. Two sliders
	encoding one degree of freedom, plus a third direction that was a no-op. See
	[[feedback_linear_interactive_controls]]: interactive state should be the real DOFs, so that
	every distinct slider position is a distinct result.

	Every _sync() call pushes the new direction into BOTH the live LightSet (so direct lighting
	updates immediately) and ShadowMap.reposition() (so the shadow tracks
	it) -- the same two-call pattern this session's osgx-shadow.cpp/osgx-gbuffer.cpp proofs
	already validated live, just driven by ImGui sliders here instead of SliderFloat3.
	"""

	def __init__(self, lights, shadow_map, shadow_options, bound_center, bound_radius, color, intensity):
		self.lights = lights
		self.shadow_map = shadow_map
		self.shadow_options = shadow_options
		self.bound_center = bound_center
		self.bound_radius = bound_radius
		self.color = color
		self.intensity = intensity

		d = KEY_LIGHT_DIR
		self.azimuth = math.atan2(d.y, d.x)
		self.elevation = math.atan2(d.z, math.hypot(d.x, d.y))
		self._sync()

	def _sync(self):
		# Unit-length by construction. Neither consumer requires that (both normalize), but it
		# keeps `direction` meaning exactly one thing.
		cos_elevation = math.cos(self.elevation)
		direction = osg.Vec3(
			math.cos(self.azimuth) * cos_elevation,
			math.sin(self.azimuth) * cos_elevation,
			math.sin(self.elevation)
		)

		self.lights.setDirectional(0, direction, self.color, self.intensity)

		self.shadow_map.reposition(
			direction, self.bound_center, self.bound_radius, self.shadow_options
		)

if __name__ == "__main__":
	ap = argparse.ArgumentParser()
	ap.add_argument("path", nargs="?", default=None)

	env_group = ap.add_mutually_exclusive_group()
	env_group.add_argument(
		"--hdr",
		default=None,
		help="Equirectangular HDR; bakes diffuse/specular/BRDF-LUT live (default: papermill)"
	)
	env_group.add_argument(
		"--env",
		default=None,
		help="Pre-baked osgx_pbribl environment manifest"
	)

	ap.add_argument("--ibl-diffuse", type=float, default=1.0, dest="ibl_diffuse")
	ap.add_argument("--ibl-specular", type=float, default=1.0, dest="ibl_specular")
	ap.add_argument("--no-lights", dest="lights", action="store_false", default=True)
	ap.add_argument("--floor-z", type=float, default=None)
	ap.add_argument("--floor-size", type=float, default=None)
	ap.add_argument(
		"--repl",
		action="store_true",
		default=False,
		help="Run the viewer alongside an embedded IPython REPL (see pyosg_repl.py) so "
			"uniforms/lights/SSAO params can be tweaked live while watching the render window."
	)
	ap.add_argument(
		"--no-gui",
		dest="gui",
		action="store_false",
		default=True,
		help="Disable the osgx ImGui panel. All interactive controls (IBL, exposure, tonemap, "
			"light position, shadow, post FX) live only in this panel now, so disabling it "
			"leaves no way to adjust them at runtime."
	)

	args = ap.parse_args()

	if not args.hdr and not args.env:
		args.hdr = "papermill"

	# Preserve the existing opt-in floor flags as a room whose omitted dimension(s) scale with the
	# actual asset -- a bounding sphere gives a conservative floor height even for models with
	# unusual local origins.
	args.floor = args.floor_z is not None or args.floor_size is not None

	# osg.setNotifyLevel(osg.NotifySeverity.NOTICE)

	path = resolve_model(args.path or "BoomBox")

	if not path:
		sys.exit("Cannot find model -- clone glTF-Sample-Assets into your OSG_FILE_PATH checkout")

	model = osgDB.readNodeFile(path)

	# Created early (before any of the deferred-pipeline cameras below) -- PBRIBLLightingScene.create()
	# needs a real v.camera to rotate the G-buffer's view-space values into world space, same
	# reasoning osgx-gbuffer.cpp creates its own viewer this early for.
	v = osgViewer.Viewer()

	bound = model.bound
	bound_center = bound.center
	# 1.7 matches 09/10's own REFERENCE_RADIUS fallback -- guards against a degenerate (empty or
	# single-point) model bound, which would otherwise zero out ssao_radius and the shadow extent
	# below.
	bound_radius = bound.radius if bound.radius > 1e-6 else 1.7

	print(
		f"[sketchfab] model bound: center={tuple(bound_center)} radius={bound_radius:.4f}",
		flush=True
	)

	if args.floor:
		args.floor_z = bound_center.z - bound_radius if args.floor_z is None else args.floor_z
		args.floor_size = bound_radius * 4.0 if args.floor_size is None else args.floor_size

		print(
			f"[sketchfab] grid room: floor_z={args.floor_z:.4f} size={args.floor_size:.4f}",
			flush=True
		)

	# --- IBL environment -------------------------------------------------------- #
	if args.hdr:
		hdr_path = resolve_asset(args.hdr, "hdr")

		if not hdr_path:
			sys.exit(f"Cannot find HDR {args.hdr!r} -- check pyosg-lighting/data/ or OSG_FILE_PATH")

		environment = osgx.gltf.pbribl.PBRIBLEnvironment.prepare(hdr_path, lutSize=1024)

	else:
		env_path = resolve_asset(args.env, "gltf")

		if not env_path:
			sys.exit(f"Cannot find environment manifest {args.env!r}")

		environment = osgx.gltf.pbribl.PBRIBLEnvironment.load(env_path)

	if not environment.valid():
		sys.exit("Failed to prepare/load the PBR/IBL environment")

	# --- G-buffer geometry pass -------------------------------------------------- #
	gbuffer = osgx.gltf.pbribl.PBRIBLGBuffer.create(model, W, H)

	if not gbuffer.valid():
		sys.exit("Failed to build the G-buffer geometry pass")

	# --- Grid room (optional) -- added as an extra child of the geometry pass's own
	# camera, same pattern osgx-gbuffer.cpp's floor addition already proved out. ---- #
	grid_panels = ()

	if args.floor:
		grid_room, grid_panels = create_grid_room(bound_center, bound_radius, args.floor_z, args.floor_size)

		gbuffer.gbuffer.camera.children.append(grid_room)

	# --- Shadow map (Step 8's rig, now orthographic/depth-only-override/repositionable) --- #
	shadow_map = None
	shadow_options = osgx.ShadowMapOptions()

	if args.floor:
		# A room needs the shadow frustum to cover more than the model's own casting bound, or
		# the floor/walls' sample coordinates fall outside it and read as unshadowed.
		shadow_options.extent = max(bound_radius * shadow_options.margin, args.floor_size)

	if args.lights:
		shadow_map = osgx.ShadowMap.create(
			KEY_LIGHT_DIR, bound_center, bound_radius, shadow_options
		)

		shadow_map.camera.children.append(model)

	# --- SSAO ---------------------------------------------------------------------------- #
	# Built BEFORE lighting_options/PBRIBLLightingScene.create() specifically so aoTexture can be
	# set on lighting_options normally below -- osgx.SSAO replaces the hand-rolled kernel/
	# noise/RTT-pass code this step used to carry (generate_ssao_kernel()/make_ssao_noise_texture()/
	# create_ssao_camera()/create_ssao_blur_camera(), all removed). Reads gbuffer's normal/position
	# directly -- both already exist once the geometry pass above is built.
	#
	# ssao_projection_u is a real osg.Uniform (not a bare matrix) so it can be kept and refreshed
	# every frame below -- v.camera.projectionMatrix isn't meaningfully established until the
	# window is actually realized/sized, well after this call, and can change every frame besides
	# (see osgx.SSAO.create()'s own doc comment).
	ssao_projection_u = osg.Uniform("projectionMatrix", osg.Matrixf.identity())
	ssao_radius = max(0.05, bound_radius * 0.15)
	ssao = osgx.SSAO.create(
		gbuffer.normalTexture, gbuffer.positionTexture, ssao_projection_u, W, H, ssao_radius
	)

	if not ssao.valid():
		sys.exit("Failed to build the SSAO pass")

	# --- Deferred lighting pass -------------------------------------------------- #
	lighting_options = osgx.gltf.pbribl.PBRIBLLightingPassOptions()

	lighting_options.tonemap = False # bloom needs pre-tonemap linear HDR; final_cam tonemaps
	lighting_options.shadowMap = shadow_map
	lighting_options.aoTexture = ssao.aoTexture

	lighting = osgx.gltf.pbribl.PBRIBLLightingScene.create(
		gbuffer, environment, v.camera, args.ibl_diffuse, args.ibl_specular, lighting_options
	)

	if not lighting.valid():
		sys.exit("Failed to build the lighting pass")

	# PBRIBLLightingScene.create() returns a POST_RENDER camera drawing straight to the backbuffer
	# by default (the "pipeline ends here" shape options.tonemap=True implies) -- re-target it to
	# an offscreen texture ourselves so bloom/final can chain after it, exactly as its own doc
	# comment in PBRIBL.hpp says to.
	lighting_cam = lighting.node

	hdr_color_tex = osg.Texture2D(
		size=(W, H),
		internalFormat=GL_RGB16F,
		filter=(osg.Texture.LINEAR, osg.Texture.LINEAR),
		dataVariance=osg.Object.DYNAMIC,
	)

	lighting_cam.renderOrder = (osg.Camera.PRE_RENDER, 4)
	lighting_cam.renderTargetImplementation = osg.Camera.FRAME_BUFFER_OBJECT
	lighting_cam.viewport = osg.Viewport(0, 0, W, H)
	lighting_cam.clearMask = GL_COLOR_BUFFER_BIT
	lighting_cam.attach(osg.Camera.COLOR_BUFFER0, hdr_color_tex)

	# --- Lights: single directional key light via osgx.LightSet, live on the lighting
	# pass camera's own StateSet -- that's where osgx_DirectLighting() actually runs; the
	# geometry pass has no lighting math to feed it to. ---------------------------------- #
	lights = osgx.LightSet()
	lighting_cam.stateSet.attributes.append(lights)

	if args.lights:
		lights.setCount(1)

	else:
		lights.setCount(0)

	light_orbit = LightOrbit(
		lights, shadow_map, shadow_options, bound_center, bound_radius, KEY_LIGHT_COLOR, KEY_LIGHT_INTENSITY
	) if args.lights else None

	# --- Bloom ----------------------------------------------------------------------------- #
	bloom_threshold_cam, bloom_blur_h_cam, bloom_blur_v_cam, bloom_blur_b_tex = create_bloom_cameras(hdr_color_tex, W, H)

	# --- Final LDR pass ---------------------------------------------------------------------- #
	# ssao.aoTexture is ALREADY the aoTex the lighting pass reads (wired via lighting_options.aoTexture
	# above, at real PBRIBLLightingScene.create() call time -- no hand-wiring workaround needed
	# anymore) -- sampled a second time here purely for this pass's own grainAOBoost effect, unrelated
	# to the lighting pass's own use of it.
	final_cam = create_final_camera(hdr_color_tex, bloom_blur_b_tex, ssao.aoTexture, W, H)

	fc_ss = final_cam.stateSet
	fc_ss.uniforms["tonemapMode"] = 1 # ACES (Narkowicz) -- preferred over PBR Neutral by eye
	fc_ss.uniforms["exposure"] = 0.0
	fc_ss.uniforms["bloomStrength"] = 0.5
	fc_ss.uniforms["caStrength"] = 0.003
	fc_ss.uniforms["sharpenStrength"] = 0.25
	fc_ss.uniforms["vignetteStrength"] = 0.35
	fc_ss.uniforms["grainStrength"] = 0.02
	fc_ss.uniforms["grainSize"] = 1.0
	fc_ss.uniforms["grainAnimated"] = True
	fc_ss.uniforms["grainAOBoost"] = 0.0
	fc_ss.uniforms["colorLift"] = 0.0
	fc_ss.uniforms["colorGamma"] = 1.0
	fc_ss.uniforms["colorGain"] = 1.0
	fc_ss.uniforms["postEnabled"] = True

	tonemap_mode_u = fc_ss.uniforms["tonemapMode"]
	exposure_u = fc_ss.uniforms["exposure"]
	bloom_strength_u = fc_ss.uniforms["bloomStrength"]
	ca_strength_u = fc_ss.uniforms["caStrength"]
	sharpen_strength_u = fc_ss.uniforms["sharpenStrength"]
	vignette_strength_u = fc_ss.uniforms["vignetteStrength"]
	grain_strength_u = fc_ss.uniforms["grainStrength"]
	grain_size_u = fc_ss.uniforms["grainSize"]
	grain_animated_u = fc_ss.uniforms["grainAnimated"]
	grain_ao_boost_u = fc_ss.uniforms["grainAOBoost"]
	color_lift_u = fc_ss.uniforms["colorLift"]
	color_gamma_u = fc_ss.uniforms["colorGamma"]
	color_gain_u = fc_ss.uniforms["colorGain"]
	post_enabled_u = fc_ss.uniforms["postEnabled"]

	# --- Debug blit camera (Visualize Mode) --------------------------------------------------- #
	debug_cam, debug_channel_mode_u = create_debug_camera(bound_radius * 4.0, W, H)

	DEBUG_MODES = (
		# (label, texture-or-None, channelMode)
		("0: Composite", None, 0),
		("1: Albedo", gbuffer.albedoTexture, 3),
		("2: Normal", gbuffer.normalTexture, 1),
		("3: Material", gbuffer.materialTexture, 0),
		("4: Emissive", gbuffer.emissiveTexture, 3),
		("5: Depth", gbuffer.positionTexture, 4),
		("6: SSAO", ssao.aoTexture, 2),
	)

	# A single-element list, not a bare variable -- select_visualize_mode()/draw_visualize_mode()
	# are nested inside the `if __name__ == "__main__":` block, not a real enclosing function, so
	# `nonlocal` has no scope to bind to here (matches 10-dynamicprobes.py's pending_rebake=[True]
	# for the same reason).
	visualize_mode = [0]

	def select_visualize_mode(mode):
		visualize_mode[0] = mode
		label, tex, channel_mode = DEBUG_MODES[mode]
		composite = tex is None

		# ONLY the backbuffer-drawing cameras get toggled -- final_cam (POST_RENDER, the composite)
		# vs debug_cam (POST_RENDER, order 1). Every PRE_RENDER->FBO stage keeps running in every
		# mode, deliberately: a debug mode that samples an RTT texture must leave the camera that
		# WRITES that texture enabled, or it blits an attachment nothing rendered into this frame --
		# undefined, spatially uniform, unaffected by camera movement, and utterly convincing as a
		# "broken render pass" when it is really just a broken instrument. Adding a mode that
		# sampled hdr_color_tex while nodeMask'ing lighting_cam off cost real debugging time on
		# exactly this. The few unread fullscreen passes this leaves running are not worth
		# reintroducing that failure mode to avoid.
		final_cam.nodeMask = 0xffffffff if composite else 0
		debug_cam.nodeMask = 0 if composite else 0xffffffff

		if not composite:
			debug_cam.stateSet.textureAttributes[0] = tex
			debug_channel_mode_u.value = channel_mode

		print(f"[sketchfab] visualize mode: {label}", flush=True)

	# --- Light gizmo (osgx.LightGizmos -- ports what this file used to hand-roll) ------------- #
	gizmos = osgx.LightGizmos(lights, model) if args.lights else None

	if gizmos is not None:
		# Order 2 -- after both lighting_cam's re-target (order 4, PRE_RENDER, doesn't compete)
		# and debug_cam (POST_RENDER, order 1) -- the gizmo overlay is never nodeMask-toggled by
		# select_visualize_mode(), so it needs to be the one thing guaranteed to draw last
		# regardless of view mode. Same fix this session's osgx-gbuffer.cpp needed.
		gizmos.overlay.renderOrder = (osg.Camera.POST_RENDER, 2)

	root = osg.Group()

	if environment.root is not None:
		root.children.append(environment.root)

	# Combined per-frame update: the lighting pass's view-matrix uniforms (PBRIBLLightingScene.update())
	# plus SSAO's own forward projection matrix (see ssao_projection_u's own comment -- neither is
	# meaningfully established until well after the cameras that need them are built). Installed on
	# whichever camera is the FIRST PRE_RENDER camera in this scene graph (add-order breaks the tie
	# between shadow_map.camera and gbuffer.gbuffer.camera, both default order 0) -- see
	# PBRIBLLightingScene.update()'s own comment for why it must NOT be v.camera's own preDrawCallback
	# or application code after v.frame() returns, both of which hand the lighting pass a
	# one-frame-stale matrix relative to what the geometry pass just rendered with.
	def update_per_frame(ri):
		lighting.update(v.camera)

		ssao_projection_u.value = osg.Matrixf(v.camera.projectionMatrix)

	if shadow_map is not None:
		root.children.append(shadow_map.camera)

		shadow_map.camera.preDrawCallback = update_per_frame

	else:
		# No shadow camera to pin to -- gbuffer.gbuffer.camera becomes the first PRE_RENDER
		# camera instead (--no-lights).
		gbuffer.gbuffer.camera.preDrawCallback = update_per_frame

	root.children.append(gbuffer.gbuffer.camera)
	root.children.append(ssao.rawCamera)
	root.children.append(ssao.blurCamera)
	root.children.append(lighting_cam)
	root.children.append(bloom_threshold_cam)
	root.children.append(bloom_blur_h_cam)
	root.children.append(bloom_blur_v_cam)
	root.children.append(final_cam)
	root.children.append(debug_cam)

	if gizmos is not None:
		root.children.append(gizmos)

	select_visualize_mode(0)

	v.sceneData = root
	v.cameraManipulator = osgGA.TrackballManipulator()

	# See osgx-gbuffer.cpp's own comment on View.setCameraManipulator() -- it unconditionally
	# resets manip.node to getSceneData() before computing the initial home position, so retarget
	# AFTER attaching the manipulator, not before, or the orbiting RTT/gizmo cameras inflate the
	# computed home distance.
	v.cameraManipulator.node = model
	v.cameraManipulator.home(0.0)
	v.camera.clearColor = osg.Vec4(48.0 / 255.0, 53.0 / 255.0, 66.0 / 255.0, 1.0)

	# --- ImGui panel: all interactive controls live here -- no keyboard shortcuts. ------------ #
	if args.gui:
		gui_opts = osgx.imgui.Options()
		gui_opts.dock = osgx.imgui.Dock.LEFT
		gui_opts.dock_width = 320.0

		# gizmos.overlay pinned as the explicit draw camera -- left at the default, Widget draws
		# via v.camera's own PostDrawCallback, which fires BEFORE any nested POST_RENDER camera
		# (final_cam, debug_cam, the gizmo overlay -- none are View slaves) actually runs; their
		# later draw painted straight over the panel. Same fix this session's
		# osgx-shadow.cpp/osgx-gbuffer.cpp needed -- see osgx/ImGui.hpp's Widget constructor
		# comment for the full rationale. Falls back to final_cam if there's no gizmo (--no-lights).
		draw_camera = gizmos.overlay if gizmos is not None else final_cam
		gui = osgx.imgui.Widget(v, draw_camera, gui_opts)
		closed_section = osgx.imgui.SectionOptions(default_open=False)

		def draw_visualize_mode(ri):
			mode_labels = [label for label, _, _ in DEBUG_MODES]
			changed, value = osgx.imgui.radio_group(visualize_mode[0], mode_labels, False)

			if changed: select_visualize_mode(value)

		gui.addSection(
			"Visualize Mode",
			draw_visualize_mode,
			osgx.imgui.SectionOptions(default_open=True)
		)

		def draw_ibl_knobs(ri):
			changed, value = osgx.imgui.slider_float_nudge(
				"IBL Diffuse", lighting.iblDiffuseIntensity.value, 0.0, 2.0
			)

			if changed: lighting.iblDiffuseIntensity.value = value

			changed, value = osgx.imgui.slider_float_nudge(
				"IBL Specular", lighting.iblSpecularIntensity.value, 0.0, 2.0
			)

			if changed: lighting.iblSpecularIntensity.value = value

		gui.addSection("IBL", draw_ibl_knobs, closed_section)

		# ssao.radius/ssao.bias are real live osg.Uniforms (osgx.SSAO.create()) -- no pass
		# rebuild needed, same shape every other slider here already uses.
		def draw_ssao_knobs(ri):
			changed, value = osgx.imgui.slider_float("Radius", ssao.radius.value, 0.01, 2.0)

			if changed: ssao.radius.value = value

			changed, value = osgx.imgui.slider_float("Bias", ssao.bias.value, 0.0, 0.1)

			if changed: ssao.bias.value = value

		gui.addSection("SSAO", draw_ssao_knobs, closed_section)

		def draw_exposure_knobs(ri):
			changed, value = osgx.imgui.slider_float(
				"Exposure##slider", exposure_u.value, -8.0, 8.0, "%.2f EV"
			)

			if changed: exposure_u.value = value

		gui.addSection("Exposure", draw_exposure_knobs, closed_section)

		def draw_tonemap_knobs(ri):
			mode_labels = ["0: PBR Neutral", "1: ACES", "2: Reinhard", "3: None (clamped)"]

			changed, value = osgx.imgui.radio_group(int(tonemap_mode_u.value), mode_labels, False)

			if changed: tonemap_mode_u.value = value

		gui.addSection("Tonemap", draw_tonemap_knobs, closed_section)

		if args.floor:
			room_material = {"reflective": False}

			def set_room_material(reflective):
				roughness = 0.15 if reflective else 0.85
				metallic = 1.0 if reflective else 0.0

				for grid in grid_panels:
					grid.stateSet.uniforms["roomRoughness"] = roughness
					grid.stateSet.uniforms["roomMetallic"] = metallic

			def draw_grid_room_knobs(ri):
				changed, reflective = osgx.imgui.checkbox(
					"Reflective metal", room_material["reflective"]
				)

				if changed:
					room_material["reflective"] = reflective
					set_room_material(reflective)

			gui.addSection("Grid Room", draw_grid_room_knobs, closed_section)

		if light_orbit is not None:
			def draw_light_direction_knobs(ri):
				h = light_orbit

				changed, value = osgx.imgui.slider_float(
					"Azimuth", math.degrees(h.azimuth), -180.0, 180.0, "%.1f deg"
				)

				if changed:
					h.azimuth = math.radians(value)
					h._sync()

				# Clamped short of +-90: straight down/up is a degenerate lookAt inside
				# ShadowMap.reposition() (its up vector is world +Y, so the poles that
				# actually break it are +-Y, but a light exactly on the Z axis still produces a
				# shadow frustum with no useful orientation).
				changed, value = osgx.imgui.slider_float(
					"Elevation", math.degrees(h.elevation), -89.0, 89.0, "%.1f deg"
				)

				if changed:
					h.elevation = math.radians(value)
					h._sync()

			# "Direction", not "Position" -- a directional light has no position; see LightOrbit.
			gui.addSection("Light Direction", draw_light_direction_knobs, closed_section)

		if shadow_map is not None:
			def draw_shadow_knobs(ri):
				changed, value = osgx.imgui.slider_float(
					"Shadow Strength", shadow_map.strength.value, 0.0, 1.0
				)

				if changed: shadow_map.strength.value = value

				changed, value = osgx.imgui.slider_float(
					"Shadow Bias", shadow_map.bias.value, 0.0, 0.02, "%.4f"
				)

				if changed: shadow_map.bias.value = value

			gui.addSection("Shadow", draw_shadow_knobs, closed_section)

		def draw_post_fx_knobs(ri):
			# Sketchfab's own "No Post-Processing" toggle -- gates CA/sharpen/vignette/grain/
			# color-balance in FINAL_FRAGMENT_SHADER (exposure and tonemap stay on regardless).
			changed, value = osgx.imgui.checkbox("Post Processing", bool(post_enabled_u.value))

			if changed: post_enabled_u.value = value

			changed, value = osgx.imgui.slider_float("Bloom Strength", bloom_strength_u.value, 0.0, 2.0)

			if changed: bloom_strength_u.value = value

			changed, value = osgx.imgui.slider_float(
				"Chromatic Aberration", ca_strength_u.value, 0.0, 0.02, "%.4f"
			)

			if changed: ca_strength_u.value = value

			changed, value = osgx.imgui.slider_float("Sharpen", sharpen_strength_u.value, -0.5, 1.5)

			if changed: sharpen_strength_u.value = value

			changed, value = osgx.imgui.slider_float("Vignette", vignette_strength_u.value, 0.0, 1.0)

			if changed: vignette_strength_u.value = value

			changed, value = osgx.imgui.slider_float("Grain", grain_strength_u.value, 0.0, 0.2, "%.4f")

			if changed: grain_strength_u.value = value

			changed, value = osgx.imgui.slider_float("Grain Size", grain_size_u.value, 1.0, 8.0, "%.1f px")

			if changed: grain_size_u.value = value

			changed, value = osgx.imgui.checkbox("Grain Animated", bool(grain_animated_u.value))

			if changed: grain_animated_u.value = value

			changed, value = osgx.imgui.slider_float("Grain AO Boost", grain_ao_boost_u.value, 0.0, 1.0)

			if changed: grain_ao_boost_u.value = value

			changed, value = osgx.imgui.slider_float("Color Lift", color_lift_u.value, -0.5, 0.5, "%.3f")

			if changed: color_lift_u.value = value

			changed, value = osgx.imgui.slider_float("Color Gamma", color_gamma_u.value, 0.1, 3.0)

			if changed: color_gamma_u.value = value

			changed, value = osgx.imgui.slider_float("Color Gain", color_gain_u.value, 0.0, 3.0)

			if changed: color_gain_u.value = value

		gui.addSection("Post FX", draw_post_fx_knobs, closed_section)

		gui.addStatsSection(v)
		gui.addProfilerSection(v, root, default_open=False)

	# --- --repl: hand the render loop to pyosg_repl.py's IPython/asyncio bridge -------------- #
	if args.repl:
		examples_dir = pathlib.Path(__file__).resolve().parent.parent

		if str(examples_dir) not in sys.path:
			sys.path.insert(0, str(examples_dir))

		from pyosg_repl import repl

		repl(v, globals())

	else:
		while not v.done:
			v.frame()
