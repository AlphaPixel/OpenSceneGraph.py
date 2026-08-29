#!/usr/bin/env python3

# "Voxelizes" a single RTT slice of any model: render it to a small color
# texture, then draw one instanced cube per texel, colored via texelFetch()
# so each instance lands on an exact texel center with no filtering.
#
# Run standalone:
#
#   ./pyosg-voxelize.py path/to/scene.gltf --grid 64 --lift 0.2 --rotate
#
# Or, since this started life as (and still works as) a pure helper library
# with no module-level Viewer/env setup, `exec()` it directly into an
# already-running pyosg_repl.py session (which already owns `viewer`/`osg`
# in its namespace and drives its own frame loop) to build a scene up by
# hand at the prompt instead of via the CLI above:
#
#   p = "examples/pyosg-voxelize.py"
#   exec(compile(open(p).read(), p, "exec"), globals())
#
#   rttCam, colorTex, depthTex, model = create_rtt_camera("path/to/scene.gltf", 32)
#   voxels = create_voxel_geode(colorTex, depthTex, 32, 32)
#
#   viewer.sceneData = osg.Group(children=(rttCam, voxels))
#   viewer.cameraManipulator = osgGA.TrackballManipulator()

import argparse
import time

from OpenSceneGraph import *
from OpenSceneGraph.GL import *

import osgx

# Wall-clock-driven turntable spin, same __call__(self, node, nv) convention as
# the other UpdateCallback classes across these examples (e.g. LiveUpdateCallback
# in pyosg-dynamic-verts.py) -- no osg.NodeCallback subclassing needed.
class SpinCallback:
	def __init__(self, axis=(0, 0, 1), speed=0.4):
		self.axis = osg.Vec3d(*axis)
		self.speed = speed
		self.t0 = time.time()

	def __call__(self, node, nv):
		node.matrix = osg.Matrix.rotate((time.time() - self.t0) * self.speed, self.axis)

		return True

# Wraps `child` in a new MatrixTransform that spins it about `axis` (default Z,
# matching this scene's up axis) at `speed` radians/sec -- put this between an
# RTT camera and the loaded model so the RTT "slice" keeps changing over time,
# which makes the instanced-cube grid visibly track a live, moving source
# rather than looking like a static baked image.
def make_spinner(child, axis=(0, 0, 1), speed=0.4):
	t = osg.MatrixTransform()

	t.children.append(child)
	t.updateCallback = SpinCallback(axis, speed)

	return t

# Trimmed PBR shader for lighting a raw osgDB.readNodeFile()'d glTF model well
# enough to RTT-snapshot. Used to be a hand-copy of examples/pyosg-lighting/
# 09-ibl.py's full shader (shadows/scanline/animated-lights/IBL-cubemap
# stripped, ambient replaced by its `iblEnabled == 0` hemisphere fallback) --
# that copy is what prompted porting the reusable parts (the osgx_gltf_Material
# material-buffer contract, material/shading-normal/emissive/alpha reads, and the
# hemisphere-ambient fallback itself) into osgGLTF/PBR.hpp plus generic osgx/PBR.hpp and
# osgx/IBL.hpp, pulled in below via shader-library pragmas and
# osgx.gltf.pbribl.resolveShaderLibs()
# instead of copy-pasted a third time. Only the direct-light loop, tonemap
# application, and main() -- the part that's genuinely specific to what this
# example wants lit and how -- stay hand-written here.
PBR_FALLBACK_VERTEX_SHADER = """
#version 460 core

in vec4 osg_Vertex;
in vec3 osg_Normal;
in vec4 osg_Tangent;
in vec2 osg_MultiTexCoord0;

uniform mat4 osg_ModelViewProjectionMatrix;
uniform mat4 osg_ModelViewMatrix;
uniform mat3 osg_NormalMatrix;

out vec3 vNGeom;
out vec3 vPosition;
out vec4 vTangent;
out vec2 vUV;

void main() {
	vec4 eyePos = osg_ModelViewMatrix * osg_Vertex;
	vPosition = eyePos.xyz;
	vUV = osg_MultiTexCoord0;
	vNGeom = normalize(osg_NormalMatrix * osg_Normal);
	vTangent = vec4(osg_NormalMatrix * osg_Tangent.xyz, osg_Tangent.w);

	gl_Position = osg_ModelViewProjectionMatrix * osg_Vertex;
}
"""

PBR_FALLBACK_FRAGMENT_SHADER_SRC = """
#version 460 core

#define NUM_LIGHTS 3
// osgx::pbr's D_GGX/G_SCHLICK/G_SMITH/etc. snippets assume `PI` is already
// declared (see osgx/PBR.hpp) rather than bundling their own -- it must be
// declared here, before the #pragma lines below expand to text that uses it.
const float PI = 3.14159265359;

#pragma osgx::pbr MATERIAL_STRUCT, D_GGX, G_SCHLICK, G_SMITH, F_SCHLICK, DIRECT_SPECULAR, TONEMAP_PBR_NEUTRAL
#pragma osgx::gltf MATERIAL_INPUTS, GET_MATERIAL, SHADING_NORMAL, EMISSIVE, ALPHA_COVERAGE
#pragma osgx::ibl HEMISPHERE_AMBIENT

in vec3 vNGeom;
in vec3 vPosition;
in vec4 vTangent;
in vec2 vUV;

uniform vec3 skyColor;
uniform vec3 groundColor;

uniform mat4 osg_ViewMatrix;

uniform vec3 lightPos[NUM_LIGHTS];
uniform vec3 lightColor[NUM_LIGHTS];
uniform float lightRadius[NUM_LIGHTS];

out vec4 fragColor;

// osgx_DirectSpecular already folds NdotL into its own D*G*F term (see
// osgx/PBR.hpp) -- only the Lambert diffuse half needs an explicit NdotL
// multiply here, or specular would get it applied twice.
vec3 evaluateDirectLighting(osgx_Material mat, vec3 N, vec3 V, float NdotV) {
	vec3 Lo = vec3(0.0);

	for (int i = 0; i < NUM_LIGHTS; i++) {
		vec3 lEye = (osg_ViewMatrix * vec4(lightPos[i], 1.0)).xyz;
		vec3 lVec = lEye - vPosition;
		float dist = length(lVec);
		vec3 L = lVec / dist;
		float r = lightRadius[i];
		float atten = 1.0 / (1.0 + (dist * dist) / (r * r));
		float NdotL = max(dot(N, L), 0.0);
		vec3 H = normalize(L + V);
		float HdotV = max(dot(H, V), 0.0);
		vec3 F = osgx_F_Schlick(HdotV, mat.F0);
		vec3 kD = (vec3(1.0) - F) * (1.0 - mat.metallic);
		vec3 diffuse = kD * mat.albedo / PI * NdotL;
		vec3 specular = osgx_DirectSpecular(N, V, L, NdotV, mat.roughness, mat.F0);

		Lo += (diffuse + specular) * lightColor[i] * atten;
	}

	return Lo;
}

void main() {
	float alpha = osgx_gltf_AlphaCoverage(vUV);
	if (osgx_gltf_alphaMode == 1.0 && alpha < osgx_gltf_alphaCutoff) discard;

	vec3 N = osgx_gltf_ShadingNormal(vNGeom, vTangent, vPosition, vUV);
	vec3 V = normalize(-vPosition);
	// osgx::gltf::pbribl::GET_MATERIAL now takes separate baseColor/ORM UVs
	// (per-slot TEXCOORD_n support); this shader only ever produces one UV
	// set, so pass vUV for both.
	osgx_Material mat = osgx_gltf_GetMaterial(vUV, vUV, N);
	float NdotV = max(dot(N, V), 0.0);

	vec3 worldUp = normalize(mat3(osg_ViewMatrix) * vec3(0.0, 0.0, 1.0));

	vec3 Lo = evaluateDirectLighting(mat, N, V, NdotV);
	vec3 ambient = osgx_HemisphereAmbient(N, worldUp, mat.albedo, mat.ao, skyColor, groundColor);
	// osgx_gltf_Emissive() now reads the per-material osgx_gltf_emissiveFactor/
	// osgx_gltf_hasEmissiveMap uniforms the loader sets, rather than taking a
	// caller-supplied factor.
	vec3 emissive = osgx_gltf_Emissive(vUV);

	vec3 color = ambient + Lo + emissive;
	color = osgx_TonemapPBRNeutral(color);
	color = pow(color, vec3(1.0 / 2.2));

	fragColor = vec4(color, alpha);
}
"""

PBR_FALLBACK_FRAGMENT_SHADER = osgx.gltf.pbribl.resolveShaderLibs(PBR_FALLBACK_FRAGMENT_SHADER_SRC)

# Applies the fallback PBR shader above to `node` (in place -- overrides
# whatever Program the glTF loader's own StateSet may or may not carry).
# key_dir/fill_dir/*_distance are scaled against `node.bound`, not absolute
# world coordinates, so the same defaults land reasonably on any model's
# scale -- these ratios are what got tuned live against Batman (radius
# ~1.4), just re-expressed as bound-relative so a CLI run against some other
# model isn't left completely unlit.
def apply_gltf_fallback_pbr(
	node,
	key_dir=(0.35, -0.6, 0.72),
	fill_dir=(-0.4, -0.75, 0.34),
	key_distance=2.0,
	fill_distance=1.6,
	key_intensity=9.0,
	fill_intensity=2.5,
	sky_color=(0.55, 0.6, 0.75),
	ground_color=(0.18, 0.14, 0.12),
):
	bound = node.bound
	center = osg.Vec3d(bound.center) if bound.valid() else osg.Vec3d(0, 0, 0)
	radius = max(bound.radius, 1e-3) if bound.valid() else 1.0

	key_pos = center + osg.Vec3d(*key_dir) * (radius * key_distance)
	fill_pos = center + osg.Vec3d(*fill_dir) * (radius * fill_distance)

	light_pos = (osg.Vec3(key_pos), osg.Vec3(fill_pos), osg.Vec3(0, 0, 0))
	light_color = (
		osg.Vec3(key_intensity, key_intensity, key_intensity * 0.94),
		osg.Vec3(fill_intensity * 0.85, fill_intensity * 0.85, fill_intensity),
		osg.Vec3(0, 0, 0),
	)
	light_radius = (radius * 4.0, radius * 3.5, 1.0)

	p = osg.Program(name="voxelizeFallbackPBR", shaders=(
		osg.Shader(osg.Shader.VERTEX, PBR_FALLBACK_VERTEX_SHADER),
		osg.Shader(osg.Shader.FRAGMENT, PBR_FALLBACK_FRAGMENT_SHADER)
	))
	osgx.gltf.shader.configureProgram(p)

	ss = node.stateSet

	osgx.gltf.shader.configureStateSet(ss)
	ss.attributes[osg.StateAttribute.PROGRAM] = (p, osg.StateAttribute.ON | osg.StateAttribute.OVERRIDE)
	ss.uniforms["skyColor"] = osg.Vec3(*sky_color)
	ss.uniforms["groundColor"] = osg.Vec3(*ground_color)

	lp = osg.Uniform(osg.Uniform.Type.FLOAT_VEC3, "lightPos", light_pos)
	lc = osg.Uniform(osg.Uniform.Type.FLOAT_VEC3, "lightColor", light_color)
	lr = osg.Uniform(osg.Uniform.Type.FLOAT, "lightRadius", light_radius)

	ss.uniforms.extend((lp, lc, lr))

	return node

# gl_VertexID-indexed unit cube (36 verts, hard per-face normals via
# gl_VertexID / 6) -- no CPU-side vertex/normal arrays or index buffer at
# all, matching the fully-procedural technique already proven out in
# pyosg-instanced.py/pyosg-instanced-ssbo.py (DrawElementsUInt isn't exposed
# to Python in this binding, only DrawArrays -- this sidesteps needing it).
VOXEL_VERTEX_SHADER = """
#version 430 core

uniform mat4 osg_ModelViewProjectionMatrix;
uniform mat4 osg_ModelViewMatrix;
uniform mat3 osg_NormalMatrix;
uniform sampler2D srcTex;
uniform sampler2D depthTex;
uniform int gridW;
uniform int gridH;
uniform float spacing;
uniform float cubeSize;
uniform float depthFarEpsilon;

flat out vec4 vColor;
flat out vec3 vNormalEye;
out vec3 vPositionEye;

const vec3 cubeVerts[36] = vec3[36](
	vec3(-0.5,-0.5, 0.5), vec3( 0.5,-0.5, 0.5), vec3( 0.5, 0.5, 0.5),
	vec3(-0.5,-0.5, 0.5), vec3( 0.5, 0.5, 0.5), vec3(-0.5, 0.5, 0.5),

	vec3(-0.5, 0.5,-0.5), vec3( 0.5, 0.5,-0.5), vec3( 0.5,-0.5,-0.5),
	vec3(-0.5, 0.5,-0.5), vec3( 0.5,-0.5,-0.5), vec3(-0.5,-0.5,-0.5),

	vec3(-0.5, 0.5,-0.5), vec3(-0.5, 0.5, 0.5), vec3( 0.5, 0.5, 0.5),
	vec3(-0.5, 0.5,-0.5), vec3( 0.5, 0.5, 0.5), vec3( 0.5, 0.5,-0.5),

	vec3(-0.5,-0.5,-0.5), vec3( 0.5,-0.5,-0.5), vec3( 0.5,-0.5, 0.5),
	vec3(-0.5,-0.5,-0.5), vec3( 0.5,-0.5, 0.5), vec3(-0.5,-0.5, 0.5),

	vec3( 0.5,-0.5,-0.5), vec3( 0.5, 0.5,-0.5), vec3( 0.5, 0.5, 0.5),
	vec3( 0.5,-0.5,-0.5), vec3( 0.5, 0.5, 0.5), vec3( 0.5,-0.5, 0.5),

	vec3(-0.5,-0.5, 0.5), vec3(-0.5, 0.5, 0.5), vec3(-0.5, 0.5,-0.5),
	vec3(-0.5,-0.5, 0.5), vec3(-0.5, 0.5,-0.5), vec3(-0.5,-0.5,-0.5)
);

const vec3 faceNormal[6] = vec3[6](
	vec3(0.0, 0.0, 1.0), vec3(0.0, 0.0,-1.0),
	vec3(0.0, 1.0, 0.0), vec3(0.0,-1.0, 0.0),
	vec3(1.0, 0.0, 0.0), vec3(-1.0, 0.0, 0.0)
);

void main() {
	int face = gl_VertexID / 6;

	float id = float(gl_InstanceID);

	float gx = mod(id, float(gridW));
	float gy = floor(id / float(gridW));

	vec4 texel = texelFetch(srcTex, ivec2(int(gx), int(gy)), 0);
	float depth = texelFetch(depthTex, ivec2(int(gx), int(gy)), 0).r;

	// Collapse this instance's geometry to a single point (zero-area, so it
	// rasterizes nothing) when nothing was ever rasterized into this texel in
	// the RTT pass -- i.e. its depth still sits at the cleared far plane
	// (~1.0). A color-distance-from-clear-color test looked equivalent at
	// first, but a batsuit is itself near-black, so real model texels landed
	// inside that same "close to background" color radius and got wrongly
	// discarded; depth has no such ambiguity; it is only ever <1.0 where the
	// model actually rendered, regardless of how dark that surface's color
	// is. Done here rather than with `discard` in the fragment shader: that
	// would still rasterize the full cube (wasted fill + it'd still occlude/
	// write depth), whereas a degenerate vertex costs nothing beyond the
	// vertex shader itself.
	bool isBackground = depth > (1.0 - depthFarEpsilon);
	vec3 local = isBackground ? vec3(0.0) : cubeVerts[gl_VertexID] * cubeSize;

	// Grid spans X (horizontal) / Z (vertical); Y is the cube's thin
	// "depth" axis, facing back toward the RTT camera that produced
	// srcTex -- so the mosaic reads as a flat picture facing the viewer.
	vec2 grid = (vec2(gx, gy) - vec2(float(gridW), float(gridH)) * 0.5) * spacing;
	vec3 world = local + vec3(grid.x, 0.0, grid.y);

	vColor = texel;
	vNormalEye = normalize(osg_NormalMatrix * faceNormal[face]);
	vPositionEye = (osg_ModelViewMatrix * vec4(world, 1.0)).xyz;

	gl_Position = osg_ModelViewProjectionMatrix * vec4(world, 1.0);
}
"""

VOXEL_FRAGMENT_SHADER = """
#version 430 core

flat in vec4 vColor;
flat in vec3 vNormalEye;
in vec3 vPositionEye;

uniform float exposure;
uniform float lift;

out vec4 fragColor;

void main() {
	// Camera-relative "headlight" (N.V in eye space) rather than a fixed
	// world-direction light: a flat mosaic viewed dead-on shows almost
	// exclusively the one face pointed straight at the camera, so a fixed
	// light direction gives that entire view a single flat shade with no
	// cue that it's actually a grid of cubes -- looked fine from an angle
	// (many differently-shaded faces visible at once) but went dark/flat
	// head-on. A headlight instead makes whichever face is facing the
	// viewer the brightest one, in any orientation.
	vec3 V = normalize(-vPositionEye);
	float NdotV = max(dot(normalize(vNormalEye), V), 0.0);
	float shade = 0.45 + 0.55 * NdotV;

	// `shade` alone tops out at exactly the source texel's own brightness,
	// which is no help against a genuinely near-black source material (a
	// batsuit). exposure is a straight gain; lift is a screen-blend toward
	// white (1 - (1-x)*(1-lift)) that raises shadows without clipping
	// anything already bright (belt, skin tones stay put near 1.0).
	vec3 color = vColor.rgb * exposure;
	color = 1.0 - (1.0 - color) * (1.0 - lift);

	fragColor = vec4(color * shade, 1.0);
}
"""

# Loads `model_path`, frames it with a fixed orthographic "front" (-Y looking
# toward +Y) camera sized to its bounding sphere, and renders it into a
# `size`x`size` RGBA texture every frame (so this is live/continuous, not a
# one-shot bake -- cheap at these resolutions, and lets an animated/live
# source scene stay reflected in the voxel mosaic for free).
def create_rtt_camera(
	model_path,
	size=32,
	eye_dir=(0, -1, 0),
	up=(0, 0, 1),
	margin=1.15,
	clear_color=(0.05, 0.05, 0.08),
):
	model = osgDB.readNodeFile(model_path)

	if model is None:
		raise RuntimeError(f"failed to load {model_path!r}")

	bound = model.bound

	if not bound.valid():
		raise RuntimeError(f"{model_path!r} has no valid bounds")

	center = osg.Vec3d(bound.center)
	radius = max(bound.radius, 1e-3)

	eye = center + osg.Vec3d(*eye_dir) * (radius * 3.0)
	half = radius * margin

	cb = osg.Texture2D()

	cb.size = (size, size)
	cb.internalFormat = GL_RGBA
	cb.filter = (osg.Texture.NEAREST, osg.Texture.NEAREST)

	db = osg.Texture2D()

	db.size = (size, size)
	db.internalFormat = GL_DEPTH_COMPONENT24
	db.sourceFormat = GL_DEPTH_COMPONENT
	db.sourceType = GL_FLOAT
	db.filter = (osg.Texture.NEAREST, osg.Texture.NEAREST)

	cam = osg.Camera()

	cam.renderOrder = osg.Camera.PRE_RENDER
	cam.renderTargetImplementation = osg.Camera.FRAME_BUFFER_OBJECT
	cam.referenceFrame = osg.Transform.ABSOLUTE_RF
	cam.clearMask = GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT
	cam.clearColor = osg.Vec4(*clear_color, 1.0)
	cam.viewport = osg.Viewport(0, 0, size, size)
	cam.viewMatrix = osg.Matrix.lookAt(eye, center, osg.Vec3d(*up))
	cam.projectionMatrix = osg.Matrix.ortho(-half, half, -half, half, 0.01, radius * 10.0)
	cam.name = "voxelize RTT"

	cam.attach(osg.Camera.COLOR_BUFFER, cb)
	cam.attach(osg.Camera.DEPTH_BUFFER, db)
	cam.children.append(model)

	return cam, cb, db, model

# Builds the instanced-cube mosaic Geode reading `color_tex`/`depth_tex`
# (`grid_w` x `grid_h`, matching the RTT texture size 1:1 for exact texel/
# cube mapping).
def create_voxel_geode(
	color_tex,
	depth_tex,
	grid_w,
	grid_h,
	cube_size=0.8,
	padding=0.2,
	exposure=1.6,
	lift=0.15,
	depth_far_epsilon=1e-4,
):
	spacing = cube_size + padding

	g = osg.Geometry()

	g.primitiveSets.append(osg.DrawArrays(
		osg.PrimitiveSet.TRIANGLES, 0, 36, grid_w * grid_h
	))

	half_extent = max(grid_w, grid_h) * spacing * 0.5

	g.initialBound = osg.BoundingBox(
		-half_extent, -cube_size, -half_extent,
		 half_extent,  cube_size,  half_extent
	)

	p = osg.Program(name="voxelizeProgram", shaders=(
		osg.Shader(osg.Shader.VERTEX, VOXEL_VERTEX_SHADER),
		osg.Shader(osg.Shader.FRAGMENT, VOXEL_FRAGMENT_SHADER)
	))

	r = osg.Geode(drawables=(g,))

	r.stateSet.attributes.append(p)
	r.stateSet.textureAttributes[0] = color_tex
	r.stateSet.textureAttributes[1] = depth_tex
	r.stateSet.uniforms["srcTex"] = 0
	r.stateSet.uniforms["depthTex"] = 1
	r.stateSet.uniforms["gridW"] = grid_w
	r.stateSet.uniforms["gridH"] = grid_h
	r.stateSet.uniforms["spacing"] = spacing
	r.stateSet.uniforms["cubeSize"] = cube_size
	r.stateSet.uniforms["exposure"] = exposure
	r.stateSet.uniforms["lift"] = lift
	r.stateSet.uniforms["depthFarEpsilon"] = depth_far_epsilon

	return r

# --------------------------------------------------------------------------- #
# Standalone CLI / runner contract
# --------------------------------------------------------------------------- #
# The real pipeline-assembly entrypoint -- returns the root Node, no viewer/window side effects.
# Deliberately does NOT touch os.environ/OpenSceneGraph import order at all (see the module
# docstring: this file is a "pure helper library with no module-level Viewer/env setup", so it
# stays exec()-able into an already-running pyosg_repl.py session with zero side effects) -- the
# usual `from pyosg_example import window_size` import stays scoped to the `__main__` guard below,
# not module top, same as `argparse`'s CLI-only usage.
def build_scene(w, h):
	global _args

	ap = argparse.ArgumentParser()
	ap.add_argument("model", help="path to a model file (glTF, etc.)")
	ap.add_argument("--grid", type=int, default=32, help="grid width/height in cubes (default: 32)")
	ap.add_argument("--lift", type=float, default=0.15, help="shadow-lift amount, 0-1 (default: 0.15)")
	ap.add_argument(
		"--rotate",
		type=float,
		nargs="?",
		const=0.4,
		default=None,
		metavar="RAD_PER_SEC",
		help="spin the model inside the RTT camera (default 0.4 rad/s if given with no value)"
	)

	_args = args = ap.parse_args()

	rttCam, colorTex, depthTex, model = create_rtt_camera(args.model, args.grid)

	apply_gltf_fallback_pbr(model)

	del rttCam.children[0]
	rttCam.children.append(make_spinner(model, speed=args.rotate) if args.rotate is not None else model)

	voxels = create_voxel_geode(colorTex, depthTex, args.grid, args.grid, lift=args.lift)

	return osg.Group(children=(rttCam, voxels))

# Set by build_scene(), unused by configure_viewer() today -- kept for parity/future use with the
# rest of this project's _args stash convention (pyosg-khronos-viewer.py etc.); this file has no
# viewer-level interactivity beyond the default TrackballManipulator both runners already provide.
_args = None

# Guarded on `_osg_repl_controller` (not just `__name__`) because exec()-loading this file into an
# already-running pyosg_repl.py session -- the documented library usage above -- also runs with
# __name__ == "__main__" in that session's own globals(); `_osg_repl_controller` only exists there
# once pyosg_repl.repl() has already run, which is exactly the case this block must not fire in
# (it'd otherwise spin up a second competing osgViewer.Viewer + frame loop).
if __name__ == "__main__" and "_osg_repl_controller" not in globals():
	from pyosg_example import window_size

	osg.setNotifyLevel(osg.NotifySeverity.NOTICE)

	W, H = window_size()

	viewer = osgViewer.Viewer()
	root = build_scene(W, H)

	viewer.sceneData = root
	viewer.cameraManipulator = osgGA.TrackballManipulator()

	while not viewer.done:
		viewer.frame()
