#!/usr/bin/env python3
#vimrun! python3 08-shadows.py

# Step 8 -- Shadow Mapping
# New concept: a PRE_RENDER "shadow camera" looks at the scene from the key light's POV
# and writes a depth texture (the shadow map). In the main PBR pass every fragment is
# transformed to light-clip space; comparing that depth against the shadow map tells us
# whether the fragment is in shadow.
#
# Unlike steps 0-7, the direct-lighting math and the shadow test are NOT hand-rolled here --
# both come from osgx (osgx.pbr.LightSet for the lights, osgx.shadow for the shadow camera +
# the shadowed osgx_DirectLighting() hook). That's a deliberate choice specific to this step:
# by now (Step 6 already taught the underlying Cook-Torrance math), re-deriving it a second
# time just to add shadows would be re-teaching, not teaching -- see the fragment shaders
# below for how little is left once osgx.pbr/osgx.shadow do the actual lighting work.
#
# Scene-graph structure (avoids texture feedback loops):
#
# root
# +-- shadow_map.camera (PRE_RENDER) <- renders "model" into depth texture
# | +-- model
# +-- main_group (LightSet + shadow uniforms; unit 4 = shadow depth texture)
# +-- model <- same node, different parent
# +-- floor <- receives BoomBox shadow via shared unit 4
#
# The shadow texture is ONLY bound at unit 4 on main_group's stateSet. During the
# shadow pass the camera traverses shadow_map.camera -> model (main_group is not in that
# path), so unit 4 is unbound there -- no read-while-write feedback loop on the depth texture.
#
# The shadow matrix is WORLD space (not eye space, unlike the old hand-rolled version this
# replaced) -- osgx_DirectLighting()/osgx_ShadowFactor() both work in world space, so
# createDirectionalShadowMap() only has to compose lightView*lightProj once at setup. Since
# the key light is static here, that's the only computation needed -- no per-frame
# preDrawCallback recomputing the shadow matrix off the orbiting viewer camera.

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
from OpenSceneGraph.GL import *

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

# Only material reading (baseColor/normal/ORM/emissive) and the TBN reconstruction are
# hand-rolled here -- that's Step 4/5/6 material, already taught. Direct lighting is one call:
# osgx_DirectLighting(N, V, worldPos, mat), declared by DIRECT_LIGHTING_DECL and DEFINED by a
# separate shader object added in __main__ below (osgx.shadow.makeShadowedDirectLightingHookShader()
# instead of osgx.pbr's unshadowed default -- same call site either way, see PBR.hpp's
# DIRECT_LIGHTING_DECL/DIRECT_LIGHTING_HOOK_DEFAULT comment for why that swap needs nothing else
# to change here).
FRAGMENT_SHADER = """
#version 460 core

#pragma osgx::pbr MATERIAL_STRUCT, DIRECT_LIGHTING_DECL

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

// Exported by osgGLTF per material. This older forward example does not use
// its full material buffer yet, but it can still honor texture alpha coverage.
uniform float osgx_gltf_alphaMode;
uniform float osgx_gltf_alphaCutoff;

uniform vec3 emissiveFactor;
uniform float scanlineFreq;
uniform float scanlineStrength;
uniform vec3 skyColor;
uniform vec3 groundColor;

uniform mat4 osg_ViewMatrix;
uniform mat4 osg_ViewMatrixInverse;

out vec4 fragColor;

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
	vec3 N_eye = normalize(TBN * nMap);

	osgx_Material mat;

	mat.albedo = baseColor.rgb;
	mat.ao = texture(ormTex, vUV).r;
	mat.roughness = texture(ormTex, vUV).g;
	mat.metallic = texture(ormTex, vUV).b;
	mat.F0 = mix(vec3(0.04), mat.albedo, mat.metallic);

	// osgx_DirectLighting()/osgx_ShadowFactor() both work in WORLD space -- rotate N/V and
	// reconstruct worldPos from the eye-space values the vertex shader already computed.
	mat3 invViewRot = transpose(mat3(osg_ViewMatrix));
	vec3 N = invViewRot * N_eye;
	vec3 V = invViewRot * normalize(-vPosition);
	vec3 worldPos = (osg_ViewMatrixInverse * vec4(vPosition, 1.0)).xyz;

	vec3 Lo = osgx_DirectLighting(N, V, worldPos, mat);

	// World up is just (0,0,1) now that N is already in world space -- no rotation needed
	// (the old eye-space version had to rotate world-up INTO eye space to compare against N).
	float hemi = dot(N, vec3(0.0, 0.0, 1.0)) * 0.5 + 0.5;
	vec3 ambient = mix(groundColor, skyColor, hemi) * mat.albedo * mat.ao;

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

# Flat albedo, no textures -- otherwise identical shape to the model's fragment shader above:
# build an osgx_Material by hand, call osgx_DirectLighting() once.
FLOOR_FRAGMENT = """
#version 460 core

#pragma osgx::pbr MATERIAL_STRUCT, DIRECT_LIGHTING_DECL

in vec3 vPosition;
in vec3 vNormal;

uniform mat4 osg_ViewMatrix;
uniform mat4 osg_ViewMatrixInverse;

out vec4 fragColor;

void main() {
	osgx_Material mat;

	mat.albedo = vec3(0.82, 0.76, 0.62); // warm light stone/concrete
	mat.ao = 1.0;
	mat.roughness = 0.9;
	mat.metallic = 0.0;
	mat.F0 = vec3(0.04);

	mat3 invViewRot = transpose(mat3(osg_ViewMatrix));
	vec3 N = invViewRot * normalize(vNormal);
	vec3 V = invViewRot * normalize(-vPosition);
	vec3 worldPos = (osg_ViewMatrixInverse * vec4(vPosition, 1.0)).xyz;

	vec3 Lo = osgx_DirectLighting(N, V, worldPos, mat);

	fragColor = vec4(vec3(0.06) * mat.albedo + Lo, 1.0);
}
"""

if __name__ == "__main__":
	import argparse

	ap = argparse.ArgumentParser()
	ap.add_argument("path", nargs="?", default=None)
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

	path = resolve_model(args.path or "BoomBox")

	if not path:
		sys.exit("Cannot find model -- clone glTF-Sample-Assets into your OSG_FILE_PATH checkout")

	model = osgDB.readNodeFile(path)

	# One shader object defines osgx_DirectLighting() for BOTH programs below (model and floor)
	# -- osg.Shader objects can be shared/attached to more than one Program, same as any other
	# osgx hook shader.
	hook_shader = osgx.shadow.makeShadowedDirectLightingHookShader()

	p = osg.Program(name="pbr_shadow", shaders=(
		osg.Shader(osg.Shader.VERTEX, VERTEX_SHADER),
		osg.Shader(osg.Shader.FRAGMENT, osgx.resolveShaderLibs(FRAGMENT_SHADER)),
		hook_shader
	))
	p.bindAttribLocation["osg_Tangent"] = 7

	# BoomBox-specific: PBR program, texture samplers, emissive/scanline/hemi uniforms.
	ss = model.stateSet

	ss.attributes.append(p)
	ss.uniforms["baseColorTex"] = 0
	ss.uniforms["normalTex"] = 1
	ss.uniforms["ormTex"] = 2
	ss.uniforms["emissiveTex"] = 3
	ss.uniforms["emissiveFactor"] = osg.Vec3(1.0, 1.0, 1.0)
	ss.uniforms["scanlineFreq"] = 1.5
	ss.uniforms["scanlineStrength"] = 0.5
	ss.uniforms["skyColor"] = osg.Vec3(0.15, 0.20, 0.35)
	ss.uniforms["groundColor"] = osg.Vec3(0.12, 0.08, 0.05)

	# --- Floor (optional) --------------------------------------------------- #
	if args.floor:
		S, Z = args.floor_size, args.floor_z
		floor_quad = osg.createTexturedQuadGeometry(
			osg.Vec3(-S / 2, -S / 2, Z),
			osg.Vec3(S, 0, 0),
			osg.Vec3(0, S, 0)
		)
		floor_geode = osg.Geode()
		floor_geode.drawables.append(floor_quad)

		floor_p = osg.Program(name="floor_shadow", shaders=(
			osg.Shader(osg.Shader.VERTEX, FLOOR_VERTEX),
			osg.Shader(osg.Shader.FRAGMENT, osgx.resolveShaderLibs(FLOOR_FRAGMENT)),
			hook_shader
		))
		floor_geode.stateSet.attributes.append(floor_p)

	# --- Scene graph ---------------------------------------------------------- #
	main_group = osg.Group()
	mg_ss = main_group.stateSet

	main_group.children.append(model)

	if args.floor:
		main_group.children.append(floor_geode)

	# --- Lights: same 3-point rig as before, now via osgx.pbr.LightSet. Pure inverse-square
	# falloff (no artificial radius-based cutoff, unlike the old hand-rolled atten() formula) --
	# these intensities aren't a straight port of the old lightColor/lightRadius values, tune to
	# taste.
	lights = osgx.pbr.LightSet.create(mg_ss)

	lights.setCount(3)
	lights.setPoint(0, KEY_LIGHT_POS, osg.Vec3(1.0, 0.9, 0.7), 1.6)
	lights.setPoint(1, FILL_LIGHT_POS_0, osg.Vec3(0.3, 0.5, 1.0), 1.2)
	lights.setPoint(2, FILL_LIGHT_POS_1, osg.Vec3(1.0, 0.5, 0.2), 1.0)

	# --- Shadow map ----------------------------------------------------------- #
	# Only light 0 (the key light) casts a shadow -- ShadowMap.casterIndex defaults to 0.
	# Direction is derived from the key light's position toward the model's own bound, scaled
	# off that bound (like 09-ibl.py's light rig) instead of hardcoded near/far/FOV tuned to
	# BoomBox's specific size.
	bound = model.bound
	light_dir = (bound.center - KEY_LIGHT_POS).normalized()

	shadow_map = osgx.shadow.createDirectionalShadowMap(light_dir, bound.center, bound.radius)

	shadow_map.camera.children.append(model)

	mg_ss.textureAttributes[4] = shadow_map.depthTexture
	mg_ss.uniforms["osgx_shadowMap"] = 4
	mg_ss.uniforms.extend((
		shadow_map.shadowMatrix, shadow_map.bias, shadow_map.strength, shadow_map.casterIndex
	))

	root = osg.Group()

	root.children.extend((shadow_map.camera, main_group))

	v = osgViewer.Viewer()
	v.sceneData = root
	v.cameraManipulator = osgGA.TrackballManipulator()

	while not v.done:
		v.frame()
