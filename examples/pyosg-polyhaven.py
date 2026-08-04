#!/usr/bin/env python3
#vimrun! ../examples/pyosg-polyhaven.py
#
# pyosg-polyhaven.py worn_brick_wall --texture
# pyosg-polyhaven.py https://polyhaven.com/a/worn_brick_wall --texture
# pyosg-polyhaven.py /path/to/local.gltf --texture
# pyosg-polyhaven.py worn_brick_wall --texture --res 4k
#
# pyosg-polyhaven.py qwantani_dusk_2 --hdr
# pyosg-polyhaven.py https://polyhaven.com/a/qwantani_dusk_2 --hdr
# pyosg-polyhaven.py /path/to/local.hdr --hdr
# pyosg-polyhaven.py qwantani_dusk_2 --hdr --res 4k

import sys
import os
import math
import json
import argparse
import urllib.request
import urllib.parse

os.environ.update({
	"OSG_WINDOW": "50 50 800 800",
	"OSG_THREADING": "SingleThreaded",
	"OSG_GL_CONTEXT_PROFILE_MASK": "1",
	"OSG_GL_VERSION": "4.6",
	"OSG_GL_CONTEXT_VERSION": "4.6",
})

from OpenSceneGraph import osg, osgDB, osgViewer, osgGA
from OpenSceneGraph.GL import *

import osgx

GL_TEXTURE_CUBE_MAP_SEAMLESS = 0x884F

# --------------------------------------------------------------------------- #
# --texture mode shaders
# --------------------------------------------------------------------------- #

VERTEX_SHADER = """
#version 460 core

in vec4 osg_Vertex;
in vec3 osg_Normal;
in vec2 osg_MultiTexCoord0;

uniform mat4 osg_ModelViewProjectionMatrix;
uniform mat4 osg_ModelViewMatrix;
uniform mat3 osg_NormalMatrix;

out vec3 vNormal;
out vec3 vPosition;
out vec2 vUV;

void main() {
	vec4 eyePos = osg_ModelViewMatrix * osg_Vertex;
	vPosition = eyePos.xyz;
	vNormal = normalize(osg_NormalMatrix * osg_Normal);
	vUV = osg_MultiTexCoord0;
	gl_Position = osg_ModelViewProjectionMatrix * osg_Vertex;
}
"""

FRAGMENT_SHADER = """
#version 460 core

#define NUM_LIGHTS 2
const float PI = 3.14159265359;

in vec3 vNormal;
in vec3 vPosition;
in vec2 vUV;

uniform sampler2D baseColorTex; // unit 0
uniform sampler2D normalTex; // unit 1
uniform sampler2D ormTex; // unit 2 R=AO G=Roughness B=Metallic

uniform vec3 skyColor;
uniform vec3 groundColor;
uniform mat4 osg_ViewMatrix;
uniform vec3 lightPos[NUM_LIGHTS];
uniform vec3 lightColor[NUM_LIGHTS];
uniform float lightRadius[NUM_LIGHTS]; // attenuation falloff distance only -- NOT physical size
uniform float lightSourceRadius[NUM_LIGHTS]; // physical sphere radius -- widens the highlight itself

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

// Sphere light "representative point" trick (Karis, "Real Shading in Unreal Engine 4", 2013):
// bends the light direction used for the specular term toward the closest point on the light's
// physical sphere to the ideal mirror-reflection ray, instead of always pointing at its center.
// This is what actually makes a highlight bigger/softer as the light gets larger -- unlike
// lightRadius above, which only changes attenuation. toLightCenter is UNNORMALIZED (light center
// minus shading point); R is the normalized reflection vector.
vec3 sphereLightDir(vec3 toLightCenter, vec3 R, float sourceRadius) {
	vec3 centerToRay = dot(toLightCenter, R) * R - toLightCenter;
	vec3 closestPoint = toLightCenter + centerToRay * clamp(
		sourceRadius / max(length(centerToRay), 0.0001), 0.0, 1.0
	);

	return normalize(closestPoint);
}

void main() {
	// Derivative TBN: recovers tangent frame from screen-space derivatives.
	// Works on any mesh with UVs - no tangent vertex attribute required.
	vec3 Q1 = dFdx(vPosition);
	vec3 Q2 = dFdy(vPosition);
	vec2 st1 = dFdx(vUV);
	vec2 st2 = dFdy(vUV);
	float d = st1.x * st2.y - st2.x * st1.y;
	vec3 T = normalize(( Q1 * st2.y - Q2 * st1.y) / d);
	vec3 B = normalize((-Q1 * st2.x + Q2 * st1.x) / d);
	mat3 TBN = mat3(T, B, normalize(vNormal));

	vec3 nMap = texture(normalTex, vUV).rgb * 2.0 - 1.0;
	vec3 N = normalize(TBN * nMap);
	vec3 V = normalize(-vPosition);
	vec3 R = reflect(-V, N);

	vec3 albedo = texture(baseColorTex, vUV).rgb;
	float ao = texture(ormTex, vUV).r;
	float roughness = texture(ormTex, vUV).g;
	float metallic = texture(ormTex, vUV).b;

	vec3 F0 = mix(vec3(0.04), albedo, metallic);
	vec3 Lo = vec3(0.0);

	for (int i = 0; i < NUM_LIGHTS; i++) {
		vec3 lEye = (osg_ViewMatrix * vec4(lightPos[i], 1.0)).xyz;
		vec3 lVec = lEye - vPosition;
		float dist = length(lVec);
		vec3 L = lVec / dist; // true direction to light center -- used for diffuse/atten

		float r = lightRadius[i];
		float atten = 1.0 / (1.0 + (dist * dist) / (r * r));
		float NdotV = max(dot(N, V), 0.0);

		// Diffuse stays on the true light direction -- Lambertian doesn't have a highlight-size
		// problem, only specular does.
		float NdotL = max(dot(N, L), 0.0);
		vec3 F_diffuse = F_Schlick(max(dot(normalize(L + V), V), 0.0), F0);
		vec3 kD = (vec3(1.0) - F_diffuse) * (1.0 - metallic);
		vec3 diffuse = kD * albedo / PI;

		// Specular uses the sphere-light representative point instead of L -- this is what
		// actually makes the highlight bigger/softer as lightSourceRadius grows, unlike
		// lightRadius (attenuation only, see uniform declaration above).
		vec3 Lspec = sphereLightDir(lVec, R, lightSourceRadius[i]);
		vec3 Hspec = normalize(Lspec + V);
		float NdotLspec = max(dot(N, Lspec), 0.0);
		float NdotHspec = max(dot(N, Hspec), 0.0);
		float HdotVspec = max(dot(Hspec, V), 0.0);

		// Widen roughness to conserve energy as the sphere gets bigger/closer -- otherwise a
		// large source would just paint a brighter SMALL highlight instead of a genuinely
		// bigger/softer one (same normalization Karis 2013 uses).
		float alpha = roughness * roughness;
		float alphaPrime = clamp(alpha + lightSourceRadius[i] / (2.0 * dist), 0.0, 1.0);
		float roughnessPrime = sqrt(alphaPrime);

		float D = D_GGX(NdotHspec, roughnessPrime);
		float G = G_Smith(NdotV, NdotLspec, roughnessPrime);
		vec3 F = F_Schlick(HdotVspec, F0);

		vec3 specular = (D * G * F) / max(4.0 * NdotV * NdotLspec, 0.001);

		Lo += diffuse * lightColor[i] * NdotL * atten
			+ specular * lightColor[i] * NdotLspec * atten;
	}

	vec3 worldUp = normalize(mat3(osg_ViewMatrix) * vec3(0.0, 0.0, 1.0));
	float hemi = dot(N, worldUp) * 0.5 + 0.5;
	vec3 ambient = mix(groundColor, skyColor, hemi) * albedo * ao;

	fragColor = vec4(ambient + Lo, 1.0);
}
"""

# --------------------------------------------------------------------------- #
# --hdr mode shaders -- horizontal cross layout, literal GL cubemap face
# directions baked into the geometry (see build_cross_geode() below). Matches
# osgx-ktx2-skybox.cpp/osgx-ibl.cpp's cross-mode convention exactly, which is
# why no Z-up remap is needed here.
# --------------------------------------------------------------------------- #

CROSS_VERTEX_SHADER = """
#version 460 core

in vec4 osg_Vertex;
layout(location = 1) in vec3 faceDir;

out vec3 vDir;

void main() {
	vDir = faceDir;
	gl_Position = vec4(osg_Vertex.xy, 0.0, 1.0);
}
"""

CROSS_FRAGMENT_SHADER = """
#version 460 core

uniform samplerCube envMap;
uniform float mipLevel;

in vec3 vDir;

out vec4 fragColor;

void main() {
	vec3 color = textureLod(envMap, normalize(vDir), mipLevel).rgb;

	// Reinhard tone map + gamma -- the cubemap is linear HDR.
	color = color / (color + vec3(1.0));
	color = pow(color, vec3(1.0 / 2.2));

	fragColor = vec4(color, 1.0);
}
"""

CACHE_DIR = os.path.expanduser("~/.cache/polyhaven")

def slug_from_arg(arg):
	if arg.startswith("http"):
		return urllib.parse.urlparse(arg).path.rstrip("/").split("/")[-1]

	return arg

def _fetch(url, dest):
	req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})

	with urllib.request.urlopen(req, timeout=120) as r, open(dest, "wb") as f:
		f.write(r.read())

def _fetch_polyhaven_metadata(slug):
	osg.notice(f"[polyhaven] fetching metadata for '{slug}'...")

	api_url = f"https://api.polyhaven.com/files/{slug}"

	try:
		req = urllib.request.Request(api_url, headers={"User-Agent": "Mozilla/5.0"})

		return json.loads(urllib.request.urlopen(req, timeout=15).read())

	except Exception as e:
		sys.exit(f"[polyhaven] API request failed: {e}")

def download_polyhaven_texture(slug, res="2k"):
	dest_dir = os.path.join(CACHE_DIR, slug, res)
	gltf_path = os.path.join(dest_dir, f"{slug}_{res}.gltf")

	if os.path.exists(gltf_path):
		osg.notice(f"[polyhaven] cached: {gltf_path}")

		return gltf_path

	os.makedirs(dest_dir, exist_ok=True)

	data = _fetch_polyhaven_metadata(slug)

	try:
		gltf_info = data["gltf"][res]["gltf"]

	except KeyError:
		available = list(data.get("gltf", {}).keys())

		sys.exit(f"[polyhaven] no GLTF at resolution '{res}'. Available: {available}")

	gltf_url = gltf_info["url"]
	includes = gltf_info.get("include", {})

	osg.notice(f"[polyhaven] downloading {slug} {res} GLTF...")

	_fetch(gltf_url, gltf_path)

	for rel_path, file_info in includes.items():
		dest = os.path.join(dest_dir, rel_path)

		os.makedirs(os.path.dirname(dest), exist_ok=True)

		osg.notice(f"[polyhaven] {rel_path}")

		_fetch(file_info["url"], dest)

	osg.notice(f"[polyhaven] done -> {gltf_path}")

	return gltf_path

def download_polyhaven_hdr(slug, res="2k"):
	dest_dir = os.path.join(CACHE_DIR, slug, res)
	hdr_path = os.path.join(dest_dir, f"{slug}_{res}.hdr")

	if os.path.exists(hdr_path):
		osg.notice(f"[polyhaven] cached: {hdr_path}")

		return hdr_path

	os.makedirs(dest_dir, exist_ok=True)

	data = _fetch_polyhaven_metadata(slug)

	try:
		hdr_info = data["hdri"][res]["hdr"]

	except KeyError:
		available = list(data.get("hdri", {}).keys())

		sys.exit(f"[polyhaven] no HDRI at resolution '{res}'. Available: {available}")

	osg.notice(f"[polyhaven] downloading {slug} {res} HDR...")

	_fetch(hdr_info["url"], hdr_path)

	osg.notice(f"[polyhaven] done -> {hdr_path}")

	return hdr_path

# --------------------------------------------------------------------------- #
# --hdr mode: cross-shaped skybox display
# --------------------------------------------------------------------------- #

# 6 quads in NDC, arranged as a horizontal cross (4 cols x 3 rows), unindexed
# (2 triangles/6 verts per face) -- osg.DrawElementsUInt isn't exposed to
# Python in this binding, only osg.DrawArrays, so there's no index buffer.
#
# [+Y] row 2
# [-X] [+Z] [+X] [-Z] row 1
# [-Y] row 0
#
# Directions per corner follow the OpenGL cubemap spec (dir(s,t) = MA +
# (2s-1)*SC + (2t-1)*TC) and match osgx-ktx2-skybox.cpp/osgx-ibl.cpp's cross
# layout exactly.
CROSS_FACES = (
	# +Y
	(-0.25, 2.0 / 3.0, ((-1, 1, -1), (1, 1, -1), (1, 1, 1), (-1, 1, 1))),
	# -X
	(-0.75, 0.0, ((-1, 1, -1), (-1, 1, 1), (-1, -1, 1), (-1, -1, -1))),
	# +Z
	(-0.25, 0.0, ((-1, 1, 1), (1, 1, 1), (1, -1, 1), (-1, -1, 1))),
	# +X
	(0.25, 0.0, ((1, 1, 1), (1, 1, -1), (1, -1, -1), (1, -1, 1))),
	# -Z
	(0.75, 0.0, ((1, 1, -1), (-1, 1, -1), (-1, -1, -1), (1, -1, -1))),
	# -Y
	(-0.25, -2.0 / 3.0, ((-1, -1, 1), (1, -1, 1), (1, -1, -1), (-1, -1, -1))),
)

def build_cross_geode(cubemap, mip_uniform):
	cw = 0.25
	ch = 1.0 / 3.0

	vert_list = []
	dir_list = []

	for cx, cy, corner_dirs in CROSS_FACES:
		corners = (
			(cx - cw, cy - ch),
			(cx + cw, cy - ch),
			(cx + cw, cy + ch),
			(cx - cw, cy + ch),
		)
		quad = tuple(zip(corners, corner_dirs)) # (BL, BR, TR, TL), each ((x, y), dir)

		for (x, y), d in (quad[0], quad[1], quad[2], quad[0], quad[2], quad[3]):
			vert_list.append(osg.Vec3(x, y, 0.0))
			dir_list.append(osg.Vec3(*d))

	dirs = osg.Vec3Array(dir_list)
	dirs.binding = osg.Array.BIND_PER_VERTEX

	geom = osg.Geometry(
		vertexArray=osg.Vec3Array(vert_list),
		primitiveSets=(osg.DrawArrays(osg.PrimitiveSet.TRIANGLES, 0, len(vert_list)),)
	)
	geom.vertexAttrib[1] = dirs

	p = osg.Program(name="polyhaven_cross", shaders=(
		osg.Shader(osg.Shader.VERTEX, CROSS_VERTEX_SHADER),
		osg.Shader(osg.Shader.FRAGMENT, CROSS_FRAGMENT_SHADER),
	))
	p.bindAttribLocation["faceDir"] = 1

	geode = osg.Geode()
	geode.drawables.append(geom)

	ss = geode.stateSet

	ss.setMode(GL_CULL_FACE, osg.StateAttribute.OFF | osg.StateAttribute.OVERRIDE)
	ss.setMode(GL_DEPTH_TEST, osg.StateAttribute.OFF | osg.StateAttribute.OVERRIDE)
	ss.setMode(GL_TEXTURE_CUBE_MAP_SEAMLESS, osg.StateAttribute.ON)
	ss.setAttributeAndModes(p)
	ss.textureAttributes[0] = cubemap
	ss.uniforms["envMap"] = 0
	ss.uniforms.extend((mip_uniform,))

	return geode

class MipScrollHandler(osgGA.GUIEventHandler):
	"""
	+/-, ,/., or scroll to step the roughness mip level -- matches
	osgx-ibl.cpp's MipScrollHandler so the tools share muscle memory.
	"""

	def __init__(self, mip_uniform, max_mip):
		super().__init__()

		self.mip_uniform = mip_uniform
		self.max_mip = max_mip
		self.mip_level = 0.0

	def handle(self, ea, aa):
		delta = 0.0

		if ea.type == osgGA.GUIEventAdapter.KEYDOWN:
			if ea.key in (ord("+"), ord("=")):
				delta = 1.0

			elif ea.key in (ord("-"), ord("_")):
				delta = -1.0

			elif ea.key in (ord("."), ord(">")):
				delta = 0.25

			elif ea.key in (ord(","), ord("<")):
				delta = -0.25

			else:
				return False

		elif ea.type == osgGA.GUIEventAdapter.SCROLL:
			if ea.scrollingMotion == osgGA.GUIEventAdapter.SCROLL_UP:
				delta = 0.5

			elif ea.scrollingMotion == osgGA.GUIEventAdapter.SCROLL_DOWN:
				delta = -0.5

			else:
				return False

		else:
			return False

		self.mip_level = max(0.0, min(float(self.max_mip), self.mip_level + delta))
		self.mip_uniform.value = self.mip_level

		osg.notice(f"[polyhaven] mip level {self.mip_level:.2f} / {self.max_mip}")

		return True

def run_texture(args):
	src = args.source

	if src.endswith(".gltf") and os.path.exists(src):
		gltf_path = src

	else:
		gltf_path = download_polyhaven_texture(slug_from_arg(src), args.res)

	root = osgDB.readNodeFile(gltf_path)

	if not root:
		sys.exit(f"[polyhaven] osgDB failed to load: {gltf_path}")

	p = osg.Program(name="polyhaven_pbr", shaders=(
		osg.Shader(osg.Shader.VERTEX, VERTEX_SHADER),
		osg.Shader(osg.Shader.FRAGMENT, FRAGMENT_SHADER),
	))

	ss = root.stateSet
	ss.setAttributeAndModes(p)

	ss.uniforms["baseColorTex"] = 0
	ss.uniforms["normalTex"] = 1
	ss.uniforms["ormTex"] = 2
	ss.uniforms["skyColor"] = osg.Vec3(0.18, 0.20, 0.25)
	ss.uniforms["groundColor"] = osg.Vec3(0.05, 0.04, 0.03)

	lightPos = osg.Uniform(osg.Uniform.Type.FLOAT_VEC3, "lightPos", (
		osg.Vec3(-3.0, 4.0, 5.0), # warm key: upper-left
		osg.Vec3( 4.0, -2.0, 2.0) # cool fill: lower-right
	))

	lightColor = osg.Uniform(osg.Uniform.Type.FLOAT_VEC3, "lightColor", (
		osg.Vec3(7.0, 6.6, 5.6), # warm white key
		osg.Vec3(1.5, 1.8, 4.0) # cool blue fill
	))

	lightRadius = osg.Uniform(osg.Uniform.Type.FLOAT, "lightRadius", (28.0, 26.0))

	lightSourceRadius = osg.Uniform(osg.Uniform.Type.FLOAT, "lightSourceRadius", (
		args.light_source_radius, args.light_source_radius
	))

	ss.uniforms.extend((lightPos, lightColor, lightRadius, lightSourceRadius))

	v = osgViewer.Viewer()

	v.sceneData = root
	v.cameraManipulator = osgGA.TrackballManipulator()
	v.camera.clearColor = osg.Vec4(0.08, 0.08, 0.08, 1.0)

	while not v.done:
		v.frame()

def run_hdr(args):
	src = args.source

	if src.lower().endswith((".hdr", ".exr")) and os.path.exists(src):
		hdr_path = src

	else:
		hdr_path = download_polyhaven_hdr(slug_from_arg(src), args.res)

	root = osg.Group()

	v = osgViewer.Viewer()

	v.sceneData = root
	v.cameraManipulator = osgGA.TrackballManipulator()
	v.camera.clearColor = osg.Vec4(0.05, 0.05, 0.05, 1.0)

	# The bake needs a real GL context (PRE_RENDER FBO cameras), so realize
	# one frame of nothing before touching osgx.ibl -- same ordering
	# 10-dynamicprobes.py uses for its first live bake.
	v.frame()

	image = osgDB.readImageFile(hdr_path)

	if not image:
		sys.exit(f"[polyhaven] osgDB failed to load: {hdr_path}")

	osg.notice(
		f"[polyhaven] baking GGX prefilter "
		f"({args.prefilter_size}x{args.prefilter_size}, {args.samples} samples)..."
	)

	options = osgx.ibl.GGXPrefilterOptions()

	options.prefilterSize = args.prefilter_size
	options.sampleCount = args.samples
	options.maxFrames = args.max_frames
	options.readbackFrame = 2

	bake_scene = osgx.ibl.createGGXPrefilterScene(image, options)

	root.children.append(bake_scene.root)
	v.camera.postDrawCallback = bake_scene.readback

	frame = 0

	while frame < options.maxFrames and not bake_scene.readback.done:
		v.frame()

		frame += 1

	v.camera.postDrawCallback = None
	bake_scene.root.nodeMask = 0

	if not bake_scene.readback.done:
		sys.exit("[polyhaven] GGX prefilter bake did not complete")

	cubemap = osgx.ibl.finishGGXPrefilter(bake_scene.readback)

	# GPU-baked mips are already embedded per-face -- don't let OSG
	# regenerate them (see GGXPrefilter.hpp).
	cubemap.useHardwareMipMapGeneration = False

	# Matches GGXPrefilter.cpp's own mipCountForSize(): the highest valid mip
	# index for a power-of-two cube face, i.e. floor(log2(size)).
	max_mip = int(math.floor(math.log2(args.prefilter_size)))
	mip_uniform = osg.Uniform("mipLevel", 0.0)

	root.children.append(build_cross_geode(cubemap, mip_uniform))
	v.eventHandlers.append(MipScrollHandler(mip_uniform, max_mip))

	osg.notice(
		f"[polyhaven] done -- {max_mip + 1} mip levels; "
		"+/-, ,/., or scroll to step roughness"
	)

	while not v.done:
		v.frame()

if __name__ == "__main__":
	osg.setNotifyLevel(osg.NotifySeverity.NOTICE)

	ap = argparse.ArgumentParser(
		description="Render a Polyhaven texture (PBR sphere) or HDRI (cross-shaped skybox)"
	)
	ap.add_argument(
		"source", nargs="?", default=None,
		help="Polyhaven slug, URL, or local file path "
			"(default: worn_brick_wall for --texture, qwantani_dusk_2 for --hdr)"
	)

	mode_group = ap.add_mutually_exclusive_group()
	mode_group.add_argument(
		"--texture", action="store_true",
		help="Render the asset as a Cook-Torrance PBR sphere (default)"
	)
	mode_group.add_argument(
		"--hdr", action="store_true",
		help="GGX-prefilter the HDRI and display it as a cross-shaped skybox (read-only)"
	)

	ap.add_argument(
		"--res", default="2k",
		help="Download resolution, e.g. 1k/2k/4k/8k -- availability depends on the asset "
			"(default: 2k)"
	)
	ap.add_argument(
		"--light-source-radius", type=float, default=1.0,
		help="[--texture] Physical sphere radius of both lights, in scene units -- widens/"
			"softens the specular highlight itself (0 = point light, sharp). NOT the same as "
			"the existing per-light falloff distance. Default: 1.0"
	)
	ap.add_argument(
		"--prefilter-size", type=int, default=256,
		help="[--hdr] GPU prefilter cubemap face size (default: 256)"
	)
	ap.add_argument(
		"--samples", type=int, default=1024,
		help="[--hdr] GGX prefilter sample count (default: 1024)"
	)
	ap.add_argument(
		"--max-frames", type=int, default=8,
		help="[--hdr] Max frames to wait for the bake's GPU readback (default: 8)"
	)
	args = ap.parse_args()

	if args.source is None:
		args.source = "qwantani_dusk_2" if args.hdr else "worn_brick_wall"

	if args.hdr:
		run_hdr(args)

	else:
		run_texture(args)
