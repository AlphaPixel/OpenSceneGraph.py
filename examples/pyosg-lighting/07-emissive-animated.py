#!/usr/bin/env python3
#vimrun! python3 ../examples/pyosg-lighting-7-emissive-animated.py ../examples/data/BoomBox/glTF/BoomBox.gltf

import sys
import os

os.environ.update({
	"OSG_WINDOW": "50 50 800 600",
	"OSG_THREADING": "SingleThreaded",
	"OSG_GL_CONTEXT_PROFILE_MASK": "1",
	"OSG_GL_VERSION": "4.6",
	"OSG_GL_CONTEXT_VERSION": "4.6"
})

from OpenSceneGraph import *

# Animated lights — the only change from step 7 is that light POSITIONS are
# no longer uniforms. Instead we use `osg_SimulationTime` (an OSG built-in
# updated automatically every frame) to compute orbiting positions entirely
# on the GPU. No DrawCallback, no CPU math, no extra Python code.
#
# Each light orbits at a different speed, radius, and Z height, with a
# 120° phase offset (2*PI/3 ≈ 2.094 rad) so they spread evenly.
# A subtle sine pulse on each light's intensity gives a breathing quality.

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
	vPosition   = eyePos.xyz;
	vUV         = osg_MultiTexCoord0;

	vec3 N = normalize(osg_NormalMatrix * osg_Normal);
	vec3 T = normalize(osg_NormalMatrix * osg_Tangent.xyz);
	T = normalize(T - dot(T, N) * N);
	vec3 B = cross(N, T) * osg_Tangent.w;

	vNGeom = N;
	vT     = T;
	vB     = B;

	gl_Position = osg_ModelViewProjectionMatrix * osg_Vertex;
}
"""

FRAGMENT_SHADER = """
#version 460 core

#define NUM_LIGHTS 3
const float PI     = 3.14159265359;
const float TWO_PI = 6.28318530718;

in vec3 vT;
in vec3 vB;
in vec3 vNGeom;
in vec3 vPosition;
in vec2 vUV;

uniform sampler2D baseColorTex;
uniform sampler2D normalTex;
uniform sampler2D ormTex;
uniform sampler2D emissiveTex;

uniform vec3  emissiveFactor;
uniform float scanlineFreq;
uniform float scanlineStrength;
uniform vec3  skyColor;
uniform vec3  groundColor;

uniform mat4  osg_ViewMatrix;
uniform float osg_SimulationTime;

uniform vec3  lightColor[NUM_LIGHTS];
uniform float lightRadius[NUM_LIGHTS];

out vec4 fragColor;

float D_GGX(float NdotH, float roughness) {
	float a  = roughness * roughness;
	float a2 = a * a;
	float d  = NdotH * NdotH * (a2 - 1.0) + 1.0;
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

vec3 F_Schlick(float HdotV, vec3 F0) {
	return F0 + (1.0 - F0) * pow(1.0 - HdotV, 5.0);
}

void main() {
	mat3 TBN = mat3(normalize(vT), normalize(vB), normalize(vNGeom));
	vec3 nMap = texture(normalTex, vUV).rgb * 2.0 - 1.0;
	vec3 N    = normalize(TBN * nMap);
	vec3 V    = normalize(-vPosition);

	vec3  albedo    = texture(baseColorTex, vUV).rgb;
	float ao        = texture(ormTex, vUV).r;
	float roughness = texture(ormTex, vUV).g;
	float metallic  = texture(ormTex, vUV).b;

	vec3 F0 = mix(vec3(0.04), albedo, metallic);
	vec3 Lo = vec3(0.0);

	float t = osg_SimulationTime;

	// Animated world-space light positions: three lights orbiting at different
	// speeds, radii, and heights, evenly phased 120° apart.
	vec3 lPos[NUM_LIGHTS];
	lPos[0] = vec3(cos(t * 0.8)              * 1.0,  sin(t * 0.8)              * 1.0,  0.8);
	lPos[1] = vec3(cos(t * 0.5 + TWO_PI/3.0) * 0.9,  sin(t * 0.5 + TWO_PI/3.0) * 0.9,  0.3);
	lPos[2] = vec3(cos(t * 0.3 + TWO_PI/1.5) * 0.7,  sin(t * 0.3 + TWO_PI/1.5) * 0.7, -0.2);

	// Subtle breathing pulse per light, out of phase with each other.
	float pulse[NUM_LIGHTS];
	pulse[0] = 0.8 + 0.2 * sin(t * 1.3);
	pulse[1] = 0.8 + 0.2 * sin(t * 0.9 + 1.0);
	pulse[2] = 0.8 + 0.2 * sin(t * 0.6 + 2.1);

	for (int i = 0; i < NUM_LIGHTS; i++) {
		vec3  lEye  = (osg_ViewMatrix * vec4(lPos[i], 1.0)).xyz;
		vec3  lVec  = lEye - vPosition;
		float dist  = length(lVec);
		vec3  L     = lVec / dist;

		float r     = lightRadius[i];
		float atten = 1.0 / (1.0 + (dist * dist) / (r * r));

		vec3  H     = normalize(L + V);
		float NdotL = max(dot(N, L), 0.0);
		float NdotV = max(dot(N, V), 0.0);
		float NdotH = max(dot(N, H), 0.0);
		float HdotV = max(dot(H, V), 0.0);

		float D = D_GGX(NdotH, roughness);
		float G = G_Smith(NdotV, NdotL, roughness);
		vec3  F = F_Schlick(HdotV, F0);

		vec3 kD = (vec3(1.0) - F) * (1.0 - metallic);

		vec3 diffuse  = kD * albedo / PI;
		vec3 specular = (D * G * F) / max(4.0 * NdotV * NdotL, 0.001);

		Lo += (diffuse + specular) * lightColor[i] * pulse[i] * NdotL * atten;
	}

	vec3  worldUp = normalize(mat3(osg_ViewMatrix) * vec3(0.0, 0.0, 1.0));
	float hemi    = dot(N, worldUp) * 0.5 + 0.5;
	vec3  ambient = mix(groundColor, skyColor, hemi) * albedo * ao;

	vec3 emissive = texture(emissiveTex, vUV).rgb * emissiveFactor;
	float scanline = 0.5 + 0.5 * sin(gl_FragCoord.y * scanlineFreq);
	emissive *= mix(1.0, scanline, scanlineStrength);

	fragColor = vec4(ambient + Lo + emissive, 1.0);
}
"""

if __name__ == "__main__":
	osg.setNotifyLevel(osg.NotifySeverity.NOTICE)

	path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
		os.path.dirname(os.path.abspath(__file__)),
		"data/BoomBox/glTF/BoomBox.gltf"
	)

	root = osgDB.readNodeFile(path)

	p = osg.Program(name="emissive_animated", shaders=(
		osg.Shader(osg.Shader.VERTEX, VERTEX_SHADER),
		osg.Shader(osg.Shader.FRAGMENT, FRAGMENT_SHADER)
	))

	p.bindAttribLocation["osg_Tangent"] = 7

	ss = root.stateSet
	ss.attributes.append(p)

	ss.uniforms["baseColorTex"]      = 0
	ss.uniforms["normalTex"]         = 1
	ss.uniforms["ormTex"]            = 2
	ss.uniforms["emissiveTex"]       = 3
	ss.uniforms["emissiveFactor"]    = osg.Vec3(1.0, 1.0, 1.0)
	ss.uniforms["scanlineFreq"]      = 1.5
	ss.uniforms["scanlineStrength"]  = 0.5
	ss.uniforms["skyColor"]          = osg.Vec3(0.15, 0.20, 0.35)
	ss.uniforms["groundColor"]       = osg.Vec3(0.12, 0.08, 0.05)

	# lightPos is gone — computed from osg_SimulationTime in the shader.
	lightColor = osg.Uniform(osg.Uniform.Type.FLOAT_VEC3, "lightColor", 3)
	lightColor[0] = osg.Vec3(1.0, 0.9, 0.7)   # warm key
	lightColor[1] = osg.Vec3(0.3, 0.5, 1.0)   # cool fill
	lightColor[2] = osg.Vec3(1.0, 0.4, 0.2)   # warm back

	lightRadius = osg.Uniform(osg.Uniform.Type.FLOAT, "lightRadius", 3)
	lightRadius[0] = 5.0
	lightRadius[1] = 1.8
	lightRadius[2] = 1.5

	ss.uniforms.extend((lightColor, lightRadius))

	v = osgViewer.Viewer()
	v.sceneData = root
	v.cameraManipulator = osgGA.TrackballManipulator()

	while not v.done:
		v.frame()
