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

# Blinn-Phong: three additions on top of Lambert.
#
# 1. Ambient - a constant lift so the dark side is never pitch-black. This is a hack (real ambient
# is the integral of all incoming light), but it's cheap and surprisingly effective.
#
# 2. Specular via the halfway vector H = normalize(L + V). H is the surface normal a microfacet
# would need to have to perfectly mirror L toward V. Using H (Blinn) instead of the pure reflection
# vector (Phong) is both faster and more physically plausible.
#
# 3. Eye-space position passed from VS -> FS so we can compute V per-fragment.

VERTEX_SHADER = """
#version 460 core

in vec4 osg_Vertex;
in vec3 osg_Normal;

uniform mat4 osg_ModelViewProjectionMatrix;
uniform mat4 osg_ModelViewMatrix;
uniform mat3 osg_NormalMatrix;
uniform mat4 osg_ViewMatrix;

uniform vec3 lightDir;

out vec3 vNormal;
out vec3 vPosition;
out vec3 vLightDir;

void main() {
	vec4 eyePos = osg_ModelViewMatrix * osg_Vertex;

	vPosition = eyePos.xyz;
	vNormal = normalize(osg_NormalMatrix * osg_Normal);
	vLightDir = normalize(mat3(osg_ViewMatrix) * lightDir);

	gl_Position = osg_ModelViewProjectionMatrix * osg_Vertex;
}
"""

FRAGMENT_SHADER = """
#version 460 core

in vec3 vNormal;
in vec3 vPosition;
in vec3 vLightDir;

uniform vec3 albedo;
uniform vec3 lightColor;
uniform vec3 specularColor;
uniform float ambient;
uniform float shininess;

out vec4 fragColor;

void main() {
	vec3 N = normalize(vNormal);
	vec3 L = vLightDir;

	// View direction: from the fragment toward the camera (eye is at origin in eye space).
	vec3 V = normalize(-vPosition);

	// Halfway vector: the normal a perfect mirror surface would need to redirect L toward V.
	// Higher shininess = tighter, more mirror-like highlight.
	vec3 H = normalize(L + V);
	float diff = max(dot(N, L), 0.0);
	float spec = pow(max(dot(N, H), 0.0), shininess);

	vec3 result = albedo * (ambient + lightColor * diff) + specularColor * lightColor * spec;

	fragColor = vec4(result, 1.0);
}
"""

def build_scene(w, h):
	path = resolve_model(sys.argv[1] if len(sys.argv) > 1 else "BoomBox")

	if not path:
		sys.exit("Cannot find model -- clone glTF-Sample-Assets into your OSG_FILE_PATH checkout")

	root = osgDB.readNodeFile(path)

	p = osg.Program(name="blinnphong", shaders=(
		osg.Shader(osg.Shader.VERTEX, VERTEX_SHADER),
		osg.Shader(osg.Shader.FRAGMENT, FRAGMENT_SHADER)
	))

	ss = root.stateSet
	ss.attributes.append(p)

	ss.uniforms["lightDir"] = osg.Vec3(0.5, 0.5, 1.0)
	ss.uniforms["lightColor"] = osg.Vec3(1.0, 1.0, 1.0)
	ss.uniforms["albedo"] = osg.Vec3(0.8, 0.7, 0.6)
	ss.uniforms["specularColor"] = osg.Vec3(0.5, 0.5, 0.5)
	ss.uniforms["ambient"] = 0.1
	ss.uniforms["shininess"] = 32.0

	return root

if __name__ == "__main__":
	osg.setNotifyLevel(osg.NotifySeverity.NOTICE)

	v = osgViewer.Viewer()

	v.sceneData = build_scene(*window_size())
	v.cameraManipulator = osgGA.TrackballManipulator()

	while not v.done:
		v.frame()
