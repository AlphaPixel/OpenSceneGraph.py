#!/usr/bin/env python3

"""Three scenes, all demonstrating the same thing from different angles: how to inject into and
customize OSG.py/osgx's PBR material pipeline. Each scene picks a different point in that
pipeline to hook:

- sweep [default] -- the SANCTIONED path: a real osgx.Material StateAttribute per mesh, under a
  live GL context, rendered via osgx.gltf.pbribl.PBRIBLScene.create() -- the same production
  PBR/IBL pipeline pyosg-khronos-viewer.py uses for real glTF assets, applied here to plain
  osgx/OSG geometry instead (see pyosg-metal-sphere.py for the single-shape version of this same
  idea, and aipython/30-pbribl.md's "PBRIBLScene.create() is not limited to glTF-loaded nodes"
  section). Two rows of small osgx Polyhedron instances (--shape: tetrahedron/cube/octahedron/
  icosahedron [default]/dodecahedron/pentagonal-trapezohedron): metallic=0.0 (dielectric) on top,
  metallic=1.0 (metal) on the bottom, roughness sweeping left to right on both rows. A fixed
  reddish baseColor makes the metal/dielectric difference obvious -- metals tint their specular
  by albedo, dielectrics keep a neutral white F0=0.04 specular. A single osg.ShapeDrawable
  "chrome ball" (metallic=1.0, roughness=0.0, near-white base color) sits in front of the two
  rows -- a smooth continuous surface gives roughness/metallic every angle to show up, unlike a
  polyhedron's flat facets, and confirms osgx.Material also works as a plain
  StateSet.attributes.append() on vanilla geometry, not just osgx's own shapes.

- glitter -- the BYPASS path, take one: fine, camera-stable specular sparkle/"dust", driven by a
  hand-rolled per-face vertex attribute instead of a real osgx.Material StateAttribute. Started
  as osgx's "how do we reproduce, on a bare osgx.Polyhedron, the accidental dust-grain look that
  fell out of osgx-gbuffer-dice.cpp's curvature estimator at an extreme gain" thread (see osgx's
  CLAUDE.md/TODO.md for the fuller writeup of the original accident). A cellular/Voronoi hash
  partitions world-space position into irregular cells, each contributing a small CONSTANT random
  offset to the shading NORMAL before it reaches osgx_DirectLighting() -- a real normal
  perturbation, not a color mask, so it's a genuine PBR/lighting interaction (confirmed live: a
  tight near-mirror lobe reads as loud dense sparkle, a fully rough dielectric lobe averages the
  same jitter away to nearly nothing). The 20-face metallic/roughness sweep (GLITTER_MATERIAL_
  COMBOS, one (metallic, roughness) pair per face, cycling) demonstrates that coupling across one
  object. Confirmed camera-stable (doesn't swim as the view orbits) and correctly scaled (grain
  gets physically bigger/smaller on screen as you zoom, not pinned to a fixed pixel size).

- spots -- the BYPASS path, take two: a winding, contiguous "maze"/animal-print blob pattern
  (multi-octave world-space FBM noise, thresholded, with a second high-frequency hash layered
  onto the THRESHOLD comparison itself so the blob boundary reads as finely jagged/staticky
  rather than a smooth anti-aliased curve), selecting between two real osgx_Material presets
  (cream/rough base, near-black/slightly-glossier spots) fed through osgx_DirectLighting(), same
  as glitter -- but no per-vertex data at all, just fragment-shader math and uniforms. The pattern
  was first tuned in isolation as a raw black/white mask -- the same "isolate the pattern
  question from the lighting question" approach osgx-gbuffer-dice.cpp's own "Wear Mask" debug
  view uses -- before being wired in here. Confirmed live: this reads as genuine hide/coat
  material variation (a sheen difference between patches, not just a flat color swap), and the
  object's own faceted shading still shows through underneath rather than flattening into a
  decal. Live-tunable uniforms: mazeFrequency (blob size), mazeThreshold/mazeOctaves (topology),
  jitterFrequency/jitterAmount (edge fineness/width), baseColor/baseRoughness/baseMetallic and
  spotColor/spotRoughness/spotMetallic (the two material presets). Current maze values still
  leave calmer/quieter blob INTERIORS than the original reference screenshot that inspired this
  mode; next things to try are pushing mazeFrequency higher (more, smaller blobs packed tighter
  leaves less calm interior per blob) and/or widening jitterAmount/mazeEdge together (a wider
  soft zone with the same jitter riding on it eats further into the interiors).

Run standalone (scene name, default "sweep", may be omitted -- see parse_args()):

	./pyosg-material.py
	./pyosg-material.py sweep --shape cube
	./pyosg-material.py --hdr path/to/environment.hdr
	./pyosg-material.py glitter
	./pyosg-material.py spots

Run through the Qt-free example runner (build_scene(w, h) is this file's runnable contract --
see ../pyosg-cli for the convention):

	../pyosg-cli material -- --hdr path/to/environment.hdr
	../pyosg-cli material -- spots
"""

import argparse
import os
import pathlib
import sys

os.environ.setdefault("OSG_WINDOW", "50 50 1000 400")
os.environ.setdefault("OSG_THREADING", "SingleThreaded")
os.environ.setdefault("OSG_GL_CONTEXT_PROFILE_MASK", "1")
os.environ.setdefault("OSG_GL_VERSION", "4.6")
os.environ.setdefault("OSG_GL_CONTEXT_VERSION", "4.6")
os.environ.setdefault(
	"OSG_LIBRARY_PATH", ":".join((
		"/home/cubicool/dev/osgx/BUILD-g++-13.3.0-NOASAN/plugins/ktx2",
		"/home/cubicool/dev/osgx/BUILD-g++-13.3.0-NOASAN/plugins/gltf"
	))
)

from pyosg_example import label

from OpenSceneGraph import *
from OpenSceneGraph.GL import *

import osgx

# Must happen before the first GraphicsContext is created -- see pyosg-metal-sphere.py/
# pyosg-khronos-viewer.py's own module-level numMultiSamples = 8. Without this, a near-mirror
# surface's fast-changing reflection has nothing smoothing it and looks visibly noisy/jagged.
osg.DisplaySettings.instance.numMultiSamples = 8

# The one directional light every scene below shares -- factored out now that having all three
# scenes in one file makes the duplication obvious (each used to carry its own identical copy).
def build_light_set():
	lights = osgx.LightSet()

	lights.setCount(1)
	lights.setDirectional(0, osg.Vec3(0.3, 0.5, -1.0), osg.Vec3(1.0, 0.97, 0.9), 3.0)

	return lights

# ---------------------------------------------------------------------------------------------
# sweep
# ---------------------------------------------------------------------------------------------

SWEEP_BASE_COLOR = (0.75, 0.15, 0.12)
SWEEP_ROUGHNESS_STEPS = (0.05, 0.20, 0.40, 0.60, 0.80, 1.00)
SWEEP_SPACING = 1.4

# Near-white, not pure black-and-white -- a metal with albedo (1,1,1) is non-physical (real metals
# always absorb SOME wavelengths; that's what gives gold/copper their tint), but close enough here,
# and keeping it colorless is the whole point -- see the sphere's own module-doc paragraph above.
SWEEP_SPHERE_BASE_COLOR = (0.95, 0.95, 0.95)
SWEEP_SPHERE_RADIUS = 0.75

# All six share the exact same (center, radius, layout) constructor -- see osgx-shapes.cpp.
SWEEP_SHAPES = {
	"tetrahedron": osgx.Tetrahedron,
	"cube": osgx.Cube,
	"octahedron": osgx.Octahedron,
	"icosahedron": osgx.Icosahedron,
	"dodecahedron": osgx.Dodecahedron,
	"pentagonal-trapezohedron": osgx.PentagonalTrapezohedron,
}
SWEEP_SHAPE_RADIUS = 0.55

# Verbatim from pyosg-khronos-viewer.py -- same HDR/manifest resolution contract (a literal path,
# then osgx.findDataFile()), duplicated rather than imported since these example scripts are each
# independently runnable, same reasoning osgx's own conftest.py gives for not sharing test helpers
# cross-repo.
def resolve_asset(value, suffix, candidates=()):
	path = pathlib.Path(value).expanduser()

	if path.is_file():
		return path

	resolved = osgx.findDataFile(value, list(candidates), suffix)

	if resolved:
		return pathlib.Path(resolved)

	raise FileNotFoundError(f"Cannot find {value!r}")

# OSG_FILE_PATH doesn't cover osgx's own build-tree env/ manifests -- see
# pyosg-metal-sphere.py's identical helper for why OSGX_ENV_DIR is needed as a fallback.
OSGX_ENV_DIR = pathlib.Path("/home/cubicool/dev/osgx/BUILD-g++-13.3.0-NOASAN/env")

def resolve_environment_manifest(value):
	path = pathlib.Path(value).expanduser()

	if path.is_file():
		return path

	resolved = osgx.findDataFile(value, ("env/{}.gltf",))

	if resolved:
		return pathlib.Path(resolved)

	candidate = OSGX_ENV_DIR / f"{value}.gltf"

	if candidate.is_file():
		return candidate

	raise FileNotFoundError(f"Cannot find environment manifest {value!r}")

# One shape per (metallic, roughness) combo -- a SEPARATE mesh, SEPARATE StateSet, SEPARATE
# osgx.Material each, not one mesh with per-face/per-vertex variation (that's what the glitter
# scene's own GLITTER_MATERIAL_COMBOS already exercises, via a hand-rolled vertex attribute
# instead of a real StateAttribute -- deliberately not what this scene is testing).
def build_sweep_row(y, metallic, shape_cls):
	group = osg.Group(name=f"row-metallic-{metallic}")

	for i, roughness in enumerate(SWEEP_ROUGHNESS_STEPS):
		geode = osg.Geode(name=f"shape-m{metallic}-r{roughness}")
		shape = shape_cls(osg.Vec3(), SWEEP_SHAPE_RADIUS)
		ss = geode.stateSet

		material = osgx.Material()

		material.baseColor = osg.Vec4(*SWEEP_BASE_COLOR, 1.0)
		material.roughness = roughness
		material.metallic = metallic

		ss.attributes.append(material)

		geode.drawables.append(shape)

		xform = osg.MatrixTransform(
			matrix=osg.Matrixd.translate(
				(i - (len(SWEEP_ROUGHNESS_STEPS) - 1) / 2.0) * SWEEP_SPACING, 0.0, y
			)
		)

		xform.children.append(geode)
		group.children.append(xform)

	return group

# The "chrome ball" reflection probe -- see the module docstring's own paragraph on why.
def build_sweep_sphere():
	geode = osg.Geode(name="chrome-sphere")
	drawable = osg.ShapeDrawable(osg.Sphere(osg.Vec3(), SWEEP_SPHERE_RADIUS))
	ss = geode.stateSet

	material = osgx.Material()

	material.baseColor = osg.Vec4(*SWEEP_SPHERE_BASE_COLOR, 1.0)
	material.roughness = 0.0
	material.metallic = 1.0

	ss.attributes.append(material)
	geode.drawables.append(drawable)

	xform = osg.MatrixTransform(matrix=osg.Matrixd.translate(0.0, 1.6, 0.0))

	xform.children.append(geode)

	return xform

def build_sweep_scene(args):
	shapes = osg.Group(name="shapes")
	ss = shapes.stateSet

	ss.modes[GL_CULL_FACE] = osg.StateAttribute.ON
	ss.attributes.append(build_light_set())

	shape_cls = SWEEP_SHAPES[args.shape]

	# TODO: Can this support `extend(node, node, node)`, instead of being REQUIRED to encapsulate
	# everything in a sequence?
	shapes.children.extend((
		build_sweep_row(0.6, 0.0, shape_cls), # dielectric row
		build_sweep_row(-0.6, 1.0, shape_cls), # metal row
		build_sweep_sphere()
	))

	if args.hdr:
		hdr_path = resolve_asset(args.hdr, "hdr", ("glTF-Sample-Environments/{}",))
		environment = osgx.gltf.pbribl.PBRIBLEnvironment.prepare(str(hdr_path), lutSize=1024)

	else:
		env_path = resolve_environment_manifest(args.env)
		environment = osgx.gltf.pbribl.PBRIBLEnvironment.load(str(env_path))

	if not environment.valid():
		raise RuntimeError(f"failed to prepare PBR IBL resources for {args.hdr or args.env}")

	# Program/IBL textures attach to `shapes`' own StateSet, inherited by every child below --
	# only each Geode's own osgx.Material differs, matching how a real scene shares one shader
	# (and one environment) across many differently-materialed primitives. LightSet (above) and
	# the Program PBRIBLScene.create() attaches here coexist on the same StateSet without
	# conflict -- different StateAttribute::Type/member slots (LightSet is Type.CAPABILITY
	# member=1, Material is member=0, Program is its own Type entirely).
	pbr = osgx.gltf.pbribl.PBRIBLScene.create(
		shapes, environment, iblDiffuseIntensity=1.0, iblSpecularIntensity=1.0
	)

	if not pbr.valid():
		raise RuntimeError("failed to apply PBR/IBL environment")

	root = osg.Group(name="root")

	if environment.root is not None:
		root.children.append(environment.root)

	root.children.append(pbr.node)

	return root

# ---------------------------------------------------------------------------------------------
# glitter
# ---------------------------------------------------------------------------------------------

# 1 / GRAIN_FREQUENCY is the physical grain size, in world units, on a radius-1.2 icosahedron --
# tune this first if you retarget a differently-scaled model.
GRAIN_FREQUENCY = 60.0
GRAIN_AMPLITUDE = 0.5

# One (metallic, roughness) pair per icosahedron face, cycling if there are more faces than
# entries -- sweeps from mirror-metal through fully-rough-dielectric so the roughness/grain
# coupling above is visible on one object. A real single-material consumer would drop this and
# just set flat `metallic`/`roughness` uniforms instead of a per-face vertex attribute.
GLITTER_MATERIAL_COMBOS = (
	(1.00, 0.00), (0.50, 0.50), (0.00, 1.00), (1.00, 1.00), (0.00, 0.00),
	(0.25, 0.75), (0.75, 0.25), (1.00, 0.50), (0.50, 0.00), (0.00, 0.50),
	(0.75, 0.75), (0.25, 0.25), (0.90, 0.10), (0.10, 0.90), (0.50, 1.00),
	(1.00, 0.25), (0.00, 0.25), (0.60, 0.40), (0.40, 0.60), (0.15, 0.15),
)

GLITTER_VERTEX_SHADER = """
#version 460 core

in vec3 position;
in vec3 normal;
in vec2 materialParams;

uniform mat4 osg_ModelViewProjectionMatrix;
uniform mat4 osg_ModelViewMatrix;
uniform mat3 osg_NormalMatrix;

out vec3 vNormal;
out vec3 vPosition;
out vec2 vMaterialParams;

void main() {
	vNormal = osg_NormalMatrix * normal;
	vPosition = (osg_ModelViewMatrix * vec4(position, 1.0)).xyz;
	vMaterialParams = materialParams;
	gl_Position = osg_ModelViewProjectionMatrix * vec4(position, 1.0);
}
"""

GLITTER_FRAGMENT_SHADER = """
#version 460 core

const float PI = 3.14159265359;

#pragma osgx::pbr MATERIAL_STRUCT, DIRECT_LIGHTING_DECL

in vec3 vNormal;
in vec3 vPosition;
in vec2 vMaterialParams;

uniform mat4 osg_ViewMatrix;
uniform mat4 osg_ViewMatrixInverse;

uniform vec3 albedo;
uniform vec3 ambientColor;
uniform float ambientIntensity;

uniform float grainFrequency;
uniform float grainAmplitude;

out vec4 fragColor;

float hash13(vec3 p) {
	p = fract(p * 0.1031);
	p += dot(p, p.yzx + 33.33);
	return fract((p.x + p.y) * p.z);
}

vec3 cellPoint(vec3 cell) {
	vec3 h = vec3(
		hash13(cell + vec3(11.1, 0.0, 0.0)),
		hash13(cell + vec3(0.0, 27.3, 0.0)),
		hash13(cell + vec3(0.0, 0.0, 71.7))
	);
	return cell + h;
}

// Cellular/Voronoi partition -- irregular grain SHAPES (nearest jittered feature point wins),
// but still a per-cell CONSTANT random normal offset once a winning cell is found. No distance
// value is used as a mask/color anywhere -- only the cell SHAPE changes, not what's done with it.
vec3 grainOffset(vec3 p) {
	vec3 baseCell = floor(p);
	float bestDist = 1e9;
	vec3 bestCell = baseCell;

	for(int z = -1; z <= 1; z++) {
		for(int y = -1; y <= 1; y++) {
			for(int x = -1; x <= 1; x++) {
				vec3 cell = baseCell + vec3(x, y, z);
				float d = distance(p, cellPoint(cell));

				if(d < bestDist) {
					bestDist = d;
					bestCell = cell;
				}
			}
		}
	}

	return vec3(
		hash13(bestCell + vec3(17.1, 0.0, 0.0)),
		hash13(bestCell + vec3(0.0, 43.7, 0.0)),
		hash13(bestCell + vec3(0.0, 0.0, 91.3))
	) - 0.5;
}

void main() {
	osgx_Material mat;

	mat3 invViewRot = transpose(mat3(osg_ViewMatrix));
	vec3 geomN = invViewRot * normalize(vNormal);
	vec3 V = invViewRot * normalize(-vPosition);
	vec3 worldPos = (osg_ViewMatrixInverse * vec4(vPosition, 1.0)).xyz;

	vec3 grain = grainOffset(worldPos * grainFrequency) * grainAmplitude;
	vec3 N = normalize(geomN + grain);

	float metallic = clamp(vMaterialParams.x, 0.0, 1.0);
	float roughness = clamp(vMaterialParams.y, 0.04, 1.0);

	mat.albedo = albedo;
	mat.ao = 1.0;
	mat.roughness = roughness;
	mat.metallic = metallic;
	mat.F0 = mix(vec3(0.04), albedo, metallic);

	vec3 color = ambientColor * ambientIntensity * mat.albedo * mat.ao;

	color += osgx_DirectLighting(N, V, worldPos, mat);

	color = pow(clamp(color, vec3(0.0), vec3(1.0)), vec3(1.0 / 2.2));

	fragColor = vec4(color, 1.0);
}
"""

def build_glitter_scene():
	geode = osg.Geode(name="glitter-icosahedron")
	shape = osgx.Icosahedron(osg.Vec3(), 1.2)
	ss = geode.stateSet

	material_array = osg.Vec2Array([
		osg.Vec2(*GLITTER_MATERIAL_COMBOS[i % len(GLITTER_MATERIAL_COMBOS)])
		for i in range(len(shape.faces))
	])

	shape.setFaceAttribute(2, material_array)
	shape.rebuild()

	geode.drawables.append(shape)
	ss.modes[GL_CULL_FACE] = osg.StateAttribute.ON

	program = osg.Program(name="pyosg-material-glitter", shaders=(
		osg.Shader(osg.Shader.VERTEX, GLITTER_VERTEX_SHADER, name="glitter-vertex"),
		osg.Shader(
			osg.Shader.FRAGMENT, osgx.resolveShaderLibs(GLITTER_FRAGMENT_SHADER), name="glitter-fragment"
		),
		osgx.makeDirectLightingHookShader(),
	))
	program.bindAttribLocation["position"] = 0
	program.bindAttribLocation["normal"] = 1
	program.bindAttribLocation["materialParams"] = 2

	ss.attributes[osg.StateAttribute.PROGRAM] = program
	ss.uniforms.update({
		"albedo": osg.Vec3(0.05, 0.05, 0.06),
		"ambientColor": osg.Vec3(1.0, 1.0, 1.0),
		"ambientIntensity": 0.15,
		"grainFrequency": GRAIN_FREQUENCY,
		"grainAmplitude": GRAIN_AMPLITUDE,
	})
	ss.attributes.append(build_light_set())

	root = osg.Group(name="root")

	root.children.append(geode)

	return root

# ---------------------------------------------------------------------------------------------
# spots
# ---------------------------------------------------------------------------------------------

SPOTS_MAZE_FREQUENCY = 15.0
SPOTS_MAZE_THRESHOLD = 0.5
SPOTS_MAZE_EDGE = 0.002
SPOTS_MAZE_OCTAVES = 5
SPOTS_JITTER_FREQUENCY = 500.0
SPOTS_JITTER_AMOUNT = 0.10

# The two osgx_Material presets the spot mask blends between -- animal-print styling: cream/
# rough base, near-black/slightly-glossier spots (a real roughness difference, not just color,
# so the two patches catch specular light differently under osgx_DirectLighting()).
SPOTS_BASE_COLOR = (0.85, 0.78, 0.65)
SPOTS_BASE_ROUGHNESS = 0.6
SPOTS_BASE_METALLIC = 0.0
SPOTS_SPOT_COLOR = (0.05, 0.05, 0.05)
SPOTS_SPOT_ROUGHNESS = 0.35
SPOTS_SPOT_METALLIC = 0.0

SPOTS_VERTEX_SHADER = """
#version 460 core

in vec3 position;
in vec3 normal;

uniform mat4 osg_ModelViewProjectionMatrix;
uniform mat4 osg_ModelViewMatrix;
uniform mat3 osg_NormalMatrix;

out vec3 vNormal;
out vec3 vPosition;

void main() {
	vNormal = osg_NormalMatrix * normal;
	vPosition = (osg_ModelViewMatrix * vec4(position, 1.0)).xyz;
	gl_Position = osg_ModelViewProjectionMatrix * vec4(position, 1.0);
}
"""

SPOTS_FRAGMENT_SHADER = """
#version 460 core

const float PI = 3.14159265359;

#pragma osgx::pbr MATERIAL_STRUCT, DIRECT_LIGHTING_DECL

in vec3 vNormal;
in vec3 vPosition;

uniform mat4 osg_ViewMatrix;
uniform mat4 osg_ViewMatrixInverse;

uniform vec3 ambientColor;
uniform float ambientIntensity;

uniform float mazeFrequency;
uniform float mazeThreshold;
uniform float mazeEdge;
uniform int mazeOctaves;
uniform float jitterFrequency;
uniform float jitterAmount;

uniform vec3 baseColor;
uniform float baseRoughness;
uniform float baseMetallic;
uniform vec3 spotColor;
uniform float spotRoughness;
uniform float spotMetallic;

out vec4 fragColor;

float hash13(vec3 p) {
	p = fract(p * 0.1031);
	p += dot(p, p.yzx + 33.33);
	return fract((p.x + p.y) * p.z);
}

float valueNoise3(vec3 p) {
	vec3 i = floor(p);
	vec3 f = fract(p);
	vec3 u = f * f * (3.0 - 2.0 * f);

	float n000 = hash13(i + vec3(0.0, 0.0, 0.0));
	float n100 = hash13(i + vec3(1.0, 0.0, 0.0));
	float n010 = hash13(i + vec3(0.0, 1.0, 0.0));
	float n110 = hash13(i + vec3(1.0, 1.0, 0.0));
	float n001 = hash13(i + vec3(0.0, 0.0, 1.0));
	float n101 = hash13(i + vec3(1.0, 0.0, 1.0));
	float n011 = hash13(i + vec3(0.0, 1.0, 1.0));
	float n111 = hash13(i + vec3(1.0, 1.0, 1.0));

	float nx00 = mix(n000, n100, u.x);
	float nx10 = mix(n010, n110, u.x);
	float nx01 = mix(n001, n101, u.x);
	float nx11 = mix(n011, n111, u.x);

	float nxy0 = mix(nx00, nx10, u.y);
	float nxy1 = mix(nx01, nx11, u.y);

	return mix(nxy0, nxy1, u.z);
}

float fbm3(vec3 p) {
	float sum = 0.0;
	float amp = 0.5;
	float freq = 1.0;

	for(int i = 0; i < 8; i++) {
		if(i >= mazeOctaves) break;

		sum += amp * valueNoise3(p * freq);
		freq *= 2.0;
		amp *= 0.5;
	}

	return sum;
}

void main() {
	osgx_Material mat;

	mat3 invViewRot = transpose(mat3(osg_ViewMatrix));
	vec3 N = invViewRot * normalize(vNormal);
	vec3 V = invViewRot * normalize(-vPosition);
	vec3 worldPos = (osg_ViewMatrixInverse * vec4(vPosition, 1.0)).xyz;

	float n = fbm3(worldPos * mazeFrequency);
	float jitter = (hash13(worldPos * jitterFrequency) - 0.5) * jitterAmount;
	float spot = smoothstep(mazeThreshold - mazeEdge, mazeThreshold + mazeEdge, n + jitter);

	mat.albedo = mix(baseColor, spotColor, spot);
	mat.ao = 1.0;
	mat.roughness = mix(baseRoughness, spotRoughness, spot);
	mat.metallic = mix(baseMetallic, spotMetallic, spot);
	mat.F0 = mix(vec3(0.04), mat.albedo, mat.metallic);

	vec3 color = ambientColor * ambientIntensity * mat.albedo * mat.ao;

	color += osgx_DirectLighting(N, V, worldPos, mat);

	color = pow(clamp(color, vec3(0.0), vec3(1.0)), vec3(1.0 / 2.2));

	fragColor = vec4(color, 1.0);
}
"""

def build_spots_scene():
	geode = osg.Geode(name="spots-icosahedron")
	shape = osgx.Icosahedron(osg.Vec3(), 1.2)
	ss = geode.stateSet

	geode.drawables.append(shape)
	ss.modes[GL_CULL_FACE] = osg.StateAttribute.ON

	program = osg.Program(name="pyosg-material-spots", shaders=(
		osg.Shader(osg.Shader.VERTEX, SPOTS_VERTEX_SHADER, name="spots-vertex"),
		osg.Shader(
			osg.Shader.FRAGMENT, osgx.resolveShaderLibs(SPOTS_FRAGMENT_SHADER), name="spots-fragment"
		),
		osgx.makeDirectLightingHookShader(),
	))
	program.bindAttribLocation["position"] = 0
	program.bindAttribLocation["normal"] = 1

	ss.attributes[osg.StateAttribute.PROGRAM] = program
	ss.uniforms.update({
		"ambientColor": osg.Vec3(1.0, 1.0, 1.0),
		"ambientIntensity": 0.15,
		"mazeFrequency": SPOTS_MAZE_FREQUENCY,
		"mazeThreshold": SPOTS_MAZE_THRESHOLD,
		"mazeEdge": SPOTS_MAZE_EDGE,
		"mazeOctaves": SPOTS_MAZE_OCTAVES,
		"jitterFrequency": SPOTS_JITTER_FREQUENCY,
		"jitterAmount": SPOTS_JITTER_AMOUNT,
		"baseColor": osg.Vec3(*SPOTS_BASE_COLOR),
		"baseRoughness": SPOTS_BASE_ROUGHNESS,
		"baseMetallic": SPOTS_BASE_METALLIC,
		"spotColor": osg.Vec3(*SPOTS_SPOT_COLOR),
		"spotRoughness": SPOTS_SPOT_ROUGHNESS,
		"spotMetallic": SPOTS_SPOT_METALLIC,
	})
	ss.attributes.append(build_light_set())

	root = osg.Group(name="root")

	root.children.append(geode)

	return root

# ---------------------------------------------------------------------------------------------

SCENES = ("sweep", "glitter", "spots")

# Scene name is a subcommand (each scene owns its own flags -- only "sweep" takes --shape/--hdr/
# --env, and there's no reason for "glitter"/"spots" to inherit those), but it's also OPTIONAL:
# bare `./pyosg-material.py` or `./pyosg-material.py --hdr foo.hdr` must keep working exactly as
# pyosg-material.py always has, so a missing/unrecognized leading token is treated as "sweep" was
# typed explicitly, rather than making everyone type `sweep` for the default scene.
def parse_args():
	parser = argparse.ArgumentParser(description=__doc__)
	subparsers = parser.add_subparsers(dest="scene")

	sweep = subparsers.add_parser("sweep", help="metallic/roughness grid via osgx.Material (default)")

	sweep.add_argument(
		"--shape",
		choices=sorted(SWEEP_SHAPES),
		default="icosahedron",
		help="which osgx Polyhedron to use for the two rows (default: icosahedron)"
	)

	sweep_environment = sweep.add_mutually_exclusive_group()

	sweep_environment.add_argument(
		"--hdr",
		metavar="PATH",
		help="source HDR environment; bakes diffuse, BRDF LUT, and GGX-prefiltered specular live"
	)
	sweep_environment.add_argument(
		"--env",
		metavar="MANIFEST",
		default="pisa",
		help="fully pre-baked osgx_pbribl environment manifest (default: pisa)"
	)

	subparsers.add_parser("glitter", help="per-face vertex-attribute-driven normal-perturbation sparkle")
	subparsers.add_parser("spots", help="fragment-shader FBM-driven animal-print material blend")

	argv = sys.argv[1:]

	if not argv or argv[0] not in SCENES:
		argv = ["sweep"] + argv

	return parser.parse_args(argv)

# Recovered by configure_viewer() below (module-level stash -- same convention as
# pyosg-khronos-viewer.py's _args/_pbr -- build_scene()'s own contract is "return a Node", no
# second channel to hand back a plain Python closure it also needs later).
_switch_scene = None

# The real pipeline-assembly entrypoint -- returns the root Node, no viewer/window side effects.
# Matches ../pyosg-cli's convention (and etc/pyside6-glsl.py's Qt-embedded sibling) so both can
# run this too. All three scenes are pure functions of (args) with no shared/global state, so
# switch_scene() below can freely rebuild any of them again later, live.
def build_scene(w, h):
	global _switch_scene

	args = parse_args()

	def make_scene(name):
		if name == "glitter":
			return build_glitter_scene()

		if name == "spots":
			return build_spots_scene()

		return build_sweep_scene(args)

	root = osg.Group(name="root")
	hint = label("1 default | 2 glitter | 3 spots", w, h)
	current = {"scene": make_scene(args.scene)}

	root.children.append(current["scene"])
	root.children.append(hint)

	# Swaps root's scene child for a freshly-built one -- re-appending hint afterward instead of
	# inserting the new scene at a fixed index, since root.children has no positional insert;
	# append+remove is the only mutation every other example in this repo already relies on.
	def switch_scene(name):
		new_scene = make_scene(name)

		root.children.remove(current["scene"])
		root.children.remove(hint)
		root.children.append(new_scene)
		root.children.append(hint)

		current["scene"] = new_scene

	_switch_scene = switch_scene

	return root

# 1/2/3 rebuild and swap in the sweep/glitter/spots scene live -- --scene/--shape/--hdr/--env
# still select the INITIAL scene (and sweep's own look) at startup; this only adds live
# switching between the three on top, matching every other keyboard-driven example in this repo.
class SceneSwitchHandler(osgGA.GUIEventHandler):
	def __init__(self, switch_scene):
		super().__init__()

		self.switch_scene = switch_scene

	def handle(self, ea, aa):
		if ea.handled or ea.type != osgGA.GUIEventAdapter.KEYUP:
			return False

		if ea.key == ord("1"):
			self.switch_scene("sweep")

			return True

		if ea.key == ord("2"):
			self.switch_scene("glitter")

			return True

		if ea.key == ord("3"):
			self.switch_scene("spots")

			return True

		return False

def configure_viewer(viewer, root):
	viewer.eventHandlers.append(SceneSwitchHandler(_switch_scene))

if __name__ == "__main__":
	viewer = osgViewer.Viewer()
	root = build_scene(1000, 400)

	viewer.sceneData = root
	viewer.cameraManipulator = osgGA.TrackballManipulator()
	viewer.cameraManipulator.home(0)

	configure_viewer(viewer, root)

	while not viewer.done:
		viewer.frame()
