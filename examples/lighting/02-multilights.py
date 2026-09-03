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

# Two additions on top of Blinn-Phong:
#
# 1. Point lights - each light now has a world-space POSITION instead of a
# direction. The per-fragment light vector L must be computed from
# (lightPos - fragmentPos), and its length gives us the distance.
#
# 2. Attenuation - light energy falls off with distance. We use an
# inverse-square form normalized by a radius parameter:
#
# atten = 1 / (1 + dist2 / radius2)
#
# At dist=0, atten=1.0. At dist=radius, atten=0.5. Intuitive to tune.
#
# The lights below are a classic cinematography "three-point" setup:
#
# key - main bright warm light, defines primary shape
# fill - cool, dimmer, fills the shadow side without flattening it
# back - warm accent behind/below, lifts the back edge off the background

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
uniform float ambient;
uniform float shininess;

// OSG built-in -- gives us world->eye transform for light positions.
uniform mat4 osg_ViewMatrix;

uniform vec3 lightPos[NUM_LIGHTS]; // world space
uniform vec3 lightColor[NUM_LIGHTS];
uniform float lightRadius[NUM_LIGHTS]; // dist at which intensity halves

out vec4 fragColor;

void main() {
	vec3 N = normalize(vNormal);
	vec3 V = normalize(-vPosition);

	// Start with ambient -- independent of all lights.
	vec3 result = albedo * ambient;

	for (int i = 0; i < NUM_LIGHTS; i++) {
		// Transform light position from world space into eye space to match vPosition.
		vec3 lEye = (osg_ViewMatrix * vec4(lightPos[i], 1.0)).xyz;
		vec3 lVec = lEye - vPosition;
		float dist = length(lVec);
		vec3 L = lVec / dist;

		float r = lightRadius[i];
		float atten = 1.0 / (1.0 + (dist * dist) / (r * r));

		vec3 H = normalize(L + V);
		float diff = max(dot(N, L), 0.0);
		float spec = pow(max(dot(N, H), 0.0), shininess);

		result += (albedo * diff + specularColor * spec) * lightColor[i] * atten;
	}

	fragColor = vec4(result, 1.0);
}
"""

def build_scene(w, h):
	path = resolve_model(sys.argv[1] if len(sys.argv) > 1 else "BoomBox")

	if not path:
		sys.exit("Cannot find model -- clone glTF-Sample-Assets into your OSG_FILE_PATH checkout")

	root = osgDB.readNodeFile(path)

	p = osg.Program(name="multilights", shaders=(
		osg.Shader(osg.Shader.VERTEX, VERTEX_SHADER),
		osg.Shader(osg.Shader.FRAGMENT, FRAGMENT_SHADER)
	))

	ss = root.stateSet

	ss.attributes.append(p)

	ss.uniforms["albedo"] = osg.Vec3(0.8, 0.7, 0.6)
	ss.uniforms["specularColor"] = osg.Vec3(0.5, 0.5, 0.5)
	ss.uniforms["ambient"] = 0.04
	ss.uniforms["shininess"] = 64.0

	# Three-point lighting setup: key (warm), fill (cool), back/rim (warm accent).
	lightPos = osg.Uniform(osg.Uniform.Type.FLOAT_VEC3, "lightPos", (
		osg.Vec3( 0.8, 0.6, 1.0),
		osg.Vec3(-0.8, 0.3, 0.5),
		osg.Vec3( 0.0, -0.6, 0.2)
	))

	# Or, you can use this syntax!
	lightColor = osg.Uniform(osg.Uniform.Type.FLOAT_VEC3, "lightColor", 3)
	lightColor[0] = osg.Vec3(1.0, 0.9, 0.7)
	lightColor[1] = osg.Vec3(0.3, 0.5, 1.0)
	lightColor[2] = osg.Vec3(1.0, 0.5, 0.2)

	# But really, we prefer this syntax, don't we?
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
