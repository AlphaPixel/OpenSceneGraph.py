#!/usr/bin/env python3
#vimrun! ../examples/pyosg-blur.py

from OpenSceneGraph import *
from OpenSceneGraph.GL import *

import os

W, H = 800, 600

os.environ.update({
	"OSG_WINDOW": f"50 50 {W} {H}",
	"OSG_THREADING": "SingleThreaded",
	"OSG_GL_CONTEXT_PROFILE_MASK": "1",
	"OSG_GL_VERSION": "4.6",
	"OSG_GL_CONTEXT_VERSION": "4.6",
})

FULLSCREEN_VERT = """
#version 330 core

in vec4 osg_Vertex;
in vec2 osg_MultiTexCoord0;

out vec2 uv;

void main() {
	uv = osg_MultiTexCoord0;
	gl_Position = osg_Vertex;
}
"""

BLUR_FRAG_OLD = """
#version 330 core

uniform sampler2D inputTex;
uniform vec2 texelStep;

in vec2 uv;

out vec4 fragColor;

void main() {
	// 9-tap-ish Gaussian weights.
	// Offsets are in units of texelStep, so:
	// horizontal: texelStep = vec2(1.0 / width, 0.0)
	// vertical: texelStep = vec2(0.0, 1.0 / height)

	vec4 sum = vec4(0.0);

	sum += texture(inputTex, uv - 4.0 * texelStep) * 0.0162162162;
	sum += texture(inputTex, uv - 3.0 * texelStep) * 0.0540540541;
	sum += texture(inputTex, uv - 2.0 * texelStep) * 0.1216216216;
	sum += texture(inputTex, uv - 1.0 * texelStep) * 0.1945945946;
	sum += texture(inputTex, uv ) * 0.2270270270;
	sum += texture(inputTex, uv + 1.0 * texelStep) * 0.1945945946;
	sum += texture(inputTex, uv + 2.0 * texelStep) * 0.1216216216;
	sum += texture(inputTex, uv + 3.0 * texelStep) * 0.0540540541;
	sum += texture(inputTex, uv + 4.0 * texelStep) * 0.0162162162;

	fragColor = sum;
}
"""

BLUR_FRAG = """
#version 330 core

uniform sampler2D inputTex;
uniform vec2 texelStep;
// uniform float blurRadius;

in vec2 uv;

out vec4 fragColor;

void main() {
	// vec2 step = texelStep * blurRadius;
	vec2 step = texelStep * 8;

	vec4 sum = vec4(0.0);

	sum += texture(inputTex, uv - 4.0 * step) * 0.0162162162;
	sum += texture(inputTex, uv - 3.0 * step) * 0.0540540541;
	sum += texture(inputTex, uv - 2.0 * step) * 0.1216216216;
	sum += texture(inputTex, uv - 1.0 * step) * 0.1945945946;
	sum += texture(inputTex, uv ) * 0.2270270270;
	sum += texture(inputTex, uv + 1.0 * step) * 0.1945945946;
	sum += texture(inputTex, uv + 2.0 * step) * 0.1216216216;
	sum += texture(inputTex, uv + 3.0 * step) * 0.0540540541;
	sum += texture(inputTex, uv + 4.0 * step) * 0.0162162162;

	fragColor = sum;
}
"""

COMPOSITE_FRAG = """
#version 330 core

uniform sampler2D sceneTex;
uniform sampler2D blurTex;

uniform float glowStrength;

in vec2 uv;

out vec4 fragColor;

void main() {
	vec4 scene = texture(sceneTex, uv);
	vec4 blur = texture(blurTex, uv);

	// Red sensor/display-style tint applied to the original.
	vec3 redScene = scene.rgb * vec3(1.0, 0.28, 0.28);

	// Red glow from blurred image.
	vec3 redGlow = blur.rgb * vec3(1.0, 0.12, 0.08) * glowStrength;

	// Screen-space scanlines.
	float scan = step(0.35, fract(gl_FragCoord.y * 0.25));
	scan = mix(0.72, 1.0, scan);

	// Vignette.
	float d = distance(uv, vec2(0.5));
	float vignette = smoothstep(0.42, 0.12, d);

	vec3 color = (redScene + redGlow) * scan * vignette;

	fragColor = vec4(color, 1.0);
}
"""

def make_color_texture(w, h):
	tex = osg.Texture2D()

	tex.size = (w, h)
	tex.internalFormat = GL_RGBA
	tex.filter = (osg.Texture.LINEAR, osg.Texture.LINEAR)
	tex.wrap = (osg.Texture.CLAMP_TO_EDGE, osg.Texture.CLAMP_TO_EDGE)

	return tex

def make_fullscreen_quad():
	geode = osg.Geode(name="fullscreen-quad")

	geode.drawables.append(osg.createTexturedQuadGeometry(
		osg.Vec3(-1.0, -1.0, -1.0),
		osg.Vec3(2.0, 0.0, 0.0),
		osg.Vec3(0.0, 2.0, 0.0),
	))

	return geode

def make_program(name, vert, frag):
	return osg.Program(name=name, shaders=(
		osg.Shader(osg.Shader.VERTEX, vert),
		osg.Shader(osg.Shader.FRAGMENT, frag),
	))

def make_scene_rtt_pass(output_tex, scene, w, h, name="Scene RTT"):
	cam = osg.Camera()

	cam.name = name
	cam.renderOrder = (osg.Camera.PRE_RENDER, 0)
	cam.renderTargetImplementation = osg.Camera.FRAME_BUFFER_OBJECT
	cam.clearMask = GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT
	# Important for blur/glow: clear to transparent black-ish, not visible blue.
	# Since the final composite currently ignores alpha, RGB is what matters most.
	cam.clearColor = osg.Vec4(0.0, 0.0, 0.0, 1.0)
	cam.viewport = osg.Viewport(0, 0, w, h)
	cam.attach(osg.Camera.COLOR_BUFFER, output_tex)

	cam.children.append(scene)

	return cam

def make_fullscreen_rtt_pass(
	input_tex,
	output_tex,
	frag_shader,
	w,
	h,
	name="Post RTT",
	order=1,
	extra_uniforms=None
):
	cam = osg.Camera()

	cam.name = name
	cam.renderOrder = (osg.Camera.PRE_RENDER, order)
	cam.dataVariance = osg.Object.DYNAMIC
	cam.renderTargetImplementation = osg.Camera.FRAME_BUFFER_OBJECT
	cam.clearMask = GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT
	cam.clearColor = osg.Vec4(0.0, 0.0, 0.0, 1.0)
	cam.viewport = osg.Viewport(0, 0, w, h)
	cam.projectionMatrix = osg.Matrix.identity()
	cam.viewMatrix = osg.Matrix.identity()
	cam.referenceFrame = osg.Transform.ABSOLUTE_RF
	cam.allowEventFocus = False

	cam.attach(osg.Camera.COLOR_BUFFER, output_tex)

	prog = make_program(f"{name}_program", FULLSCREEN_VERT, frag_shader)

	cam.stateSet.setAttributeAndModes(
		prog,
		osg.StateAttribute.ON | osg.StateAttribute.OVERRIDE
	)

	cam.stateSet.setTextureAttributeAndModes(
		0,
		input_tex,
		osg.StateAttribute.ON | osg.StateAttribute.OVERRIDE
	)

	cam.stateSet.uniforms["inputTex"] = 0

	if extra_uniforms:
		for k, v in extra_uniforms.items():
			cam.stateSet.uniforms[k] = v

	cam.children.append(make_fullscreen_quad())

	return cam

def make_blur_pass(input_tex, output_tex, w, h, direction, name, order):
	if direction == "horizontal":
		texel_step = osg.Vec2(1.0 / float(w), 0.0)

	elif direction == "vertical":
		texel_step = osg.Vec2(0.0, 1.0 / float(h))

	else:
		raise ValueError(f"invalid blur direction: {direction!r}")

	return make_fullscreen_rtt_pass(
		input_tex=input_tex,
		output_tex=output_tex,
		frag_shader=BLUR_FRAG,
		w=w,
		h=h,
		name=name,
		order=order,
		extra_uniforms={
			"texelStep": texel_step
		}
	)

def make_composite_hud(scene_tex, blur_tex, w, h):
	cam = osg.Camera()

	cam.name = "Composite HUD"
	cam.renderOrder = osg.Camera.POST_RENDER
	cam.clearMask = GL_DEPTH_BUFFER_BIT
	cam.viewport = osg.Viewport(0, 0, w, h)
	cam.projectionMatrix = osg.Matrix.identity()
	cam.viewMatrix = osg.Matrix.identity()
	cam.referenceFrame = osg.Transform.ABSOLUTE_RF
	cam.allowEventFocus = False

	prog = make_program("composite_hud_program", FULLSCREEN_VERT, COMPOSITE_FRAG)

	cam.stateSet.setAttributeAndModes(
		prog,
		osg.StateAttribute.ON | osg.StateAttribute.OVERRIDE,
	)

	cam.stateSet.setTextureAttributeAndModes(
		0,
		scene_tex,
		osg.StateAttribute.ON | osg.StateAttribute.OVERRIDE,
	)
	cam.stateSet.setTextureAttributeAndModes(
		1,
		blur_tex,
		osg.StateAttribute.ON | osg.StateAttribute.OVERRIDE,
	)

	cam.stateSet.uniforms["sceneTex"] = 0
	cam.stateSet.uniforms["blurTex"] = 1
	cam.stateSet.uniforms["glowStrength"] = 2.0

	cam.children.append(make_fullscreen_quad())

	return cam

# Make this do WHATEVER YOU WANT. :) It'll work just fine...
def create_scene():
	return osgDB.readNodeFile("cessna.osgt")

if __name__ == "__main__":
	# Pass outputs:
	#
	# sceneColor: original osgSlug scene
	# blurA: horizontal blur of sceneColor
	# blurB: vertical blur of blurA
	sceneColor = make_color_texture(W, H)
	blurA = make_color_texture(W, H)
	blurB = make_color_texture(W, H)

	sceneColor.dataVariance = osg.Object.DYNAMIC
	blurA.dataVariance = osg.Object.DYNAMIC
	blurB.dataVariance = osg.Object.DYNAMIC

	# Pass 1:
	# Render actual scene to sceneColor.
	scene_pass = make_scene_rtt_pass(
		output_tex=sceneColor,
		scene=create_scene(),
		w=W,
		h=H,
		name="Scene RTT"
	)

	# Pass 2:
	# Horizontal blur: sceneColor -> blurA.
	blur_h_pass = make_blur_pass(
		input_tex=sceneColor,
		output_tex=blurA,
		w=W,
		h=H,
		direction="horizontal",
		name="Blur Horizontal RTT",
		order=1
	)

	# Pass 3:
	# Vertical blur: blurA -> blurB.
	blur_v_pass = make_blur_pass(
		input_tex=blurA,
		output_tex=blurB,
		w=W,
		h=H,
		direction="vertical",
		name="Blur Vertical RTT",
		order=2
	)

	# Pass 4:
	# Composite original scene + blurred glow to default framebuffer.
	hud = make_composite_hud(
		scene_tex=sceneColor,
		blur_tex=blurB,
		w=W,
		h=H
	)

	root = osg.Group()
	root.children.extend((
		scene_pass,
		blur_h_pass,
		blur_v_pass,
		hud
	))

	viewer = osgViewer.Viewer()
	viewer.sceneData = root
	viewer.cameraManipulator = osgGA.TrackballManipulator()

	# Should not be visible if HUD composite is covering the whole screen.
	viewer.camera.clearColor = osg.Vec4(1.0, 0.0, 1.0, 1.0)

	// viewer.TODO()

	while not viewer.done:
		viewer.frame()
