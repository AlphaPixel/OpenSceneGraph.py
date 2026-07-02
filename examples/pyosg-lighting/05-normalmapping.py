#!/usr/bin/env python3
#vimrun! python3 ../examples/pyosg-lighting-5-normalmapping.py ../examples/data/BoomBox/glTF/BoomBox.gltf

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

# Normal mapping: replace the smooth per-vertex geometric normal with a
# per-TEXEL normal sampled from a texture.
#
# The normal map stores normals in TANGENT SPACE -- a coordinate frame local
# to each surface point defined by three basis vectors:
#
#   T (Tangent)   -- points along the U axis of the UV map
#   B (Bitangent) -- points along the V axis (computed, not stored directly)
#   N (Normal)    -- the geometric surface normal
#
# The TBN matrix built from these three vectors transforms a tangent-space
# normal into eye space, where all our lighting math already lives.
#
# GLTF 2.0 stores tangents as VEC4: xyz = direction, w = handedness sign
# (+1 or -1) used to compute B = cross(N, T) * w. Never ignore w -- flipped
# UVs will light incorrectly without it.
#
# Loader changes (GLTFReader.h):
#   - TANGENT attribute now routed to setVertexAttribArray(7, ...)
#   - mat.normalTexture bound to texture unit 1
# We bind the name "osg_Tangent" to slot 7 via Program.bindAttribLocation.

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

	// Gram-Schmidt: ensure T is perpendicular to N after interpolation drift.
	T = normalize(T - dot(T, N) * N);

	// w encodes the handedness of the tangent frame -- critical for mirrored UVs.
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

in vec3 vT;
in vec3 vB;
in vec3 vNGeom;
in vec3 vPosition;
in vec2 vUV;

uniform sampler2D baseColorTex;
uniform sampler2D normalTex;
uniform vec3 specularColor;
uniform float shininess;
uniform vec3 skyColor;
uniform vec3 groundColor;

uniform mat4 osg_ViewMatrix;

uniform vec3 lightPos[NUM_LIGHTS];
uniform vec3 lightColor[NUM_LIGHTS];
uniform float lightRadius[NUM_LIGHTS];

out vec4 fragColor;

void main() {
	// TBN transforms tangent-space vectors -> eye space.
	// Re-normalize the interpolated basis vectors to correct for rasterizer drift.
	mat3 TBN = mat3(normalize(vT), normalize(vB), normalize(vNGeom));

	// Decode normal map: [0,1] -> [-1,1], then rotate into eye space.
	vec3 nMap = texture(normalTex, vUV).rgb * 2.0 - 1.0;
	vec3 N = normalize(TBN * nMap);

	vec3 V = normalize(-vPosition);
	vec3 albedo = texture(baseColorTex, vUV).rgb;

	vec3 worldUp = normalize(mat3(osg_ViewMatrix) * vec3(0.0, 0.0, 1.0));
	float hemi = dot(N, worldUp) * 0.5 + 0.5;
	vec3 ambient = mix(groundColor, skyColor, hemi);

	vec3 result = albedo * ambient;

	for (int i = 0; i < NUM_LIGHTS; i++) {
		vec3 lEye = (osg_ViewMatrix * vec4(lightPos[i], 1.0)).xyz;
		vec3 lVec = lEye - vPosition;
		float dist = length(lVec);
		vec3 L = lVec / dist;

		float r = lightRadius[i];
		float atten = 1.0 / (1.0 + (dist * dist) / (r * r));

		vec3 H = normalize(L + V);
		float diff = max(dot(N, L), 0.0);
		float spec = pow(max(dot(N, H), 0.0), shininess);

		result +=
			(albedo * diff +
			 specularColor * spec) * lightColor[i] * atten;
	}

	fragColor = vec4(result, 1.0);
}
"""

if __name__ == "__main__":
	osg.setNotifyLevel(osg.NotifySeverity.NOTICE)

	path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
		os.path.dirname(os.path.abspath(__file__)),
		"data/BoomBox/glTF/BoomBox.gltf"
	)

	root = osgDB.readNodeFile(path)

	p = osg.Program(name="normalmapping", shaders=(
		osg.Shader(osg.Shader.VERTEX, VERTEX_SHADER),
		osg.Shader(osg.Shader.FRAGMENT, FRAGMENT_SHADER)
	))

	# Bind the name "osg_Tangent" to vertex attribute slot 7, which is where
	# GLTFReader now routes the TANGENT accessor via setVertexAttribArray(7, ...).
	p.bindAttribLocation["osg_Tangent"] = 7

	ss = root.stateSet
	ss.setAttributeAndModes(p)

	ss.uniforms["baseColorTex"] = 0
	ss.uniforms["normalTex"] = 1

	ss.uniforms["specularColor"] = osg.Vec3(0.4, 0.4, 0.4)
	ss.uniforms["shininess"] = 64.0
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

	v = osgViewer.Viewer()
	v.sceneData = root
	v.cameraManipulator = osgGA.TrackballManipulator()

	while not v.done:
		v.frame()
