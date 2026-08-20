#!/usr/bin/env python3
#vimrun! python3 01-blinnphong.py

import sys
import os
import pathlib

os.environ.update({
	"OSG_WINDOW": "50 50 800 600",
	"OSG_THREADING": "SingleThreaded",
	"OSG_GL_CONTEXT_PROFILE_MASK": "1",
	"OSG_GL_VERSION": "4.6",
	"OSG_GL_CONTEXT_VERSION": "4.6"
})

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

if __name__ == "__main__":
	osg.setNotifyLevel(osg.NotifySeverity.NOTICE)

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

	v = osgViewer.Viewer()
	v.sceneData = root
	v.cameraManipulator = osgGA.TrackballManipulator()

	while not v.done:
		v.frame()
