#!/usr/bin/env python3
#vimrun! python3 ../examples/pyosg-lighting/08-shadows.py

# Step 8 -- Shadow Mapping
# New concept: a PRE_RENDER "shadow camera" looks at the scene from the key light's POV
# and writes a depth texture (the shadow map). In the main PBR pass every fragment is
# transformed to light-clip space; comparing that depth against the shadow map tells us
# whether the fragment is in shadow.
#
# This is a direct extension of pyosg-lighting-7-emissive.py: IDENTICAL lights,
# IDENTICAL shader math -- the only addition is shadowFactor() on the key light (light 0).
# Compare side-by-side with step 7 to see exactly what shadow mapping adds.
#
# Scene-graph structure (avoids texture feedback loops):
#
# root
# +-- shadow_cam (PRE_RENDER) <- renders "model" into depth texture
# | +-- model
# +-- main_group (unit 4 = shadow_tex; shared lights + shadowMatrix uniforms)
# +-- model <- same node, different parent
# +-- floor <- receives BoomBox shadow via shared unit 4
#
# The shadow texture is ONLY bound at unit 4 on main_group's stateSet. During the
# shadow pass the camera traverses shadow_cam -> model (main_group is not in that path),
# so unit 4 is unbound there -- no read-while-write feedback loop on the depth texture.
#
# Light 0 is static, so shadow_cam.viewMatrix/projectionMatrix are set once. The
# DrawCallback only needs to recompute shadowMatrix as the viewer camera orbits.
#
# NOTE(binding-gap): osg::Camera.setDrawBuffer(GL_NONE) / setReadBuffer(GL_NONE) are
# not yet exposed. A proper depth-only FBO sets these to skip color writes entirely.
# Workaround: attach a dummy color texture so the FBO is complete without them.

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
from OpenSceneGraph.GL import *

SHADOW_SIZE = 1024

# Same light positions as step 7 (pyosg-lighting-7-emissive.py) -- no animation.
KEY_LIGHT_POS = osg.Vec3( 0.1, 0.1, 1.0) # front-center key (shadow caster)
FILL_LIGHT_POS_0 = osg.Vec3(-0.8, 0.3, 0.5) # cool fill, left
FILL_LIGHT_POS_1 = osg.Vec3( 0.0, -0.6, 0.2) # warm back/rim

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
out vec4 vTangent;
out vec2 vUV;

void main() {
	vec4 eyePos = osg_ModelViewMatrix * osg_Vertex;
	vPosition = eyePos.xyz;
	vUV = osg_MultiTexCoord0;

	vec3 N = normalize(osg_NormalMatrix * osg_Normal);
	vec3 tangent = osg_NormalMatrix * osg_Tangent.xyz;
	vTangent = vec4(tangent, osg_Tangent.w);
	vec3 T = dot(tangent, tangent) > 1e-10 ? normalize(tangent) : vec3(0.0);
	T = dot(tangent, tangent) > 1e-10 ? normalize(T - dot(T, N) * N) : T;
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
const float PI = 3.14159265359;

in vec3 vT;
in vec3 vB;
in vec3 vNGeom;
in vec3 vPosition;
in vec4 vTangent;
in vec2 vUV;

uniform sampler2D baseColorTex;
uniform sampler2D normalTex;
uniform sampler2D ormTex;
uniform sampler2D emissiveTex;
uniform sampler2D shadowMap; // unit 4: depth from shadow camera

// Exported by osgGLTF per material. This older forward example does not use
// its full material UBO yet, but it can still honor texture alpha coverage.
uniform float osgx_gltf_alphaMode;
uniform float osgx_gltf_alphaCutoff;

uniform vec3 emissiveFactor;
uniform float scanlineFreq;
uniform float scanlineStrength;
uniform vec3 skyColor;
uniform vec3 groundColor;

uniform mat4 osg_ViewMatrix;

uniform vec3 lightPos[NUM_LIGHTS];
uniform vec3 lightColor[NUM_LIGHTS];
uniform float lightRadius[NUM_LIGHTS];

// shadowMatrix: main-camera eye space -> light clip space (bias applied in shader)
uniform mat4 shadowMatrix;
uniform float shadowBias;
uniform float shadowStrength; // 0 = shadows have no effect, 1 = fully black

out vec4 fragColor;

float D_GGX(float NdotH, float roughness) {
	float a = roughness * roughness;
	float a2 = a * a;
	float d = NdotH * NdotH * (a2 - 1.0) + 1.0;
	return a2 / (PI * d * d);
}

float G_Schlick(float NdotX, float roughness) {
	float r = roughness + 1.0;
	float k = (r * r) / 8.0;
	return NdotX / (NdotX * (1.0 - k) + k);
}

float G_Smith(float NdotV, float NdotL, float roughness) {
	return G_Schlick(NdotV, roughness) * G_Schlick(NdotL, roughness);
}

vec3 F_Schlick(float HdotV, vec3 F0) {
	return F0 + (1.0 - F0) * pow(1.0 - HdotV, 5.0);
}

// PCF 3x3: averages 9 shadow samples to soften edges and hide per-triangle acne.
float shadowFactor(vec3 eyePos) {
	vec4 sc = shadowMatrix * vec4(eyePos, 1.0);
	sc /= sc.w;
	vec3 uv = sc.xyz * 0.5 + 0.5;
	if(any(lessThan(uv, vec3(0.0))) || any(greaterThan(uv, vec3(1.0)))) return 1.0;
	vec2 sz = 1.0 / vec2(textureSize(shadowMap, 0));
	float shadow = 0.0;
	for(int x = -1; x <= 1; ++x)
		for(int y = -1; y <= 1; ++y)
			shadow += (uv.z - shadowBias > texture(shadowMap, uv.xy + vec2(x, y) * sz).r) ? 1.0 : 0.0;
	return mix(1.0, 1.0 - shadowStrength, shadow / 9.0);
}

void main() {
	vec4 baseColor = texture(baseColorTex, vUV);
	float alpha = baseColor.a;
	if (osgx_gltf_alphaMode == 1.0 && alpha < osgx_gltf_alphaCutoff) discard;

	vec3 NGeom = normalize(vNGeom);
	vec3 T, B;
	if (dot(vTangent.xyz, vTangent.xyz) > 1e-10) {
		T = normalize(vT);
		B = normalize(vB);
	} else {
		vec3 q1 = dFdx(vPosition);
		vec3 q2 = dFdy(vPosition);
		vec2 st1 = dFdx(vUV);
		vec2 st2 = dFdy(vUV);
		T = normalize(q1 * st2.t - q2 * st1.t);
		B = -normalize(cross(NGeom, T));
	}
	mat3 TBN = mat3(T, B, NGeom);
	vec3 nMap = texture(normalTex, vUV).rgb * 2.0 - 1.0;
	vec3 N = normalize(TBN * nMap);
	vec3 V = normalize(-vPosition);

	vec3 albedo = baseColor.rgb;
	float ao = texture(ormTex, vUV).r;
	float roughness = texture(ormTex, vUV).g;
	float metallic = texture(ormTex, vUV).b;

	vec3 F0 = mix(vec3(0.04), albedo, metallic);
	vec3 Lo = vec3(0.0);

	for(int i = 0; i < NUM_LIGHTS; i++) {
		vec3 lEye = (osg_ViewMatrix * vec4(lightPos[i], 1.0)).xyz;
		vec3 lVec = lEye - vPosition;
		float dist = length(lVec);
		vec3 L = lVec / dist;

		float r = lightRadius[i];
		float atten = 1.0 / (1.0 + (dist * dist) / (r * r));

		vec3 H = normalize(L + V);
		float NdotL = max(dot(N, L), 0.0);
		float NdotV = max(dot(N, V), 0.0);
		float NdotH = max(dot(N, H), 0.0);
		float HdotV = max(dot(H, V), 0.0);

		float D = D_GGX(NdotH, roughness);
		float G = G_Smith(NdotV, NdotL, roughness);
		vec3 F = F_Schlick(HdotV, F0);

		vec3 kD = (vec3(1.0) - F) * (1.0 - metallic);
		vec3 diffuse = kD * albedo / PI;
		vec3 specular = (D * G * F) / max(4.0 * NdotV * NdotL, 0.001);

		// Only light 0 (the key light) casts shadows.
		float shad = (i == 0) ? shadowFactor(vPosition) : 1.0;

		Lo += (diffuse + specular) * lightColor[i] * NdotL * atten * shad;
	}

	vec3 worldUp = normalize(mat3(osg_ViewMatrix) * vec3(0.0, 0.0, 1.0));
	float hemi = dot(N, worldUp) * 0.5 + 0.5;
	vec3 ambient = mix(groundColor, skyColor, hemi) * albedo * ao;

	vec3 emissive = texture(emissiveTex, vUV).rgb * emissiveFactor;
	float scanline = 0.5 + 0.5 * sin(gl_FragCoord.y * scanlineFreq);
	emissive *= mix(1.0, scanline, scanlineStrength);

	fragColor = vec4(ambient + Lo + emissive, alpha);
}
"""

FLOOR_VERTEX = """
#version 460 core

in vec4 osg_Vertex;
in vec3 osg_Normal;

uniform mat4 osg_ModelViewProjectionMatrix;
uniform mat4 osg_ModelViewMatrix;
uniform mat3 osg_NormalMatrix;

out vec3 vPosition;
out vec3 vNormal;

void main() {
	vec4 eyePos = osg_ModelViewMatrix * osg_Vertex;
	vPosition = eyePos.xyz;
	vNormal = normalize(osg_NormalMatrix * osg_Normal);
	gl_Position = osg_ModelViewProjectionMatrix * osg_Vertex;
}
"""

FLOOR_FRAGMENT = """
#version 460 core

#define NUM_LIGHTS 3

in vec3 vPosition;
in vec3 vNormal;

uniform vec3 lightPos[NUM_LIGHTS];
uniform vec3 lightColor[NUM_LIGHTS];
uniform float lightRadius[NUM_LIGHTS];
uniform mat4 shadowMatrix;
uniform sampler2D shadowMap;
uniform float shadowBias;
uniform float shadowStrength;
uniform mat4 osg_ViewMatrix;

out vec4 fragColor;

float shadowFactor(vec3 eyePos) {
	vec4 sc = shadowMatrix * vec4(eyePos, 1.0);
	sc /= sc.w;
	vec3 uv = sc.xyz * 0.5 + 0.5;
	if(any(lessThan(uv, vec3(0.0))) || any(greaterThan(uv, vec3(1.0)))) return 1.0;
	vec2 sz = 1.0 / vec2(textureSize(shadowMap, 0));
	float shadow = 0.0;
	for(int x = -1; x <= 1; ++x)
		for(int y = -1; y <= 1; ++y)
			shadow += (uv.z - shadowBias > texture(shadowMap, uv.xy + vec2(x, y) * sz).r) ? 1.0 : 0.0;
	return mix(1.0, 1.0 - shadowStrength, shadow / 9.0);
}

void main() {
	vec3 N = normalize(vNormal);
	vec3 albedo = vec3(0.82, 0.76, 0.62); // warm light stone/concrete
	vec3 Lo = vec3(0.0);

	for(int i = 0; i < NUM_LIGHTS; i++) {
		vec3 lEye = (osg_ViewMatrix * vec4(lightPos[i], 1.0)).xyz;
		vec3 lVec = lEye - vPosition;
		float dist = length(lVec);
		vec3 L = lVec / dist;
		float r = lightRadius[i];
		float atten = 1.0 / (1.0 + (dist * dist) / (r * r));
		float NdotL = max(dot(N, L), 0.0);
		float shad = (i == 0) ? shadowFactor(vPosition) : 1.0;
		Lo += albedo * lightColor[i] * NdotL * atten * shad;
	}

	fragColor = vec4(vec3(0.06) * albedo + Lo, 1.0);
}
"""

class WriteImageCallback(osg.Camera.DrawCallback):
	def __init__(self, texture):
		super().__init__()

		self.texture = texture
		self.write = False
		self._i = 0

	def __call__(self, ri):
		self._i += 1

		if self._i == 2:
			self.write = True

		if self.write:
			self.texture.apply(ri.state)

			img = osg.Image()

			img.readImageFromCurrentTexture(ri.contextID, False)

			osgDB.writeImageFile(img, "tmp.png")

			osg.notice("WROTE IMAGE")

			self.write = False

if __name__ == "__main__":
	import argparse

	ap = argparse.ArgumentParser()
	ap.add_argument(
		"path",
		nargs="?",
		default=os.path.join(
			os.path.dirname(os.path.abspath(__file__)),
			"data/BoomBox/glTF/BoomBox.gltf"
		)
	)
	ap.add_argument(
		"--floor-z",
		type=float,
		default=None,
		help="Floor Z in Z-up world space (default: -0.04); passing this or --floor-size activates the floor"
	)
	ap.add_argument(
		"--floor-size",
		type=float,
		default=None,
		help="Floor quad side length in metres (default: 0.15); passing this or --floor-z activates the floor"
	)
	args = ap.parse_args()

	# No floor by default; passing either flag activates it.
	args.floor = args.floor_z is not None or args.floor_size is not None
	args.floor_z = -0.04 if args.floor_z is None else args.floor_z
	args.floor_size = 0.15 if args.floor_size is None else args.floor_size

	osg.setNotifyLevel(osg.NotifySeverity.NOTICE)

	path = args.path

	model = osgDB.readNodeFile(path)

	p = osg.Program(name="pbr_shadow", shaders=(
		osg.Shader(osg.Shader.VERTEX, VERTEX_SHADER),
		osg.Shader(osg.Shader.FRAGMENT, FRAGMENT_SHADER)
	))
	p.bindAttribLocation["osg_Tangent"] = 7

	# BoomBox-specific: PBR program, texture samplers, emissive/scanline/hemi uniforms.
	ss = model.stateSet

	ss.setAttributeAndModes(p)
	ss.uniforms["baseColorTex"] = 0
	ss.uniforms["normalTex"] = 1
	ss.uniforms["ormTex"] = 2
	ss.uniforms["emissiveTex"] = 3
	ss.uniforms["shadowMap"] = 4
	ss.uniforms["emissiveFactor"] = osg.Vec3(1.0, 1.0, 1.0)
	ss.uniforms["scanlineFreq"] = 1.5
	ss.uniforms["scanlineStrength"] = 0.5
	ss.uniforms["skyColor"] = osg.Vec3(0.15, 0.20, 0.35)
	ss.uniforms["groundColor"] = osg.Vec3(0.12, 0.08, 0.05)

	# Shared by both BoomBox and floor -- live on main_group so both inherit them.
	lightPos = osg.Uniform(osg.Uniform.Type.FLOAT_VEC3, "lightPos", (
		KEY_LIGHT_POS,
		FILL_LIGHT_POS_0,
		FILL_LIGHT_POS_1
	))

	lightColor = osg.Uniform(osg.Uniform.Type.FLOAT_VEC3, "lightColor", (
		osg.Vec3(1.0, 0.9, 0.7),
		osg.Vec3(0.3, 0.5, 1.0),
		osg.Vec3(1.0, 0.5, 0.2)
	))

	lightRadius = osg.Uniform(osg.Uniform.Type.FLOAT, "lightRadius", (2.5, 1.5, 1.2))

	# shadowMatrix recomputed every frame in the DrawCallback below.
	shadow_matrix_u = osg.Uniform("shadowMatrix", osg.Matrixf.identity())
	shadow_bias_u = osg.Uniform("shadowBias", 0.005)
	shadow_strength_u = osg.Uniform("shadowStrength", 0.7)

	# --- Shadow map depth texture ---
	shadow_tex = osg.Texture2D(
		size=(SHADOW_SIZE, SHADOW_SIZE),
		internalFormat=GL_DEPTH_COMPONENT24,
		sourceFormat=GL_DEPTH_COMPONENT,
		sourceType=GL_FLOAT,
		filter=osg.Texture.NEAREST,
		wrap=osg.Texture.CLAMP_TO_EDGE,
	)

	# Dummy color texture so the FBO is complete without setDrawBuffer(GL_NONE).
	# NOTE(binding-gap): expose Camera.setDrawBuffer / setReadBuffer to remove this.
	dummy_color = osg.Texture2D(
		size=(SHADOW_SIZE, SHADOW_SIZE),
		internalFormat=GL_RGB,
		filter=osg.Texture.NEAREST,
	)

	# --- Shadow camera ---
	# Light is static: set view/proj once, never touch them again.
	# Up vector (0,1,0): (0,0,1) would nearly align with the view direction
	# from KEY_LIGHT_POS=(0.1, 0.1, 1.0) toward origin, causing degenerate lookAt.
	light_view = osg.Matrix.lookAt(
		KEY_LIGHT_POS,
		osg.Vec3(0.0, 0.0, 0.0),
		osg.Vec3(0.0, 1.0, 0.0)
	)
	# 8? FOV covers ~0.14m at 1m -- enough for the BoomBox (~0.08m).
	# near=0.8/far=1.3 brackets the model (light is ~1.005m from origin).
	light_proj = osg.Matrix.perspective(8.0, 1.0, 0.8, 1.3)

	shadow_cam = osg.Camera()

	shadow_cam.name = "ShadowCam"
	shadow_cam.renderOrder = osg.Camera.PRE_RENDER
	shadow_cam.renderTargetImplementation = osg.Camera.FRAME_BUFFER_OBJECT
	shadow_cam.referenceFrame = osg.Transform.ABSOLUTE_RF
	shadow_cam.clearMask = GL_DEPTH_BUFFER_BIT | GL_COLOR_BUFFER_BIT
	shadow_cam.clearColor = osg.Vec4(1.0, 1.0, 1.0, 1.0)
	shadow_cam.viewport = osg.Viewport(0, 0, SHADOW_SIZE, SHADOW_SIZE)
	shadow_cam.attach(osg.Camera.DEPTH_BUFFER, shadow_tex)
	shadow_cam.attach(osg.Camera.COLOR_BUFFER, dummy_color)
	shadow_cam.viewMatrix = light_view
	shadow_cam.projectionMatrix = light_proj
	shadow_cam.children.append(model)
	shadow_cam.preDrawCallback = WriteImageCallback(shadow_tex)
	# shadow_cam.preDrawCallback = lambda *a: osg.notice("HERE")

	# Floor -- receives the BoomBox shadow cast by the key light.
	# OSG world space is Z-up: floor is an XY plane at Z=args.floor_z.
	# normal = widthVec x heightVec = (S,0,0)x(0,S,0) = (0,0,S2) -> (0,0,1) ?
	if args.floor:
		S = args.floor_size
		Z = args.floor_z
		floor_quad = osg.createTexturedQuadGeometry(
			osg.Vec3(-S / 2, -S / 2, Z),
			osg.Vec3(S, 0, 0),
			osg.Vec3(0, S, 0)
		)
		floor_geode = osg.Geode()
		floor_geode.drawables.append(floor_quad)

		floor_p = osg.Program(name="floor_shadow", shaders=(
			osg.Shader(osg.Shader.VERTEX, FLOOR_VERTEX),
			osg.Shader(osg.Shader.FRAGMENT, FLOOR_FRAGMENT)
		))
		floor_geode.stateSet.setAttributeAndModes(floor_p)
		floor_geode.stateSet.uniforms["shadowMap"] = 4 # unit bound by main_group

	# main_group: shadow texture at unit 4 + shared uniforms (lights, shadow matrix).
	# Both the BoomBox and the floor inherit these via OSG state path.
	# shadow_tex is NOT in the shadow camera's state path -> no read-while-write loop.
	main_group = osg.Group()

	main_group.stateSet.setTextureAttributeAndModes(4, shadow_tex)
	main_group.stateSet.uniforms.extend((
		lightPos, lightColor, lightRadius, shadow_matrix_u, shadow_bias_u, shadow_strength_u
	))

	main_group.children.append(model)

	if args.floor:
		main_group.children.append(floor_geode)

	root = osg.Group()

	root.children.extend((shadow_cam, main_group))

	v = osgViewer.Viewer()
	v.sceneData = root
	v.cameraManipulator = osgGA.TrackballManipulator()

	def update_uniforms(ri):
		# OSG row-major convention: to get GLSL's (lightProj * lightView * inv(camView)),
		# write the REVERSED order in Python -- see ai/context-core.md "OSG matrix convention".
		cam_view = v.camera.viewMatrix
		shadow_mat = osg.Matrix.inverse(cam_view) * light_view * light_proj

		shadow_matrix_u.value = osg.Matrixf(shadow_mat)

	v.camera.preDrawCallback = update_uniforms

	while not v.done:
		v.frame()
