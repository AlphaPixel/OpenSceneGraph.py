#!/usr/bin/env python3

import sys
import pathlib

# examples/lighting/ sits one level below examples/ itself, where pyosg_example.py lives --
# unlike every flat examples/pyosg-*.py file (whose own directory IS examples/, so Python's
# automatic sys.path[0] already covers them), a standalone run of this file needs examples/
# added explicitly. Same fix pyosg-cli's own EXAMPLES_DIR insertion applies for pyosg_visitor.py.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

# Import side effect: fills in OSG_WINDOW/OSG_THREADING/OSG_GL_* env var defaults (see
# pyosg_example.py). Deliberately before `from OpenSceneGraph import *`, matching every other
# example -- these need to land before OSG's DisplaySettings reads them.
from pyosg_example import window_size

from OpenSceneGraph import *

import osgx

# Bare name (e.g. "Corset") -> glTF-Sample-Assets/Models/<name>/glTF/<name>.gltf via
# osgx.findDataFile(), same convention pyosg-khronos-viewer.py's own resolve_model() uses.
def resolve_model(value):
	path = pathlib.Path(value).expanduser()

	if path.is_file():
		return str(path)

	return osgx.findDataFile(value) or osgx.findDataFile(
		path.stem, ("glTF-Sample-Assets/Models/{}/glTF/{}.gltf",)
	) or None

# PBR: replace Blinn-Phong with the Cook-Torrance BRDF and introduce the
# metallic/roughness workflow via the ORM texture (unit 2).
#
# The ORM texture packs three channels into one image:
# R = occlusion - pre-baked contact shadows; darkens ambient in crevices
# G = roughness - 0 = mirror-smooth, 1 = fully diffuse/matte
# B = metallic - 0 = dielectric (plastic), 1 = conductor (metal)
#
# The Cook-Torrance specular BRDF has three terms:
# D - GGX Normal Distribution: how many microfacets face exactly toward H
# G - Smith Geometry: self-shadowing/masking of microfacets
# F - Fresnel-Schlick: more reflection at grazing angles
#
# The metallic flag drives two critical differences vs. Blinn-Phong:
# 1. Metals have NO diffuse (incident light is immediately absorbed/re-emitted
# as specular; there is no subsurface scattering exit)
# 2. Metals tint their specular by albedo (gold reflects gold-colored light);
# dielectrics have a near-grey F0 of ~0.04

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

uniform sampler2D baseColorTex;
uniform sampler2D normalTex;
uniform sampler2D ormTex;

uniform vec3 skyColor;
uniform vec3 groundColor;

uniform mat4 osg_ViewMatrix;

uniform vec3 lightPos[NUM_LIGHTS];
uniform vec3 lightColor[NUM_LIGHTS];
uniform float lightRadius[NUM_LIGHTS];

out vec4 fragColor;

// GGX Normal Distribution - concentration of microfacets facing H.
float D_GGX(float NdotH, float roughness) {
	float a = roughness * roughness;
	float a2 = a * a;
	float d = NdotH * NdotH * (a2 - 1.0) + 1.0;
	return a2 / (PI * d * d);
}

// Schlick-GGX Geometry - microfacet self-shadowing on one side.
float G_Schlick(float NdotX, float roughness) {
	float r = roughness + 1.0;
	float k = (r * r) / 8.0;
	return NdotX / (NdotX * (1.0 - k) + k);
}

// Smith Geometry - combines shadowing from both light and view directions.
float G_Smith(float NdotV, float NdotL, float roughness) {
	return G_Schlick(NdotV, roughness) * G_Schlick(NdotL, roughness);
}

// Fresnel-Schlick - more reflection at grazing angles.
vec3 F_Schlick(float HdotV, vec3 F0) {
	return F0 + (1.0 - F0) * pow(1.0 - HdotV, 5.0);
}

void main() {
	mat3 TBN = mat3(normalize(vT), normalize(vB), normalize(vNGeom));

	vec3 nMap = texture(normalTex, vUV).rgb * 2.0 - 1.0;
	vec3 N = normalize(TBN * nMap);
	vec3 V = normalize(-vPosition);

	vec3 albedo = texture(baseColorTex, vUV).rgb;
	float ao = texture(ormTex, vUV).r;
	float roughness = texture(ormTex, vUV).g;
	float metallic = texture(ormTex, vUV).b;

	// F0: base reflectance at normal incidence.
	// Dielectrics use a constant ~0.04; metals use their albedo color.
	vec3 F0 = mix(vec3(0.04), albedo, metallic);

	vec3 Lo = vec3(0.0);

	for (int i = 0; i < NUM_LIGHTS; i++) {
		vec3 lEye = (osg_ViewMatrix * vec4(lightPos[i], 1.0)).xyz;
		vec3 lVec = lEye - vPosition;
		float dist = length(lVec);
		vec3 L = lVec / dist;

		float r = lightRadius[i];
		float atten = 1.0 / (1.0 + (dist * dist) / (r * r));

		vec3 H = normalize(L + V);
		float NdotL = max(dot(N, L), 0.0);
		float NdotV = max(dot(N, V), 0.0);
		float NdotH = max(dot(N, H), 0.0);
		float HdotV = max(dot(H, V), 0.0);

		float D = D_GGX(NdotH, roughness);
		float G = G_Smith(NdotV, NdotL, roughness);
		vec3 F = F_Schlick(HdotV, F0);

		// kD: diffuse contribution - zero for metals (they have no diffuse).
		vec3 kD = (vec3(1.0) - F) * (1.0 - metallic);

		vec3 diffuse = kD * albedo / PI;
		vec3 specular = (D * G * F) / max(4.0 * NdotV * NdotL, 0.001);

		Lo += (diffuse + specular) * lightColor[i] * NdotL * atten;
	}

	// Hemispherical ambient scaled by ambient occlusion.
	vec3 worldUp = normalize(mat3(osg_ViewMatrix) * vec3(0.0, 0.0, 1.0));
	float hemi = dot(N, worldUp) * 0.5 + 0.5;
	vec3 ambient = mix(groundColor, skyColor, hemi) * albedo * ao;

	fragColor = vec4(ambient + Lo, 1.0);
}
"""

def build_scene(w, h):
	path = resolve_model(sys.argv[1] if len(sys.argv) > 1 else "BoomBox")

	if not path:
		sys.exit("Cannot find model -- clone glTF-Sample-Assets into your OSG_FILE_PATH checkout")

	root = osgDB.readNodeFile(path)

	p = osg.Program(name="pbr", shaders=(
		osg.Shader(osg.Shader.VERTEX, VERTEX_SHADER),
		osg.Shader(osg.Shader.FRAGMENT, FRAGMENT_SHADER)
	))

	p.bindAttribLocation["osg_Tangent"] = 7

	ss = root.stateSet

	ss.attributes.append(p)

	ss.uniforms["baseColorTex"] = 0
	ss.uniforms["normalTex"] = 1
	ss.uniforms["ormTex"] = 2

	ss.uniforms["skyColor"] = osg.Vec3(0.15, 0.20, 0.35)
	ss.uniforms["groundColor"] = osg.Vec3(0.12, 0.08, 0.05)

	lightPos = osg.Uniform(osg.Uniform.Type.FLOAT_VEC3, "lightPos", (
		osg.Vec3(0.8, 0.6, 1.0),
		osg.Vec3(-0.8, 0.3, 0.5),
		osg.Vec3(0.0, -0.6, 0.2)
	))

	lightColor = osg.Uniform(osg.Uniform.Type.FLOAT_VEC3, "lightColor", (
		osg.Vec3(1.0, 0.9, 0.7),
		osg.Vec3(0.3, 0.5, 1.0),
		osg.Vec3(1.0, 0.5, 0.2)
	))

	lightRadius = osg.Uniform(osg.Uniform.Type.FLOAT, "lightRadius", (2.0, 1.5, 1.2))

	ss.uniforms.extend((lightPos, lightColor, lightRadius))

	return root

if __name__ == "__main__":
	osg.setNotifyLevel(osg.NotifySeverity.NOTICE)

	v = osgViewer.Viewer()

	v.sceneData = build_scene(*window_size())
	v.cameraManipulator = osgGA.TrackballManipulator()

	while not v.done:
		v.frame()
