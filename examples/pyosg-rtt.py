#!/usr/bin/env python3
#vimrun! ../examples/pyosg-rtt.py

import os
import time

os.environ.update({
	"OSG_WINDOW": "50 50 800 600",
	"OSG_THREADING": "SingleThreaded",
	"OSG_GL_CONTEXT_PROFILE_MASK": "2",
	"OSG_GL_VERSION": "4.6",
	"OSG_GL_CONTEXT_VERSION": "4.6"
})

from OpenSceneGraph import *
from OpenSceneGraph.GL import *

SCENE_VERTEX_SHADER = """
#version 330 core

in vec4 osg_Vertex;
in vec4 osg_Color;
in vec3 osg_Normal;
in vec2 osg_TexCoord0;

uniform mat4 osg_ModelViewProjectionMatrix;
uniform mat4 osg_ModelViewMatrix;
uniform mat4 osg_ProjectionMatrix;
uniform mat3 osg_NormalMatrix;

out vec4 vColor;
out vec3 vNormal;
out vec3 vPosition;
// out vec2 uv;
out mat4 ProjectionMatrix;

void main() {
	vec4 posEye = osg_ModelViewMatrix * osg_Vertex;

	vPosition = posEye.xyz;
	vNormal = normalize(osg_NormalMatrix * osg_Normal);
	vColor = osg_Color;
	// uv = osg_TexCoord0;
	ProjectionMatrix = osg_ProjectionMatrix;

	gl_Position = osg_ModelViewProjectionMatrix * osg_Vertex;
}
"""

SCENE_FRAGMENT_SHADER = """
#version 330 core

in vec4 vColor;
in vec3 vNormal;
in vec3 vPosition;

out vec4 color;

void main() {
	const vec3 L = vec3(0.268, 0.358, 0.894);
	const vec3 rimColor = vec3(0.9, 0.6, 0.0);
	const float rimPower = 5.0;
	const float rimBase = 0.3;
	const float rimTint = 0.4;

	vec3 N = normalize(vNormal);

	float diffuse = max(dot(N, L), 0.0);
	float ambient = 0.25;
	float light = ambient + diffuse;

	vec3 viewDir = normalize(-vPosition);

	float rim = pow(1.0 - clamp(dot(N, viewDir), 0.0, 1.0), rimPower);

	vec3 rimLight = rim * (vec3(rimBase) + rimColor * rimTint);

	color = vec4(vColor.rgb * light + rimLight, vColor.a);
}
"""

HUD_VERTEX_SHADER = """
#version 330 core

// uniform mat4 osg_ProjectionMatrix;

in vec4 osg_Vertex;
// in vec2 osg_TexCoord0;
in vec2 osg_MultiTexCoord0;

out vec2 uv;
// out mat4 ProjectionMatrix;

void main() {
	// uv = osg_TexCoord0;
	uv = osg_MultiTexCoord0;
	// ProjectionMatrix = osg_ProjectionMatrix;

	gl_Position = osg_Vertex;
}
"""

HUD_FRAGMENT_SHADER = """
#version 330 core

uniform sampler2D colorTex;
uniform sampler2D depthTex;
uniform float znear;
uniform float zfar;
uniform mat4 projMat;

in vec2 uv;
// in mat4 ProjectionMatrix;

out vec4 color;

// Convert depth buffer value -> camera-space Z distance.
float linearizeDepth(float d, float near, float far) {
	float z = d * 2.0 - 1.0;

	return (2.0 * near * far) / (far + near - z * (far - near));
}

// Convert depth -> stable [0..1] visualization using absolute far plane.
//
// Good for visualizing things for debugging, but not PRACTICAL.
float visualizeAbsoluteDepth(float depth, float near, float far) {
	return linearizeDepth(depth, near, far) / far;
}

// Convert depth -> [0..1] relative to current near/far range.
//
// This is the standard, useful way to work with depth.
float normalizeDepthToFrustum(float depth, float near, float far) {
	float z = linearizeDepth(depth, near, far);

	return (z - near) / (far - near);
}

// ===============================================================================
// This only works on non-inversed (normal) projection matrices!
float extractNear(mat4 proj) {
	float A = proj[2][2];
	float B = proj[2][3];

	return B / (A - 1.0);
}

// This only works on non-inversed (normal) projection matrices!
float extractFar(mat4 proj) {
	float A = proj[2][2];
	float B = proj[2][3];

	return B / (A + 1.0);
}

float visualizeAbsoluteDepth_test(float depth, mat4 proj) {
	float near = extractNear(proj);
	float far = extractFar(proj);
	float z = linearizeDepth(depth, near, far);

	return z / far;
}
// ===============================================================================

void main_depth_pos()
{
	float depth = texture(depthTex, uv).r;

	vec4 clip = vec4(
		uv * 2.0 - 1.0,
		depth * 2.0 - 1.0,
		1.0
	);

	mat4 invProj = inverse(projMat);
	vec4 view = invProj * clip;
	vec3 viewPos = view.xyz / view.w;

	float z = -viewPos.z;

	color = vec4(vec3(z / 32.0), 1.0);
}

void main_depth() {
	float d = texture(depthTex, uv).r;

	color = vec4(visualizeAbsoluteDepth(d, znear, zfar));
	// color = vec4(normalizeDepthToFrustum(d, znear, zfar));
	// color = vec4(visualizeAbsoluteDepth_test(d, projMat));
}

void main() {
	// main_depth(); return;

	float d = texture(depthTex, uv).r;
	vec4 c = texture(colorTex, uv);

	// Ignore background pixels
	if (d >= 1.0) {
		color = c;
		return;
	}

	float z = linearizeDepth(d, 1.0, 10000.0);
	float fog = clamp(z / 10000.0, 0.0, 1.0);
	vec4 fogColor = vec4(0.6, 0.7, 0.9, 1.0);
	color = mix(c, fogColor, fog);
}
"""

def create_scene():
	g = osg.Geode(drawables=(
		osg.ShapeDrawable(osg.Sphere(osg.Vec3(0, 2.0, 0), 1.0)),
		osg.ShapeDrawable(osg.Sphere(osg.Vec3(0, 5.0, 0), 1.5)),
		osg.ShapeDrawable(osg.Sphere(osg.Vec3(0, 8.0, 0), 2.0)),
		osg.ShapeDrawable(osg.Sphere(osg.Vec3(0, 12.0, 0), 3.0))
	))

	p = osg.Program(name="sceneProgram")

	p.shaders.append(osg.Shader(osg.Shader.VERTEX, SCENE_VERTEX_SHADER))
	p.shaders.append(osg.Shader(osg.Shader.FRAGMENT, SCENE_FRAGMENT_SHADER))

	g.stateSet.setAttributeAndModes(p)

	return g

def create_rtt_camera():
	s = 512
	cb = osg.Texture2D()
	db = osg.Texture2D()

	cb.size = (s, s)
	cb.internalFormat = GL_RGBA
	cb.filter = (osg.Texture.LINEAR, osg.Texture.LINEAR)

	db.size = (s, s)
	db.internalFormat = GL_DEPTH_COMPONENT24
	db.sourceFormat = GL_DEPTH_COMPONENT
	db.sourceType = GL_FLOAT
	db.filter = (osg.Texture.NEAREST, osg.Texture.NEAREST)

	rttCam = osg.Camera()

	rttCam.renderOrder = osg.Camera.PRE_RENDER
	rttCam.renderTargetImplementation = osg.Camera.FRAME_BUFFER_OBJECT
	rttCam.clearMask = GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT
	rttCam.clearColor = osg.Vec4(0.1, 0.5, 0.2, 1.0)
	rttCam.viewport = osg.Viewport(0, 0, s, s)
	rttCam.name = "RTT Camera"

	rttCam.attach(osg.Camera.COLOR_BUFFER, cb)
	rttCam.attach(osg.Camera.DEPTH_BUFFER, db)
	rttCam.children.append(create_scene())

	return rttCam, cb, db

def create_hud_camera(cb, db):
	hudCam = osg.Camera()

	hudCam.referenceFrame = osg.Transform.ABSOLUTE_RF
	hudCam.renderOrder = osg.Camera.POST_RENDER
	hudCam.clearMask = 0
	hudCam.allowEventFocus = False
	hudCam.projectionMatrix = osg.Matrix.identity()
	hudCam.viewMatrix = osg.Matrix.identity()
	hudCam.name = "HUD Camera"

	g = osg.Geode()

	g.drawables.append(osg.createTexturedQuadGeometry(
		osg.Vec3(-1.0, -1.0, -1.0),
		osg.Vec3(2.0, 0.0, 0.0),
		osg.Vec3(0.0, 2.0, 0.0)
	))

	hudCam.children.append(g)

	hudCam.stateSet.setTextureAttributeAndModes(0, cb)
	hudCam.stateSet.setTextureAttributeAndModes(1, db)
	hudCam.stateSet.addUniform(osg.Uniform("colorTex", 0));
	hudCam.stateSet.addUniform(osg.Uniform("depthTex", 1));

	p = osg.Program(name="hudProgram", shaders=(
		osg.Shader(osg.Shader.VERTEX, HUD_VERTEX_SHADER),
		osg.Shader(osg.Shader.FRAGMENT, HUD_FRAGMENT_SHADER)
	))

	g.stateSet.setAttributeAndModes(p)

	return hudCam

if __name__ == "__main__":
	osg.setNotifyLevel(osg.NotifySeverity.NOTICE)

	v = osgViewer.Viewer()
	r = osg.Group()

	rttCam, cb, db = create_rtt_camera()
	hudCam = create_hud_camera(cb, db)

	r.children.extend((rttCam, hudCam))

	znear = osg.Uniform("znear", 0.0)
	zfar = osg.Uniform("zfar", 0.0)
	proj = osg.Uniform("projMat", osg.Matrixf.identity())

	hudCam.stateSet.addUniform(znear)
	hudCam.stateSet.addUniform(zfar)
	hudCam.stateSet.addUniform(proj)

	def update_uniforms(ri):
		pm = ri.state.projectionMatrix

		osg.notice(f"update_uniforms: {pm}")

		fovy, aspect, near, far = pm.getPerspective()

		# OSG ALWAYS treats uniforms as ARRAYS (and only "pretends" to be scalar with a API
		# that abstracts access to the `[0]` index. However, Python supports using either of the
		# following methods for update:
		#
		# znear[0] = float(near)
		# zfar[0] = float(far)
		# proj[0] = osg.Matrixf(pm)

		# Even though this LOOKS like setting a "scalar", the `.value` property is just a wrapper
		# around using the style above!
		znear.value = float(near)
		zfar.value = float(far)
		proj.value = osg.Matrixf(pm)

	v.sceneData = r
	v.cameraManipulator = osgGA.TrackballManipulator()
	v.camera.preDrawCallback = update_uniforms

	while not v.done:
		v.frame()

		time.sleep(0.1)

# import IPython

# IPython.embed()
