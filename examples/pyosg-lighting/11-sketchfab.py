#!/usr/bin/env python3
#vimrun! python3 ../examples/pyosg-lighting/11-sketchfab.py --ktx2 papermill --hdr papermill

# Step 11 - Sketchfab-parity capstone (first increment: deferred G-buffer restructuring)
#
# This is 09-ibl.py's exact PBR+IBL lighting math (direct lights, shadow, IBL, emissive,
# tonemap), restructured into the deferred G-buffer + composite architecture proven by
# examples/pyosg-mrt.py -- one geometry pass writes raw material/geometric data to four
# color attachments + depth via MRT (layout(location = n) out), a second fullscreen
# composite pass reads that G-buffer back and does ALL of the actual PBR shading. This is
# NOT the full Sketchfab-parity capstone yet -- no SSAO/SSR/bloom/vignette/TAA, that's
# later work once this deferred skeleton is proven (see ai/context-todo-lighting-class.md
# for the full research). Animation/skinning (09-ibl-animation.py) and live dynamic-probe
# rebaking (10-dynamicprobes.py) are both explicitly out of scope here.
#
# Why bother deferring at all for this increment: it's the prerequisite architecture the
# later post-processing passes need (they read a G-buffer, not the model's own textures/
# varyings), and it happens to buy a free Sketchfab-style "render level" layer toggle
# (press 0-8) as a side effect of having isolated the pipeline's intermediate values.
#
# Texture units:
# Geometry pass (model's own textures, unchanged from 09-ibl.py): 0 baseColor 1 normal
# 2 orm 3 emissive
# Composite pass (new namespace): 0 gAlbedo 1 gNormal 2 gMaterial 3 gEmissive 4 gDepth
# 5 shadowMap 6 envMap 7 brdfLUT

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

W, H = 800, 600

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #

SHADOW_SIZE = 1024

# Same light rig as 09-ibl.py -- see that file for the full rationale on why light
# positions scale by bounding radius (Lantern-sized models vs. BoomBox-sized ones).
REFERENCE_RADIUS = 1.7

KEY_LIGHT_DIR = osg.Vec3( 0.1, 0.1, 1.0).normalized()
FILL_LIGHT_DIR_0 = osg.Vec3(-0.8, 0.3, 0.5).normalized()
FILL_LIGHT_DIR_1 = osg.Vec3( 0.0, -0.6, 0.2).normalized()

KEY_LIGHT_DIST = osg.Vec3( 0.1, 0.1, 1.0).length()
FILL_LIGHT_DIST_0 = osg.Vec3(-0.8, 0.3, 0.5).length()
FILL_LIGHT_DIST_1 = osg.Vec3( 0.0, -0.6, 0.2).length()

LIGHT_RADII = (2.5, 1.5, 1.2)

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

// ---- Shading normal --------------------------------------------------------- //
// TBN reconstructed per-pixel from screen-space derivatives (Christian Schuler's
// "normal mapping without precomputed tangents") rather than a vertex TANGENT attribute
// -- see 09-ibl.py for why (glTF's TANGENT accessor is frequently absent).
vec3 getShadingNormal() {
	vec3 Nb = normalize(vNGeom);
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
}
"""

# Trivial G-buffer writer for the floor -- flat constants instead of a real material
# lookup (the floor has no glTF material to sample). Routed through the SAME G-buffer as
# the model (rather than kept as a separate forward pass) so it picks up real PBR direct
# lighting + IBL from the shared composite shader for free, instead of 09-ibl.py's
# FLOOR_FRAGMENT hand-duplicated shadowFactor()/getAnimatedLight() and flat hardcoded
# ambient (no IBL at all).
FLOOR_GBUFFER_VERTEX = """
#version 460 core

in vec4 osg_Vertex;
in vec3 osg_Normal;

uniform mat4 osg_ModelViewProjectionMatrix;
uniform mat3 osg_NormalMatrix;

out vec3 vNormal;

void main() {
	vNormal = normalize(osg_NormalMatrix * osg_Normal);

	gl_Position = osg_ModelViewProjectionMatrix * osg_Vertex;
}
"""

FLOOR_GBUFFER_FRAGMENT = """
#version 460 core

in vec3 vNormal;

layout(location = 0) out vec4 outAlbedo;
layout(location = 1) out vec4 outNormal;
layout(location = 2) out vec4 outMaterial;
layout(location = 3) out vec4 outEmissive;

void main() {
	outAlbedo = vec4(0.82, 0.76, 0.62, 1.0);
	outNormal = vec4(normalize(vNormal), 0.0);
	outMaterial = vec4(1.0, 0.0, 1.0, 1.0); // roughness=1 (matte), metallic=0, ao=1
	outEmissive = vec4(0.0);
}
"""

# Fullscreen NDC quad vertex shader -- shared between the BRDF LUT bake and the
# composite pass (same convention as 09-ibl.py).
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

# Composite pass: reads the 5-attachment G-buffer back and does ALL of 09-ibl.py's PBR+
# IBL shading here instead of inline during the geometry pass -- true deferred shading.
# Also implements the 0-8 render-level visualize toggle (Sketchfab-style layer switch).
COMPOSITE_FRAGMENT_SHADER = """
#version 460 core

#define NUM_LIGHTS 3
const float PI = 3.14159265359;

uniform sampler2D gAlbedo;   // unit 0
uniform sampler2D gNormal;   // unit 1
uniform sampler2D gMaterial; // unit 2
uniform sampler2D gEmissive; // unit 3
uniform sampler2D gDepth;    // unit 4
uniform sampler2D shadowMap; // unit 5
uniform samplerCube envMap;  // unit 6: prefiltered cubemap
uniform sampler2D brdfLUT;   // unit 7: split-sum BRDF LUT

uniform mat4 invProjectionMatrix;
uniform float znear;
uniform float zfar;
uniform int visualizeMode; // 0=composite 1=albedo 2=normal 3=depth 4=material
                            // 5=direct-only 6=IBL-only 7=emissive-only 8=shadow-only

// v.camera's real view matrix. NOT the same as GLSL's automatic osg_ViewMatrix here --
// this composite camera is a POST_RENDER, ABSOLUTE_RF, identity-view fullscreen quad, so
// osg_ViewMatrix would resolve to identity (it tracks whichever camera is currently
// drawing), silently freezing world-space lighting/reflections to whatever direction the
// viewer faced at startup. Set every frame from v.camera.viewMatrix instead.
uniform mat4 mainViewMatrix;
uniform mat4 shadowMatrix;

uniform vec3 lightPos[NUM_LIGHTS];
uniform vec3 lightColor[NUM_LIGHTS];
uniform float lightRadius[NUM_LIGHTS];
uniform bool animatedLights;
uniform float osg_SimulationTime;

uniform vec3 skyColor;
uniform vec3 groundColor;

uniform int iblEnabled;
uniform vec3 iblSH[9];
uniform float iblIntensity;

in vec2 vUV;

out vec4 fragColor;

// ---- Depth / position reconstruction --------------------------------------- //

float linearizeDepth(float d, float near, float far) {
	float z = d * 2.0 - 1.0;

	return (2.0 * near * far) / (far + near - z * (far - near));
}

vec3 reconstructViewPos(vec2 uv, float d) {
	vec4 clip = vec4(vec3(uv, d) * 2.0 - 1.0, 1.0);
	vec4 viewPos = invProjectionMatrix * clip;

	return viewPos.xyz / viewPos.w;
}

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
			shadow += (uv.z - 0.005 > texture(shadowMap, uv.xy + vec2(x, y) * sz).r) ? 1.0 : 0.0;
	return mix(1.0, 0.3, shadow / 9.0);
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

vec3 evaluateDirectLighting(Material mat, vec3 N, vec3 V, float NdotV, vec3 eyePos) {
	vec3 Lo = vec3(0.0);
	float t = osg_SimulationTime;

	for (int i = 0; i < NUM_LIGHTS; i++) {
		vec3 lp = lightPos[i];
		float pulse = 1.0;

		if (animatedLights) getAnimatedLight(i, t, lp, pulse);

		vec3 lEye = (mainViewMatrix * vec4(lp, 1.0)).xyz;
		vec3 lVec = lEye - eyePos;
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
		float shad = (i == 0) ? shadowFactor(eyePos) : 1.0;

		Lo += (diffuse + specular) * lightColor[i] * pulse * NdotL * atten * shad;
	}

	return Lo;
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
	vec3 ibl_diff = sh_irradiance(N_world) * mat.albedo * kD_ibl * iblIntensity;

	float maxMip = float(textureQueryLevels(envMap) - 1);
	float lod = mat.roughness * maxMip;
	vec3 r_gl = vec3(R_world.x, R_world.z, -R_world.y);
	vec3 prefilt = textureLod(envMap, r_gl, lod).rgb;
	vec2 brdf = texture(brdfLUT, vec2(NdotV, mat.roughness)).rg;
	vec3 ibl_spec = prefilt * (mat.F0 * brdf.x + brdf.y);

	return (ibl_diff + ibl_spec) * mat.ao;
}

// ---- Tonemap ------------------------------------------------------------------ //
// Khronos PBR Neutral tonemapping (matches Babylon.js "PBR Neutral" preset).
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
	vec4 albedo = texture(gAlbedo, vUV);
	vec3 rawNormal = texture(gNormal, vUV).rgb;
	vec3 ormRaw = texture(gMaterial, vUV).rgb;
	vec3 rawEmissive = texture(gEmissive, vUV).rgb;
	float d = texture(gDepth, vUV).r;

	// --- Raw G-buffer dump modes (bypass lighting entirely, including background --
	// e.g. mode 3's depth view legitimately shows far-plane white where nothing was
	// ever drawn). Albedo is stored linear (same convention as mat.albedo everywhere
	// else in this shader), so it needs the same gamma re-encode as the final
	// composite to look right on screen; normal/depth/material are raw data views,
	// not display colors, so they're left un-gamma-corrected.
	if (visualizeMode == 1) {
		fragColor = vec4(pow(albedo.rgb, vec3(1.0 / 2.2)), 1.0);

		return;
	}

	if (visualizeMode == 2) {
		fragColor = vec4(rawNormal * 0.5 + 0.5, 1.0);

		return;
	}

	if (visualizeMode == 3) {
		float lin = linearizeDepth(d, znear, zfar);
		float t = clamp((lin - znear) / (zfar - znear), 0.0, 1.0);

		fragColor = vec4(vec3(t), 1.0);

		return;
	}

	if (visualizeMode == 4) {
		fragColor = vec4(ormRaw, 1.0);

		return;
	}

	// A cleared-but-never-written background pixel has a zero-length normal (real
	// written normals are always unit length) -- same sentinel technique as
	// pyosg-mrt.py, needed only for the modes below that actually shade something.
	if (dot(rawNormal, rawNormal) < 0.0001) {
		fragColor = vec4(0.02, 0.02, 0.03, 1.0);

		return;
	}

	vec3 N = normalize(rawNormal);
	vec3 eyePos = reconstructViewPos(vUV, d);
	vec3 V = normalize(-eyePos);
	float NdotV = max(dot(N, V), 0.0);
	Material mat = unpackMaterial(albedo.rgb, ormRaw);

	if (visualizeMode == 5) {
		fragColor = vec4(pow(evaluateDirectLighting(mat, N, V, NdotV, eyePos), vec3(1.0 / 2.2)), 1.0);

		return;
	}

	if (visualizeMode == 6) {
		fragColor = vec4(pow(evaluateIBL(mat, N, V, NdotV), vec3(1.0 / 2.2)), 1.0);

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

	vec3 Lo = evaluateDirectLighting(mat, N, V, NdotV, eyePos);
	vec3 ambient = evaluateIBL(mat, N, V, NdotV);
	vec3 color = ambient + Lo + rawEmissive;
	color = tonemapPBRNeutral(color);
	color = pow(color, vec3(1.0 / 2.2));

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
# G-buffer + composite cameras
# --------------------------------------------------------------------------- #

# Five simultaneous attachments from one geometry pass -- albedo/normal/material/emissive
# color buffers plus real scene depth (distinct from shadow_tex's light-space depth).
# RELATIVE_RF (no explicit view/projection set) so this camera inherits v.camera's actual
# view/projection every frame during its PRE_RENDER traversal, same as pyosg-mrt.py's
# gbuffer camera -- that's what keeps eye-space consistent between here and the composite
# pass's depth-reconstructed eyePos.
def create_gbuffer_camera(w=W, h=H):
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

	depth_tex = osg.Texture2D()
	depth_tex.size = (w, h)
	depth_tex.internalFormat = GL_DEPTH_COMPONENT24
	depth_tex.sourceFormat = GL_DEPTH_COMPONENT
	depth_tex.sourceType = GL_FLOAT
	depth_tex.filter = (osg.Texture.NEAREST, osg.Texture.NEAREST)

	cam = osg.Camera()
	cam.renderOrder = osg.Camera.PRE_RENDER
	cam.renderTargetImplementation = osg.Camera.FRAME_BUFFER_OBJECT
	cam.clearMask = GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT
	cam.clearColor = osg.Vec4(0.0, 0.0, 0.0, 0.0)
	cam.viewport = osg.Viewport(0, 0, w, h)
	cam.name = "G-Buffer Camera"

	cam.attach(osg.Camera.COLOR_BUFFER0, albedo_tex)
	cam.attach(osg.Camera.COLOR_BUFFER1, normal_tex)
	cam.attach(osg.Camera.COLOR_BUFFER2, material_tex)
	cam.attach(osg.Camera.COLOR_BUFFER3, emissive_tex)
	cam.attach(osg.Camera.DEPTH_BUFFER, depth_tex)

	return cam, albedo_tex, normal_tex, material_tex, emissive_tex, depth_tex

# Fullscreen composite/HUD camera -- samples the G-buffer plus shadow/IBL textures and
# runs COMPOSITE_FRAGMENT_SHADER. No renderTargetImplementation set, so (like
# pyosg-mrt.py's HUD camera) it draws straight to the default/window framebuffer.
def create_composite_camera(gbuf, shadow_tex, prefilter_tex, lut_tex):
	albedo_tex, normal_tex, material_tex, emissive_tex, depth_tex = gbuf

	cam = osg.Camera()
	cam.referenceFrame = osg.Transform.ABSOLUTE_RF
	cam.renderOrder = osg.Camera.POST_RENDER
	cam.clearMask = 0
	cam.allowEventFocus = False
	cam.projectionMatrix = osg.Matrix.identity()
	cam.viewMatrix = osg.Matrix.identity()
	cam.name = "Composite"

	g = osg.Geode()
	g.drawables.append(osg.createTexturedQuadGeometry(
		osg.Vec3(-1.0, -1.0, -1.0),
		osg.Vec3(2.0, 0.0, 0.0),
		osg.Vec3(0.0, 2.0, 0.0)
	))

	cam.children.append(g)

	ss = cam.stateSet
	ss.textureAttributes[0] = albedo_tex
	ss.textureAttributes[1] = normal_tex
	ss.textureAttributes[2] = material_tex
	ss.textureAttributes[3] = emissive_tex
	ss.textureAttributes[4] = depth_tex
	ss.textureAttributes[5] = shadow_tex
	ss.textureAttributes[6] = prefilter_tex
	ss.textureAttributes[7] = lut_tex

	ss.uniforms["gAlbedo"] = 0
	ss.uniforms["gNormal"] = 1
	ss.uniforms["gMaterial"] = 2
	ss.uniforms["gEmissive"] = 3
	ss.uniforms["gDepth"] = 4
	ss.uniforms["shadowMap"] = 5
	ss.uniforms["envMap"] = 6
	ss.uniforms["brdfLUT"] = 7

	p = osg.Program(name="composite_pbr_ibl", shaders=(
		osg.Shader(osg.Shader.VERTEX, FULLSCREEN_VERTEX),
		osg.Shader(osg.Shader.FRAGMENT, COMPOSITE_FRAGMENT_SHADER),
	))

	g.stateSet.setAttributeAndModes(p)

	return cam

# --------------------------------------------------------------------------- #
# Input
# --------------------------------------------------------------------------- #

class VisualizeModeHandler(osgGA.GUIEventHandler):
	"""Press 0-8 to switch the composite pass's render level (Sketchfab-style layer toggle)."""

	def __init__(self, mode_uniform):
		super().__init__()
		self.mode_uniform = mode_uniform

	def handle(self, ea, aa):
		if ea.handled or ea.type != osgGA.GUIEventAdapter.KEYUP:
			return False

		key = ea.key

		if ord("0") <= key <= ord("8"):
			self.mode_uniform.value = key - ord("0")

			return True

		return False

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

	args.floor = args.floor_z is not None or args.floor_size is not None
	args.floor_z = -0.07 if args.floor_z is None else args.floor_z
	args.floor_size = 0.30 if args.floor_size is None else args.floor_size

	args.path = data_dir_file(args.path, "gltf")
	args.ktx2 = data_dir_file(args.ktx2, "ktx2")

	if args.hdr:
		args.hdr = data_dir_file(args.hdr, "hdr")

	osg.setNotifyLevel(osg.NotifySeverity.NOTICE)

	model = osgDB.readNodeFile(args.path)

	bound = model.bound
	bound_center = bound.center
	bound_radius = bound.radius if bound.radius > 1e-6 else REFERENCE_RADIUS
	light_scale = max(bound_radius / REFERENCE_RADIUS, 1.0)

	print(
		f"[sketchfab] model bound: center={tuple(bound_center)} "
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

	prefilter_tex.useHardwareMipMapGeneration = False

	# --- BRDF split-sum LUT (environment-independent, baked once) ----------- #
	lut_tex, lut_group = make_brdf_lut()

	# --- IBL uniforms (now live on composite_cam's stateSet) ---------------- #
	ibl_sh_u = osg.Uniform(osg.Uniform.Type.FLOAT_VEC3, "iblSH", (osg.Vec3(),) * 9)
	ibl_enabled_u = osg.Uniform("iblEnabled", 1) # always 1 - we have the cubemap
	ibl_intensity_u = osg.Uniform("iblIntensity", args.ibl_intensity)

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

	# --- Shared light uniforms (now live on composite_cam's stateSet) ------- #
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
	main_view_u = osg.Uniform("mainViewMatrix", osg.Matrixf.identity())

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

	shadow_cam = osg.Camera()
	shadow_cam.name = "ShadowCam"
	shadow_cam.renderOrder = osg.Camera.PRE_RENDER
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

	# --- Floor (optional) -- routed through the G-buffer, see FLOOR_GBUFFER_* -- #
	if args.floor:
		S, Z = args.floor_size, args.floor_z
		floor_quad = osg.createTexturedQuadGeometry(
			osg.Vec3(-S/2, -S/2, Z),
			osg.Vec3(S, 0, 0),
			osg.Vec3(0, S, 0)
		)

		floor_geode = osg.Geode()
		floor_geode.drawables.append(floor_quad)

		floor_p = osg.Program(name="floor_gbuffer", shaders=(
			osg.Shader(osg.Shader.VERTEX, FLOOR_GBUFFER_VERTEX),
			osg.Shader(osg.Shader.FRAGMENT, FLOOR_GBUFFER_FRAGMENT),
		))

		floor_geode.stateSet.setAttributeAndModes(floor_p)

	# --- G-buffer + composite cameras ---------------------------------------- #
	gbuffer_cam, albedo_tex, normal_tex, material_tex, emissive_tex, depth_tex = create_gbuffer_camera(W, H)

	gbuffer_cam.children.append(model)

	if args.floor:
		gbuffer_cam.children.append(floor_geode)

	composite_cam = create_composite_camera(
		(albedo_tex, normal_tex, material_tex, emissive_tex, depth_tex),
		shadow_tex,
		prefilter_tex,
		lut_tex
	)

	cc_ss = composite_cam.stateSet
	cc_ss.uniforms.extend((
		lightPos,
		lightColor,
		lightRadius,
		shadow_matrix_u,
		main_view_u,
		ibl_enabled_u,
		ibl_intensity_u,
		ibl_sh_u
	))
	cc_ss.uniforms["animatedLights"] = args.animated_lights
	cc_ss.uniforms["skyColor"] = osg.Vec3(0.15, 0.20, 0.35)
	cc_ss.uniforms["groundColor"] = osg.Vec3(0.12, 0.08, 0.05)

	znear_u = osg.Uniform("znear", 0.0)
	zfar_u = osg.Uniform("zfar", 0.0)
	inv_proj_u = osg.Uniform("invProjectionMatrix", osg.Matrixf.identity())
	visualize_mode_u = osg.Uniform("visualizeMode", 0)

	cc_ss.uniforms.extend((znear_u, zfar_u, inv_proj_u, visualize_mode_u))

	root = osg.Group()
	root.children.extend((shadow_cam, lut_group, gbuffer_cam, composite_cam))

	GL_TEXTURE_CUBE_MAP_SEAMLESS = 0x884F

	root.stateSet.setMode(GL_TEXTURE_CUBE_MAP_SEAMLESS, osg.StateAttribute.ON)

	# --- Viewer ------------------------------------------------------------- #
	v = osgViewer.Viewer()
	v.sceneData = root
	v.cameraManipulator = osgGA.TrackballManipulator()

	# Combined per-frame uniform update: shadow matrix (needs the real view matrix to
	# map composite-reconstructed eyePos -> light clip space), inverse projection +
	# znear/zfar (depth reconstruction), and mainViewMatrix (see COMPOSITE_FRAGMENT_
	# SHADER's comment on why osg_ViewMatrix can't be trusted on that camera).
	def update_uniforms(ri):
		cam_view = v.camera.viewMatrix
		pm = ri.state.projectionMatrix
		fovy, aspect, near, far = pm.getPerspective()

		znear_u.value = float(near)
		zfar_u.value = float(far)
		inv_proj_u.value = osg.Matrixf(osg.Matrix.inverse(pm))
		main_view_u.value = osg.Matrixf(cam_view)

		shadow_mat = osg.Matrix.inverse(cam_view) * light_view * light_proj
		shadow_matrix_u.value = osg.Matrixf(shadow_mat)

	v.camera.preDrawCallback = update_uniforms
	v.addEventHandler(VisualizeModeHandler(visualize_mode_u))

	print(
		"Press 0=composite 1=albedo 2=normal 3=depth 4=material "
		"5=direct 6=IBL 7=emissive 8=shadow",
		flush=True
	)

	# --- Async viewer loop (verbatim from 09-ibl.py) -------------------------- #
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
