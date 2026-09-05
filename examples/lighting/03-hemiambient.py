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
from pyosg_example import window_size, resolve_model

from OpenSceneGraph import *

# One change from step 2: replace the flat ambient constant with a
# HEMISPHERICAL ambient.
#
# Instead of every shadowed surface getting the same grey lift, we lerp
# between two colors based on which way the surface faces:
#
# skyColor - surfaces facing world-up (ceiling, top faces)
# groundColor - surfaces facing world-down (floor, bottom faces)
#
# hemi = dot(N, worldUp) remapped from [-1,1] -> [0,1]
# ambient = mix(groundColor, skyColor, hemi)
#
# This is cheap (one dot product), needs no textures, and immediately makes
# shadowed surfaces look like they're sitting in an environment rather than
# floating in a void.
#
# The world "up" in OSG (after the GLTF loader's Y->Z rotation) is (0,0,1).
# We rotate it into eye space with osg_ViewMatrix so it stays consistent as
# the camera orbits.

VERTEX_SHADER = """
#version 460 core

in vec4 osg_Vertex;
in vec3 osg_Normal;

uniform mat4 osg_ModelViewProjectionMatrix;
uniform mat4 osg_ModelViewMatrix;
uniform mat3 osg_NormalMatrix;

out vec3 vNormal;
out vec3 vPosition;

void main() {
	vec4 eyePos = osg_ModelViewMatrix * osg_Vertex;

	vPosition = eyePos.xyz;
	vNormal = normalize(osg_NormalMatrix * osg_Normal);

	gl_Position = osg_ModelViewProjectionMatrix * osg_Vertex;
}
"""

FRAGMENT_SHADER = """
#version 460 core

#define NUM_LIGHTS 3

in vec3 vNormal;
in vec3 vPosition;

uniform vec3 albedo;
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

	// World up is Z in OSG; bring it into eye space to match our normals.
	vec3 worldUp = normalize(mat3(osg_ViewMatrix) * vec3(0.0, 0.0, 1.0));

	// Remap dot product from [-1, 1] -> [0, 1] for the mix.
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

def build_scene(w, h):
	path = resolve_model(sys.argv[1] if len(sys.argv) > 1 else "BoomBox")

	if not path:
		sys.exit("Cannot find model -- clone glTF-Sample-Assets into your OSG_FILE_PATH checkout")

	root = osgDB.readNodeFile(path)

	p = osg.Program(name="hemiambient", shaders=(
		osg.Shader(osg.Shader.VERTEX, VERTEX_SHADER),
		osg.Shader(osg.Shader.FRAGMENT, FRAGMENT_SHADER)
	))

	ss = root.stateSet

	ss.attributes.append(p)

	ss.uniforms["albedo"] = osg.Vec3(0.8, 0.7, 0.6)
	ss.uniforms["specularColor"] = osg.Vec3(0.5, 0.5, 0.5)
	ss.uniforms["shininess"] = 64.0

	# Sky: cool blue-grey. Ground: warm dark brown. Both intentionally dim so
	# the point lights remain the primary contribution.
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
