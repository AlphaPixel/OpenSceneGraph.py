#!/usr/bin/env python3
#vimrun! python3 ../examples/pyosg-lighting/09-ibl.py --no-lights --ktx2 papermill --hdr papermill

# Step 9 - Image-Based Lighting (IBL) - static KTX2 path
#
# Loads a pre-baked GGX-prefiltered cubemap directly from a .ktx2 file via the
# osgdb_ktx2 plugin (see osgGLTF/src/ReaderWriterKTX2.cpp). A pure-Python
# dynamic FBO re-bake pipeline (live GPU prefilter, no static .ktx2) was
# attempted first and abandoned after getting stuck on a specular-loss-on-
# rebake bug - see examples/pyosg-lighting/09-ibl-dynamicfbo-ATTEMPT.py for
# that reference code, and ai/context-todo-lighting-class.md for the history.
# GPU baking was subsequently proven to work in C++ instead (osgGLTF's
# IBLBaker.cpp / osgGLTF::bakeSpecularIBL) - wiring that back into a live
# Python demo is Step 11 ("dynamic probes"), not yet started.
#
# Pipeline:
#
# prefilter_tex - loaded from --ktx2 (TextureCubeMap, mip0...N, all 6 faces)
# brdf_lut - baked once at startup via a single PRE_RENDER camera
# SH diffuse - computed asynchronously from --hdr if provided; zero otherwise
#
# Texture units (same as step 8 + 9):
# 0 baseColor 1 normal 2 ORM 3 emissive 4 shadow 5 envMap 6 brdfLUT

import sys
import os
import math
import argparse
import asyncio
import pathlib

os.environ.update({
	"OSG_WINDOW": "50 50 800 600",
	"OSG_THREADING": "SingleThreaded",
	"OSG_GL_CONTEXT_PROFILE_MASK": "1",
	"OSG_GL_VERSION": "4.6",
	"OSG_GL_CONTEXT_VERSION": "4.6",
})

import numpy as np
import cv2

from OpenSceneGraph import *
from OpenSceneGraph.GL import *

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #

SHADOW_SIZE = 1024

# Light rig, expressed as directions from the model's bounding-sphere center plus a distance/radius
# tuned for a ~1.7-unit-radius object (Cube/AnimatedCube's actual scale - the objects this rig was
# originally hand-tuned against). At load time these get scaled by max(model_radius /
# REFERENCE_RADIUS, 1.0) - never shrunk below this baseline (so BoomBox/Avocado/Cube etc. render
# identically to before), only grown for anything bigger. Without this, direct lighting collapses
# to near-zero on larger meshes (e.g. Lantern, whose ~15-unit bounding radius put every surface
# point dozens of light-radii away from these originally-fixed positions) - see
# ai/context-todo-utils.md in osgGLTF and ext/glTF-Sample-Models.md for the investigation.
REFERENCE_RADIUS = 1.7

KEY_LIGHT_DIR = osg.Vec3( 0.1, 0.1, 1.0).normalized()
FILL_LIGHT_DIR_0 = osg.Vec3(-0.8, 0.3, 0.5).normalized()
FILL_LIGHT_DIR_1 = osg.Vec3( 0.0, -0.6, 0.2).normalized()

KEY_LIGHT_DIST = osg.Vec3( 0.1, 0.1, 1.0).length()
FILL_LIGHT_DIST_0 = osg.Vec3(-0.8, 0.3, 0.5).length()
FILL_LIGHT_DIST_1 = osg.Vec3( 0.0, -0.6, 0.2).length()

LIGHT_RADII = (2.5, 1.5, 1.2)

# --------------------------------------------------------------------------- #
# SH projection
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
# Shaders
# --------------------------------------------------------------------------- #

VERTEX_SHADER = """
#version 460 core

in vec4 osg_Vertex;
in vec3 osg_Normal;
in vec4 osg_Tangent;
in vec2 osg_MultiTexCoord0;

uniform mat4 osg_ModelViewProjectionMatrix;
uniform mat4 osg_ModelViewMatrix;
uniform mat3 osg_NormalMatrix;

out vec3 vNGeom;
out vec3 vPosition;
out vec4 vTangent;
out vec2 vUV;

void main() {
	vec4 eyePos = osg_ModelViewMatrix * osg_Vertex;
	vPosition = eyePos.xyz;
	vUV = osg_MultiTexCoord0;
	vNGeom = normalize(osg_NormalMatrix * osg_Normal);
	vTangent = vec4(osg_NormalMatrix * osg_Tangent.xyz, osg_Tangent.w);

	gl_Position = osg_ModelViewProjectionMatrix * osg_Vertex;
}
"""

FRAGMENT_SHADER = """
#version 460 core

#define NUM_LIGHTS 3
const float PI = 3.14159265359;

in vec3 vNGeom;
in vec3 vPosition;
in vec4 vTangent;
in vec2 vUV;

uniform sampler2D shadowMap; // unit 4
uniform samplerCube envMap; // unit 5: prefiltered cubemap
uniform sampler2D brdfLUT; // unit 6: split-sum BRDF LUT
uniform float shadowBias;
uniform float shadowStrength; // 0 = shadows have no effect, 1 = fully black

uniform vec3 emissiveFactor;

// ---- osgGLTF material inputs ------------------------------------------------ //
// Everything below comes from osgGLTF's ReaderWriterGLTF (applyMaterial() in GLTFReader.hpp),
// grouped here as the two osgx_gltf_* declarations rather than scattered loose uniforms. Scalar
// material data arrives in one buffer; textures remain a parallel struct-of-samplers uniform.
// Layout must match the data built in GLTFReader.hpp exactly.
layout(std430, binding = 0) readonly buffer osgx_gltf_Material {
	vec4 baseColorFactor;
	float roughnessFactor;
	float metallicFactor;
	float hasBaseColorMap;
	float hasMetallicRoughnessMap;
	float hasOcclusion;
	float hasNormalMap;
} osgx_gltf_material;

struct GLTFTextures {
	sampler2D baseColor; // unit 0
	sampler2D normal; // unit 1
	sampler2D orm; // unit 2
	sampler2D emissive; // unit 3
};

uniform GLTFTextures osgx_gltf_textures;

// Core glTF alpha coverage, exported per-material by osgGLTF.  MASK keeps
// normal opaque rendering and discards transparent texels; BLEND writes this
// alpha for osgGLTF's source-over transparent StateSet.
uniform float osgx_gltf_alphaMode;
uniform float osgx_gltf_alphaCutoff;

uniform float scanlineFreq;
uniform float scanlineStrength;
uniform float osg_SimulationTime;

uniform vec3 skyColor;
uniform vec3 groundColor;

uniform mat4 osg_ViewMatrix;

uniform vec3 lightPos[NUM_LIGHTS];
uniform vec3 lightColor[NUM_LIGHTS];
uniform float lightRadius[NUM_LIGHTS];
uniform bool animatedLights;

uniform mat4 shadowMatrix;

uniform int iblEnabled;
uniform vec3 iblSH[9];
uniform float iblIntensity;

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
		iblSH[0] * 0.282095
		+ iblSH[1] * (0.488603 * N.y)
		+ iblSH[2] * (0.488603 * N.z)
		+ iblSH[3] * (0.488603 * N.x)
		+ iblSH[4] * (1.092548 * N.x * N.y)
		+ iblSH[5] * (1.092548 * N.y * N.z)
		+ iblSH[6] * (0.315392 * (3.0 * N.z * N.z - 1.0))
		+ iblSH[7] * (1.092548 * N.x * N.z)
		+ iblSH[8] * (0.546274 * (N.x * N.x - N.y * N.y)),
		vec3(0.0)
	);
}

// ---- Shading normal --------------------------------------------------------- //
// TBN reconstructed per-pixel from screen-space derivatives of position/UV
// (Christian Schuler's "normal mapping without precomputed tangents" --
// http://www.thetenthplanet.de/archives/1180) rather than a vertex TANGENT
// attribute. Matches VulkanSceneGraph's standard_pbr.frag exactly - glTF's
// TANGENT accessor is optional and frequently absent (DamagedHelmet,
// MetalRoughSpheres, Fox in glTF-Sample-Models all ship without one), and
// osg_Tangent reading OpenGL's default (0,0,0,1) for an unbound attribute
// produced NaN through normalize((0,0,0)) - this sidesteps that failure
// mode entirely rather than requiring GLTFReader.hpp to synthesize tangents.
vec3 getShadingNormal() {
	vec3 Nb = normalize(vNGeom);
	if (!bool(osgx_gltf_material.hasNormalMap)) return Nb;

	vec3 tangentNormal = texture(osgx_gltf_textures.normal, vUV).rgb * 2.0 - 1.0;

	vec3 T, B;
	if (dot(vTangent.xyz, vTangent.xyz) > 1e-10) {
		T = normalize(vTangent.xyz);
		B = normalize(cross(Nb, T)) * vTangent.w;
	} else {
		vec3 q1 = dFdx(vPosition);
		vec3 q2 = dFdy(vPosition);
		vec2 st1 = dFdx(vUV);
		vec2 st2 = dFdy(vUV);
		T = normalize(q1 * st2.t - q2 * st1.t);
		B = -normalize(cross(Nb, T));
	}
	mat3 TBN = mat3(T, B, Nb);

	return normalize(TBN * tangentNormal);
}

// ---- Material --------------------------------------------------------------- //
// Bundles the per-fragment material values fed into both the direct-light loop
// and the IBL ambient term, VSG-standard_pbr.frag-style (see PBRInfo in
// ~/dev/vsgExamples/data/shaders/standard_pbr.frag) - just scoped to what our
// single fixed GGX BRDF needs, not the full pluggable-diffuse-model struct VSG
// uses to switch between Lambert/OrenNayar/Gotanda/Burley/Disney.
struct Material {
	vec3 albedo;
	float ao;
	float roughness;
	float metallic;
	vec3 F0;
};

Material getMaterial(vec3 N) {
	Material mat;

	// Same "unconditional texture() has no fallback" gap as occlusion below,
	// but for baseColor - a factor-only material (no baseColorTexture, e.g.
	// most of the glTF-Sample-Models *Test conformance set) would otherwise
	// read an unbound unit 0 as black instead of its authored flat color.
	mat.albedo = bool(osgx_gltf_material.hasBaseColorMap)
		? texture(osgx_gltf_textures.baseColor, vUV).rgb
		: osgx_gltf_material.baseColorFactor.rgb;
	// The R channel of a glTF metallicRoughnessTexture is spec-unused unless
	// the material also declares an occlusionTexture pointing at the same
	// (or a merged) image - hasOcclusion reflects that, set by
	// GLTFReader.hpp per-material. Trusting R unconditionally silently
	// zeroes the entire ambient/IBL term below on any material that never
	// authored real AO data.
	mat.ao = bool(osgx_gltf_material.hasOcclusion) ? texture(osgx_gltf_textures.orm, vUV).r : 1.0;
	// Same story for roughness/metallic: a material can be entirely
	// factor-driven with no metallicRoughnessTexture at all (e.g. Fox:
	// roughnessFactor=0.58, no texture) - multiplying an unbound unit 2's
	// zero read by the factor silently discarded it, forcing roughness/
	// metallic to 0 (mirror-smooth) regardless of what was authored.
	mat.roughness = bool(osgx_gltf_material.hasMetallicRoughnessMap)
		? texture(osgx_gltf_textures.orm, vUV).g * osgx_gltf_material.roughnessFactor
		: osgx_gltf_material.roughnessFactor;
	mat.metallic = bool(osgx_gltf_material.hasMetallicRoughnessMap)
		? texture(osgx_gltf_textures.orm, vUV).b * osgx_gltf_material.metallicFactor
		: osgx_gltf_material.metallicFactor;

	// Specular AA: clamp roughness by how fast the shading normal (including
	// normal map) rotates per pixel. Using N (post-normal-map) rather than
	// vNGeom catches the bevel/crease edges baked into the normal map, which
	// is where the visible over-sharp reflections come from.
	float normalDelta = max(
		max(abs(dFdx(N.x)), abs(dFdx(N.y))),
		max(abs(dFdy(N.x)), abs(dFdy(N.y)))
	);
	mat.roughness = max(mat.roughness, normalDelta);

	mat.F0 = mix(vec3(0.04), mat.albedo, mat.metallic);

	return mat;
}

// ---- Direct lighting -------------------------------------------------------- //

// Light i orbits the origin and pulses in intensity; only used when the animatedLights
// uniform is set (see --animated-lights). Replaces lightPos[i]/a flat 1.0 pulse.
void getAnimatedLight(int i, float t, out vec3 lp, out float pulse) {
	if (i == 0) {
		lp = vec3(cos(t*0.8)*1.0, sin(t*0.8)*1.0, 0.8);
		pulse = 0.8 + 0.2*sin(t*1.3);
	} else if (i == 1) {
		lp = vec3(cos(t*0.5+6.28318/3.0)*0.9, sin(t*0.5+6.28318/3.0)*0.9, 0.3);
		pulse = 0.8 + 0.2*sin(t*0.9+1.0);
	} else {
		lp = vec3(cos(t*0.3+6.28318/1.5)*0.7, sin(t*0.3+6.28318/1.5)*0.7,-0.2);
		pulse = 0.8 + 0.2*sin(t*0.6+2.1);
	}
}

vec3 evaluateDirectLighting(Material mat, vec3 N, vec3 V, float NdotV) {
	vec3 Lo = vec3(0.0);
	float t = osg_SimulationTime;

	for (int i = 0; i < NUM_LIGHTS; i++) {
		vec3 lp = lightPos[i];
		float pulse = 1.0;

		if (animatedLights) getAnimatedLight(i, t, lp, pulse);

		vec3 lEye = (osg_ViewMatrix * vec4(lp, 1.0)).xyz;
		vec3 lVec = lEye - vPosition;
		float dist = length(lVec);
		vec3 L = lVec / dist;
		float r = lightRadius[i];
		float atten = 1.0 / (1.0 + (dist * dist) / (r * r));
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
		float shad = (i == 0) ? shadowFactor(vPosition) : 1.0;

		Lo += (diffuse + specular) * lightColor[i] * pulse * NdotL * atten * shad;
	}

	return Lo;
}

// ---- IBL ambient ------------------------------------------------------------ //

vec3 evaluateIBL(Material mat, vec3 N, vec3 V, float NdotV) {
	if (iblEnabled == 0) {
		vec3 worldUp = normalize(mat3(osg_ViewMatrix) * vec3(0.0, 0.0, 1.0));
		float hemi = dot(N, worldUp) * 0.5 + 0.5;
		return mix(groundColor, skyColor, hemi) * mat.albedo * mat.ao;
	}

	mat3 invView = transpose(mat3(osg_ViewMatrix));
	vec3 N_world = invView * N;
	vec3 V_world = invView * V;
	vec3 R_world = reflect(-V_world, N_world);

	vec3 F_ibl = F_Schlick_roughness(NdotV, mat.F0, mat.roughness);
	vec3 kD_ibl = (1.0 - F_ibl) * (1.0 - mat.metallic);
	vec3 ibl_diff = sh_irradiance(N_world) * mat.albedo * kD_ibl * iblIntensity;

	float maxMip = float(textureQueryLevels(envMap) - 1);
	float lod = mat.roughness * maxMip;
	vec3 r_gl = vec3(R_world.x, R_world.z, -R_world.y);
	vec3 prefilt = textureLod(envMap, r_gl, lod).rgb;
	vec2 brdf = texture(brdfLUT, vec2(NdotV, mat.roughness)).rg;
	vec3 ibl_spec = prefilt * (mat.F0 * brdf.x + brdf.y);

	return (ibl_diff + ibl_spec) * mat.ao;
}

// ---- Emissive ---------------------------------------------------------------- //

vec3 getEmissive() {
	vec3 emissive = texture(osgx_gltf_textures.emissive, vUV).rgb * emissiveFactor;
	float scanline = 0.5 + 0.5 * sin(vUV.y * scanlineFreq - osg_SimulationTime * 10.0);
	return emissive * mix(1.0, scanline, scanlineStrength);
}

float getAlphaCoverage() {
	float alpha = bool(osgx_gltf_material.hasBaseColorMap)
		? texture(osgx_gltf_textures.baseColor, vUV).a
		: 1.0;
	return alpha * osgx_gltf_material.baseColorFactor.a;
}

// ---- Tonemap ------------------------------------------------------------------ //
// Khronos PBR Neutral tonemapping (matches Babylon.js "PBR Neutral" preset).
// Hue-preserving, no ACES orange shift at high luminance.
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

// ---- Main ----------------------------------------------------------------- //

void main() {
	float alpha = getAlphaCoverage();
	if (osgx_gltf_alphaMode == 1.0 && alpha < osgx_gltf_alphaCutoff) discard;

	vec3 N = getShadingNormal();
	vec3 V = normalize(-vPosition);
	Material mat = getMaterial(N);
	float NdotV = max(dot(N, V), 0.0);

	vec3 Lo = evaluateDirectLighting(mat, N, V, NdotV);
	vec3 ambient = evaluateIBL(mat, N, V, NdotV);
	vec3 emissive = getEmissive();

	vec3 color = ambient + Lo + emissive;
	color = tonemapPBRNeutral(color);
	color = pow(color, vec3(1.0 / 2.2));

	fragColor = vec4(color, alpha);
}
"""

FLOOR_VERTEX = """
#version 460 core

in vec4 osg_Vertex;
in vec3 osg_Normal;

uniform mat4 osg_ModelViewProjectionMatrix;
uniform mat4 osg_ModelViewMatrix;
uniform mat3 osg_NormalMatrix;

out vec3 vPosition;
out vec3 vNormal;

void main() {
	vec4 eyePos = osg_ModelViewMatrix * osg_Vertex;
	vPosition = eyePos.xyz;
	vNormal = normalize(osg_NormalMatrix * osg_Normal);
	gl_Position = osg_ModelViewProjectionMatrix * osg_Vertex;
}
"""

FLOOR_FRAGMENT = """
#version 460 core

#define NUM_LIGHTS 3

in vec3 vPosition;
in vec3 vNormal;

uniform vec3 lightPos[NUM_LIGHTS];
uniform vec3 lightColor[NUM_LIGHTS];
uniform float lightRadius[NUM_LIGHTS];
uniform bool animatedLights;
uniform mat4 shadowMatrix;
uniform sampler2D shadowMap;
uniform float shadowBias;
uniform float shadowStrength;
uniform mat4 osg_ViewMatrix;
uniform float osg_SimulationTime;

out vec4 fragColor;

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

// Light i orbits the origin; only used when the animatedLights uniform is set (see
// --animated-lights). Replaces lightPos[i]. The floor never modulates by pulse, so it's
// computed here for symmetry with the PBR fragment shader's getAnimatedLight() but discarded.
void getAnimatedLight(int i, float t, out vec3 lp, out float pulse) {
	if (i == 0) {
		lp = vec3(cos(t*0.8)*1.0, sin(t*0.8)*1.0, 0.8);
		pulse = 0.8 + 0.2*sin(t*1.3);
	} else if (i == 1) {
		lp = vec3(cos(t*0.5+6.28318/3.0)*0.9, sin(t*0.5+6.28318/3.0)*0.9, 0.3);
		pulse = 0.8 + 0.2*sin(t*0.9+1.0);
	} else {
		lp = vec3(cos(t*0.3+6.28318/1.5)*0.7, sin(t*0.3+6.28318/1.5)*0.7,-0.2);
		pulse = 0.8 + 0.2*sin(t*0.6+2.1);
	}
}

void main() {
	vec3 N = normalize(vNormal);
	vec3 albedo = vec3(0.82, 0.76, 0.62);
	vec3 Lo = vec3(0.0);
	float t = osg_SimulationTime;

	for (int i = 0; i < NUM_LIGHTS; i++) {
		vec3 lp = lightPos[i];
		float pulse = 1.0;

		if (animatedLights) getAnimatedLight(i, t, lp, pulse);

		vec3 lEye = (osg_ViewMatrix * vec4(lp, 1.0)).xyz;
		vec3 lVec = lEye - vPosition;
		float dist = length(lVec);
		vec3 L = lVec / dist;
		float r = lightRadius[i];
		float atten = 1.0 / (1.0 + (dist * dist) / (r * r));
		float NdotL = max(dot(N, L), 0.0);
		float shad = (i == 0) ? shadowFactor(vPosition) : 1.0;
		Lo += albedo * lightColor[i] * NdotL * atten * shad;
	}
	fragColor = vec4(vec3(0.06) * albedo + Lo, 1.0);
}
"""

# Fullscreen NDC quad vertex shader - shared between BRDF LUT bake and any
# future screen-space passes.
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

# ---- One-shot bake helper --------------------------------------------------- #
# Disables a PRE_RENDER bake group's nodeMask after it has rendered exactly one
# frame (so a startup-only bake camera doesn't keep re-rendering every frame).
# Call bake() to re-enable it for exactly one more frame (e.g. to re-bake after
# swapping the bake's source data).
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
	lut_tex = osg.Texture2D(
		size=(lut_size, lut_size),
		internalFormat=GL_RGBA,
		filter=(osg.Texture.LINEAR, osg.Texture.LINEAR),
		wrap=osg.Texture.CLAMP_TO_EDGE,
	)

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

	cam = osg.Camera(
		name="BRDFLutBake",
		renderOrder=osg.Camera.PRE_RENDER,
		renderTargetImplementation=osg.Camera.FRAME_BUFFER_OBJECT,
		referenceFrame=osg.Transform.ABSOLUTE_RF,
		clearMask=GL_COLOR_BUFFER_BIT,
		viewport=osg.Viewport(0, 0, lut_size, lut_size),
		projectionMatrix=osg.Matrix.identity(),
		viewMatrix=osg.Matrix.identity(),
	)
	cam.attach(osg.Camera.COLOR_BUFFER0, lut_tex, 0, 0, False)
	cam.stateSet.attributes.append(bake_p)
	cam.children.append(quad_geode)
	bake_group.children.append(cam)

	return lut_tex, bake_group

# If the passed-in file exists, simply return it; if not, try and find it inside example data dir.
# For convenience, we'll try all the extensions we support, as well as assuming cetain directory
# structures.
def data_dir_file(f, suffix=None):
	if os.path.exists(f):
		return f

	# How do make this case insensitive? :) We'd have to "walk" the potential directories
	# for comparison... seems like there's gotta be a Python stdlib function for this?
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
		"--ibl-intensity",
		type=float,
		default=0.1,
		help="IBL exposure scale (default: 0.1)"
	)
	ap.add_argument("--no-lights", dest="lights", action="store_false", default=True)
	ap.add_argument("--animated-lights", dest="animated_lights", action="store_true", default=False)
	ap.add_argument("--floor-z", type=float, default=None)
	ap.add_argument("--floor-size", type=float, default=None)

	args = ap.parse_args()

	# No floor by default; passing either flag activates it.
	args.floor = args.floor_z is not None or args.floor_size is not None
	args.floor_z = -0.07 if args.floor_z is None else args.floor_z
	args.floor_size = 0.30 if args.floor_size is None else args.floor_size

	args.path = data_dir_file(args.path, "gltf")
	args.ktx2 = data_dir_file(args.ktx2, "ktx2")

	if args.hdr:
		args.hdr = data_dir_file(args.hdr, "hdr")

	osg.setNotifyLevel(osg.NotifySeverity.NOTICE)

	model = osgDB.readNodeFile(args.path)

	# REFERENCE_RADIUS is the scale the hardcoded rig directions/distances were tuned against -
	# never shrink below that (so already-good renders like BoomBox/Avocado/Cube are untouched),
	# only grow proportionally for bigger meshes so direct lighting doesn't collapse to near-zero
	# on anything larger (Lantern was the extreme case: ~15-unit bounding radius vs. fixed light
	# positions ~1 unit from the origin).
	bound = model.bound
	bound_center = bound.center
	bound_radius = bound.radius if bound.radius > 1e-6 else REFERENCE_RADIUS
	light_scale = max(bound_radius / REFERENCE_RADIUS, 1.0)

	print(
		f"[lighting] model bound: center={tuple(bound_center)} "
		f"radius={bound_radius:.4f}  light_scale={light_scale:.3f}",
		flush=True
	)

	key_light_pos = bound_center + KEY_LIGHT_DIR * (KEY_LIGHT_DIST * light_scale)
	fill_light_pos_0 = bound_center + FILL_LIGHT_DIR_0 * (FILL_LIGHT_DIST_0 * light_scale)
	fill_light_pos_1 = bound_center + FILL_LIGHT_DIR_1 * (FILL_LIGHT_DIST_1 * light_scale)
	light_radius_scaled = tuple(r * light_scale for r in LIGHT_RADII)

	# --- Load prefiltered cubemap from KTX2 --------------------------------- #
	prefilter_tex = osgDB.readObjectFile(args.ktx2)

	if not isinstance(prefilter_tex, osg.TextureCubeMap):
		print(
			f"ERROR: {args.ktx2!r} did not return a TextureCubeMap "
			f"(got {type(prefilter_tex).__name__})",
			flush=True
		)

		sys.exit(1)

	# KTX2 has hand-baked mips - don't let OSG regenerate them
	prefilter_tex.useHardwareMipMapGeneration = False

	# --- BRDF split-sum LUT (environment-independent, baked once) ----------- #
	lut_tex, lut_group = make_brdf_lut()

	# --- IBL uniforms ------------------------------------------------------- #
	ibl_sh_u = osg.Uniform(osg.Uniform.Type.FLOAT_VEC3, "iblSH", (osg.Vec3(),) * 9)
	ibl_enabled_u = osg.Uniform("iblEnabled", 1) # always 1 - we have the cubemap
	ibl_intensity_u = osg.Uniform("iblIntensity", args.ibl_intensity)

	# --- PBR program -------------------------------------------------------- #
	p = osg.Program(name="pbr_ibl", shaders=(
		osg.Shader(osg.Shader.VERTEX, VERTEX_SHADER),
		osg.Shader(osg.Shader.FRAGMENT, FRAGMENT_SHADER),
	))

	ss = model.stateSet

	ss.attributes[osg.StateAttribute.PROGRAM] = (
		p,
		osg.StateAttribute.ON | osg.StateAttribute.OVERRIDE | osg.StateAttribute.PROTECTED
	)

	ss.uniforms["osgx_gltf_textures.baseColor"] = 0
	ss.uniforms["osgx_gltf_textures.normal"] = 1
	ss.uniforms["osgx_gltf_textures.orm"] = 2
	ss.uniforms["osgx_gltf_textures.emissive"] = 3
	ss.uniforms["shadowMap"] = 4
	ss.uniforms["envMap"] = 5
	ss.uniforms["brdfLUT"] = 6
	ss.uniforms["emissiveFactor"] = osg.Vec3(1.0, 1.0, 1.0)
	ss.uniforms["scanlineFreq"] = 1000.0
	ss.uniforms["scanlineStrength"] = 0.5
	ss.uniforms["skyColor"] = osg.Vec3(0.15, 0.20, 0.35)
	ss.uniforms["groundColor"] = osg.Vec3(0.12, 0.08, 0.05)

	# --- Shared light uniforms ---------------------------------------------- #
	lightPos = osg.Uniform(osg.Uniform.Type.FLOAT_VEC3, "lightPos", (
		key_light_pos,
		fill_light_pos_0,
		fill_light_pos_1,
	))

	if args.lights:
		lightColor = osg.Uniform(osg.Uniform.Type.FLOAT_VEC3, "lightColor", (
			osg.Vec3(1.0, 0.9, 0.7),
			osg.Vec3(0.3, 0.5, 1.0),
			osg.Vec3(1.0, 0.5, 0.2),
		))

	else:
		lightColor = osg.Uniform(osg.Uniform.Type.FLOAT_VEC3, "lightColor", (
			osg.Vec3(),
			osg.Vec3(),
			osg.Vec3()
		))

	lightRadius = osg.Uniform(osg.Uniform.Type.FLOAT, "lightRadius", light_radius_scaled)

	shadow_matrix_u = osg.Uniform("shadowMatrix", osg.Matrixf.identity())
	shadow_bias_u = osg.Uniform("shadowBias", 0.005)
	shadow_strength_u = osg.Uniform("shadowStrength", 0.7)

	# --- Shadow map --------------------------------------------------------- #
	shadow_tex = osg.Texture2D(
		size=(SHADOW_SIZE, SHADOW_SIZE),
		internalFormat=GL_DEPTH_COMPONENT24,
		sourceFormat=GL_DEPTH_COMPONENT,
		sourceType=GL_FLOAT,
		filter=osg.Texture.NEAREST,
		wrap=osg.Texture.CLAMP_TO_EDGE,
	)

	dummy_color = osg.Texture2D(size=(SHADOW_SIZE, SHADOW_SIZE), internalFormat=GL_RGB)

	# Shadow camera gets its OWN position - deliberately decoupled from key_light_pos (which stays
	# exactly as validated for direct-light shading/attenuation). Reusing key_light_pos's distance
	# here (a previous attempt) put the camera closer to the object than its own bounding radius
	# for every model except BoomBox, forcing near->0.01 while far stretched out to cover the
	# object - e.g. Lantern hit a ~2870:1 near:far ratio, which collapses shadow-map depth
	# precision to nothing (the comparison in shadowFactor() never triggers - looks like "no
	# shadow" but is really "no usable depth precision"). Cube was already at ~328:1, just not
	# noticed. Fixing this needs the shadow camera to sit far enough back for a fixed, comfortable
	# FOV, which bounds near:far to a healthy ratio by construction regardless of model size --
	# same direction as the key light (still reads as "cast by the key light"), just a different
	# vantage point purely for the depth pass.
	SHADOW_HALF_FOV_DEG = 25.0
	SHADOW_MARGIN = 1.3
	shadow_distance = bound_radius * SHADOW_MARGIN / math.tan(math.radians(SHADOW_HALF_FOV_DEG))
	shadow_light_pos = bound_center + KEY_LIGHT_DIR * shadow_distance

	light_view = osg.Matrix.lookAt(
		shadow_light_pos,
		bound_center,
		osg.Vec3(0, 1, 0)
	)

	shadow_near = max(0.01, shadow_distance - bound_radius * SHADOW_MARGIN)
	shadow_far = shadow_distance + bound_radius * SHADOW_MARGIN

	light_proj = osg.Matrix.perspective(2.0 * SHADOW_HALF_FOV_DEG, 1.0, shadow_near, shadow_far)

	shadow_cam = osg.Camera(
		name="ShadowCam",
		renderOrder=osg.Camera.PRE_RENDER,
		renderTargetImplementation=osg.Camera.FRAME_BUFFER_OBJECT,
		referenceFrame=osg.Transform.ABSOLUTE_RF,
		clearMask=GL_DEPTH_BUFFER_BIT | GL_COLOR_BUFFER_BIT,
		clearColor=osg.Vec4(1, 1, 1, 1),
		viewport=osg.Viewport(0, 0, SHADOW_SIZE, SHADOW_SIZE),
	)
	shadow_cam.attach(osg.Camera.DEPTH_BUFFER, shadow_tex)
	shadow_cam.attach(osg.Camera.COLOR_BUFFER, dummy_color)
	shadow_cam.viewMatrix = light_view
	shadow_cam.projectionMatrix = light_proj
	shadow_cam.children.append(model)

	# --- Floor (optional) --------------------------------------------------- #
	if args.floor:
		S, Z = args.floor_size, args.floor_z
		floor_quad = osg.createTexturedQuadGeometry(
			osg.Vec3(-S/2, -S/2, Z),
			osg.Vec3(S, 0, 0),
			osg.Vec3(0, S, 0)
		)

		floor_geode = osg.Geode()
		floor_geode.drawables.append(floor_quad)

		floor_p = osg.Program(name="floor_ibl", shaders=(
			osg.Shader(osg.Shader.VERTEX, FLOOR_VERTEX),
			osg.Shader(osg.Shader.FRAGMENT, FLOOR_FRAGMENT),
		))

		floor_geode.stateSet.attributes.append(floor_p)
		floor_geode.stateSet.uniforms["shadowMap"] = 4

	# --- Scene graph -------------------------------------------------------- #
	main_group = osg.Group()
	mg_ss = main_group.stateSet
	mg_ss.textureAttributes[4] = shadow_tex
	mg_ss.textureAttributes[5] = prefilter_tex
	mg_ss.textureAttributes[6] = lut_tex
	mg_ss.uniforms.extend((
		lightPos,
		lightColor,
		lightRadius,
		shadow_matrix_u,
		shadow_bias_u,
		shadow_strength_u,
		ibl_enabled_u,
		ibl_intensity_u,
		ibl_sh_u
	))
	mg_ss.uniforms["animatedLights"] = args.animated_lights

	main_group.children.append(model)

	if args.floor:
		main_group.children.append(floor_geode)

	root = osg.Group()
	root.children.extend((shadow_cam, lut_group, main_group))

	GL_TEXTURE_CUBE_MAP_SEAMLESS = 0x884F

	root.stateSet.modes[GL_TEXTURE_CUBE_MAP_SEAMLESS] = osg.StateAttribute.ON

	# --- Viewer ------------------------------------------------------------- #
	v = osgViewer.Viewer()
	v.sceneData = root
	v.cameraManipulator = osgGA.TrackballManipulator()

	def update_shadow(ri):
		cam_view = v.camera.viewMatrix
		shadow_mat = osg.Matrix.inverse(cam_view) * light_view * light_proj
		shadow_matrix_u.value = osg.Matrixf(shadow_mat)

	v.camera.preDrawCallback = update_shadow

	# --- Async viewer loop -------------------------------------------------- #
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

			try:
				while True:
					sh = queue.get_nowait()

					for i, rgb in enumerate(sh):
						ibl_sh_u[i] = osg.Vec3(*rgb)

			except asyncio.QueueEmpty:
				pass

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
