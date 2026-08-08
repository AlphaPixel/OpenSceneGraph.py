#!/usr/bin/env python3
#vimrun! python3 ../examples/pyosg-lighting-4-basecolor.py ../examples/data/BoomBox/glTF/BoomBox.gltf

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

# One change from step 3: replace the flat `albedo` uniform with the model's
# actual base color texture.
#
# The GLTF loader already bound the base color texture to unit 0 on each
# geometry's stateSet. Our program sits on the root stateSet; OSG accumulates
# state root->leaf, so both are active when the geometry renders. We just need
# to tell the fragment shader which unit to sample and pass UV coordinates
# through from the vertex shader.
#
# `osg_MultiTexCoord0` is the OSG built-in alias for TEXCOORD_0 -- the same
# attribute the loader stored via setTexCoordArray(0, ...).

VERTEX_SHADER = """
#version 460 core

in vec4 osg_Vertex;
in vec3 osg_Normal;
in vec2 osg_MultiTexCoord0;

uniform mat4 osg_ModelViewProjectionMatrix;
uniform mat4 osg_ModelViewMatrix;
uniform mat3 osg_NormalMatrix;

out vec3 vNormal;
out vec3 vPosition;
out vec2 vUV;

void main() {
	vec4 eyePos = osg_ModelViewMatrix * osg_Vertex;

	vPosition = eyePos.xyz;
	vNormal = normalize(osg_NormalMatrix * osg_Normal);
	vUV = osg_MultiTexCoord0;

	gl_Position = osg_ModelViewProjectionMatrix * osg_Vertex;
}
"""

FRAGMENT_SHADER = """
#version 460 core

#define NUM_LIGHTS 3

in vec3 vNormal;
in vec3 vPosition;
in vec2 vUV;

uniform sampler2D baseColorTex;
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
	vec3 N = normalize(vNormal);
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

	p = osg.Program(name="basecolor", shaders=(
		osg.Shader(osg.Shader.VERTEX, VERTEX_SHADER),
		osg.Shader(osg.Shader.FRAGMENT, FRAGMENT_SHADER)
	))

	ss = root.stateSet

	ss.attributes.append(p)

	# The texture is on the geometry's stateSet (bound by the GLTF loader).
	# We just tell the shader which unit to sample -- OSG state inheritance
	# makes it visible at render time.
	ss.uniforms["baseColorTex"] = 0

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
