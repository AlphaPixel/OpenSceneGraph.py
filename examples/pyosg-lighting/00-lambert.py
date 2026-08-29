#!/usr/bin/env python3

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

# Lambert diffuse: the simplest physically-motivated lighting model.
#
# The only thing determining brightness is the angle between the surface normal
# and the incoming light direction. Surfaces facing the light are bright;
# surfaces perpendicular to it are dark; surfaces facing away are pure black.
#
# There is intentionally NO ambient term here. That pitch-black dark side is
# not a bug - it is what Lambert alone gives you, and it is the baseline we
# will improve in subsequent examples.

VERTEX_SHADER = """
#version 460 core

in vec4 osg_Vertex;
in vec3 osg_Normal;

uniform mat4 osg_ModelViewProjectionMatrix;
uniform mat3 osg_NormalMatrix;
uniform mat4 osg_ViewMatrix;

uniform vec3 lightDir;

out vec3 vNormal;
out vec3 vLightDir;

void main() {
	// osg_NormalMatrix is the inverse-transpose of the upper-left 3x3 of the
	// ModelView matrix, which correctly handles non-uniform scaling.
	vNormal = normalize(osg_NormalMatrix * osg_Normal);

	// lightDir arrives as a world-space direction. We rotate it into eye space
	// so the light stays fixed in the world as the camera orbits the model.
	vLightDir = normalize(mat3(osg_ViewMatrix) * lightDir);

	gl_Position = osg_ModelViewProjectionMatrix * osg_Vertex;
}
"""

FRAGMENT_SHADER = """
#version 460 core

in vec3 vNormal;
in vec3 vLightDir;

uniform vec3 albedo;
uniform vec3 lightColor;

out vec4 fragColor;

void main() {
	vec3 N = normalize(vNormal);

	// The Lambert term: how much light hits this surface.
	// clamp to [0, 1] - negative means the surface faces away from the light.
	float diff = max(dot(N, vLightDir), 0.0);

	fragColor = vec4(albedo * lightColor * diff, 1.0);
}
"""

if __name__ == "__main__":
	osg.setNotifyLevel(osg.NotifySeverity.NOTICE)

	path = resolve_model(sys.argv[1] if len(sys.argv) > 1 else "BoomBox")

	if not path:
		sys.exit("Cannot find model -- clone glTF-Sample-Assets into your OSG_FILE_PATH checkout")

	root = osgDB.readNodeFile(path)

	p = osg.Program(name="lambert", shaders=(
		osg.Shader(osg.Shader.VERTEX, VERTEX_SHADER),
		osg.Shader(osg.Shader.FRAGMENT, FRAGMENT_SHADER)
	))

	ss = root.stateSet

	ss.attributes.append(p)

	# World-space light direction (not required to be unit-length; VS normalizes it).
	ss.uniforms["lightDir"] = osg.Vec3(0.5, 0.5, 1.0)

	# Try changing these to see the raw effect of the Lambert term.
	ss.uniforms["lightColor"] = osg.Vec3(1.0, 1.0, 1.0)
	ss.uniforms["albedo"] = osg.Vec3(0.8, 0.7, 0.6)

	v = osgViewer.Viewer()
	v.sceneData = root
	v.cameraManipulator = osgGA.TrackballManipulator()

	while not v.done:
		v.frame()
