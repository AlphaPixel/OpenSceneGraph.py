#!/usr/bin/env python3
#vimrun! python3 ../examples/pyosg-lighting/11-sketchfab.py --ktx2 papermill --hdr papermill

# Step 11 - Sketchfab-parity capstone (increment 2: post-processing chain)
#
# Increment 1 (commit c5a3359) restructured 09-ibl.py's PBR+IBL lighting into a deferred
# G-buffer + composite architecture and validated it against Sketchfab itself -- see
# ai/context-todo-lighting-class.md for the full comparison writeup. This increment adds
# most of Sketchfab's post-processing filter chain on top of that G-buffer: SSAO, bloom,
# and a final LDR pass (tonemap, vignette, grain, chromatic aberration, sharpening, color
# balance). SSR/DOF/TAA stay out of scope -- the research doc flags those as the hardest/
# most artifact-prone of the chain, better as their own later increment.
#
# Pipeline shape:
# shadow_cam -> gbuffer_cam (MRT: albedo/normal/material/emissive/depth) -> ssao_cam ->
# ssao_blur_cam -> composite_cam (PBR+IBL+shadow+SSAO, writes LINEAR HDR, no tonemap) ->
# bloom_threshold_cam -> bloom_blur_h_cam -> bloom_blur_v_cam -> final_cam (bloom add,
# tonemap, gamma, vignette/grain/CA/sharpen/color-balance -> window).
#
# Press 0-9 to inspect individual G-buffer/pipeline layers (Sketchfab-style render-level
# toggle); press 'p' to toggle the whole post-processing chain on/off (Sketchfab's own
# "No Post-Processing" button).
#
# Texture units (independent namespace per camera):
# gbuffer_cam (model's own textures):  0 baseColor 1 normal 2 orm 3 emissive
# ssao_cam:                            0 gDepth 1 gNormal 2 ssaoNoise 3 gPosition
# ssao_blur_cam:                       0 aoRawTex
# composite_cam:                       0 gAlbedo 1 gNormal 2 gMaterial 3 gEmissive 4 gDepth
#                                      5 shadowMap 6 envMap 7 brdfLUT 8 aoTex
#                                      9 gPosition
# bloom_threshold_cam:                 0 hdrColorTex
# bloom_blur_h_cam / bloom_blur_v_cam: 0 inputTex
# final_cam:                           0 hdrColorTex 1 bloomTex 2 aoTex

import sys
import os
import math
import argparse
import asyncio
import pathlib

W, H = 1024, 768

os.environ.update({
	"OSG_WINDOW": f"50 50 {W} {H}",
	"OSG_THREADING": "SingleThreaded",
	"OSG_GL_CONTEXT_PROFILE_MASK": "1",
	"OSG_GL_VERSION": "4.6",
	"OSG_GL_CONTEXT_VERSION": "4.6",
})

import numpy as np
import cv2

from OpenSceneGraph import *
from OpenSceneGraph.GL import *

import osgDebug

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #

SHADOW_SIZE = 1024

# Not in OpenSceneGraph.GL's hand-curated allowlist -- raw GL enums defined locally,
# same workaround already needed for GL_TEXTURE_CUBE_MAP_SEAMLESS below.
GL_R8 = 0x8229
GL_RGB32F = 0x8815
GL_TEXTURE_CUBE_MAP_SEAMLESS = 0x884F

SSAO_KERNEL_SIZE = 16
SSAO_NOISE_SIZE = 4

# Single directional key light -- temporary simplification (2026-07-11) while
# debugging the shadow-drift bug (mode 8's shadowFactor() visibly swims as the
# camera orbits, unlike Sketchfab's stable self-shadowing). A point light has no
# single canonical direction to reason about; a directional light matches
# shadow_cam's own fixed-direction assumption exactly, removing one variable
# while isolating the shadowMatrix math. Fill lights 0/1 and per-light distance/
# radius attenuation are dropped entirely, not just zeroed -- see 09-ibl.py for
# the original 3-point-light rig if this needs reverting.
REFERENCE_RADIUS = 1.7

KEY_LIGHT_DIR = osg.Vec3(0.1, 0.1, 1.0).normalized()

# --------------------------------------------------------------------------- #
# SH projection (verbatim from 09-ibl.py -- only iblSH's stateSet home moves)
# SH = Spherical Harmonics
# --------------------------------------------------------------------------- #

def compute_sh(hdr_path):
	"""
	Project equirectangular HDR onto L0-L2 SH. Returns list of 9 [R,G,B].
	Cosine-lobe A_l weights baked in so GLSL is a plain dot-product sum.
	cv2 loads .hdr as BGR float32 - flip to RGB.
	"""
	print("[ibl] loading HDR for SH (Spherical Harmonics)...", flush=True)

	bgr = cv2.imread(hdr_path, cv2.IMREAD_ANYDEPTH | cv2.IMREAD_COLOR)
	img = bgr[..., ::-1].astype(np.float32)
	H, W = img.shape[:2]

	print(f"[ibl] HDR {W}x{H} max={img.max():.2f}", flush=True)

	theta = (np.arange(H) + 0.5) / H * np.pi
	phi = (np.arange(W) + 0.5) / W * 2.0 * np.pi
	th, ph = np.meshgrid(theta, phi, indexing="ij")
	sin_t = np.sin(th)

	x = sin_t * np.cos(ph)
	y = sin_t * np.sin(ph)
	z = np.cos(th)

	d_omega = sin_t * (np.pi / H) * (2.0 * np.pi / W)

	Y = [
		np.full((H, W), 0.282095),
		0.488603 * y,
		0.488603 * z,
		0.488603 * x,
		1.092548 * x * y,
		1.092548 * y * z,
		0.315392 * (3*z*z - 1),
		1.092548 * x * z,
		0.546274 * (x*x - y*y),
	]

	A = [
		np.pi,
		2*np.pi/3,
		2*np.pi/3,
		2*np.pi/3,
		np.pi/4,
		np.pi/4,
		np.pi/4,
		np.pi/4,
		np.pi/4
	]

	sh = []

	for i, (yi, ai) in enumerate(zip(Y, A)):
		rgb = np.sum(img * (yi * d_omega)[..., np.newaxis], axis=(0, 1)) * ai

		sh.append([float(rgb[0]), float(rgb[1]), float(rgb[2])])

		print(f"[ibl] SH[{i}] = ({rgb[0]:.4f}, {rgb[1]:.4f}, {rgb[2]:.4f})", flush=True)

	print("[ibl] SH done.", flush=True)

	return sh

async def task_compute_sh(queue, hdr_path):
	try:
		sh = await asyncio.to_thread(compute_sh, hdr_path)

		await queue.put(sh)

	except Exception as e:
		print(f"[ibl] ERROR computing SH: {e}", flush=True)

# --------------------------------------------------------------------------- #
# SSAO kernel + noise (Python-side setup, same numpy -> osg.Image -> Texture2D
# pattern already proven in 10-dynamicprobes.py's paint_random_faces())
# --------------------------------------------------------------------------- #

def generate_ssao_kernel(n=SSAO_KERNEL_SIZE, seed=0):
	"""Hemisphere-oriented sample kernel, quadratically clustered toward the origin --
	the standard SSAO kernel shape (Crysis-era; still the baseline technique today)."""
	rng = np.random.default_rng(seed)
	kernel = []

	for i in range(n):
		v = np.array([rng.uniform(-1.0, 1.0), rng.uniform(-1.0, 1.0), rng.uniform(0.05, 1.0)])
		v /= np.linalg.norm(v)
		v *= rng.uniform(0.0, 1.0)

		scale = 0.1 + 0.9 * (i / n) ** 2

		kernel.append(osg.Vec3(*(v * scale)))

	return kernel

def make_ssao_noise_texture(size=SSAO_NOISE_SIZE, seed=1):
	"""Tiny tiled texture of random tangent-space rotation vectors -- removes the visible
	banding a fixed kernel would otherwise leave (every pixel sampling identical relative
	directions)."""
	rng = np.random.default_rng(seed)

	img = osg.Image()
	img.allocateImage(size, size, 1, GL_RGB, GL_FLOAT)

	arr = np.asarray(img)
	arr[..., 0] = rng.uniform(-1.0, 1.0, (size, size))
	arr[..., 1] = rng.uniform(-1.0, 1.0, (size, size))
	arr[..., 2] = 0.0

	tex = osg.Texture2D()
	tex.image = [img]
	tex.filter = osg.Texture.NEAREST
	tex.wrap = osg.Texture.REPEAT

	return tex

# --------------------------------------------------------------------------- #
# Shaders
# --------------------------------------------------------------------------- #

# Geometry-pass vertex shader -- identical to 09-ibl.py's VERTEX_SHADER. Note this also
# runs (unchanged) on shadow_cam's depth-only pass, since shadow_cam shares model's
# Program; only gl_Position matters there.
GBUFFER_VERTEX_SHADER = """
#version 460 core

in vec4 osg_Vertex;
in vec3 osg_Normal;
in vec2 osg_MultiTexCoord0;

uniform mat4 osg_ModelViewProjectionMatrix;
uniform mat4 osg_ModelViewMatrix;
uniform mat3 osg_NormalMatrix;

out vec3 vNGeom;
out vec3 vPosition;
out vec2 vUV;

void main() {
	vec4 eyePos = osg_ModelViewMatrix * osg_Vertex;
	vPosition = eyePos.xyz;
	vUV = osg_MultiTexCoord0;
	vNGeom = normalize(osg_NormalMatrix * osg_Normal);

	gl_Position = osg_ModelViewProjectionMatrix * osg_Vertex;
}
"""

# Geometry-pass fragment shader -- resolves per-fragment material/geometric data (exactly
# what 09-ibl.py's getShadingNormal()/getMaterial()/getEmissive() already computed) and
# writes it to the G-buffer via MRT instead of shading it. NO lighting/BRDF/shadow/IBL
# code lives here at all -- that all moved to COMPOSITE_FRAGMENT_SHADER below, since this
# shader has no idea what camera/light rig is even in play.
GBUFFER_FRAGMENT_SHADER = """
#version 460 core

in vec3 vNGeom;
in vec3 vPosition;
in vec2 vUV;

// ---- osgGLTF material inputs ------------------------------------------------ //
// See 09-ibl.py for the full rationale on the UBO/sampler-struct split (GLSL disallows
// opaque/sampler types inside a std140 uniform block).
layout(std140, binding = 0) uniform osgGLTF_Material {
	vec4 baseColorFactor;
	float roughnessFactor;
	float metallicFactor;
	float hasBaseColorMap;
	float hasMetallicRoughnessMap;
	float hasOcclusion;
	float hasNormalMap;
} osgGLTF_material;

struct GLTFTextures {
	sampler2D baseColor; // unit 0
	sampler2D normal; // unit 1
	sampler2D orm; // unit 2
	sampler2D emissive; // unit 3
};

uniform GLTFTextures osgGLTF_textures;

uniform vec3 emissiveFactor;
uniform float scanlineFreq;
uniform float scanlineStrength;
uniform float osg_SimulationTime;

layout(location = 0) out vec4 outAlbedo;   // gAlbedo
layout(location = 1) out vec4 outNormal;   // gNormal (view-space, RGB16F, no encode needed)
layout(location = 2) out vec4 outMaterial; // gMaterial: R=roughness G=metallic B=ao (glTF ORM order)
layout(location = 3) out vec4 outEmissive; // gEmissive (fully resolved, RGB16F for HDR headroom)
layout(location = 4) out vec4 outPosition; // gPosition (actual view-space position; avoids depth reconstruction drift)

// ---- Shading normal --------------------------------------------------------- //
// TBN reconstructed per-pixel from screen-space derivatives (Christian Schuler's
// "normal mapping without precomputed tangents") rather than a vertex TANGENT attribute
// -- see 09-ibl.py for why (glTF's TANGENT accessor is frequently absent).
vec3 getShadingNormal() {
	vec3 Nb = normalize(vNGeom);

	// glTF doubleSided materials (thin single-sided sheets like capes/cloth with
	// no back geometry) rely on the renderer negating the normal on back-facing
	// fragments -- osgGLTF's loader disables backface culling per-material for
	// these (see GLTFReader.hpp's applyMaterial()), so those fragments DO reach
	// here now; without this flip they'd light as if facing away from the
	// camera/light on every back-facing triangle. No-op for ordinary single-sided
	// materials: culling stays enabled for those, so gl_FrontFacing is always
	// true and this branch never fires.
	if (!gl_FrontFacing) Nb = -Nb;

	if (!bool(osgGLTF_material.hasNormalMap)) return Nb;

	vec3 tangentNormal = texture(osgGLTF_textures.normal, vUV).rgb * 2.0 - 1.0;

	vec3 q1 = dFdx(vPosition);
	vec3 q2 = dFdy(vPosition);
	vec2 st1 = dFdx(vUV);
	vec2 st2 = dFdy(vUV);

	vec3 T = normalize(q1 * st2.t - q2 * st1.t);
	vec3 B = -normalize(cross(Nb, T));
	mat3 TBN = mat3(T, B, Nb);

	return normalize(TBN * tangentNormal);
}

// ---- Material --------------------------------------------------------------- //
// No F0 field here (unlike 09-ibl.py's Material struct) -- F0 = mix(0.04, albedo,
// metallic) is a pure function of two values already in the G-buffer (gAlbedo,
// gMaterial.g), so the composite pass's unpackMaterial() recomputes it instead of this
// pass storing a redundant derived quantity as a fifth G-buffer channel.
struct Material {
	vec3 albedo;
	float ao;
	float roughness;
	float metallic;
};

Material getMaterial(vec3 N) {
	Material mat;

	// A factor-only material (no baseColorTexture, e.g. most of the glTF-Sample-Models
	// *Test conformance set) would otherwise read an unbound unit 0 as black instead of
	// its authored flat color.
	mat.albedo = bool(osgGLTF_material.hasBaseColorMap)
		? texture(osgGLTF_textures.baseColor, vUV).rgb
		: osgGLTF_material.baseColorFactor.rgb;
	// The R channel of a glTF metallicRoughnessTexture is spec-unused unless the
	// material also declares an occlusionTexture pointing at the same (or merged) image.
	mat.ao = bool(osgGLTF_material.hasOcclusion) ? texture(osgGLTF_textures.orm, vUV).r : 1.0;
	// A material can be entirely factor-driven with no metallicRoughnessTexture at all
	// (e.g. Fox: roughnessFactor=0.58, no texture) -- trusting an unbound unit 2's zero
	// read unconditionally would force roughness/metallic to 0 (mirror-smooth).
	mat.roughness = bool(osgGLTF_material.hasMetallicRoughnessMap)
		? texture(osgGLTF_textures.orm, vUV).g * osgGLTF_material.roughnessFactor
		: osgGLTF_material.roughnessFactor;
	mat.metallic = bool(osgGLTF_material.hasMetallicRoughnessMap)
		? texture(osgGLTF_textures.orm, vUV).b * osgGLTF_material.metallicFactor
		: osgGLTF_material.metallicFactor;

	// Specular AA: clamp roughness by how fast the shading normal rotates per pixel.
	// Must happen HERE, in the geometry pass -- it needs dFdx/dFdy of N in UV/triangle
	// space, which the G-buffer's screen-space normal texture can't reconstruct later
	// without conflating it with silhouette edges.
	float normalDelta = max(
		max(abs(dFdx(N.x)), abs(dFdx(N.y))),
		max(abs(dFdy(N.x)), abs(dFdy(N.y)))
	);
	mat.roughness = max(mat.roughness, normalDelta);

	return mat;
}

// ---- Emissive ---------------------------------------------------------------- //
vec3 getEmissive() {
	vec3 emissive = texture(osgGLTF_textures.emissive, vUV).rgb * emissiveFactor;
	float scanline = 0.5 + 0.5 * sin(vUV.y * scanlineFreq - osg_SimulationTime * 10.0);
	return emissive * mix(1.0, scanline, scanlineStrength);
}

void main() {
	vec3 N = getShadingNormal();
	Material mat = getMaterial(N);

	outAlbedo = vec4(mat.albedo, 1.0);
	outNormal = vec4(N, 0.0);
	outMaterial = vec4(mat.roughness, mat.metallic, mat.ao, 1.0);
	outEmissive = vec4(getEmissive(), 1.0);
	outPosition = vec4(vPosition, 1.0);
}
"""

# Shared G-buffer vertex stage for the room frame's simple unlit material.
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

# The grid room is unlit for now, but it still writes a complete G-buffer record so
# it shares the model's depth buffer. That makes this the correct foundation for the
# later shadow-receiving material rather than a forward overlay drawn above the model.
GRID_ROOM_VERTEX = """
#version 460 core

in vec4 osg_Vertex;
in vec3 osg_Normal;
in vec2 osg_MultiTexCoord0;

uniform mat4 osg_ModelViewProjectionMatrix;
uniform mat4 osg_ModelViewMatrix;
uniform mat3 osg_NormalMatrix;
uniform vec2 u_canvasSize;

out vec2 vGridPos;
out vec3 vNormal;
out vec3 vPosition;

void main() {
	vGridPos = osg_MultiTexCoord0 * u_canvasSize;
	vNormal = normalize(osg_NormalMatrix * osg_Normal);
	vPosition = (osg_ModelViewMatrix * osg_Vertex).xyz;
	gl_Position = osg_ModelViewProjectionMatrix * osg_Vertex;
}
"""

GRID_ROOM_FRAGMENT = """
#version 460 core

in vec2 vGridPos;
in vec3 vNormal;
in vec3 vPosition;

uniform float u_gridInterval;
uniform float u_gridIntervalStrong;
uniform float u_lineWidthPx;
uniform vec4 u_colorBg;
uniform vec4 u_colorLine;
uniform vec4 u_colorLineStrong;
uniform float roomRoughness;
uniform float roomMetallic;

layout(location = 0) out vec4 outAlbedo;
layout(location = 1) out vec4 outNormal;
layout(location = 2) out vec4 outMaterial;
layout(location = 3) out vec4 outEmissive;
layout(location = 4) out vec4 outPosition;

float gridLine(vec2 pos, float interval, float widthPx) {
	vec2 cells = pos / interval;
	vec2 pixelDistance = abs(fract(cells - 0.5) - 0.5) / fwidth(cells);
	float distanceToNearestLine = min(pixelDistance.x, pixelDistance.y);
	return 1.0 - smoothstep(widthPx - 0.5, widthPx + 0.5, distanceToNearestLine);
}

void main() {
	float line = gridLine(vGridPos, u_gridInterval, u_lineWidthPx);
	float strong = u_gridIntervalStrong > 0.0
		? gridLine(vGridPos, u_gridIntervalStrong, u_lineWidthPx * 1.5)
		: 0.0;
	float coverage = max(line, strong);

	// Unlike the earlier unlit guide, every panel fragment now writes a matte
	// material. That gives the deferred composite a real receiver surface for the
	// existing shadow map; the grid is simply a brighter albedo detail on it.
	vec3 gridColor = mix(u_colorLine.rgb, u_colorLineStrong.rgb, strong);
	vec3 albedo = mix(u_colorBg.rgb, gridColor, coverage);
	outAlbedo = vec4(albedo, 1.0);
	outNormal = vec4(normalize(vNormal), 0.0);
	outMaterial = vec4(roomRoughness, roomMetallic, 1.0, 1.0);
	outEmissive = vec4(0.0);
	outPosition = vec4(vPosition, 1.0);
}
"""

FRAME_GBUFFER_FRAGMENT = """
#version 460 core

in vec3 vNormal;
in vec3 vPosition;

uniform vec3 frameColor;

layout(location = 0) out vec4 outAlbedo;
layout(location = 1) out vec4 outNormal;
layout(location = 2) out vec4 outMaterial;
layout(location = 3) out vec4 outEmissive;
layout(location = 4) out vec4 outPosition;

void main() {
	outAlbedo = vec4(0.0);
	outNormal = vec4(normalize(vNormal), 0.0);
	outMaterial = vec4(1.0, 0.0, 1.0, 1.0);
	outEmissive = vec4(frameColor, 1.0);
	outPosition = vec4(vPosition, 1.0);
}
"""

# Fullscreen NDC quad vertex shader -- shared between the BRDF LUT bake and every
# post-processing pass below (same convention as 09-ibl.py).
FULLSCREEN_VERTEX = """
#version 460 core
in vec4 osg_Vertex;
in vec2 osg_MultiTexCoord0;
out vec2 vUV;
void main() {
	vUV = osg_MultiTexCoord0;
	gl_Position = vec4(osg_Vertex.xy, 0.0, 1.0);
}
"""

# SSAO pass: hemisphere-kernel screen-space ambient occlusion, reading the G-buffer's
# depth+normal directly. Outputs a single raw (noisy) occlusion value; ssao_blur_cam
# denoises it before composite_cam consumes it.
SSAO_FRAGMENT_SHADER = """
#version 460 core

#define NUM_SAMPLES 16

uniform sampler2D gDepth;    // unit 0 (used only for its size, below -- see gPosition)
uniform sampler2D gNormal;   // unit 1
uniform sampler2D ssaoNoise; // unit 2
uniform sampler2D gPosition; // unit 3: real view-space position (same buffer the composite
                             // pass uses) -- avoids reconstructing position from gDepth via
                             // invProjectionMatrix, which depends on v.camera's own near/far.
                             // v.camera never directly culls the model (it's nested two Camera
                             // levels down inside gbuffer_cam), so its OSG-auto-tightened near/
                             // far doesn't reliably track gbuffer_cam's own (separately
                             // tightened) near/far -- the same near/far-mismatch class BUG.md's
                             // gPosition fix solved for the composite pass's shading.

uniform mat4 projectionMatrix; // forward -- projects hemisphere samples back to screen space.
                                // Near/far-agnostic: for a symmetric frustum, the x/y terms used
                                // below (offset.xy) reduce to 1/tan(fovy/2 or fovx/2), with the
                                // near-plane distance canceling out algebraically -- only fovy/
                                // aspect matter, so this stays correct even though it's still
                                // sourced from v.camera's projectionMatrix, not gbuffer_cam's.

uniform vec3 samples[NUM_SAMPLES];
uniform float ssaoRadius;
uniform float ssaoBias;

in vec2 vUV;

out vec4 fragColor;

void main() {
	vec3 rawN = texture(gNormal, vUV).rgb;

	// Same background sentinel as the composite pass -- an unwritten pixel has a
	// zero-length normal; normalize(0) would produce NaN, and there's no real geometry
	// to occlude anyway, so just report "no occlusion" immediately.
	if (dot(rawN, rawN) < 0.0001) {
		fragColor = vec4(1.0, 0.0, 0.0, 1.0);

		return;
	}

	vec3 N = normalize(rawN);
	vec3 fragPos = texture(gPosition, vUV).xyz;

	vec2 noiseScale = vec2(textureSize(gDepth, 0)) / float(textureSize(ssaoNoise, 0).x);
	vec3 rvec = texture(ssaoNoise, vUV * noiseScale).xyz;
	vec3 tangent = normalize(rvec - N * dot(rvec, N));
	vec3 bitangent = cross(N, tangent);
	mat3 TBN = mat3(tangent, bitangent, N);

	float occlusion = 0.0;

	for (int i = 0; i < NUM_SAMPLES; i++) {
		vec3 samplePos = fragPos + (TBN * samples[i]) * ssaoRadius;

		vec4 offset = projectionMatrix * vec4(samplePos, 1.0);
		offset.xyz /= offset.w;
		offset.xyz = offset.xyz * 0.5 + 0.5;

		float sampleDepth = texture(gPosition, offset.xy).z;
		float rangeCheck = smoothstep(0.0, 1.0, ssaoRadius / max(abs(fragPos.z - sampleDepth), 0.0001));

		occlusion += (sampleDepth >= samplePos.z + ssaoBias ? 1.0 : 0.0) * rangeCheck;
	}

	fragColor = vec4(vec3(1.0 - occlusion / float(NUM_SAMPLES)), 1.0);
}
"""

# Small fixed-radius box blur to denoise the hemisphere-kernel noise -- deliberately NOT
# the two-pass separable Gaussian bloom uses below; a small fixed radius doesn't benefit
# from separability the way a large-radius bloom blur does.
SSAO_BLUR_FRAGMENT_SHADER = """
#version 460 core

uniform sampler2D aoRawTex;

in vec2 vUV;

out vec4 fragColor;

void main() {
	vec2 texel = 1.0 / vec2(textureSize(aoRawTex, 0));
	float sum = 0.0;

	for (int x = -2; x < 2; x++)
		for (int y = -2; y < 2; y++)
			sum += texture(aoRawTex, vUV + vec2(x, y) * texel).r;

	fragColor = vec4(vec3(sum / 16.0), 1.0);
}
"""

# Bloom bright-pass extract -- soft-knee smoothstep rather than a hard cutoff, so bloom
# doesn't flicker as luminance crosses the threshold frame to frame.
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

# Generic separable-Gaussian blur pass -- same 9-tap weights as examples/pyosg-blur.py,
# duplicated here rather than imported (every examples/pyosg-lighting/*.py file is
# self-contained; no cross-example imports anywhere in this repo). Used twice for bloom
# (horizontal then vertical, each into its own texture -- not ping-ponged).
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

# Composite pass: reads the 5-attachment G-buffer + blurred SSAO back and does ALL of
# 09-ibl.py's PBR+IBL shading here instead of inline during the geometry pass -- true
# deferred shading. Writes LINEAR HDR color (no tonemap/gamma -- that moved to
# final_cam, since bloom needs to sample pre-tonemap HDR). Also implements the 0-9
# render-level visualize toggle (Sketchfab-style layer switch).
COMPOSITE_FRAGMENT_SHADER = """
#version 460 core

const float PI = 3.14159265359;

uniform sampler2D gAlbedo;   // unit 0
uniform sampler2D gNormal;   // unit 1
uniform sampler2D gMaterial; // unit 2
uniform sampler2D gEmissive; // unit 3
uniform sampler2D gDepth;    // unit 4
uniform sampler2D shadowMap; // unit 5
uniform samplerCube envMap;  // unit 6: prefiltered cubemap
uniform sampler2D brdfLUT;   // unit 7: split-sum BRDF LUT
uniform sampler2D aoTex;     // unit 8: blurred SSAO
uniform sampler2D gPosition; // unit 9: view-space position written by the geometry pass

uniform float znear;
uniform float zfar;
uniform int visualizeMode; // 0=composite 1=albedo 2=normal 3=depth 4=material
                            // 5=direct-only 6=IBL-only 7=emissive-only 8=shadow-only 9=AO-only

// v.camera's real view matrix. NOT the same as GLSL's automatic osg_ViewMatrix here --
// this composite camera is an ABSOLUTE_RF, identity-view fullscreen quad, so
// osg_ViewMatrix would resolve to identity (it tracks whichever camera is currently
// drawing), silently freezing world-space lighting/reflections to whatever direction the
// viewer faced at startup. Set every frame from v.camera.viewMatrix instead.
uniform mat4 mainViewMatrix;
uniform mat4 invViewProj;
uniform mat4 shadowMatrix;
uniform float shadowBias;
uniform float shadowStrength; // 0 = shadows have no effect, 1 = fully black -- see shadowFactor()
uniform bool shadowDebugTint; // tint shadowed composite pixels red -- see main()'s use below

uniform vec3 lightDir;   // world-space direction FROM the surface TOWARD the light (normalized)
uniform vec3 lightColor;

uniform vec3 skyColor;
uniform vec3 groundColor;

uniform int iblEnabled;
uniform vec3 iblSH[9];
// Independent diffuse-irradiance/specular-reflection intensity, not one shared
// iblIntensity -- see evaluateIBL() below for why they used to have to move together.
uniform float iblDiffuseIntensity;
uniform float iblSpecularIntensity;

in vec2 vUV;

out vec4 fragColor;

// ---- PBR helpers ---------------------------------------------------------- //

float D_GGX(float NdotH, float roughness) {
	float a = roughness * roughness;
	float a2 = a * a;
	float d = NdotH * NdotH * (a2 - 1.0) + 1.0;
	return a2 / (PI * d * d);
}

float G_Schlick(float NdotX, float roughness) {
	float r = roughness + 1.0;
	float k = (r * r) / 8.0;
	return NdotX / (NdotX * (1.0 - k) + k);
}

float G_Smith(float NdotV, float NdotL, float roughness) {
	return G_Schlick(NdotV, roughness) * G_Schlick(NdotL, roughness);
}

vec3 F_Schlick(float cosTheta, vec3 F0) {
	return F0 + (1.0 - F0) * pow(1.0 - cosTheta, 5.0);
}

vec3 F_Schlick_roughness(float cosTheta, vec3 F0, float roughness) {
	return F0 + (max(vec3(1.0 - roughness), F0) - F0) * pow(1.0 - cosTheta, 5.0);
}

// ---- Shadow --------------------------------------------------------------- //

float shadowFactor(vec3 eyePos) {
	vec4 sc = shadowMatrix * vec4(eyePos, 1.0);
	sc /= sc.w;
	vec3 uv = sc.xyz * 0.5 + 0.5;
	if (any(lessThan(uv, vec3(0.0))) || any(greaterThan(uv, vec3(1.0)))) return 1.0;
	vec2 sz = 1.0 / vec2(textureSize(shadowMap, 0));
	float shadow = 0.0;
	for (int x = -1; x <= 1; x++)
		for (int y = -1; y <= 1; y++)
			shadow += (uv.z - shadowBias > texture(shadowMap, uv.xy + vec2(x, y) * sz).r) ? 1.0 : 0.0;
	return mix(1.0, 1.0 - shadowStrength, shadow / 9.0);
}

// ---- IBL ------------------------------------------------------------------ //

vec3 sh_irradiance(vec3 N) {
	return max(
		iblSH[0]
		+ iblSH[1]*N.y + iblSH[2]*N.z + iblSH[3]*N.x
		+ iblSH[4]*N.x*N.y + iblSH[5]*N.y*N.z
		+ iblSH[6]*(3.0*N.z*N.z - 1.0)
		+ iblSH[7]*N.x*N.z + iblSH[8]*(N.x*N.x - N.y*N.y),
		vec3(0.0)
	);
}

// ---- Material unpack --------------------------------------------------------- //

struct Material {
	vec3 albedo;
	float ao;
	float roughness;
	float metallic;
	vec3 F0;
};

Material unpackMaterial(vec3 albedo, vec3 ormRaw) {
	Material mat;
	mat.albedo = albedo;
	mat.roughness = ormRaw.r;
	mat.metallic = ormRaw.g;
	mat.ao = ormRaw.b;
	mat.F0 = mix(vec3(0.04), mat.albedo, mat.metallic);
	return mat;
}

// ---- Direct lighting -------------------------------------------------------- //

// shad is shadowFactor(eyePos), computed once by the caller -- shared with the
// shadowDebugTint overlay in main() rather than each recomputing it separately.
vec3 evaluateDirectLighting(Material mat, vec3 N, vec3 V, float NdotV, float shad) {
	// Single directional light -- no position, no distance attenuation. L is the
	// same direction everywhere in the scene, so unlike the old point-light rig
	// there's no per-fragment lVec/dist to get wrong.
	vec3 L = normalize(mat3(mainViewMatrix) * lightDir);
	vec3 H = normalize(L + V);
	float NdotL = max(dot(N, L), 0.0);
	float NdotH = max(dot(N, H), 0.0);
	float HdotV = max(dot(H, V), 0.0);
	float D = D_GGX(NdotH, mat.roughness);
	float G = G_Smith(NdotV, NdotL, mat.roughness);
	vec3 F = F_Schlick(HdotV, mat.F0);
	vec3 kD = (vec3(1.0) - F) * (1.0 - mat.metallic);
	vec3 diffuse = kD * mat.albedo / PI;
	vec3 specular = (D * G * F) / max(4.0 * NdotV * NdotL, 0.001);

	return (diffuse + specular) * lightColor * NdotL * shad;
}

// ---- IBL ambient ------------------------------------------------------------ //

vec3 evaluateIBL(Material mat, vec3 N, vec3 V, float NdotV) {
	if (iblEnabled == 0) {
		vec3 worldUp = normalize(mat3(mainViewMatrix) * vec3(0.0, 0.0, 1.0));
		float hemi = dot(N, worldUp) * 0.5 + 0.5;
		return mix(groundColor, skyColor, hemi) * mat.albedo * mat.ao;
	}

	mat3 invView = transpose(mat3(mainViewMatrix));
	vec3 N_world = invView * N;
	vec3 V_world = invView * V;
	vec3 R_world = reflect(-V_world, N_world);

	vec3 F_ibl = F_Schlick_roughness(NdotV, mat.F0, mat.roughness);
	vec3 kD_ibl = (1.0 - F_ibl) * (1.0 - mat.metallic);
	vec3 ibl_diff = sh_irradiance(N_world) * mat.albedo * kD_ibl * iblDiffuseIntensity;

	float maxMip = float(textureQueryLevels(envMap) - 1);
	float lod = mat.roughness * maxMip;
	vec3 r_gl = vec3(R_world.x, R_world.z, -R_world.y);
	vec3 prefilt = textureLod(envMap, r_gl, lod).rgb;
	vec2 brdf = texture(brdfLUT, vec2(NdotV, mat.roughness)).rg;
	// A single shared iblIntensity used to force ambient fill and mirror-like
	// reflections to move together -- turning up the diffuse SH term enough to read
	// as ambient fill also blew out reflections, and turning down reflections to a
	// sane brightness crushed ambient back to near-black. Independent controls let
	// the "how strong is the environment's soft fill" and "how strong are its
	// reflections" questions be answered separately, which is what actually
	// differs between our render and Sketchfab's -- see BUG.md item 1.
	vec3 ibl_spec = prefilt * (mat.F0 * brdf.x + brdf.y) * iblSpecularIntensity;

	return (ibl_diff + ibl_spec) * mat.ao;
}

// ---- Main ----------------------------------------------------------------- //

void main() {
	vec4 albedo = texture(gAlbedo, vUV);
	vec3 rawNormal = texture(gNormal, vUV).rgb;
	vec3 ormRaw = texture(gMaterial, vUV).rgb;
	vec3 rawEmissive = texture(gEmissive, vUV).rgb;
	float d = texture(gDepth, vUV).r;

	// --- Raw G-buffer dump modes (bypass lighting entirely, including background --
	// e.g. mode 2's normal view reads flat mid-gray where nothing was ever drawn).
	// Albedo is stored linear (same convention as mat.albedo everywhere else in this
	// shader), so it needs the same gamma re-encode as the final composite to look
	// right on screen; normal/depth/material/AO are raw data views, not display
	// colors, so they're left un-gamma-corrected.
	if (visualizeMode == 1) {
		fragColor = vec4(pow(albedo.rgb, vec3(1.0 / 2.2)), 1.0);

		return;
	}

	if (visualizeMode == 2) {
		fragColor = vec4(rawNormal * 0.5 + 0.5, 1.0);

		return;
	}

	if (visualizeMode == 3) {
		// Was: linearizeDepth(d, znear, zfar) straight off gDepth. gDepth was
		// written by gbuffer_cam's OWN near/far-tightened projection -- its cull
		// traversal only sees "model" (+floor), a different/smaller subgraph than
		// v.camera's -- so its actual near/far need not match znear/zfar (from
		// v.camera.projectionMatrix, used below only as a display range). Same
		// mismatch class as the reconstructViewPos() bug BUG.md's gPosition fix
		// solved for shading; it silently compressed every model fragment toward
		// t=0 (black) while cleared background pixels (d=1 exactly) still landed
		// at t=1 regardless of the mismatch, since linearizeDepth(1, near, far)
		// == far for ANY near/far -- hence "black model on white background."
		// gPosition.z depends only on the VIEW matrix (shared by both cameras),
		// never the projection, so it stays correct regardless of that mismatch.
		vec3 posEye = texture(gPosition, vUV).xyz;
		float lin = -posEye.z;
		float t = clamp((lin - znear) / (zfar - znear), 0.0, 1.0);

		fragColor = vec4(vec3(t), 1.0);

		return;
	}

	if (visualizeMode == 4) {
		fragColor = vec4(ormRaw, 1.0);

		return;
	}

	if (visualizeMode == 9) {
		fragColor = vec4(vec3(texture(aoTex, vUV).r), 1.0);

		return;
	}

	// A cleared-but-never-written background pixel has a zero-length normal (real
	// written normals are always unit length) -- same sentinel technique as
	// pyosg-mrt.py, needed only for the modes below that actually shade something.
	//
	// Faux skybox: reconstruct a world-space view ray for this pixel from just vUV
	// and invViewProj (no geometry, no cubemap sample) and shade it with the same
	// sky/ground hemisphere gradient evaluateIBL() already uses for ambient fallback
	// lighting -- keeps the background visually consistent with the model's own
	// ambient term instead of introducing a second, unrelated look. Standard near/
	// far-unprojection-difference technique for a ray direction: near/far plane
	// choice is arbitrary and cancels out of the final normalized direction, so this
	// is unaffected by gbuffer_cam's own near/far tightening (see the znear/zfar
	// mismatch comment above, mode 3). A live REPL session first proved this pattern by sampling
	// envMap directly here instead of a gradient -- see git history/BUG.md if a real
	// cubemap-background mode is ever wanted again.
	if (dot(rawNormal, rawNormal) < 0.0001) {
		vec2 ndc = vUV * 2.0 - 1.0;
		vec4 nearP = invViewProj * vec4(ndc, -1.0, 1.0);
		vec4 farP  = invViewProj * vec4(ndc,  1.0, 1.0);
		vec3 rayDir = normalize(farP.xyz / farP.w - nearP.xyz / nearP.w);

		fragColor = vec4(mix(groundColor, skyColor, smoothstep(-0.08, 0.08, rayDir.z)), 1.0);

		return;
	}

	vec3 N = normalize(rawNormal);
	// Use the exact position that the geometry pass shaded. Reconstructing this from
	// depth is fragile when OSG tightens the main camera's near/far planes during
	// culling: the depth buffer then reflects an adjusted projection matrix that is
	// not necessarily the matrix exposed as v.camera.projectionMatrix.
	vec3 eyePos = texture(gPosition, vUV).xyz;
	vec3 V = normalize(-eyePos);
	float NdotV = max(dot(N, V), 0.0);
	Material mat = unpackMaterial(albedo.rgb, ormRaw);
	float ssao = texture(aoTex, vUV).r;
	float shad = shadowFactor(eyePos);

	if (visualizeMode == 5) {
		fragColor = vec4(pow(evaluateDirectLighting(mat, N, V, NdotV, shad), vec3(1.0 / 2.2)), 1.0);

		return;
	}

	if (visualizeMode == 6) {
		fragColor = vec4(pow(evaluateIBL(mat, N, V, NdotV) * ssao, vec3(1.0 / 2.2)), 1.0);

		return;
	}

	if (visualizeMode == 7) {
		fragColor = vec4(pow(rawEmissive, vec3(1.0 / 2.2)), 1.0);

		return;
	}

	if (visualizeMode == 8) {
		fragColor = vec4(vec3(shadowFactor(eyePos)), 1.0);

		return;
	}

	// SSAO multiplies (doesn't replace) the material's own baked AO -- they're
	// complementary: gMaterial.b is a static, authored/texture-baked value, ssao is a
	// live screen-space approximation of contact occlusion neither texture nor a flat
	// light rig can know about.
	vec3 Lo = evaluateDirectLighting(mat, N, V, NdotV, shad);
	vec3 ambient = evaluateIBL(mat, N, V, NdotV) * ssao;
	vec3 color = ambient + Lo + rawEmissive;

	// Debug aid for tuning shadowStrength/bias against the ACTUAL composite result
	// rather than mode 8 alone (see BUG.md item 2's note) -- tints how much this
	// pixel's direct term got darkened by the shadow map, independent of whatever
	// ambient/emissive is riding on top of it.
	if (shadowDebugTint) color = mix(color, vec3(1.0, 0.0, 0.0), (1.0 - shad) * 0.7);

	// No tonemap/gamma here anymore -- this is now a LINEAR HDR intermediate that
	// bloom_threshold_cam needs to sample before anything gets compressed to LDR;
	// final_cam does tonemap+gamma once, after bloom is added back in.
	fragColor = vec4(color, 1.0);
}
"""

BRDF_LUT_FRAGMENT = """
#version 460 core
const float PI = 3.14159265359;
in vec2 vUV;
out vec4 fragColor;

float RadicalInverse_VdC(uint bits) {
	bits = (bits << 16u) | (bits >> 16u);
	bits = ((bits & 0x55555555u) << 1u) | ((bits & 0xAAAAAAAAu) >> 1u);
	bits = ((bits & 0x33333333u) << 2u) | ((bits & 0xCCCCCCCCu) >> 2u);
	bits = ((bits & 0x0F0F0F0Fu) << 4u) | ((bits & 0xF0F0F0F0u) >> 4u);
	bits = ((bits & 0x00FF00FFu) << 8u) | ((bits & 0xFF00FF00u) >> 8u);
	return float(bits) * 2.3283064365386963e-10;
}

vec2 hammersley(uint i, uint N) {
	return vec2(float(i) / float(N), RadicalInverse_VdC(i));
}

vec3 importanceSampleGGX(vec2 Xi, float roughness) {
	float a = roughness * roughness;
	float phi = 2.0 * PI * Xi.x;
	float cosTheta = sqrt((1.0 - Xi.y) / (1.0 + (a * a - 1.0) * Xi.y));
	float sinTheta = sqrt(1.0 - cosTheta * cosTheta);
	return vec3(sinTheta * cos(phi), sinTheta * sin(phi), cosTheta);
}

float G_GGX_IBL(float NdotX, float roughness) {
	float k = (roughness * roughness) / 2.0;
	return NdotX / (NdotX * (1.0 - k) + k);
}

void main() {
	float NdotV = max(vUV.x, 1e-4);
	float roughness = vUV.y;
	vec3 V = vec3(sqrt(1.0 - NdotV * NdotV), 0.0, NdotV);

	float F_scale = 0.0, F_bias = 0.0;
	const uint SAMPLES = 1024u;
	for (uint i = 0u; i < SAMPLES; i++) {
		vec2 Xi = hammersley(i, SAMPLES);
		vec3 H = importanceSampleGGX(Xi, roughness);
		vec3 L = normalize(2.0 * dot(V, H) * H - V);
		float NdotL = max(L.z, 0.0);
		float NdotH = max(H.z, 0.0);
		float VdotH = max(dot(V, H), 0.0);
		if (NdotL > 0.0) {
			float G = G_GGX_IBL(NdotV, roughness) * G_GGX_IBL(NdotL, roughness);
			float G_vis = G * VdotH / max(NdotH * NdotV, 0.001);
			float Fc = pow(1.0 - VdotH, 5.0);
			F_scale += (1.0 - Fc) * G_vis;
			F_bias += Fc * G_vis;
		}
	}
	fragColor = vec4(F_scale / float(SAMPLES), F_bias / float(SAMPLES), 0.0, 1.0);
}
"""

# Final LDR pass: additively composites bloom into the HDR color, tonemaps, gamma-
# encodes, then applies vignette/grain/chromatic-aberration/sharpening/color-balance --
# all cheap single-pass color-only effects per the research doc's own complexity tiering,
# so they share one shader rather than a pass each. Relays composite_cam's debug output
# untouched whenever visualizeMode != 0 (see the module docstring at the top of this file
# for why that's the correct fix rather than re-deriving debug views here).
FINAL_FRAGMENT_SHADER = """
#version 460 core

uniform sampler2D hdrColorTex; // unit 0
uniform sampler2D bloomTex;    // unit 1
uniform sampler2D aoTex;       // unit 2: same blurred SSAO composite_cam already reads

uniform int visualizeMode;
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

// Khronos PBR Neutral tonemapping -- identical to composite_cam's old inline version,
// just relocated here: bloom needs to sample pre-tonemap HDR (research doc's ordering
// rule), so tonemap can only happen once bloom has already been added back in.
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

// Narkowicz 2015 fit to the ACES reference rendering transform -- the common
// "ACES-style" filmic curve most game engines actually ship (the real ACES
// RRT+ODT is a 3D LUT, not a closed-form curve). More contrast/saturation
// falloff in the highlights than PBR Neutral, which is the point of comparing
// them side by side.
vec3 tonemapACES(vec3 x) {
	const float a = 2.51;
	const float b = 0.03;
	const float c = 2.43;
	const float d = 0.59;
	const float e = 0.14;

	return clamp((x * (a * x + b)) / (x * (c * x + d) + e), 0.0, 1.0);
}

// Simple Reinhard (x / (1+x)) -- the baseline every other curve gets judged
// against: cheapest possible highlight rolloff, no contrast shaping, desaturates
// less gracefully than either of the above at high intensities.
vec3 tonemapReinhard(vec3 x) {
	return x / (1.0 + x);
}

void main() {
	if (visualizeMode != 0) {
		fragColor = texture(hdrColorTex, vUV);

		return;
	}

	vec3 hdr;

	if (postEnabled) {
		// Chromatic aberration has to happen WHILE assembling color, not after -- you
		// can't offset one channel of an already-combined vec3. Each offset sample
		// includes its own bloom contribution so CA and bloom don't visibly separate.
		vec2 caDir = (vUV - 0.5) * caStrength;

		float r = texture(hdrColorTex, vUV - caDir).r + texture(bloomTex, vUV - caDir).r * bloomStrength;
		float g = texture(hdrColorTex, vUV).g          + texture(bloomTex, vUV).g          * bloomStrength;
		float b = texture(hdrColorTex, vUV + caDir).b + texture(bloomTex, vUV + caDir).b * bloomStrength;

		hdr = vec3(r, g, b);

		// Sharpen (unsharp mask), in linear HDR, on the un-aberrated center sample --
		// sharpening the CA-offset channels separately would just resharpen the
		// aberration itself. 4-tap cross pattern, no extra RTT pass needed.
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

	// Exposure applies regardless of postEnabled -- it's a core linear-HDR-to-
	// tonemap step, not a stylistic extra like CA/sharpen/vignette/grain below.
	hdr *= exp2(exposure);

	vec3 color;

	if (tonemapMode == 1) color = tonemapACES(hdr);
	else if (tonemapMode == 2) color = tonemapReinhard(hdr);
	else if (tonemapMode == 3) color = clamp(hdr, 0.0, 1.0);
	else color = tonemapPBRNeutral(hdr);

	color = pow(color, vec3(1.0 / 2.2));

	if (postEnabled) {
		// Color balance -- simplified single-range lift/gamma/gain (not the full
		// shadow/midtone/highlight split a real grading tool exposes -- more uniforms
		// than a teaching example needs without a UI to scrub them live).
		color = pow(max(color + colorLift, 0.0), vec3(1.0 / colorGamma)) * colorGain;

		float d = distance(vUV, vec2(0.5));
		float vig = smoothstep(0.8, 0.2, d);
		color *= mix(1.0 - vignetteStrength, 1.0, vig);

		// floor()'d to a coarser cell before hashing, so grainSize > 1 gives chunkier
		// "kernels" instead of scaling the noise's own frequency content -- same trick
		// as the sharpen/blur taps above, just quantizing position instead of blurring.
		vec2 grainCell = floor(gl_FragCoord.xy / max(grainSize, 1.0));

		if (grainAnimated) grainCell += osg_SimulationTime;

		float g = fract(sin(dot(grainCell, vec2(12.9898, 78.233))) * 43758.5453);

		// aoTex is 1.0 = unoccluded, lower = darker/more-occluded (see the SSAO pass's
		// own `1.0 - occlusion` output) -- mix() from "everywhere" to "only where dark"
		// lets grainAOBoost=0 reproduce the original uniform grain exactly, and ramps
		// toward concentrating it in AO crevices as it increases.
		float aoMask = mix(1.0, 1.0 - texture(aoTex, vUV).r, grainAOBoost);

		color += (g - 0.5) * grainStrength * aoMask;
	}

	fragColor = vec4(clamp(color, 0.0, 1.0), 1.0);
}
"""

# ---- One-shot bake helper (verbatim from 09-ibl.py) ------------------------- #

class SingleBake:
	def __init__(self, group):
		self.group = group
		self.done = False

		group.updateCallback = self

	def __call__(self, node, nv):
		if self.done:
			node.nodeMask = 0

		self.done = True

		return True

	def bake(self):
		self.group.nodeMask = 0xFFFFFFFF
		self.done = False

# --------------------------------------------------------------------------- #
# BRDF LUT bake (environment-independent - fires once at startup)
# --------------------------------------------------------------------------- #

def make_brdf_lut(lut_size=512):
	lut_tex = osg.Texture2D()
	lut_tex.size = (lut_size, lut_size)
	lut_tex.internalFormat = GL_RGBA
	lut_tex.filter = (osg.Texture.LINEAR, osg.Texture.LINEAR)
	lut_tex.wrap = osg.Texture.CLAMP_TO_EDGE

	bake_p = osg.Program(name="brdf_lut", shaders=(
		osg.Shader(osg.Shader.VERTEX, FULLSCREEN_VERTEX),
		osg.Shader(osg.Shader.FRAGMENT, BRDF_LUT_FRAGMENT),
	))

	quad = osg.createTexturedQuadGeometry(
		osg.Vec3(-1, -1, 0),
		osg.Vec3(2, 0, 0),
		osg.Vec3(0, 2, 0)
	)

	quad_geode = osg.Geode()
	quad_geode.drawables.append(quad)

	bake_group = osg.Group()

	SingleBake(bake_group)

	cam = osg.Camera()
	cam.name = "BRDFLutBake"
	cam.renderOrder = osg.Camera.PRE_RENDER
	cam.renderTargetImplementation = osg.Camera.FRAME_BUFFER_OBJECT
	cam.referenceFrame = osg.Transform.ABSOLUTE_RF
	cam.clearMask = GL_COLOR_BUFFER_BIT
	cam.viewport = osg.Viewport(0, 0, lut_size, lut_size)
	cam.projectionMatrix = osg.Matrix.identity()
	cam.viewMatrix = osg.Matrix.identity()
	cam.attach(osg.Camera.COLOR_BUFFER0, lut_tex, 0, 0, False)
	cam.stateSet.setAttributeAndModes(bake_p)
	cam.children.append(quad_geode)
	bake_group.children.append(cam)

	return lut_tex, bake_group

# --------------------------------------------------------------------------- #
# G-buffer + post-processing cameras
# --------------------------------------------------------------------------- #

# Six simultaneous attachments from one geometry pass -- albedo/normal/material/emissive/
# view-position color buffers plus real scene depth (distinct from shadow_tex's light-space depth).
# RELATIVE_RF (no explicit view/projection set) so this camera inherits v.camera's actual
# view/projection every frame during its PRE_RENDER traversal, same as pyosg-mrt.py's
# gbuffer camera -- that's what keeps eye-space consistent between here and the composite
# pass's depth-reconstructed eyePos.
def create_gbuffer_camera(w=W, h=H, msaa_samples=0):
	albedo_tex = osg.Texture2D()
	albedo_tex.size = (w, h)
	albedo_tex.internalFormat = GL_RGBA
	albedo_tex.filter = (osg.Texture.LINEAR, osg.Texture.LINEAR)

	normal_tex = osg.Texture2D()
	normal_tex.size = (w, h)
	normal_tex.internalFormat = GL_RGB16F
	normal_tex.filter = (osg.Texture.NEAREST, osg.Texture.NEAREST)

	material_tex = osg.Texture2D()
	material_tex.size = (w, h)
	material_tex.internalFormat = GL_RGB
	material_tex.filter = (osg.Texture.NEAREST, osg.Texture.NEAREST)

	emissive_tex = osg.Texture2D()
	emissive_tex.size = (w, h)
	emissive_tex.internalFormat = GL_RGB16F
	emissive_tex.filter = (osg.Texture.LINEAR, osg.Texture.LINEAR)

	position_tex = osg.Texture2D()
	position_tex.size = (w, h)
	position_tex.internalFormat = GL_RGB32F
	position_tex.filter = (osg.Texture.NEAREST, osg.Texture.NEAREST)

	depth_tex = osg.Texture2D()
	depth_tex.size = (w, h)
	depth_tex.internalFormat = GL_DEPTH_COMPONENT24
	depth_tex.sourceFormat = GL_DEPTH_COMPONENT
	depth_tex.sourceType = GL_FLOAT
	depth_tex.filter = (osg.Texture.NEAREST, osg.Texture.NEAREST)

	# Marked DYNAMIC (not left at OSG's default) since each of these is both a render
	# target here AND a sampler input in later passes -- same fix
	# ~/dev/slughorn/ai/enterprise-hud3d.py applies to all of its RTT textures. Without
	# it, OSG's default caching can treat a texture as static after its first successful
	# bind and skip properly re-applying it on later frames.
	for tex in (albedo_tex, normal_tex, material_tex, emissive_tex, position_tex, depth_tex):
		tex.dataVariance = osg.Object.DYNAMIC

	cam = osg.Camera()
	cam.renderOrder = (osg.Camera.PRE_RENDER, 1)
	cam.renderTargetImplementation = osg.Camera.FRAME_BUFFER_OBJECT
	cam.clearMask = GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT
	cam.clearColor = osg.Vec4(0.0, 0.0, 0.0, 0.0)
	cam.viewport = osg.Viewport(0, 0, w, h)
	cam.name = "G-Buffer Camera"

	# A non-zero count makes OSG render the whole MRT G-buffer into multisample
	# renderbuffers, then resolve each attachment into these ordinary Texture2Ds.
	# The downstream SSAO/composite passes can therefore keep sampling sampler2D.
	for buffer, tex in (
		(osg.Camera.COLOR_BUFFER0, albedo_tex),
		(osg.Camera.COLOR_BUFFER1, normal_tex),
		(osg.Camera.COLOR_BUFFER2, material_tex),
		(osg.Camera.COLOR_BUFFER3, emissive_tex),
		(osg.Camera.COLOR_BUFFER4, position_tex),
		(osg.Camera.DEPTH_BUFFER, depth_tex),
	):
		cam.attach(buffer, tex, multisampleSamples=msaa_samples)

	return cam, albedo_tex, normal_tex, material_tex, emissive_tex, position_tex, depth_tex

# Generic fullscreen post-process RTT camera factory -- adapted from examples/
# pyosg-blur.py's make_fullscreen_rtt_pass()/make_blur_pass(), generalized to accept
# multiple input textures (pyosg-blur.py's version only ever needed one) since ssao_cam
# samples three. `textures` is {unit: (texture, uniform_name)}.
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
	# Fullscreen passes have no depth relationship. OSG gives this FBO an implicit
	# depth renderbuffer; if depth testing is inherited while only color is cleared,
	# frame 0 writes depth and identical frame-1 fragments all fail GL_LESS.
	ss.setMode(
		GL_DEPTH_TEST,
		osg.StateAttribute.OFF | osg.StateAttribute.OVERRIDE
	)

	for unit, (tex, uniform_name) in textures.items():
		ss.textureAttributes[unit] = tex
		ss.uniforms[uniform_name] = unit

	if extra_uniforms:
		for k, val in extra_uniforms.items():
			ss.uniforms[k] = val

	p = osg.Program(name=f"{name}_program", shaders=(
		osg.Shader(osg.Shader.VERTEX, FULLSCREEN_VERTEX),
		osg.Shader(osg.Shader.FRAGMENT, frag_shader),
	))

	ss.setAttributeAndModes(p)

	g = osg.Geode()
	g.drawables.append(osg.createTexturedQuadGeometry(
		osg.Vec3(-1.0, -1.0, -1.0),
		osg.Vec3(2.0, 0.0, 0.0),
		osg.Vec3(0.0, 2.0, 0.0)
	))

	cam.children.append(g)

	return cam

# SSAO raw pass + denoise blur -- reads gDepth/gNormal directly, no dependency on
# composite_cam (runs before it). ssao_radius is in view-space world units, scaled by
# the caller against the model's bounding radius (same reasoning 09-ibl.py applies to
# its point-light radii -- a fixed-world-unit radius doesn't generalize between
# BoomBox-scale and Lantern-scale models).
def create_ssao_camera(depth_tex, normal_tex, noise_tex, position_tex, samples_u, radius, bias=0.02, w=W, h=H):
	ao_raw_tex = osg.Texture2D()
	ao_raw_tex.size = (w, h)
	ao_raw_tex.internalFormat = GL_R8
	ao_raw_tex.sourceFormat = GL_RED
	ao_raw_tex.sourceType = GL_UNSIGNED_BYTE
	ao_raw_tex.filter = (osg.Texture.LINEAR, osg.Texture.LINEAR)
	ao_raw_tex.dataVariance = osg.Object.DYNAMIC

	cam = make_fullscreen_rtt_pass(
		textures={
			0: (depth_tex, "gDepth"),
			1: (normal_tex, "gNormal"),
			2: (noise_tex, "ssaoNoise"),
			3: (position_tex, "gPosition"),
		},
		output_tex=ao_raw_tex,
		frag_shader=SSAO_FRAGMENT_SHADER,
		w=w, h=h,
		name="SSAO",
		order=2,
		extra_uniforms={
			"ssaoRadius": radius,
			"ssaoBias": bias,
		}
	)

	cam.stateSet.uniforms.extend((samples_u,))

	return cam, ao_raw_tex

def create_ssao_blur_camera(ao_raw_tex, w=W, h=H):
	ao_tex = osg.Texture2D()
	ao_tex.size = (w, h)
	ao_tex.internalFormat = GL_R8
	ao_tex.sourceFormat = GL_RED
	ao_tex.sourceType = GL_UNSIGNED_BYTE
	ao_tex.filter = (osg.Texture.LINEAR, osg.Texture.LINEAR)
	ao_tex.dataVariance = osg.Object.DYNAMIC

	cam = make_fullscreen_rtt_pass(
		textures={0: (ao_raw_tex, "aoRawTex")},
		output_tex=ao_tex,
		frag_shader=SSAO_BLUR_FRAGMENT_SHADER,
		w=w, h=h,
		name="SSAOBlur",
		order=3,
	)

	return cam, ao_tex

# Composite camera -- now a PRE_RENDER FBO pass writing linear HDR (previously POST_
# RENDER, drawing straight to the window; see the module docstring). Needs its OWN
# explicit viewport now that it owns an FBO -- absent, this silently produces a black/
# empty hdrColorTex, since a fresh FBO pass doesn't inherit the default framebuffer's
# viewport the way the old draw-straight-to-window version implicitly did.
def create_composite_camera(gbuf, shadow_tex, prefilter_tex, lut_tex, ao_tex, hdr_color_tex, w=W, h=H):
	albedo_tex, normal_tex, material_tex, emissive_tex, position_tex, depth_tex = gbuf

	cam = osg.Camera()
	cam.referenceFrame = osg.Transform.ABSOLUTE_RF
	cam.renderOrder = (osg.Camera.PRE_RENDER, 4)
	cam.renderTargetImplementation = osg.Camera.FRAME_BUFFER_OBJECT
	cam.dataVariance = osg.Object.DYNAMIC
	cam.clearMask = GL_COLOR_BUFFER_BIT
	cam.clearColor = osg.Vec4(0.0, 0.0, 0.0, 0.0)
	cam.viewport = osg.Viewport(0, 0, w, h)
	cam.allowEventFocus = False
	cam.projectionMatrix = osg.Matrix.identity()
	cam.viewMatrix = osg.Matrix.identity()
	cam.name = "Composite"

	cam.attach(osg.Camera.COLOR_BUFFER0, hdr_color_tex)

	g = osg.Geode()
	g.drawables.append(osg.createTexturedQuadGeometry(
		osg.Vec3(-1.0, -1.0, -1.0),
		osg.Vec3(2.0, 0.0, 0.0),
		osg.Vec3(0.0, 2.0, 0.0)
	))

	cam.children.append(g)

	ss = cam.stateSet
	# See make_fullscreen_rtt_pass(): prevent the implicit FBO depth buffer from
	# rejecting this same fullscreen quad on frame 1 and every frame thereafter.
	ss.setMode(
		GL_DEPTH_TEST,
		osg.StateAttribute.OFF | osg.StateAttribute.OVERRIDE
	)
	ss.textureAttributes[0] = albedo_tex
	ss.textureAttributes[1] = normal_tex
	ss.textureAttributes[2] = material_tex
	ss.textureAttributes[3] = emissive_tex
	ss.textureAttributes[4] = depth_tex
	ss.textureAttributes[5] = shadow_tex
	ss.textureAttributes[6] = prefilter_tex
	ss.textureAttributes[7] = lut_tex
	ss.textureAttributes[8] = ao_tex
	ss.textureAttributes[9] = position_tex

	ss.uniforms["gAlbedo"] = 0
	ss.uniforms["gNormal"] = 1
	ss.uniforms["gMaterial"] = 2
	ss.uniforms["gEmissive"] = 3
	ss.uniforms["gDepth"] = 4
	ss.uniforms["shadowMap"] = 5
	ss.uniforms["envMap"] = 6
	ss.uniforms["brdfLUT"] = 7
	ss.uniforms["aoTex"] = 8
	ss.uniforms["gPosition"] = 9

	p = osg.Program(name="composite_pbr_ibl", shaders=(
		osg.Shader(osg.Shader.VERTEX, FULLSCREEN_VERTEX),
		osg.Shader(osg.Shader.FRAGMENT, COMPOSITE_FRAGMENT_SHADER),
	))

	g.stateSet.setAttributeAndModes(p)

	return cam

# Bloom: threshold-extract -> horizontal blur -> vertical blur, all reusing
# make_fullscreen_rtt_pass(). Single-scale two-pass blur, not a downsample/upsample mip
# pyramid -- the sanctioned simplification for a teaching example (real engines pyramid
# for a wider, cheaper glow; footnote only, not built here).
def create_bloom_cameras(hdr_color_tex, w=W, h=H):
	bright_tex = osg.Texture2D()
	bright_tex.size = (w, h)
	bright_tex.internalFormat = GL_RGB16F
	bright_tex.filter = (osg.Texture.LINEAR, osg.Texture.LINEAR)

	blur_a_tex = osg.Texture2D()
	blur_a_tex.size = (w, h)
	blur_a_tex.internalFormat = GL_RGB16F
	blur_a_tex.filter = (osg.Texture.LINEAR, osg.Texture.LINEAR)

	blur_b_tex = osg.Texture2D()
	blur_b_tex.size = (w, h)
	blur_b_tex.internalFormat = GL_RGB16F
	blur_b_tex.filter = (osg.Texture.LINEAR, osg.Texture.LINEAR)

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

# Final LDR pass -- new last camera in the chain, takes over composite_cam's old role of
# drawing straight to the window (no renderTargetImplementation set, same as pyosg-mrt.py's
# HUD camera / composite_cam's own pre-increment-2 shape).
def create_final_camera(hdr_color_tex, bloom_tex, ao_tex, w=W, h=H):
	cam = osg.Camera()
	cam.referenceFrame = osg.Transform.ABSOLUTE_RF
	cam.renderOrder = osg.Camera.POST_RENDER
	cam.clearMask = 0
	cam.allowEventFocus = False
	cam.projectionMatrix = osg.Matrix.identity()
	cam.viewMatrix = osg.Matrix.identity()
	cam.name = "Final"

	g = osg.Geode()
	g.drawables.append(osg.createTexturedQuadGeometry(
		osg.Vec3(-1.0, -1.0, -1.0),
		osg.Vec3(2.0, 0.0, 0.0),
		osg.Vec3(0.0, 2.0, 0.0)
	))

	cam.children.append(g)

	ss = cam.stateSet
	# The final fullscreen pass does not use depth either. Keep its state explicit
	# instead of inheriting GL_DEPTH_TEST from the viewer's real-geometry pass.
	ss.setMode(
		GL_DEPTH_TEST,
		osg.StateAttribute.OFF | osg.StateAttribute.OVERRIDE
	)
	ss.textureAttributes[0] = hdr_color_tex
	ss.textureAttributes[1] = bloom_tex
	ss.textureAttributes[2] = ao_tex
	ss.uniforms["hdrColorTex"] = 0
	ss.uniforms["bloomTex"] = 1
	ss.uniforms["aoTex"] = 2

	p = osg.Program(name="final_post", shaders=(
		osg.Shader(osg.Shader.VERTEX, FULLSCREEN_VERTEX),
		osg.Shader(osg.Shader.FRAGMENT, FINAL_FRAGMENT_SHADER),
	))

	g.stateSet.setAttributeAndModes(p)

	return cam

def create_grid_room(bound_center, bound_radius, floor_z, room_size):
	"""Create the optional Z-up model guide room.

	`room_size` is the full floor width/depth (the existing --floor-size meaning).
	The room is centered on the asset's horizontal bound center, while its floor is
	explicitly positioned so callers can place it at the model's conservative base.
	"""
	half_width = room_size * 0.5
	room_height = max(
		bound_center.z + bound_radius - floor_z + bound_radius * 0.5,
		room_size * 0.75
	)
	center_x, center_y = bound_center.x, bound_center.y
	frame_width = max(bound_radius * 0.035, room_size * 0.008)

	grid_program = osg.Program(name="grid_room_gbuffer", shaders=(
		osg.Shader(osg.Shader.VERTEX, GRID_ROOM_VERTEX),
		osg.Shader(osg.Shader.FRAGMENT, GRID_ROOM_FRAGMENT),
	))
	frame_program = osg.Program(name="grid_room_frame_gbuffer", shaders=(
		osg.Shader(osg.Shader.VERTEX, UNLIT_GBUFFER_VERTEX),
		osg.Shader(osg.Shader.FRAGMENT, FRAME_GBUFFER_FRAGMENT),
	))

	def make_grid(corner, width, height):
		grid = osgDebug.Grid(corner, width, height)
		grid.canvasSize = osg.Vec2(500.0, 500.0)
		grid.gridInterval = 50.0
		grid.gridIntervalStrong = 250.0
		grid.lineWidthPx = 1.0
		grid.colorBg = osg.Vec4(0.055, 0.070, 0.110, 1.0)
		grid.colorLine = osg.Vec4(0.20, 0.30, 0.48, 1.0)
		grid.colorLineStrong = osg.Vec4(0.52, 0.68, 0.90, 1.0)
		grid.stateSet.uniforms["roomRoughness"] = 0.85
		grid.stateSet.uniforms["roomMetallic"] = 0.0
		grid.stateSet.setAttributeAndModes(
			grid_program,
			osg.StateAttribute.ON | osg.StateAttribute.OVERRIDE
		)
		# Grid's normal forward-rendered state enables alpha blending so transparent
		# background pixels reveal the framebuffer behind it. In the G-buffer that
		# would blend the normal target with its zero alpha and leave it cleared;
		# composite then mistakes an actual grid line for sky. Discard handles the
		# transparent parts here, so deferred rendering must write every attachment
		# without blending.
		grid.stateSet.setMode(GL_BLEND, osg.StateAttribute.OFF | osg.StateAttribute.OVERRIDE)

		return grid

	# The floor is XY at floor_z; rear/right walls make the same open, Z-up room
	# as osgdebug-grid.cpp. The model stays centered horizontally in the room.
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
		osg.Vec3(0.0, room_size, 0.0),
		osg.Vec3(0.0, 0.0, room_height)
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

	frame.stateSet.setAttributeAndModes(frame_program, osg.StateAttribute.ON | osg.StateAttribute.OVERRIDE)
	frame.stateSet.uniforms["frameColor"] = osg.Vec3(0.55, 0.60, 0.70)

	room = osg.Group()
	room.children.extend((panels, frame))

	return room, (floor, back_wall, right_wall)

# --------------------------------------------------------------------------- #
# Light gizmo: a directional light has no position or reach, only an angle --
# a sphere-at-a-point implies a location/falloff that isn't physically real.
# Instead this draws a wireframe quad ("plane") perpendicular to lightDir,
# representing the infinite plane of parallel rays, plus a single normal-style
# line emitting from its center toward the scene to show ray direction. Both
# are one GL_LINES Geometry: a LINE_LOOP for the quad outline and a LINES pair
# for the direction stub. Position/orientation are recomputed every frame from
# the live lightDir/lightColor uniforms via an updateCallback, so edits made
# through --repl (see pyosg_repl.repl() call below) are reflected immediately
# without rebuilding the scene graph. Rendered as its own POST_RENDER pass
# after final_cam, RELATIVE_RF (inherits the real viewer camera's view/
# projection, same as gbuffer_cam) with depth test off -- always visible,
# simplest possible overlay. Not depth-tested against the real scene:
# final_cam already wrote straight to the backbuffer, so there's no usable
# depth buffer left to test against at this point in the pipeline.
# --------------------------------------------------------------------------- #

GIZMO_VERTEX_SHADER = """
#version 460 core

in vec4 osg_Vertex;

uniform mat4 osg_ModelViewProjectionMatrix;

void main() {
	gl_Position = osg_ModelViewProjectionMatrix * osg_Vertex;
}
"""

GIZMO_FRAGMENT_SHADER = """
#version 460 core

uniform vec3 gizmoColor;

out vec4 fragColor;

void main() {
	fragColor = vec4(gizmoColor, 1.0);
}
"""

class LightGizmoCallback:
	def __init__(self, bound_center, plane_geom, color_u, light_dir_u, light_color_u, plane_half_size, normal_length):
		self.bound_center = bound_center
		self.plane_geom = plane_geom
		self.color_u = color_u
		self.light_dir_u = light_dir_u
		self.light_color_u = light_color_u
		self.plane_half_size = plane_half_size
		self.normal_length = normal_length
		# Arrowhead proportions, relative to the direction stub's own length rather
		# than plane_half_size -- keeps the head's size tied to the line it's
		# marking, not the (much larger, independently tunable) outer quad.
		self.arrow_back = normal_length * 0.2
		self.arrow_width = normal_length * 0.15

	def __call__(self, node, nv):
		d = self.light_dir_u.value
		length = d.length()
		n = d / length if length > 1e-6 else osg.Vec3(0.0, 0.0, 1.0)
		center = self.bound_center + d
		half = self.plane_half_size

		# Build an orthonormal in-plane basis perpendicular to n. Z-up reference
		# vector, except when n is nearly parallel to it (near the poles of the
		# orbit), where X is used instead to avoid a degenerate/zero-length cross.
		up_ref = osg.Vec3(1.0, 0.0, 0.0) if abs(n.z) > 0.99 else osg.Vec3(0.0, 0.0, 1.0)
		u = up_ref.cross(n)
		u = u / u.length()
		v = n.cross(u)

		# Mutate the existing array in place and dirty() it, rather than handing
		# setVertexArray() a brand-new Vec3Array every frame. A new array is a new
		# BufferData identity to OSG, so it can never look like "an update to
		# something I already know" -- only "first-time allocation," forcing an
		# expensive glBufferData() reallocation every single frame instead of the
		# cheap glBufferSubData() path OSG already uses for genuine in-place
		# updates. Was spamming OSG's buffer-object-pool notify output on every
		# frame ("Allocating new glBufferData(), _allocatedSize=24") and a likely
		# contributor to an intermittent NVIDIA driver segfault during zoom.
		plane_array = self.plane_geom.vertexArray

		plane_array[0] = center + u * half + v * half
		plane_array[1] = center - u * half + v * half
		plane_array[2] = center - u * half - v * half
		plane_array[3] = center + u * half - v * half
		plane_array[4] = center
		# Points back toward the model -- the rays' direction of travel, not the
		# outward-facing normal toward the light source.
		tip = center - n * self.normal_length
		plane_array[5] = tip

		# Arrowhead: two short segments from the tip, angled back toward the plane
		# and splayed out along the in-plane `u` axis, so the stub reads as a
		# direction (like a normal-with-arrowhead) instead of a symmetric line
		# whose depth/heading is ambiguous at a glance. Each segment needs its own
		# copy of the tip vertex -- GL_LINES draws consecutive vertex pairs, so a
		# single shared tip can't anchor two separate segments in one DrawArrays.
		wing_base = tip + n * self.arrow_back

		plane_array[6] = tip
		plane_array[7] = wing_base + u * self.arrow_width
		plane_array[8] = tip
		plane_array[9] = wing_base - u * self.arrow_width
		plane_array.dirty()

		# array.dirty() only marks the GPU buffer for re-upload -- it does NOT touch
		# the Geometry's cached bounding volume, which was computed once (early on,
		# from whatever position the plane happened to be in at the time) and never
		# again. Left alone, culling keeps testing every subsequent frame against
		# that stale bound, so once the light moves far enough that the ORIGINAL
		# position falls outside the frustum, the plane vanishes forever even though
		# its current, real position is clearly onscreen -- group/cam.cullingActive
		# don't help here, they only affect ancestor-level traversal shortcuts, not
		# this drawable's own per-frame cull test.
		self.plane_geom.dirtyBound()

		c = self.light_color_u.value
		m = max(c.x, c.y, c.z, 1e-4)

		self.color_u.value = osg.Vec3(c.x / m, c.y / m, c.z / m)

		return True

def create_light_gizmo(bound_center, bound_radius, light_dir_u, light_color_u):
	# Stay proportional across differently-scaled assets, and large enough to
	# read as "an infinite plane of parallel rays" rather than a small marker.
	plane_half_size = bound_radius * 2.5
	normal_length = bound_radius * 0.8

	p = osg.Program(name="light_gizmo", shaders=(
		osg.Shader(osg.Shader.VERTEX, GIZMO_VERTEX_SHADER),
		osg.Shader(osg.Shader.FRAGMENT, GIZMO_FRAGMENT_SHADER),
	))
	# Match the geometry binding below explicitly instead of relying on OSG's
	# compatibility/core-profile vertex-attribute aliasing policy.
	p.bindAttribLocation["osg_Vertex"] = 0

	# Plane outline (LINE_LOOP, vertices 0-3) + direction stub (LINES, vertices
	# 4-5) + arrowhead (LINES, vertices 6-9) in a single Geometry -- vertex array
	# mutated in place each frame (see LightGizmoCallback.__call__), not replaced
	# wholesale.
	plane_geom = osg.Geometry()
	plane_array = osg.Vec3Array([bound_center] * 10)
	plane_array.dataVariance = osg.Object.DYNAMIC
	plane_geom.vertexArray = plane_array
	plane_geom.vertexAttrib[0] = plane_array
	plane_geom.primitiveSets.append(osg.DrawArrays(osg.PrimitiveSet.LINE_LOOP, 0, 4))
	plane_geom.primitiveSets.append(osg.DrawArrays(osg.PrimitiveSet.LINES, 4, 2))
	plane_geom.primitiveSets.append(osg.DrawArrays(osg.PrimitiveSet.LINES, 6, 4))
	plane_geom.dataVariance = osg.Object.DYNAMIC
	plane_geom.useVertexBufferObjects = True
	plane_geode = osg.Geode()
	plane_geode.drawables.append(plane_geom)

	group = osg.Group()
	group.children.append(plane_geode)
	group.cullingActive = False

	color_u = osg.Uniform("gizmoColor", osg.Vec3(1.0, 1.0, 1.0))
	ss = group.stateSet
	ss.setAttributeAndModes(p)
	ss.uniforms.extend((color_u,))

	group.updateCallback = LightGizmoCallback(
		bound_center, plane_geom, color_u, light_dir_u, light_color_u, plane_half_size, normal_length
	)

	cam = osg.Camera()
	cam.name = "LightGizmo"
	cam.renderOrder = (osg.Camera.POST_RENDER, 1)
	cam.clearMask = 0
	cam.allowEventFocus = False
	cam.cullingActive = False
	cam.stateSet.setMode(GL_DEPTH_TEST, osg.StateAttribute.OFF | osg.StateAttribute.OVERRIDE)
	cam.children.append(group)

	return cam

# --------------------------------------------------------------------------- #
# Input
# --------------------------------------------------------------------------- #
#
# All interactive controls now live in the ImGui panel (see the `if args.gui:`
# block below) -- no keyboard shortcuts. LightOrbit is the one state-holding
# class left here: it's not an event handler, just the orbit math (azimuth/
# radius/height -> light_dir_u) that the GUI's Light Position sliders drive
# directly via ._sync(), same object either way.

class LightOrbit:
	"""Predictable cylindrical orbit state around the model's Z-up axis.

	The uniform stores the moon's world-space offset from the model center. Lighting
	and the shadow camera normalize that offset to obtain the inward/outward ray
	direction; the gizmo uses its full value so radius and rung remain visible.
	"""

	def __init__(self, light_dir_u, bound_radius):
		self.light_dir_u = light_dir_u
		self.min_radius = bound_radius * 0.1

		initial_distance = bound_radius * 1.5
		d = KEY_LIGHT_DIR.normalized() * initial_distance
		self.azimuth = math.atan2(d.y, d.x)
		self.orbit_radius = max(math.hypot(d.x, d.y), self.min_radius)
		self.height = d.z
		self._sync()

	def _sync(self):
		self.light_dir_u.value = osg.Vec3(
			math.cos(self.azimuth) * self.orbit_radius,
			math.sin(self.azimuth) * self.orbit_radius,
			self.height
		)

# If the passed-in file exists, simply return it; if not, try and find it inside example data dir.
def data_dir_file(f, suffix=None):
	if os.path.exists(f):
		return f

	dfs = [os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", fn) for fn in (
		f,
		f"{f}/glTF/{f}",
		f"{f}/glTF/{f}.gltf",
		f"{f}.gltf",
		f"{f}.hdr",
		f"{f}.ktx2"
	)]

	for df in dfs:
		if os.path.exists(df):
			f = pathlib.Path(df)

			if not suffix or f".{suffix}" == f.suffix:
				return df

	raise FileNotFoundError(f"{f} not a valid file")

if __name__ == "__main__":
	ap = argparse.ArgumentParser()
	ap.add_argument(
		"path",
		nargs="?",
		default="BoomBox/glTF/BoomBox.gltf"
	)
	ap.add_argument(
		"--ktx2",
		required=True,
		help="Pre-baked GGX-prefiltered cubemap (.ktx2)",
		default="papermill"
	)
	ap.add_argument(
		"--hdr",
		default=None,
		help="Equirectangular HDR for SH diffuse (optional; hemisphere fallback if omitted)"
	)
	ap.add_argument(
		"--ibl-diffuse-intensity",
		type=float,
		default=0.1,
		help="IBL ambient-fill (SH diffuse irradiance) exposure scale (default: 0.1)"
	)
	ap.add_argument(
		"--ibl-specular-intensity",
		type=float,
		default=0.1,
		help="IBL reflection (prefiltered specular) exposure scale (default: 0.1)"
	)
	ap.add_argument("--no-lights", dest="lights", action="store_false", default=True)
	ap.add_argument("--floor-z", type=float, default=None)
	ap.add_argument("--floor-size", type=float, default=None)
	ap.add_argument(
		"--msaa",
		type=int,
		choices=(0, 2, 4, 8),
		default=0,
		help="MSAA samples for the G-buffer geometry pass (default: 0)",
	)
	ap.add_argument(
		"--repl",
		action="store_true",
		default=False,
		help="Run the viewer alongside an embedded IPython REPL (see pyosg_repl.py) "
			"so uniforms/lights can be tweaked live while watching the render window."
	)
	ap.add_argument(
		"--no-gui",
		dest="gui",
		action="store_false",
		default=True,
		help="Disable the osgDebug ImGui panel. All interactive controls (IBL, "
			"exposure, tonemap, light position, shadow, post FX) live only in this "
			"panel now, so disabling it leaves no way to adjust them at runtime."
	)

	args = ap.parse_args()

	args.floor = args.floor_z is not None or args.floor_size is not None

	args.path = data_dir_file(args.path, "gltf")
	args.ktx2 = data_dir_file(args.ktx2, "ktx2")

	if args.hdr:
		args.hdr = data_dir_file(args.hdr, "hdr")

	osg.setNotifyLevel(osg.NotifySeverity.NOTICE)

	model = osgDB.readNodeFile(args.path)

	bound = model.bound
	bound_center = bound.center
	bound_radius = bound.radius if bound.radius > 1e-6 else REFERENCE_RADIUS

	print(
		f"[sketchfab] model bound: center={tuple(bound_center)} radius={bound_radius:.4f}",
		flush=True
	)

	# Preserve the existing opt-in floor flags, but turn them into a room guide whose
	# omitted dimension(s) scale with the actual asset. A bounding sphere gives a
	# conservative floor height even for models with unusual local origins.
	if args.floor:
		args.floor_z = bound_center.z - bound_radius if args.floor_z is None else args.floor_z
		args.floor_size = bound_radius * 4.0 if args.floor_size is None else args.floor_size

		print(
			f"[sketchfab] grid room: floor_z={args.floor_z:.4f} "
			f"size={args.floor_size:.4f}",
			flush=True
		)

	# --- Load prefiltered cubemap from KTX2 --------------------------------- #
	prefilter_tex = osgDB.readObjectFile(args.ktx2)

	if not isinstance(prefilter_tex, osg.TextureCubeMap):
		print(
			f"ERROR: {args.ktx2!r} did not return a TextureCubeMap "
			f"(got {type(prefilter_tex).__name__})",
			flush=True
		)

		sys.exit(1)

	prefilter_tex.useHardwareMipMapGeneration = False

	# --- BRDF split-sum LUT (environment-independent, baked once) ----------- #
	lut_tex, lut_group = make_brdf_lut()

	# --- IBL uniforms (live on composite_cam's stateSet) --------------------- #
	ibl_sh_u = osg.Uniform(osg.Uniform.Type.FLOAT_VEC3, "iblSH", (osg.Vec3(),) * 9)
	ibl_enabled_u = osg.Uniform("iblEnabled", 1) # always 1 - we have the cubemap
	ibl_diffuse_intensity_u = osg.Uniform("iblDiffuseIntensity", args.ibl_diffuse_intensity)
	ibl_specular_intensity_u = osg.Uniform("iblSpecularIntensity", args.ibl_specular_intensity)

	# --- G-buffer geometry-pass program -------------------------------------- #
	p = osg.Program(name="gbuffer_pbr", shaders=(
		osg.Shader(osg.Shader.VERTEX, GBUFFER_VERTEX_SHADER),
		osg.Shader(osg.Shader.FRAGMENT, GBUFFER_FRAGMENT_SHADER),
	))

	ss = model.stateSet

	ss.setAttributeAndModes(
		p,
		osg.StateAttribute.ON | osg.StateAttribute.OVERRIDE | osg.StateAttribute.PROTECTED
	)

	ss.uniforms["osgGLTF_textures.baseColor"] = 0
	ss.uniforms["osgGLTF_textures.normal"] = 1
	ss.uniforms["osgGLTF_textures.orm"] = 2
	ss.uniforms["osgGLTF_textures.emissive"] = 3
	ss.uniforms["emissiveFactor"] = osg.Vec3(1.0, 1.0, 1.0)
	ss.uniforms["scanlineFreq"] = 1000.0
	ss.uniforms["scanlineStrength"] = 0.5

	# --- Key light uniforms (live on composite_cam's stateSet) -------------- #
	# lightColor is raw linear HDR radiance, not a display color -- values around
	# 1.0 read as quite dim once BRDF/NdotL/tonemap all take their cut, which is why
	# direct lighting was barely visible in mode 0 next to full-strength IBL
	# reflections. 3x brighter (same warm hue) makes direct lighting actually read.
	light_dir_u = osg.Uniform("lightDir", KEY_LIGHT_DIR)
	light_color_u = osg.Uniform(
		"lightColor",
		osg.Vec3(3.0, 2.7, 2.1) if args.lights else osg.Vec3()
	)
	# Was hardcoded (0.005) directly in shadowFactor() -- a single FIXED bias is a
	# textbook-known-insufficient technique at grazing angles (the bias needed to
	# avoid false self-shadowing/"acne" scales with how grazing the angle between
	# the surface normal and the light is; a fixed value is only ever "enough" at
	# some angles). Exposed as a uniform so it can be tuned live via --repl instead
	# of guessing at a shader-source constant and restarting every time.
	shadow_bias_u = osg.Uniform("shadowBias", 0.005)
	# 0.7 preserves the old hardcoded mix(1.0, 0.3, ...) floor (see BUG.md item 2's
	# note on shadowFactor() being diluted by the unshadowed ambient term) --
	# floor = 1 - shadowStrength, so 0 = shadows have zero effect, 1 = fully black.
	shadow_strength_u = osg.Uniform("shadowStrength", 0.7)
	shadow_debug_tint_u = osg.Uniform("shadowDebugTint", False)

	# --- Frame-global uniforms (live on root.stateSet -- inherited by every camera
	# under it regardless of PRE_RENDER/POST_RENDER order; see the update_uniforms
	# comment below for why they're updated from shadow_cam's preDrawCallback, not
	# v.camera's) ------------------------------------------------------------- #
	shadow_matrix_u = osg.Uniform("shadowMatrix", osg.Matrixf.identity())
	main_view_u = osg.Uniform("mainViewMatrix", osg.Matrixf.identity())
	# Clip-to-world matrix for the composite pass's background fill (see
	# COMPOSITE_FRAGMENT_SHADER's background-sentinel branch) -- reconstructs a
	# world-space view ray per background pixel from just vUV, no geometry needed.
	inv_view_proj_u = osg.Uniform("invViewProj", osg.Matrixf.identity())
	znear_u = osg.Uniform("znear", 0.0)
	zfar_u = osg.Uniform("zfar", 0.0)
	proj_forward_u = osg.Uniform("projectionMatrix", osg.Matrixf.identity())
	visualize_mode_u = osg.Uniform("visualizeMode", 0)
	post_enabled_u = osg.Uniform("postEnabled", True)

	# --- Shadow map (verbatim from 09-ibl.py) -------------------------------- #
	shadow_tex = osg.Texture2D()
	shadow_tex.size = (SHADOW_SIZE, SHADOW_SIZE)
	shadow_tex.internalFormat = GL_DEPTH_COMPONENT24
	shadow_tex.sourceFormat = GL_DEPTH_COMPONENT
	shadow_tex.sourceType = GL_FLOAT
	shadow_tex.filter = osg.Texture.NEAREST
	shadow_tex.wrap = osg.Texture.CLAMP_TO_EDGE

	dummy_color = osg.Texture2D()
	dummy_color.size = (SHADOW_SIZE, SHADOW_SIZE)
	dummy_color.internalFormat = GL_RGB

	shadow_tex.dataVariance = osg.Object.DYNAMIC
	dummy_color.dataVariance = osg.Object.DYNAMIC

	SHADOW_MARGIN = 1.3
	# This is a directional light, so its rays must be parallel.  The old
	# perspective projection made it behave like a spotlight whose rays diverged
	# from shadow_light_pos, even though direct lighting used one constant direction
	# everywhere.  An orthographic box makes the lighting and shadow models agree.
	# A room receiver needs the directional-light projection to cover more than
	# the model's own casting bound. The model alone still supplies shadow-map
	# depth; this only keeps the floor/wall sample coordinates in range.
	shadow_extent = max(
		bound_radius * SHADOW_MARGIN,
		args.floor_size if args.floor else 0.0
	)
	shadow_distance = shadow_extent * 2.0
	shadow_light_pos = bound_center + KEY_LIGHT_DIR * shadow_distance

	light_view = osg.Matrix.lookAt(
		shadow_light_pos,
		bound_center,
		osg.Vec3(0, 1, 0)
	)

	shadow_near = max(0.01, shadow_distance - shadow_extent)
	shadow_far = shadow_distance + shadow_extent

	light_proj = osg.Matrix.ortho(
		-shadow_extent, shadow_extent,
		-shadow_extent, shadow_extent,
		shadow_near, shadow_far
	)

	shadow_cam = osg.Camera()
	shadow_cam.name = "ShadowCam"
	shadow_cam.renderOrder = (osg.Camera.PRE_RENDER, 0)
	shadow_cam.renderTargetImplementation = osg.Camera.FRAME_BUFFER_OBJECT
	shadow_cam.referenceFrame = osg.Transform.ABSOLUTE_RF
	shadow_cam.clearMask = GL_DEPTH_BUFFER_BIT | GL_COLOR_BUFFER_BIT
	shadow_cam.clearColor = osg.Vec4(1, 1, 1, 1)
	shadow_cam.viewport = osg.Viewport(0, 0, SHADOW_SIZE, SHADOW_SIZE)
	shadow_cam.attach(osg.Camera.DEPTH_BUFFER, shadow_tex)
	shadow_cam.attach(osg.Camera.COLOR_BUFFER, dummy_color)
	shadow_cam.viewMatrix = light_view
	shadow_cam.projectionMatrix = light_proj
	shadow_cam.children.append(model)
	# Disable frustum culling for this camera's own subgraph -- same fix
	# ~/dev/slughorn/ai/enterprise-hud3d.py uses on its real-geometry RTT passes
	# (ent_pass.cullingActive = False). Without it, OSG's automatic scene-bounding-
	# volume computation across root (now spanning several ABSOLUTE_RF fullscreen
	# quads in unrelated reference frames alongside real geometry) can produce a bad
	# bound for a nested camera's subgraph once cull caching settles in -- symptom is
	# "renders fine for one frame, then gets culled out."
	shadow_cam.cullingActive = False

	# --- Grid room (optional) -- replaces the old single floor quad. It is routed
	# --- through the G-buffer for correct depth against the model. ---------------- #
	if args.floor:
		grid_room, grid_panels = create_grid_room(
			bound_center, bound_radius, args.floor_z, args.floor_size
		)

	# --- G-buffer -------------------------------------------------------------- #
	gbuffer_cam, albedo_tex, normal_tex, material_tex, emissive_tex, position_tex, depth_tex = create_gbuffer_camera(
		W, H, msaa_samples=args.msaa
	)

	gbuffer_cam.children.append(model)

	if args.floor:
		gbuffer_cam.children.append(grid_room)

	# Same reasoning as shadow_cam.cullingActive above.
	gbuffer_cam.cullingActive = False

	# --- SSAO -------------------------------------------------------------------- #
	ssao_kernel_u = osg.Uniform(osg.Uniform.Type.FLOAT_VEC3, "samples", tuple(generate_ssao_kernel()))
	ssao_noise_tex = make_ssao_noise_texture()
	ssao_radius = max(0.05, bound_radius * 0.15)

	ssao_cam, ao_raw_tex = create_ssao_camera(
		depth_tex, normal_tex, ssao_noise_tex, position_tex, ssao_kernel_u, ssao_radius, w=W, h=H
	)
	ssao_blur_cam, ao_tex = create_ssao_blur_camera(ao_raw_tex, W, H)

	# --- Composite (PRE_RENDER, writes linear HDR) ------------------------------ #
	hdr_color_tex = osg.Texture2D()
	hdr_color_tex.size = (W, H)
	hdr_color_tex.internalFormat = GL_RGB16F
	hdr_color_tex.filter = (osg.Texture.LINEAR, osg.Texture.LINEAR)
	hdr_color_tex.dataVariance = osg.Object.DYNAMIC

	composite_cam = create_composite_camera(
		(albedo_tex, normal_tex, material_tex, emissive_tex, position_tex, depth_tex),
		shadow_tex,
		prefilter_tex,
		lut_tex,
		ao_tex,
		hdr_color_tex,
		W, H
	)

	cc_ss = composite_cam.stateSet
	cc_ss.uniforms.extend((
		light_dir_u,
		light_color_u,
		shadow_bias_u,
		shadow_strength_u,
		shadow_debug_tint_u,
		ibl_enabled_u,
		ibl_diffuse_intensity_u,
		ibl_specular_intensity_u,
		ibl_sh_u
	))
	cc_ss.uniforms["skyColor"] = osg.Vec3(0.04, 0.06, 0.12)
	cc_ss.uniforms["groundColor"] = osg.Vec3(0.015, 0.012, 0.010)

	# --- Bloom -------------------------------------------------------------------- #
	bloom_threshold_cam, bloom_blur_h_cam, bloom_blur_v_cam, bloom_blur_b_tex = create_bloom_cameras(hdr_color_tex, W, H)

	# --- Final LDR pass ------------------------------------------------------------ #
	final_cam = create_final_camera(hdr_color_tex, bloom_blur_b_tex, ao_tex, W, H)

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

	# Kept as direct references (rather than re-fetched via fc_ss.uniforms[...]
	# each frame) so the ImGui "Post FX" section below can read/write .value
	# directly, same pattern as shadow_strength_u/shadow_bias_u above.
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

	# --- Light gizmo (wireframe plane + direction arrow) ---------------------- #
	gizmo_cam = create_light_gizmo(bound_center, bound_radius, light_dir_u, light_color_u)

	root = osg.Group()
	root.children.extend((
		shadow_cam,
		lut_group,
		gbuffer_cam,
		ssao_cam,
		ssao_blur_cam,
		composite_cam,
		bloom_threshold_cam,
		bloom_blur_h_cam,
		bloom_blur_v_cam,
		final_cam,
		gizmo_cam,
	))

	root.stateSet.setMode(GL_TEXTURE_CUBE_MAP_SEAMLESS, osg.StateAttribute.ON)
	root.stateSet.uniforms.extend((
		znear_u,
		zfar_u,
		proj_forward_u,
		main_view_u,
		inv_view_proj_u,
		shadow_matrix_u,
		visualize_mode_u,
		post_enabled_u,
	))

	# --- Viewer ------------------------------------------------------------- #
	manip = osgGA.TrackballManipulator()

	v = osgViewer.Viewer(osg.ArgumentParser("11-sketchfab", ("11-sketchfab.py", "--samples", "8")))

	v.sceneData = root
	v.cameraManipulator = manip

	# View.setCameraManipulator() unconditionally does manip.setNode(getSceneData())
	# before computing its own initial home position (see osgViewer::View::
	# setCameraManipulator(), View.cpp) -- so setting manip.node BEFORE this point
	# (as this code used to) gets silently clobbered back to root right here, and the
	# orbiting gizmo/RTT cameras inflate the computed home distance. Retarget after
	# attaching instead, so only the actual asset defines the bounds -- and note that
	# setting .node alone does NOT reposition the camera, an explicit home() call is
	# required too (this is literally what pressing Spacebar does at runtime, via
	# StandardManipulator::handleKeyDown -- confirmed 2026-07-16 by reproducing the
	# "model invisible until Spacebar" bug live over the aipython REPL bridge).
	manip.node = model
	manip.home(0.0)

	# Combined per-frame uniform update: shadow matrix, inverse+forward projection,
	# znear/zfar, and mainViewMatrix (see COMPOSITE_FRAGMENT_SHADER's comment on why
	# osg_ViewMatrix can't be trusted on these cameras).
	#
	# Attached to shadow_cam.preDrawCallback, NOT v.camera.preDrawCallback -- verified
	# directly against OSG 3.6.5's RenderStage::draw() (osgUtil/RenderStage.cpp):
	# drawPreRenderStages() runs BEFORE this camera's own getPreDrawCallback(), which
	# runs before drawInner(), which runs before drawPostRenderStages(). That means
	# every PRE_RENDER camera nested under v.camera finishes drawing BEFORE
	# v.camera.preDrawCallback ever fires for that frame -- a PRE_RENDER consumer of
	# these uniforms would silently read a one-frame-stale value if this callback
	# stayed on v.camera (increment 1 never hit this because composite_cam was its
	# only consumer, and was POST_RENDER -- drawn after v.camera's own preDrawCallback).
	# shadow_cam is the numerically-first PRE_RENDER camera (order 0), so attaching it
	# there guarantees this fires before every other PRE_RENDER stage this frame.
	def update_uniforms(ri):
		cam_view = v.camera.viewMatrix
		pm = v.camera.projectionMatrix

		# znear/zfar are a pure DISPLAY range for mode 3's depth visualization now
		# (see COMPOSITE_FRAGMENT_SHADER's mode-3 comment) -- not used to reconstruct
		# or un-project anything, so they don't need to match any camera's actual
		# clip planes. bound_radius-derived constants instead of pm.getPerspective():
		# v.camera never directly culls the model (it sits two Camera levels down,
		# inside gbuffer_cam), so OSG's own near/far auto-tightening on v.camera
		# itself doesn't track the model's actual scale the way gbuffer_cam's own
		# (separately computed) near/far does -- verified against OSG 3.6.5's
		# CullVisitor::apply(Camera&)/popProjectionMatrix() (osgUtil/CullVisitor.cpp):
		# each Camera clamps a private, per-camera projection copy on its OWN cull,
		# never writing the result back onto the Camera object itself, so
		# v.camera.projectionMatrix read from Python is always whatever fixed matrix
		# was set at startup -- unrelated to bound_radius. This was previously
		# invisible because mode 3 also read gDepth (written by gbuffer_cam) through
		# that same wrong znear/zfar; switching mode 3 to gPosition (view-matrix-only,
		# so immune to the mismatch) exposed that znear/zfar itself was never
		# meaningful, rather than just mismatched between two cameras.
		znear_u.value = max(bound_radius * 0.01, 1e-4)
		zfar_u.value = bound_radius * 20.0
		proj_forward_u.value = osg.Matrixf(pm)
		main_view_u.value = osg.Matrixf(cam_view)
		inv_view_proj_u.value = osg.Matrixf(osg.Matrix.inverse(cam_view * pm))

		# Shadow camera tracks the LIVE lightDir uniform every frame now, instead of
		# the KEY_LIGHT_DIR constant frozen at startup -- previously, moving the
		# light interactively (REPL or x/y/z keys) changed mode 5 (direct lighting)
		# immediately but had zero effect on mode 8 (shadowFactor), since the actual
		# shadow-casting camera never knew the light had moved. Only the VIEW
		# direction depends on lightDir; near/far/FOV (light_proj) depend only on
		# bound_radius, so that stays fixed. Setting shadow_cam.viewMatrix here
		# (inside its own preDrawCallback, i.e. during THIS frame's draw phase)
		# takes effect for next frame's cull, not this one -- a one-frame lag,
		# imperceptible once the light stops moving.
		d = light_dir_u.value
		light_dir_now = d.normalized() if d.length() > 1e-5 else KEY_LIGHT_DIR
		shadow_light_pos_now = bound_center + light_dir_now * shadow_distance
		current_light_view = osg.Matrix.lookAt(shadow_light_pos_now, bound_center, osg.Vec3(0, 1, 0))
		shadow_cam.viewMatrix = current_light_view

		# OSG row-vector convention: v' = v * M applies matrices left-to-right, so
		# "eye -> world -> light-eye -> light-clip" composes in that literal
		# reading order. Verified 2026-07-11 with a pure Python/OSG-space
		# diagnostic (transforming bound_center through this exact chain and
		# comparing against a camera-independent ground truth computed straight
		# from light_view/light_proj) -- this order cancels cam_view exactly
		# regardless of zoom/rotation; a reversed order (chasing a GLSL
		# column-vector argument that doesn't apply to CPU-side composition)
		# did not.
		shadow_mat = osg.Matrix.inverse(cam_view) * current_light_view * light_proj
		shadow_matrix_u.value = osg.Matrixf(shadow_mat)

	shadow_cam.preDrawCallback = update_uniforms
	light_orbit_handler = LightOrbit(light_dir_u, bound_radius)

	# --- ImGui panel: all interactive controls live here now -- no keyboard ---
	# --- shortcuts (osgDebug.imgui.Widget -- see osgdebug's TODO.md's "Knobs, ---
	# --- not frameworks" section). ------------------------------------------ #
	if args.gui:
		# gizmo_cam is the final POST_RENDER camera (it follows final_cam), so it
		# must be the explicit draw_camera: Widget defaults to v.camera/
		# slave-0, whose PostDrawCallback fires BEFORE final_cam's later fullscreen
		# composite and the subsequent gizmo draw -- ImGui would render then be
		# overwritten,
		# while its mouse-capture bookkeeping stayed live (an invisible rectangle
		# eating mouse input). See osgDebug.hpp's Widget constructor comment.
		# Pinned to the left edge -- see osgDebug.hpp's Dock enum comment: the
		# system imgui package isn't built from the docking branch, so this is a
		# fixed sidebar (no drag-to-dock like osgEarth's ImGuiEventHandler), just
		# enough to keep the panel out of the way of the model.
		#
		# TODO: Convert this to kwargs!
		gui_opts = osgDebug.imgui.Options()
		gui_opts.dock = osgDebug.imgui.Dock.LEFT
		gui_opts.dock_width = 320.0

		gui = osgDebug.imgui.Widget(v, gizmo_cam, gui_opts)
		closed_section = osgDebug.imgui.SectionOptions(default_open=False)

		def draw_visualize_mode(ri):
			mode_labels = [
				"0: Composite", "1: Albedo", "2: Normal", "3: Depth", "4: Material",
				"5: Direct", "6: IBL", "7: Emissive", "8: Shadow", "9: AO"
			]

			changed, value = osgDebug.imgui.radio_group(
				int(visualize_mode_u.value), mode_labels, False
			)

			if changed: visualize_mode_u.value = value

		gui.addSection("Visualize Mode", draw_visualize_mode)

		def draw_ibl_knobs(ri):
			changed, value = osgDebug.imgui.slider_float_nudge(
				"IBL Diffuse", ibl_diffuse_intensity_u.value, 0.0, 2.0
			)

			if changed: ibl_diffuse_intensity_u.value = value

			changed, value = osgDebug.imgui.slider_float_nudge(
				"IBL Specular", ibl_specular_intensity_u.value, 0.0, 2.0
			)

			if changed: ibl_specular_intensity_u.value = value

		gui.addSection("IBL", draw_ibl_knobs, closed_section)

		def draw_exposure_knobs(ri):
			# "##slider" keeps the visible label as "Exposure" but gives the widget an
			# ImGui ID distinct from the "Exposure" CollapsingHeader above it -- a plain
			# (non-expand) section's header isn't wrapped in its own PushID, so a control
			# reusing the section's exact name collides with the header's own ID and the
			# two widgets end up fighting over the same click/drag state. Every other
			# section avoids this by naming its controls differently from the header
			# (e.g. "Shadow" header / "Shadow Strength" slider); this is the only one
			# where they matched.
			changed, value = osgDebug.imgui.slider_float(
				"Exposure##slider", exposure_u.value, -8.0, 8.0, "%.2f EV"
			)

			if changed: exposure_u.value = value

		gui.addSection("Exposure", draw_exposure_knobs, closed_section)

		def draw_tonemap_knobs(ri):
			mode_labels = ["0: PBR Neutral", "1: ACES", "2: Reinhard", "3: None (clamped)"]

			changed, value = osgDebug.imgui.radio_group(
				int(tonemap_mode_u.value), mode_labels, False
			)

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
				changed, reflective = osgDebug.imgui.checkbox(
					"Reflective metal", room_material["reflective"]
				)

				if changed:
					room_material["reflective"] = reflective
					set_room_material(reflective)

			gui.addSection("Grid Room", draw_grid_room_knobs, closed_section)

		def draw_light_position_knobs(ri):
			h = light_orbit_handler

			changed, value = osgDebug.imgui.slider_float(
				"Light Azimuth", math.degrees(h.azimuth), -180.0, 180.0, "%.1f deg"
			)

			if changed:
				h.azimuth = math.radians(value)
				h._sync()

			changed, value = osgDebug.imgui.slider_float(
				"Light Orbit Radius", h.orbit_radius, h.min_radius, bound_radius * 3.0
			)

			if changed:
				h.orbit_radius = value
				h._sync()

			changed, value = osgDebug.imgui.slider_float(
				"Light Height", h.height, -bound_radius * 3.0, bound_radius * 3.0
			)

			if changed:
				h.height = value
				h._sync()

		gui.addSection("Light Position", draw_light_position_knobs, closed_section)

		def draw_shadow_knobs(ri):
			changed, value = osgDebug.imgui.slider_float(
				"Shadow Strength", shadow_strength_u.value, 0.0, 1.0
			)

			if changed: shadow_strength_u.value = value

			changed, value = osgDebug.imgui.slider_float(
				"Shadow Bias", shadow_bias_u.value, 0.0, 0.02, "%.4f"
			)

			if changed: shadow_bias_u.value = value

			# Tints how much a pixel's direct term got darkened by the shadow map --
			# lets shadowStrength/bias be tuned against the ACTUAL composite (mode 0)
			# rather than mode 8 alone, since ambient/emissive riding on top of Lo
			# otherwise hides how strong the shadow's contribution really is.
			changed, value = osgDebug.imgui.checkbox(
				"Debug Tint (red)", bool(shadow_debug_tint_u.value)
			)

			if changed: shadow_debug_tint_u.value = value

		gui.addSection("Shadow", draw_shadow_knobs, closed_section)

		def draw_post_fx_knobs(ri):
			# Sketchfab's own "No Post-Processing" toggle -- gates CA/sharpen/vignette/
			# grain/color-balance in FINAL_FRAGMENT_SHADER (exposure and tonemap stay
			# on regardless; see FINAL_FRAGMENT_SHADER's postEnabled comment).
			changed, value = osgDebug.imgui.checkbox(
				"Post Processing", bool(post_enabled_u.value)
			)

			if changed: post_enabled_u.value = value

			changed, value = osgDebug.imgui.slider_float(
				"Bloom Strength", bloom_strength_u.value, 0.0, 2.0
			)

			if changed: bloom_strength_u.value = value

			changed, value = osgDebug.imgui.slider_float(
				"Chromatic Aberration", ca_strength_u.value, 0.0, 0.02, "%.4f"
			)

			if changed: ca_strength_u.value = value

			changed, value = osgDebug.imgui.slider_float(
				"Sharpen", sharpen_strength_u.value, -0.5, 1.5
			)

			if changed: sharpen_strength_u.value = value

			changed, value = osgDebug.imgui.slider_float(
				"Vignette", vignette_strength_u.value, 0.0, 1.0
			)

			if changed: vignette_strength_u.value = value

			changed, value = osgDebug.imgui.slider_float(
				"Grain", grain_strength_u.value, 0.0, 0.2, "%.4f"
			)

			if changed: grain_strength_u.value = value

			changed, value = osgDebug.imgui.slider_float(
				"Grain Size", grain_size_u.value, 1.0, 8.0, "%.1f px"
			)

			if changed: grain_size_u.value = value

			changed, value = osgDebug.imgui.checkbox(
				"Grain Animated", bool(grain_animated_u.value)
			)

			if changed: grain_animated_u.value = value

			changed, value = osgDebug.imgui.slider_float(
				"Grain AO Boost", grain_ao_boost_u.value, 0.0, 1.0
			)

			if changed: grain_ao_boost_u.value = value

			changed, value = osgDebug.imgui.slider_float(
				"Color Lift", color_lift_u.value, -0.5, 0.5, "%.3f"
			)

			if changed: color_lift_u.value = value

			changed, value = osgDebug.imgui.slider_float(
				"Color Gamma", color_gamma_u.value, 0.1, 3.0
			)

			if changed: color_gamma_u.value = value

			changed, value = osgDebug.imgui.slider_float(
				"Color Gain", color_gain_u.value, 0.0, 3.0
			)

			if changed: color_gain_u.value = value

		gui.addSection("Post FX", draw_post_fx_knobs, closed_section)

		# Per-drawable GPU timestamp timings.  Keep this expandable section last so
		# the scene controls above retain their natural height in the docked panel.
		gui.addStatsSection(v)
		gui.addProfilerSection(v, root, default_open=False)

	def apply_pending_sh(queue):
		try:
			while True:
				sh = queue.get_nowait()

				for i, rgb in enumerate(sh):
					ibl_sh_u[i] = osg.Vec3(*rgb)

		except asyncio.QueueEmpty:
			pass

	# --- --repl: hand the render loop to pyosg_repl.py's IPython/asyncio bridge -- #
	# Lets uniforms/lights/SSAO params be edited live from a REPL while the window
	# keeps rendering, instead of 11-bug.py/12-bug.py's pattern of pausing before
	# any v.frame() call for manual single-step debugging. This used to hand-roll
	# the IPython.embed()+enable_gui("asyncio") dance directly in this file (see
	# git history if that's ever needed again) -- pyosg_repl.py now owns that
	# mechanism, proven first here, generalized so 09-ibl-animation.py and
	# pyosg-taa.py share the identical fix.
	if args.repl:
		# pyosg_repl.py is one directory above this example. Keep that proof module
		# importable when this file is launched directly, where sys.path[0] is the
		# pyosg-lighting directory rather than examples/.
		examples_dir = pathlib.Path(__file__).resolve().parent.parent

		if str(examples_dir) not in sys.path:
			sys.path.insert(0, str(examples_dir))

		from IPython.core.async_helpers import get_asyncio_loop
		from pyosg_repl import repl

		loop = get_asyncio_loop()
		queue = asyncio.Queue()
		tasks = []

		if args.hdr:
			tasks.append(loop.create_task(task_compute_sh(queue, args.hdr)))

		try:
			# globals() deliberately exposes this example's live viewer, scene graph,
			# G-buffer/post-processing cameras, uniforms, and helper functions at the
			# prompt.
			repl(v, globals(), frame_callback=lambda: apply_pending_sh(queue))

		finally:
			for task in tasks:
				task.cancel()

			loop.run_until_complete(asyncio.gather(*tasks, return_exceptions=True))

	else:
		# --- Async viewer loop (verbatim from 09-ibl.py) ------------------------ #
		loop = asyncio.new_event_loop()
		queue = asyncio.Queue()
		asyncio.set_event_loop(loop)

		tasks = []

		if args.hdr:
			tasks.append(loop.create_task(task_compute_sh(queue, args.hdr)))

		try:
			while not v.done:
				v.frame()

				loop.run_until_complete(asyncio.sleep(0))
				apply_pending_sh(queue)

		finally:
			for task in tasks:
				task.cancel()

			try:
				for task in tasks:
					loop.run_until_complete(task)

			except asyncio.CancelledError:
				pass

			loop.run_until_complete(asyncio.sleep(0))
			loop.stop()
			loop.close()
