#!/usr/bin/env python3
#vimrun! ../examples/pyosg-polyhaven-texture.py
#
# pyosg-polyhaven-texture.py worn_brick_wall
# pyosg-polyhaven-texture.py https://polyhaven.com/a/worn_brick_wall
# pyosg-polyhaven-texture.py /path/to/local.gltf
# pyosg-polyhaven-texture.py worn_brick_wall --res 4k

import sys
import os
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

CACHE_DIR = os.path.expanduser("~/.cache/polyhaven")

def slug_from_arg(arg):
	if arg.startswith("http"):
		return urllib.parse.urlparse(arg).path.rstrip("/").split("/")[-1]

	return arg

def download_polyhaven(slug, res="2k"):
	dest_dir = os.path.join(CACHE_DIR, slug, res)
	gltf_path = os.path.join(dest_dir, f"{slug}_{res}.gltf")

	if os.path.exists(gltf_path):
		osg.notice(f"[polyhaven] cached: {gltf_path}")

		return gltf_path

	os.makedirs(dest_dir, exist_ok=True)

	osg.notice(f"[polyhaven] fetching metadata for '{slug}'...")
	api_url = f"https://api.polyhaven.com/files/{slug}"

	try:
		req = urllib.request.Request(api_url, headers={"User-Agent": "Mozilla/5.0"})
		data = json.loads(urllib.request.urlopen(req, timeout=15).read())

	except Exception as e:
		sys.exit(f"[polyhaven] API request failed: {e}")

	try:
		gltf_info = data["gltf"][res]["gltf"]

	except KeyError:
		available = list(data.get("gltf", {}).keys())

		sys.exit(f"[polyhaven] no GLTF at resolution '{res}'. Available: {available}")

	gltf_url = gltf_info["url"]
	includes = gltf_info.get("include", {})

	def fetch(url, dest):
		req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})

		with urllib.request.urlopen(req, timeout=60) as r, open(dest, "wb") as f:
			f.write(r.read())

	osg.notice(f"[polyhaven] downloading {slug} {res} GLTF...")

	fetch(gltf_url, gltf_path)

	for rel_path, file_info in includes.items():
		dest = os.path.join(dest_dir, rel_path)

		os.makedirs(os.path.dirname(dest), exist_ok=True)

		osg.notice(f"[polyhaven] {rel_path}")

		fetch(file_info["url"], dest)

	osg.notice(f"[polyhaven] done -> {gltf_path}")

	return gltf_path

if __name__ == "__main__":
	osg.setNotifyLevel(osg.NotifySeverity.NOTICE)

	ap = argparse.ArgumentParser(
		description="Render a Polyhaven texture on a sphere using Cook-Torrance PBR"
	)
	ap.add_argument(
		"source", nargs="?", default="worn_brick_wall",
		help="Polyhaven slug, URL, or local .gltf path (default: worn_brick_wall)"
	)
	ap.add_argument(
		"--res", default="2k", choices=["1k", "2k", "4k"],
		help="Download resolution (default: 2k)"
	)
	ap.add_argument(
		"--light-source-radius", type=float, default=1.0,
		help="Physical sphere radius of both lights, in scene units -- widens/softens the "
			"specular highlight itself (0 = point light, sharp). NOT the same as the "
			"existing per-light falloff distance. Default: 1.0"
	)
	args = ap.parse_args()

	src = args.source

	if src.endswith(".gltf") and os.path.exists(src):
		gltf_path = src

	else:
		gltf_path = download_polyhaven(slug_from_arg(src), args.res)

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
