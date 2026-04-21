#!/usr/bin/env python3
#vimrun! ../examples/pyosg-rtt.py

import os
import time

# You might want to tweak or override these for your environment. However,
# modifying the `OSG_THREADING` variable isn't advised, as properly interacting
# with the Python GIL is notoriously difficult to do. You'll have MUCH better
# luck using Python's `async/await` support (and other examples demonstrate
# doing exactly that).
os.environ.update({
	"OSG_WINDOW": "50 50 800 600",
	"OSG_THREADING": "SingleThreaded",
	"OSG_GL_CONTEXT_PROFILE_MASK": "1",
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

uniform mat4 osg_ModelViewProjectionMatrix;
uniform mat4 osg_ModelViewMatrix;
uniform mat4 osg_ProjectionMatrix;
uniform mat3 osg_NormalMatrix;

out vec4 vColor;
out vec3 vNormal;
out vec3 vPosition;

void main() {
	vec4 posEye = osg_ModelViewMatrix * osg_Vertex;

	vPosition = posEye.xyz;
	vNormal = normalize(osg_NormalMatrix * osg_Normal);
	vColor = osg_Color;

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

in vec4 osg_Vertex;
in vec2 osg_MultiTexCoord0;

out vec2 uv;

void main() {
	uv = osg_MultiTexCoord0;

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

void main_depth_pos() {
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
	main_depth(); return;

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

# Create the actual 3D scene you're interested in manipulating! This function has
# no awareness of an RTT setup; it simply creates the scene and returns it. You
# could, for example, set the returned `Node` as `viewer.sceneData` directly and
# view it OUTSIDE of the RTT pipeline.
def create_scene():
	g = osg.Geode(drawables=(
		osg.ShapeDrawable(osg.Sphere(osg.Vec3(0, 2.0, 0), 1.0)),
		osg.ShapeDrawable(osg.Sphere(osg.Vec3(0, 5.0, 0), 1.5)),
		osg.ShapeDrawable(osg.Sphere(osg.Vec3(0, 8.0, 0), 2.0)),
		osg.ShapeDrawable(osg.Sphere(osg.Vec3(0, 12.0, 0), 3.0))
	))

	p = osg.Program(name="sceneProgram")

	# Similar to `Group.children`, MOST THINGS in OSG.py that "behave" like sequences
	# in C++ are wrapped with sequence-like "proxies" in Python (and support all of
	# the official "Sequence Protocol" behaviors a Python programmer would expect)!
	p.shaders.append(osg.Shader(osg.Shader.VERTEX, SCENE_VERTEX_SHADER))
	p.shaders.append(osg.Shader(osg.Shader.FRAGMENT, SCENE_FRAGMENT_SHADER))

	g.stateSet.setAttributeAndModes(p)

	return g

# Create the RTT (Render To Texture) `Camera` instance using the specified width/height
# dimensions. Any children attached to this instance will be rendered using the attached
# color buffer and depth buffers, which we will later query in a secondary "HUD" `Camera`.
#
# NOTE: In addition to the `Camera`, this function also returns the color/depth buffer
# `Texture` instances, which the "HUD" will need in order to directly "sample" from them
# in its own shader pipeline.
def create_rtt_camera(w=512, h=512):
	cb = osg.Texture2D()
	db = osg.Texture2D()

	cb.size = (w, h)
	cb.internalFormat = GL_RGBA
	cb.filter = (osg.Texture.LINEAR, osg.Texture.LINEAR)

	db.size = (w, h)
	db.internalFormat = GL_DEPTH_COMPONENT24
	db.sourceFormat = GL_DEPTH_COMPONENT
	db.sourceType = GL_FLOAT
	db.filter = (osg.Texture.NEAREST, osg.Texture.NEAREST)

	cam = osg.Camera()

	cam.renderOrder = osg.Camera.PRE_RENDER
	cam.renderTargetImplementation = osg.Camera.FRAME_BUFFER_OBJECT
	cam.clearMask = GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT
	cam.clearColor = osg.Vec4(0.1, 0.5, 0.2, 1.0)
	cam.viewport = osg.Viewport(0, 0, w, h)
	cam.name = "RTT Camera"

	cam.attach(osg.Camera.COLOR_BUFFER, cb)
	cam.attach(osg.Camera.DEPTH_BUFFER, db)

	return cam, cb, db

# Creates a special "HUD" `Camera` using the specified color/depth `Texture` arguments.
# These types of cameras typically access one or more "sources" (the buffer/texture
# attachments) to "composite" a scene within a screen-aligned, NDC quad. This process
# forms the basis for "Render To Texture", and once your "HUD" `Camera` has access
# to the raw buffers in its shader pipeline (via `sampler2d` or similar in GLSL), all
# kinds of cool techniques open up!
def create_hud_camera(cb, db):
	cam = osg.Camera()

	cam.referenceFrame = osg.Transform.ABSOLUTE_RF
	cam.renderOrder = osg.Camera.POST_RENDER
	cam.clearMask = 0
	cam.allowEventFocus = False
	cam.projectionMatrix = osg.Matrix.identity()
	cam.viewMatrix = osg.Matrix.identity()
	cam.name = "HUD Camera"

	g = osg.Geode()

	# We use the OSG helper here, passing in width/height arguments that result in a
	# screen aligned, full-sized NDC ("Normalized Device Coordinates") quad. This is
	# sometimes referred to as "clip space", as well as a handful of other names.
	g.drawables.append(osg.createTexturedQuadGeometry(
		osg.Vec3(-1.0, -1.0, -1.0),
		osg.Vec3(2.0, 0.0, 0.0),
		osg.Vec3(0.0, 2.0, 0.0)
	))

	cam.children.append(g)

	cam.stateSet.setTextureAttributeAndModes(0, cb)
	cam.stateSet.setTextureAttributeAndModes(1, db)

	cam.stateSet.uniforms["colorTex"] = 0
	cam.stateSet.uniforms["depthTex"] = 1

	# cam.stateSet.addUniform(osg.Uniform("colorTex", 0))
	# cam.stateSet.addUniform(osg.Uniform("depthTex", 1))
	# cam.stateSet.uniforms.extend((
	# 	osg.Uniform("colorTex", 0),
	# 	osg.Uniform("depthTex", 1)
	# ))

	# Most properties on OSG.py objects can OPTIONALLY be set during creation using
	# keyword arguments; key/value pairs are passed down the entire inheritance chain,
	# and each object's constructor chooses which key/value pairs are appropriate for it.
	p = osg.Program(name="hudProgram", shaders=(
		osg.Shader(osg.Shader.VERTEX, HUD_VERTEX_SHADER),
		osg.Shader(osg.Shader.FRAGMENT, HUD_FRAGMENT_SHADER)
	))

	g.stateSet.setAttributeAndModes(p)

	return cam

if __name__ == "__main__":
	osg.setNotifyLevel(osg.NotifySeverity.NOTICE)

	v = osgViewer.Viewer()
	r = osg.Group()

	rttCam, cb, db = create_rtt_camera(800, 600)
	hudCam = create_hud_camera(cb, db)

	# This is how the RTT camera "knows" what to render...
	rttCam.children.append(create_scene())

	r.children.extend((rttCam, hudCam))

	znear = osg.Uniform("znear", 0.0)
	zfar = osg.Uniform("zfar", 0.0)
	proj = osg.Uniform("projMat", osg.Matrixf.identity())

	hudCam.stateSet.uniforms.extend((znear, zfar, proj))

	# This function is used as the `Camera.DrawCallback` for the default `osgViewer.Viewer`
	# camera, and injects the proper near/far Z values into our `Program` state every frame.
	#
	# OSG recomputes the znear/zfar every frame (based on its `CameraManipulator`) so that
	# the resultant depth range has as much precision as possible. MANY post-processing
	# techniques rely on being able to properly query and/or "linearize" depth values, so
	# it's important that you're always working with accurate values.
	def update_uniforms(ri):
		pm = ri.state.projectionMatrix

		# osg.notice(f"update_uniforms: {pm}")

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
		#
		# znear.value = float(near)
		# zfar.value = float(far)
		# proj.value = osg.Matrixf(pm)

		hudCam.stateSet.uniforms["znear"] = float(near)
		hudCam.stateSet.uniforms["zfar"] = float(far)
		hudCam.stateSet.uniforms["proj"] = osg.Matrixf(pm)

	v.sceneData = r
	v.cameraManipulator = osgGA.TrackballManipulator()
	v.camera.preDrawCallback = update_uniforms

	# You could just call `v.run()`, but it's informative to demonstrate different ways of
	# "driving" the redraw/render process.
	while not v.done:
		v.frame()

		time.sleep(0.1)
