#!/usr/bin/env python3
#vimrun! python3 ../examples/pyosg-lighting/09-ibl.py --no-floor --no-lights --ktx2 papermill --hdr papermill

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
# SH diffuse - computed synchronously from --hdr if provided; zero otherwise
#
# Texture units (same as step 8 + 9):
# 0 baseColor 1 normal 2 ORM 3 emissive 4 shadow 5 envMap 6 brdfLUT

import sys
import os
import time
import argparse
import threading
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

KEY_LIGHT_POS = osg.Vec3( 0.1, 0.1, 1.0)
FILL_LIGHT_POS_0 = osg.Vec3(-0.8, 0.3, 0.5)
FILL_LIGHT_POS_1 = osg.Vec3( 0.0, -0.6, 0.2)

# --------------------------------------------------------------------------- #
# SH projection (synchronous - no async needed without FBO bake)
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

	A = [np.pi,
		 2*np.pi/3, 2*np.pi/3, 2*np.pi/3,
		 np.pi/4, np.pi/4, np.pi/4, np.pi/4, np.pi/4]

	sh = []

	for i, (yi, ai) in enumerate(zip(Y, A)):
		rgb = np.sum(img * (yi * d_omega)[..., np.newaxis], axis=(0, 1)) * ai

		sh.append([float(rgb[0]), float(rgb[1]), float(rgb[2])])

		print(f"[ibl] SH[{i}] = ({rgb[0]:.4f}, {rgb[1]:.4f}, {rgb[2]:.4f})", flush=True)

	print("[ibl] SH done.", flush=True)

	return sh

# --------------------------------------------------------------------------- #
# Shaders
# --------------------------------------------------------------------------- #

VERTEX_SHADER = """
#version 460 core

in vec4 osg_Vertex;
in vec3 osg_Normal;
in vec2 osg_MultiTexCoord0;
in vec4 osg_Tangent;

uniform mat4 osg_ModelViewProjectionMatrix;
uniform mat4 osg_ModelViewMatrix;
uniform mat3 osg_NormalMatrix;

out vec3 vT;
out vec3 vB;
out vec3 vNGeom;
out vec3 vPosition;
out vec2 vUV;

void main() {
	vec4 eyePos = osg_ModelViewMatrix * osg_Vertex;
	vPosition = eyePos.xyz;
	vUV = osg_MultiTexCoord0;

	vec3 N = normalize(osg_NormalMatrix * osg_Normal);
	vec3 T = normalize(osg_NormalMatrix * osg_Tangent.xyz);
	T = normalize(T - dot(T, N) * N);
	vec3 B = cross(N, T) * osg_Tangent.w;

	vNGeom = N;
	vT = T;
	vB = B;

	gl_Position = osg_ModelViewProjectionMatrix * osg_Vertex;
}
"""

FRAGMENT_SHADER = """
#version 460 core

#define NUM_LIGHTS 3
const float PI = 3.14159265359;

in vec3 vT;
in vec3 vB;
in vec3 vNGeom;
in vec3 vPosition;
in vec2 vUV;

uniform sampler2D baseColorTex; // unit 0
uniform sampler2D normalTex; // unit 1
uniform sampler2D ormTex; // unit 2
uniform sampler2D emissiveTex; // unit 3
uniform sampler2D shadowMap; // unit 4
uniform samplerCube envMap; // unit 5: prefiltered cubemap
uniform sampler2D brdfLUT; // unit 6: split-sum BRDF LUT

uniform vec3 emissiveFactor;
uniform float metallicFactor;
uniform float roughnessFactor;
uniform float scanlineFreq;
uniform float scanlineStrength;
uniform float osg_SimulationTime;

uniform vec3 skyColor;
uniform vec3 groundColor;

uniform mat4 osg_ViewMatrix;

uniform vec3 lightPos[NUM_LIGHTS];
uniform vec3 lightColor[NUM_LIGHTS];
uniform float lightRadius[NUM_LIGHTS];

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
	for (int x = -1; x <= 1; ++x)
		for (int y = -1; y <= 1; ++y)
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

// ---- Main ----------------------------------------------------------------- //

void main() {
	mat3 TBN = mat3(normalize(vT), normalize(vB), normalize(vNGeom));
	vec3 nMap = texture(normalTex, vUV).rgb * 2.0 - 1.0;
	vec3 N = normalize(TBN * nMap);
	vec3 V = normalize(-vPosition);

	vec3 albedo = texture(baseColorTex, vUV).rgb;
	float ao = texture(ormTex, vUV).r;
	float roughness = texture(ormTex, vUV).g * roughnessFactor;
	float metallic = texture(ormTex, vUV).b * metallicFactor;

	// Specular AA: clamp roughness by how fast the shading normal (including
	// normal map) rotates per pixel. Using N (post-normal-map) rather than
	// vNGeom catches the bevel/crease edges baked into the normal map, which
	// is where the visible over-sharp reflections come from.
	float normalDelta = max(
		max(abs(dFdx(N.x)), abs(dFdx(N.y))),
		max(abs(dFdy(N.x)), abs(dFdy(N.y)))
	);
	roughness = max(roughness, normalDelta);

	float NdotV = max(dot(N, V), 0.0);
	vec3 F0 = mix(vec3(0.04), albedo, metallic);

	// Analytical lights
	vec3 Lo = vec3(0.0);
#ifdef ANIMATED_LIGHTS
	float _t = osg_SimulationTime;
	vec3 _lp[NUM_LIGHTS];
	float _pulse[NUM_LIGHTS];
	_lp[0] = vec3(cos(_t*0.8)*1.0, sin(_t*0.8)*1.0, 0.8);
	_lp[1] = vec3(cos(_t*0.5+6.28318/3.0)*0.9, sin(_t*0.5+6.28318/3.0)*0.9, 0.3);
	_lp[2] = vec3(cos(_t*0.3+6.28318/1.5)*0.7, sin(_t*0.3+6.28318/1.5)*0.7,-0.2);
	_pulse[0] = 0.8 + 0.2*sin(_t*1.3);
	_pulse[1] = 0.8 + 0.2*sin(_t*0.9+1.0);
	_pulse[2] = 0.8 + 0.2*sin(_t*0.6+2.1);
#endif
	for (int i = 0; i < NUM_LIGHTS; i++) {
#ifdef ANIMATED_LIGHTS
		vec3 lEye = (osg_ViewMatrix * vec4(_lp[i], 1.0)).xyz;
#else
		vec3 lEye = (osg_ViewMatrix * vec4(lightPos[i], 1.0)).xyz;
#endif
		vec3 lVec = lEye - vPosition;
		float dist = length(lVec);
		vec3 L = lVec / dist;
		float r = lightRadius[i];
		float atten = 1.0 / (1.0 + (dist * dist) / (r * r));
		vec3 H = normalize(L + V);
		float NdotL = max(dot(N, L), 0.0);
		float NdotH = max(dot(N, H), 0.0);
		float HdotV = max(dot(H, V), 0.0);
		float D = D_GGX(NdotH, roughness);
		float G = G_Smith(NdotV, NdotL, roughness);
		vec3 F = F_Schlick(HdotV, F0);
		vec3 kD = (vec3(1.0) - F) * (1.0 - metallic);
		vec3 diffuse = kD * albedo / PI;
		vec3 specular = (D * G * F) / max(4.0 * NdotV * NdotL, 0.001);
		float shad = (i == 0) ? shadowFactor(vPosition) : 1.0;
#ifdef ANIMATED_LIGHTS
		Lo += (diffuse + specular) * lightColor[i] * _pulse[i] * NdotL * atten * shad;
#else
		Lo += (diffuse + specular) * lightColor[i] * NdotL * atten * shad;
#endif
	}

	// Ambient
	vec3 ambient;
	if (iblEnabled == 0) {
		vec3 worldUp = normalize(mat3(osg_ViewMatrix) * vec3(0.0, 0.0, 1.0));
		float hemi = dot(N, worldUp) * 0.5 + 0.5;
		ambient = mix(groundColor, skyColor, hemi) * albedo * ao;
	} else {
		mat3 invView = transpose(mat3(osg_ViewMatrix));
		vec3 N_world = invView * N;
		vec3 V_world = invView * V;
		vec3 R_world = reflect(-V_world, N_world);

		vec3 F_ibl = F_Schlick_roughness(NdotV, F0, roughness);
		vec3 kD_ibl = (1.0 - F_ibl) * (1.0 - metallic);
		vec3 ibl_diff = sh_irradiance(N_world) * albedo * kD_ibl * iblIntensity;

		float maxMip = float(textureQueryLevels(envMap) - 1);
		float lod = roughness * maxMip;
		vec3 r_gl = vec3(R_world.x, R_world.z, -R_world.y);
		vec3 prefilt = textureLod(envMap, r_gl, lod).rgb;
		vec2 brdf = texture(brdfLUT, vec2(NdotV, roughness)).rg;
		vec3 ibl_spec = prefilt * (F0 * brdf.x + brdf.y);

		ambient = (ibl_diff + ibl_spec) * ao;
	}

	// Emissive
	vec3 emissive = texture(emissiveTex, vUV).rgb * emissiveFactor;
	float scanline = 0.5 + 0.5 * sin(vUV.y * scanlineFreq - osg_SimulationTime * 10.0);
	emissive *= mix(1.0, scanline, scanlineStrength);

	vec3 color = ambient + Lo + emissive;

	// Khronos PBR Neutral tonemapping (matches Babylon.js "PBR Neutral" preset)
	// Hue-preserving, no ACES orange shift at high luminance.
	{
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
		color = clamp(color, 0.0, 1.0);
	}
	color = pow(color, vec3(1.0 / 2.2));

	fragColor = vec4(color, 1.0);
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
uniform mat4 shadowMatrix;
uniform sampler2D shadowMap;
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
	for (int x = -1; x <= 1; ++x)
		for (int y = -1; y <= 1; ++y)
			shadow += (uv.z - 0.005 > texture(shadowMap, uv.xy + vec2(x, y) * sz).r) ? 1.0 : 0.0;
	return mix(1.0, 0.3, shadow / 9.0);
}

void main() {
	vec3 N = normalize(vNormal);
	vec3 albedo = vec3(0.82, 0.76, 0.62);
	vec3 Lo = vec3(0.0);
#ifdef ANIMATED_LIGHTS
	float _t = osg_SimulationTime;
	vec3 _lp[NUM_LIGHTS];
	_lp[0] = vec3(cos(_t*0.8)*1.0, sin(_t*0.8)*1.0, 0.8);
	_lp[1] = vec3(cos(_t*0.5+6.28318/3.0)*0.9, sin(_t*0.5+6.28318/3.0)*0.9, 0.3);
	_lp[2] = vec3(cos(_t*0.3+6.28318/1.5)*0.7, sin(_t*0.3+6.28318/1.5)*0.7,-0.2);
#endif
	for (int i = 0; i < NUM_LIGHTS; i++) {
#ifdef ANIMATED_LIGHTS
		vec3 lEye = (osg_ViewMatrix * vec4(_lp[i], 1.0)).xyz;
#else
		vec3 lEye = (osg_ViewMatrix * vec4(lightPos[i], 1.0)).xyz;
#endif
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
		osg.Vec3(-1, -1, 0), osg.Vec3(2, 0, 0), osg.Vec3(0, 2, 0))
	quad_geode = osg.Geode()
	quad_geode.drawables.append(quad)

	bake_group = osg.Group()
	_done = [False]

	def bake_once(node, nv):
		if _done[0]:
			node.nodeMask = 0
		_done[0] = True
		return True

	bake_group.updateCallback = bake_once

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
# Main
# --------------------------------------------------------------------------- #

# If the passed-in file exists, simply return it; if not, try and find it inside
# example data dir. For convenience, we'll try all the extensions we support, as
# well as assuming cetain directory structures.
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
	ap.add_argument("--floor", dest="floor", action="store_true", default=True)
	ap.add_argument("--no-floor", dest="floor", action="store_false")
	ap.add_argument("--floor-z", type=float, default=-0.07)
	ap.add_argument("--floor-size", type=float, default=0.30)

	args = ap.parse_args()

	args.path = data_dir_file(args.path, "gltf")
	args.ktx2 = data_dir_file(args.ktx2, "ktx2")
	args.hdr = data_dir_file(args.hdr, "hdr")

	osg.setNotifyLevel(osg.NotifySeverity.NOTICE)

	# --- Load model --------------------------------------------------------- #
	model = osgDB.readNodeFile(args.path)

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
	ibl_enabled_u = osg.Uniform("iblEnabled", 1) # always 1 -- we have the cubemap
	ibl_intensity_u = osg.Uniform("iblIntensity", args.ibl_intensity)

	# SH computed in background so the window opens immediately
	_sh_result = [None]

	def _sh_thread():
		_sh_result[0] = compute_sh(args.hdr)

	if args.hdr:
		threading.Thread(target=_sh_thread, daemon=True).start()

	# --- PBR program -------------------------------------------------------- #
	_define = "#version 460 core\n#define ANIMATED_LIGHTS" if args.animated_lights else "#version 460 core"
	_frag = FRAGMENT_SHADER.replace("#version 460 core", _define, 1)
	_floor_frag = FLOOR_FRAGMENT.replace("#version 460 core", _define, 1)

	p = osg.Program(name="pbr_ibl", shaders=(
		osg.Shader(osg.Shader.VERTEX, VERTEX_SHADER),
		osg.Shader(osg.Shader.FRAGMENT, _frag),
	))

	p.bindAttribLocation["osg_Tangent"] = 7

	ss = model.stateSet

	ss.setAttributeAndModes(
		p,
		osg.StateAttribute.ON | osg.StateAttribute.OVERRIDE | osg.StateAttribute.PROTECTED
	)

	ss.uniforms["baseColorTex"] = 0
	ss.uniforms["normalTex"] = 1
	ss.uniforms["ormTex"] = 2
	ss.uniforms["emissiveTex"] = 3
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
		KEY_LIGHT_POS,
		FILL_LIGHT_POS_0,
		FILL_LIGHT_POS_1,
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

	lightRadius = osg.Uniform(osg.Uniform.Type.FLOAT, "lightRadius", (2.5, 1.5, 1.2))

	shadow_matrix_u = osg.Uniform("shadowMatrix", osg.Matrixf.identity())

	# --- Shadow map --------------------------------------------------------- #
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

	light_view = osg.Matrix.lookAt(
		KEY_LIGHT_POS,
		osg.Vec3(0, 0, 0),
		osg.Vec3(0, 1, 0)
	)

	light_proj = osg.Matrix.perspective(8.0, 1.0, 0.8, 1.3)

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
			osg.Shader(osg.Shader.FRAGMENT, _floor_frag),
		))

		floor_geode.stateSet.setAttributeAndModes(floor_p)
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
		ibl_enabled_u,
		ibl_intensity_u,
		ibl_sh_u
	))

	main_group.children.append(model)

	if args.floor:
		main_group.children.append(floor_geode)

	root = osg.Group()
	root.children.extend((shadow_cam, lut_group, main_group))

	GL_TEXTURE_CUBE_MAP_SEAMLESS = 0x884F

	root.stateSet.setMode(GL_TEXTURE_CUBE_MAP_SEAMLESS, osg.StateAttribute.ON)

	# --- Viewer ------------------------------------------------------------- #
	v = osgViewer.Viewer()
	v.sceneData = root
	v.cameraManipulator = osgGA.TrackballManipulator()

	def update_shadow(ri):
		cam_view = v.camera.viewMatrix
		shadow_mat = osg.Matrix.inverse(cam_view) * light_view * light_proj
		shadow_matrix_u.value = osg.Matrixf(shadow_mat)

	v.camera.preDrawCallback = update_shadow

	while not v.done:
		v.frame()

		if _sh_result[0] is not None:
			for i, rgb in enumerate(_sh_result[0]):
				ibl_sh_u[i] = osg.Vec3(*rgb)

			_sh_result[0] = None
