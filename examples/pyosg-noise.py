#!/usr/bin/env python3

"""A 24-panel GLSL noise/pattern reference gallery -- value, Perlin (+
analytic derivatives), simplex, Worley (+ derivatives), voronoi, blue noise (plain + Hilbert-
curve), craters, gabor, curl, scratches, wavelet, erosion/gullies, paper, stone, wool, and
interleaved-gradient-noise (IGN), each shown both raw and through a 6-octave fbm. All of it
(the actual noise/fbm/hash functions in FRAGMENT_SHADER_NOISE below) is third-party, used as-is
under its own license -- see the SPDX header inside the shader text itself. Original source
pasted into examples/pyosg-fragcoordxyz.py's "noise" gallery entry; pulled out into its own file
because, in context of osgx's whole "reproduce a fine world-space grain/pattern procedurally"
thread (see pyosg-material.py's "glitter"/"spots" scenes), this is a far more complete reference of exactly that kind of
building block than anything hand-rolled during that investigation.

ARCHITECTURE, SECOND REVISION: back to a SINGLE fullscreen quad + one fragment shader picking
which of the 24 styles to draw via an `id` computed from `gl_FragCoord`, matching the
ORIGINAL pasted version's own approach -- not the 24-separate-Geode/Program NDC-grid rewrite
tried first in this file's history (see git log if curious), which turned out to introduce a
real bug of its own: normalizing every panel's local coordinates independently to the identical
`-6..6` domain centered on `(0,0)` made EVERY panel hit the same floor()-lattice-boundary
artifact several of these noise functions have running through the origin, at once -- visible as
a seam in nearly every panel, confirmed live, not present in the single-shader version (which
only ever put ONE screen position through that boundary, not one per panel).

The single real bug the ORIGINAL version had -- `u_resolution` never refreshed after a window
resize, so `gl_FragCoord` (always live) and `u_resolution` (stale) disagreed about where panel
boundaries were -- is fixed here properly instead of designed around: `u_resolution` is set to
the REAL current viewport size every frame (see the `while not viewer.done:` loop below), same
place `u_time` already updates. A thin border is blackened near each cell's edge (the `margin`
uniform, a fraction of a cell, not a literal pixel count -- falls out of the same `gridF`
fractional-position math already needed for `id`, no extra tracking required) for visual
separation between panels.

The original also drew a text label under each panel by sampling a bitmap font atlas
(`u_tex1`, a `codepage12.png` fetched from a CDN URL) -- that texture was never actually loaded
anywhere in this repo, so the labels were non-functional as pasted, and are still not wired up
here. This repo has its own in-progress "pixel font" work in pyosg_dice.py; plan is to wire real
on-screen labels through that once it lands (LEGEND below is a plain console printout of the
same 24 names as a stand-in until then), plus click-to-fullscreen-in-the-viewer for a single
selected panel -- both explicitly deferred, not forgotten.

ARCHITECTURE, THIRD REVISION: one real osg.Geometry quad per panel (24 total), all sharing a
SINGLE osg.Program -- picking needs real per-object geometry (osgx identifies hits by
rendering the same scene through a second camera keyed on a per-object `pickID` uniform, which
requires each panel to be its own drawable), and the user explicitly asked for this shape
(Program -> Quad(noise 0), Quad(noise 1), ... instead of 20+ Program instances). Two things
carried over from the SECOND REVISION on purpose, not accidents:

- The fragment shader still computes its noise-space `p` from raw `gl_FragCoord`/`u_resolution`,
  never from a panel-local UV -- panel selection is now a `noiseID` uniform instead of a
  computed grid `id`, but the coordinate FEEDING every noise function is still the single
  continuous per-pixel screen position it always was. That's what actually avoided the seam
  bug (see SECOND REVISION above); switching to one draw call per panel doesn't reintroduce it
  as long as this stays true, so don't "simplify" it back to a per-quad local UV.
- Panel boundaries are no longer a shader-side `margin`/`inMargin` fraction -- each quad's own
  vertex positions are inset by PANEL_GAP directly, so the gap is real geometry, and the
  fragment shader no longer needs to know where panel edges are at all.

Since each panel is now real geometry sized/placed in world space, the viewer's master camera
is a fixed orthographic front-on view (see __main__) sized to frame the whole 6x4 grid exactly
-- no osgGA manipulator is attached, so nothing fights that. Both the visible camera and
osgx's pick camera read vertex positions through the standard
`osg_ModelViewProjectionMatrix * osg_Vertex` pipeline (see VERTEX_SHADER below), matching
osgx's own pick-camera shader (osgx/Picking.hpp) -- unlike the ORIGINAL/SECOND-REVISION vertex
shader, which wrote clip-space positions directly and ignored the camera entirely (fine when
there was nothing to pick).

ARCHITECTURE, FOURTH REVISION: the noise domain is world-space now -- `vPos`, a vertex-shader
`out vec2` of the quad's own `osg_Vertex.xy` -- instead of `gl_FragCoord`/`u_resolution`. Both
`u_resolution` and a short-lived `u_viewportOrigin` (added and removed in the same session) are
gone entirely. The THIRD REVISION's caution above ("don't simplify it back to a per-quad local
UV") is still correct about what NOT to do, but incomplete about why: `gl_FragCoord` avoided the
seam bug because it's a single coordinate continuous across the WHOLE visible grid, never reset
per panel -- but `vPos` has that same property, since each quad occupies its own non-overlapping
slice of world space that nothing renormalizes back to a shared per-quad range. World-space gets
the "stay globally continuous" property `gl_FragCoord` needed, without `gl_FragCoord`'s actual
cost: it's screen/window/viewport-dependent, which stopped being free the moment __main__ gave
the ImGui panel its own dead strip of the window (a real camera viewport offset) -- `gl_FragCoord`
needed a manually-tracked origin correction to keep sampling the right region; `vPos` never needed
to know the viewport existed at all. (`gl_FragCoord` tricks like this are exactly what
fragcoord.xyz -- this file's original source, see the top of this docstring -- is named for; fun
shader-golf there, not a requirement here.)

Interactivity (see __main__, NOT build_scene() -- picking/ImGui are viewer-level concerns, kept
out of the same build_scene(w, h) contract pyosg-cli/pyside6-glsl.py rely on, exactly like
pyosg-hover.py/pyosg-picking.py keep their own create_scene() free of them): continuous 1x1
sub-frustum hover picking (same shape as pyosg-hover.py) tints whichever panel the mouse is
over; clicking selects it. An osgx.imgui.Widget panel, docked left, carries one CollapsingHeader
section per noise type (name matches LEGEND) plus a pinned "Overview" section holding the
button that clears the selection. Selecting/deselecting a panel opens/closes its section via
osgx::imgui::Panel::setSectionOpen() -- a small addition to ~/dev/osgx (this build's real
PYOSG_OSGX_SOURCE_DIR, not the etc/osgx submodule pin; see CLAUDE.md) needed because
SectionOptions.defaultOpen only ever seeds ImGui's per-label open state the FIRST time that
label is drawn, with no existing way to force it again afterward -- see that file's own comment
on setSectionOpen() for the full rationale. Requires a rebuild before it takes effect. Each
section's own content is a placeholder for now -- real per-noise controls are next session's
work, not this one's.

Run standalone:

	./pyosg-noise.py

Run through the Qt-free example runner (build_scene(w, h) is this file's runnable contract --
see ../pyosg-cli and examples/pyosg-blur.py's own build_scene() for the convention):

	../pyosg-cli noise
"""

import os
import time

os.environ.setdefault("OSG_WINDOW", "50 50 800 600")
os.environ.setdefault("OSG_THREADING", "SingleThreaded")
os.environ.setdefault("OSG_GL_CONTEXT_PROFILE_MASK", "1")
os.environ.setdefault("OSG_GL_VERSION", "4.6")
os.environ.setdefault("OSG_GL_CONTEXT_VERSION", "4.6")

from OpenSceneGraph import *
from OpenSceneGraph.GL import *

import osgx

# Grid is 6 columns x 4 rows, row-major from the bottom-left (noiseID = col + row * 6).
GRID_COLS = 6
GRID_ROWS = 4

# World-space half-extents of the ortho camera that frames the whole grid (see __main__) --
# unitless, one world unit per cell, deliberately NOT aspect-corrected, matching the ORIGINAL
# single-quad version's own `gridF = fragCoord/resolution*grid` split: cells stretch to fill
# the window in a straight 6x4 division regardless of window aspect, not a square-cell layout.
HALF_W = GRID_COLS / 2.0
HALF_H = GRID_ROWS / 2.0

# Gap between adjacent panels, in the same world units -- real geometry now, replacing the
# shader-side `margin`/`inMargin` fraction the SECOND REVISION used (see docstring above).
PANEL_GAP = 0.03

# Full 1x1 world-space cell for a given noiseID, WITHOUT the PANEL_GAP inset -- build_scene()
# insets this itself for the quad's actual vertices; inspect mode (see __main__) uses the
# un-inset cell directly so the zoomed-in view fills the frame edge-to-edge instead of showing
# the gap border meant for the overview grid.
def cell_bounds(noise_id):
	col = noise_id % GRID_COLS
	row = noise_id // GRID_COLS

	x0 = -HALF_W + col
	y0 = -HALF_H + row

	return x0, y0, x0 + 1.0, y0 + 1.0

LEGEND = (
	"0. VALUE",
	"1. VALUE FBM",
	"2. PERLIN",
	"3. PERLIN FBM",
	"4. SIMPLEX",
	"5. SIMPLEX FBM",
	"6. WORLEY",
	"7. WORLEY FBM",
	"8. BLUE",
	"9. HILBERT BLUE",
	"10. CRATER",
	"11. CRATER FBM",
	"12. GABOR",
	"13. GABOR FBM",
	"14. SCRATCH",
	"15. SCRATCH FBM",
	"16. WAVELET",
	"17. WAVELET FBM",
	"18. EROSION",
	"19. CURL",
	"20. PAPER",
	"21. STONE",
	"22. WOOL",
	"23. IGN",
)

VERTEX_SHADER = """
#version 330 core

in vec4 osg_Vertex;

uniform mat4 osg_ModelViewProjectionMatrix;

// World-space position (no per-object model matrix here, so object space IS world space --
// see build_scene()) -- FRAGMENT_SHADER_NOISE's noise domain is keyed on this, NOT gl_FragCoord.
// Globally continuous across the whole grid exactly like gl_FragCoord was (each quad occupies
// its own non-overlapping world-space slice, never independently renormalized), so it avoids
// the SECOND REVISION's seam bug the same way -- but unlike gl_FragCoord, it's derived from
// object data instead of the window/viewport, so the noise genuinely doesn't depend on the view.
out vec2 vPos;

void main() {
	vPos = osg_Vertex.xy;

	gl_Position = osg_ModelViewProjectionMatrix * osg_Vertex;
}
"""

FRAGMENT_SHADER_NOISE = """#version 430 core
in vec2 vPos;
uniform float u_time;
uniform int noiseID;
uniform float tint;
out vec4 fragColor;

// Global panel -- one set of uniforms, all read at a single choke point (main(), before
// noiseID picks a function, and the fbm12 macro below) so every panel reacts identically
// without touching 24 separate noiseID branches. Defaults live in build_scene() (see its own
// comment) so this shader still renders correctly standalone, with no ImGui panel attached.
uniform float u_scale;
uniform int u_octaves;
uniform float u_lacunarity;
uniform float u_gain;
uniform float u_warp;
uniform float u_animSpeed;

// SPDX-License-Identifier: MIT
// Copyright (c) 2026 @lumiey
//[LICENSE] https://opensource.org/licenses/MIT

/////////// HASHES ///////////
// Fi Hash
float hash11(float p) {
    uint u = floatBitsToUint(p * 3141592653.0);
    return float(u * u * 3141592653u) / float(~0u);
}

float hash12(vec2 p) {
    uvec2 u = floatBitsToUint(p * vec2(141421356, 2718281828));
    return float((u.x ^ u.y) * 3141592653u) / float(~0u);
}

vec2 hash22(vec2 p) {
    uvec2 u = floatBitsToUint(p * vec2(141421356, 2718281828));
    return vec2((u.x ^ u.y) * uvec2(3141592653, 1618033988)) / float(~0u);
}

vec3 hash32(vec2 p) {
    uvec2 u = floatBitsToUint(p * vec2(141421356, 2718281828));
    return vec3((u.x ^ u.y) * uvec3(1732050807, 2645751311, 3316624790)) / float(~0u);
}

float hash13(vec3 p) {
    uvec3 u = floatBitsToUint(p * vec3(141421356, 2718281828, 1618033988));
    return float((u.x ^ u.y ^ u.z) * 3141592653u) / float(~0u);
}

vec3 hash33(vec3 p) {
    uvec3 u = floatBitsToUint(p * vec3(141421356, 2718281828, 1618033988));
    return vec3((u.x ^ u.y ^ u.z) * uvec3(1732050807, 2645751311, 3316624790)) / float(~0u);
}

/////////// 1D NOISE ///////////
float value11(float p) {
	float i = floor(p);
	return mix(hash11(i), hash11(i + 1.0), p - i);
}

/////////// 2D NOISE ///////////
float value12(vec2 p) {
	vec2 i = floor(p);
	vec2 f = p - i;
	f *= f * (3.0 - 2.0 * f);
	float res = mix(
		mix(hash12(i), hash12(i + vec2(1, 0)), f.x),
		mix(hash12(i + vec2(0, 1)), hash12(i + vec2(1)), f.x), f.y);
	return res;
}

float perlin12(vec2 p) {
    vec2 i = floor(p);
    vec2 f = p - i;
    vec2 u = f * f * f * (10.0 + f * (6.0 * f - 15.0));
    float a = dot(normalize(hash22(i + vec2(0, 0)) - 0.5), f - vec2(0, 0));
    float b = dot(normalize(hash22(i + vec2(1, 0)) - 0.5), f - vec2(1, 0));
    float c = dot(normalize(hash22(i + vec2(0, 1)) - 0.5), f - vec2(0, 1));
    float d = dot(normalize(hash22(i + vec2(1, 1)) - 0.5), f - vec2(1, 1));
    return mix(mix(a, b, u.x), mix(c, d, u.x), u.y) * 0.7 + 0.5;
}

// From: https://iquilezles.org/articles/gradientnoise/
vec3 perlin12d(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    vec2 u = f * f * f * (f * (f * 6.0 - 15.0) + 10.0);
    vec2 du = 30.0 * f * f * (f * (f - 2.0) + 1.0);
    vec2 ga = hash22(i + vec2(0, 0)) * 2.0 - 1.0;
    vec2 gb = hash22(i + vec2(1, 0)) * 2.0 - 1.0;
    vec2 gc = hash22(i + vec2(0, 1)) * 2.0 - 1.0;
    vec2 gd = hash22(i + vec2(1, 1)) * 2.0 - 1.0;
    float va = dot(ga, f - vec2(0, 0));
    float vb = dot(gb, f - vec2(1, 0));
    float vc = dot(gc, f - vec2(0, 1));
    float vd = dot(gd, f - vec2(1, 1));
    return vec3(va + u.x * (vb - va) + u.y * (vc - va) + u.x * u.y * (va - vb - vc + vd), ga + u.x * (gb - ga) + u.y * (gc - ga) + u.x * u.y * (ga - gb - gc + gd) + du * (u.yx * (va - vb - vc + vd) + vec2(vb, vc) - va));
}

float simplex12(vec2 p) {
	vec2 i = floor(p + (p.x + p.y) * 0.366025);
    vec2 a = p - i + (i.x + i.y) * 0.211324;
    float m = step(a.y, a.x);
    vec2 o = vec2(m, 1.0 - m);
    vec2 b = a - o + 0.211324;
	vec2 c = a - 0.577351;
    vec3 h = max(0.5 - vec3(dot(a, a), dot(b, b), dot(c, c)), 0.0);
	vec3 n = h * h * h * h *
        vec3(dot(a, hash22(i) - 0.5),
             dot(b, hash22(i + o) - 0.5),
             dot(c, hash22(i + 1.0) - 0.5));
    return dot(n, vec3(70)) + 0.5;
}

// jitter=1.0 is the standard/original behavior (cell points fully randomized within their cell);
// jitter=0.0 puts every point exactly at its cell corner, degenerating to a perfectly regular
// square grid -- a real signature change (unlike Wavelet's scale/phase, which were already real
// arguments), since the original had no notion of a tunable jitter at all. See worley12_helper()
// below for why this doesn't just take a uniform directly.
float worley12(vec2 p, float jitter) {
    vec2 i = floor(p);
    p -= i;
    float w = 1e6;
    for (float x = -1.0; x <= 1.0; ++x)
    for (float y = -1.0; y <= 1.0; ++y) {
        vec2 c = p - vec2(x, y) - hash12(i + vec2(x, y)) * jitter;
       	w = min(w, dot(c, c));
    }
    return 1.0 - sqrt(w);
}

vec3 worley12d(vec2 p) {
    vec2 i = floor(p);
    p -= i;
    float w = 1e6;
    vec2 cmin = vec2(0);
    for (float x = -1.0; x <= 1.0; ++x)
    for (float y = -1.0; y <= 1.0; ++y) {
        vec2 c = p - vec2(x, y) - hash12(i + vec2(x, y));
        float l2 = dot(c, c);
        if (l2 < w) {
            w = l2;
            cmin = c;
        }
    }
    w = sqrt(w);
    return vec3(1.0 - w, -cmin / w);
}

// s: edge smoothness
float voronoi12(vec2 x, float s) {
    s = 1.0 / s;
    vec2 p = floor(x);
    vec2 f = x - p;
	float va = 0.0;
	float wt = 0.0;
    for(float x = -1.0; x <= 1.0; x++)
    for(float y = -1.0; y <= 1.0; y++) {
		vec3 o = hash32(p + vec2(x, y));
		float d = length(vec2(x, y) - f + o.xy);
		float ww = pow(smoothstep(1.414, 0.0, d), s);
		va += o.z * ww;
		wt += ww;
    }
    return va / wt;
}

// From: https://www.shadertoy.com/view/tllcR2
float blue12(vec2 p) {
    float v = 0.0;
    for (int k = 0; k < 9; k++)
        v += hash12(p + vec2(k % 3 - 1, k / 3 - 1));
    return 0.9 * (1.125 * hash12(p) - v / 8.0) + 0.5;
}

int hilbert_encode(int n, ivec2 p) {
    int i = 0;
    for (int s = n >> 1; s > 0; s >>= 1) {
        int rx = int((p.x & s) != 0);
        int ry = int((p.y & s) != 0);
        i += s * s * ((rx << 1) | rx ^ ry);
        p ^= (p.x ^ p.y) * (1 - ry) ^ (s - 1) * (rx & (1 - ry));
    }
    return i;
}

// Modified From: https://www.shadertoy.com/view/3tB3z3
float hilbert_blue12(vec2 p) {
    return fract(0.6180339887498948482 * float(hilbert_encode(512, ivec2(p)) % 262144));
}

// Modified from: https://www.shadertoy.com/view/XsGBDt
float crater12(vec2 p) {
    vec2 f = fract(p);
    p = floor(p);
    float va = 0.;
    float wt = 0.;
    for (int i = -2; i <= 2; i++)
        for (int j = -2; j <= 2; j++) {
                vec2 g = vec2(i, j);
                vec2 o = hash22(p + g);
                float d = distance(f - g, o);
                float w = exp(-4. * d);
                va += w * sin(6.28 * sqrt(max(d, 0.06)));
                wt += w;
            }
    return abs(va / wt);
}

float gabor12(vec2 p) {
    const float kF = 8.0;
    vec2 i = floor(p);
	vec2 f = p - i;
    f *= f * (3.0 - 2.0 * f);
    return mix(mix(sin(kF * dot(p, hash22(i + vec2(0, 0)))),
               	   sin(kF * dot(p, hash22(i + vec2(1, 0)))), f.x),
               mix(sin(kF * dot(p, hash22(i + vec2(0, 1)))),
               	   sin(kF * dot(p, hash22(i + vec2(1, 1)))), f.x), f.y);
}

// Same as perlin12d(p).yz, but can be applied to other noises to get their derivative, useful when you don't have analytic noise derivative
vec2 curl22(vec2 p) {
    vec2 e = vec2(0.1, 0);
    vec2 a = vec2(perlin12(p + e.xy), perlin12(p + e.yx));
    vec2 b = vec2(perlin12(p - e.xy), perlin12(p - e.yx));
    return (a - b) / e.x * 0.5;
}

// Inspired from: https://www.shadertoy.com/view/4syXRD
float scratch(vec2 p, float f) {
    const float THICKNESS = 0.02;
    const float WAVYNESS = 0.5;

    vec2 i = floor(p);
    vec2 h = hash22(i) * vec2(3104, 554);

    p = (p - i) * 2.0 - 1.0;
    p = p * cos(h.x + h.y) + vec2(-p.y, p.x) * sin(h.x + h.y);
    p += sin(h.x - h.y);

    float x = abs(p.x - cos(h.x + p.y * 1.57) * WAVYNESS);
    x = smoothstep(THICKNESS + f, THICKNESS - f, x);
    x *= p.y * 0.5 + 0.5;

    return x;
}

float scratches12(vec2 p) {
    const float SOFTNESS = 3.0;
    const int OCTAVES = 8;

    float scratches = 0.0;
    float w = length(fwidth(p)) * SOFTNESS;
    for(int i = 0; i < OCTAVES; ++i) {
        float x = scratch(p, w);
    	scratches = max(scratches, x);
        p = p * mat2(1.0, 0.7, -0.7, 1.0) - 12.31;
        w *= 1.22;
    }
    return scratches;
}

// fbm, but uses max instead of average
float fbm_scratches12(vec2 p, int octaves) {
    float s = 0.0, a = 1.0;
	for (int i = 0; i < octaves; i++) {
		s = max(s, a * scratches12(p));
        a *= 0.5;
		p *= 2.0;
	}
	return s;
}

// From: https://www.shadertoy.com/view/wsBfzK
// use scale = 1.24 for best results
float wavelet12(vec2 p, float phase, float scale) {
    float d = 0.0, s = 1.0, m = 0.0, a;
    for (float i = 0.0; i < 4.0; ++i) {
        vec2 q = p * s, g = fract(floor(q) * vec2(123.34, 233.53));
    	g += dot(g, g + 23.234);
		a = fract(g.x * g.y) * 1e3; // + z * (mod(g.x + g.y, 2.0) - 1.0); // add vorticity
        q = (fract(q) - 0.5) * mat2(cos(a), -sin(a), sin(a), cos(a));
        d += sin(q.x * 10.0 + phase) * smoothstep(0.25, 0.0, dot(q, q)) / s;
        p = p * mat2(0.54, -0.84, 0.84, 0.54) + i;
        m += 1.0 / s;
        s *= scale;
    }
    return d / m;
}

vec3 gullies(vec2 p, vec2 slope) {
    vec2 side_dir = vec2(-slope.y, slope.x) * 3.14159265;
    vec2 id = floor(p);
    p -= id;
    vec2 height_slope = vec2(0);
    float w_sum = 0.0;
    for(int x = -1; x <= 2; x++) {
        for(int y = -1; y <= 2; y++) {
            vec2 off = vec2(x, y);
            vec2 c = p - off - hash22(id + off) + 0.5;
            float dist2 = dot(c, c);
            float w = max(0.0, exp(-dist2 * 2.0) - 0.01111);
            w_sum += w;
            float t = dot(c, side_dir);
            height_slope += vec2(cos(t), -sin(t)) * w;
        }
    }
    return vec3(height_slope.x, height_slope.y * side_dir) / w_sum;
}

// modified & simplified from: https://www.shadertoy.com/view/sf23W1
vec3 erosion12(vec2 p) {
    vec3 nd = perlin12d(p);
    float strength = 0.25, freq = 8.0, total = 1.0;
    for(int i = 0; i < 4; i++) {
        float len2 = dot(nd.yz, nd.yz);
        nd += gullies(p * freq, nd.yz * pow(len2, 0.5 * (0.5 - 1.0))) * strength * vec3(1, freq, freq);
        total += strength;
        strength *= 0.5;
        freq *= 2.0;
    }
    return nd / total;
}

vec2 fbm_paper(vec2 p, int octaves) {
	vec2 s = vec2(0);
    float m = 0.0, a = 1.0;
	for(int i = 0; i < octaves; i++) {
		s += a * clamp(perlin12d(p).yz * 0.5 + 0.5, vec2(0),  vec2(1));
		m += a;
        a *= 0.8;
        p *= 2.0;
	}
	return s / m;
}

float paper12(vec2 p) {
    return length(fbm_paper(p, 10)) / 1.414 * 0.6 + 0.4;
}

float fbm12(vec2 p, int octaves) {
    float s = 0.0, m = 0.0, a = 1.0;
	for (int i = 0; i < octaves; i++) {
        float n = perlin12(p);
		s += a * n;
		m += a;
		a *= 0.5;
		p *= 2.0;
	}
	return s / m;
}

vec3 fbm12d(vec2 p, int octaves) {
    vec3 s = vec3(0);
    float m = 0.0, a = 1.0, f = 1.0;
	for (int i = 0; i < octaves; i++) {
        vec3 n = perlin12d(p * f);
		s += a * vec3(1, f, f) * n;
		m += a;
		a *= 0.5;
		f *= 2.0;
	}
	return s / vec3(m, 1, 1);
}

vec3 fbm_stone(vec2 p, int octaves) {
    vec3 s = vec3(0);
    float a = 1.0;
    for(int i = 0; i < 6; ++i) {
        s += a * perlin12d(p);
        a *= 0.5;
        p *= 2.0;
    }
    return s;
}

float stone12(vec2 p) {
    return fbm12(p + fbm_stone(p, 6).yz * 0.4, 6);
}

vec2 fbm_wool(vec2 p, int octaves) {
	vec2 s = vec2(0.0);
    float m = 0.0, a = 1.0;
	for(int i = 0; i < octaves; i++) {
        vec2 n = perlin12d(p).yz;
		s += a * n;
		m += a;
		a *= 0.5;
		p *= 2.0;
	}
	return s / m;
}

float wool12(vec2 p) {
    vec2 n = fbm_wool(p, 6);
    return max(abs(n.x), abs(n.y));
}

// Interleaved Gradient Noise
// Cool Property: per pixel values when scrolling IGN linearly each frame is also low-discrepency, so it's low-discrepancy over space and time
float ign12(vec2 p) {
    return fract(52.9829189 * fract(dot(p, vec2(0.06711056, 0.00583715))));
}

float golden_ign12(vec2 p) {
    return float(uint(p.x) * 3242174889u + uint(p.y) * 2447445413u) * exp2(-32.0);
}

/////////// 3D NOISE ///////////
vec4 perm(vec4 x) { x *= x * 34.0 + 1.0; return x - floor(x / 289.0) * 289.0; }
float value13(vec3 p) {
    vec3 a = floor(p);
    vec3 d = p - a;
    d *= d * (3.0 - 2.0 * d);
    vec4 b = a.xxyy + vec4(0, 1, 0, 1);
    vec4 k1 = perm(b.xyxy);
    vec4 k2 = perm(k1.xyxy + b.zzww) + a.zzzz;
    vec4 k3 = perm(k2);
    vec4 k4 = perm(k2 + 1.0);
    vec4 o1 = fract(k3 * 0.02439024);
    vec4 o2 = fract(k4 * 0.02439024);
    vec4 o3 = mix(o1, o2, d.z);
    vec2 o4 = mix(o3.xz, o3.yw, d.x);
    return mix(o4.x, o4.y, d.y);
}

float perlin13(vec3 p) {
    vec3 i = floor(p);
    vec3 f = p - i;
    vec3 u = f * f * f * (10.0 + f * (6.0 * f - 15.0));
    float a0 = dot(f - vec3(0, 0, 0), normalize(hash33(i + vec3(0, 0, 0)) - 0.5));
    float b0 = dot(f - vec3(1, 0, 0), normalize(hash33(i + vec3(1, 0, 0)) - 0.5));
    float c0 = dot(f - vec3(0, 1, 0), normalize(hash33(i + vec3(0, 1, 0)) - 0.5));
    float d0 = dot(f - vec3(1, 1, 0), normalize(hash33(i + vec3(1, 1, 0)) - 0.5));
    float a1 = dot(f - vec3(0, 0, 1), normalize(hash33(i + vec3(0, 0, 1)) - 0.5));
    float b1 = dot(f - vec3(1, 0, 1), normalize(hash33(i + vec3(1, 0, 1)) - 0.5));
    float c1 = dot(f - vec3(0, 1, 1), normalize(hash33(i + vec3(0, 1, 1)) - 0.5));
    float d1 = dot(f - vec3(1, 1, 1), normalize(hash33(i + vec3(1, 1, 1)) - 0.5));
    float z0 = mix(mix(a0, b0, u.x), mix(c0, d0, u.x), u.y);
    float z1 = mix(mix(a1, b1, u.x), mix(c1, d1, u.x), u.y);
    return mix(z0, z1, u.z) * 0.7 + 0.5;
}

// From: https://iquilezles.org/articles/gradientnoise/
vec4 perlin13d(vec3 p) {
    vec3 i = floor(p);
    vec3 f = p - i;
    vec3 u = f * f * f * (f * (f * 6.0 - 15.0) + 10.0);
    vec3 du = 30.0 * f * f * (f * (f - 2.0) + 1.0);
    vec3 ga = hash33(p + vec3(0, 0, 0));
    vec3 gb = hash33(p + vec3(1, 0, 0));
    vec3 gc = hash33(p + vec3(0, 1, 0));
    vec3 gd = hash33(p + vec3(1, 1, 0));
    vec3 ge = hash33(p + vec3(0, 0, 1));
    vec3 gf = hash33(p + vec3(1, 0, 1));
    vec3 gg = hash33(p + vec3(0, 1, 1));
    vec3 gh = hash33(p + vec3(1, 1, 1));
    float va = dot(ga, f - vec3(0, 0, 0));
    float vb = dot(gb, f - vec3(1, 0, 0));
    float vc = dot(gc, f - vec3(0, 1, 0));
    float vd = dot(gd, f - vec3(1, 1, 0));
    float ve = dot(ge, f - vec3(0, 0, 1));
    float vf = dot(gf, f - vec3(1, 0, 1));
    float vg = dot(gg, f - vec3(0, 1, 1));
    float vh = dot(gh, f - vec3(1, 1, 1));
    return vec4(va + u.x*(vb-va) + u.y*(vc-va) + u.z*(ve-va) + u.x*u.y*(va-vb-vc+vd) + u.y*u.z*(va-vc-ve+vg) + u.z*u.x*(va-vb-ve+vf) + (-va+vb+vc-vd+ve-vf-vg+vh)*u.x*u.y*u.z,
                ga + u.x*(gb-ga) + u.y*(gc-ga) + u.z*(ge-ga) + u.x*u.y*(ga-gb-gc+gd) + u.y*u.z*(ga-gc-ge+gg) + u.z*u.x*(ga-gb-ge+gf) + (-ga+gb+gc-gd+ge-gf-gg+gh)*u.x*u.y*u.z +
                du * (vec3(vb,vc,ve) - va + u.yzx*vec3(va-vb-vc+vd,va-vc-ve+vg,va-vb-ve+vf) + u.zxy*vec3(va-vb-ve+vf,va-vb-vc+vd,va-vc-ve+vg) + u.yzx*u.zxy*(-va+vb+vc-vd+ve-vf-vg+vh)));
}

float simplex13(vec3 p) {
	 vec3 s = floor(p + dot(p, vec3(1.0 / 3.0)));
	 vec3 x = p - s + dot(s, vec3(1.0 / 6.0));
	 vec3 e = step(vec3(0), x - x.yzx);
	 vec3 i1 = e * (1.0 - e.zxy);
	 vec3 i2 = 1.0 - e.zxy * (1.0 - e);
	 vec3 x1 = x - i1 + 1.0 / 6.0;
	 vec3 x2 = x - i2 + 1.0 / 3.0;
	 vec3 x3 = x - 0.5;
	 vec4 w = vec4(dot(x, x), dot(x1, x1), dot(x2, x2), dot(x3, x3));
	 w = max(0.6 - w, 0.0);
	 vec4 d = vec4(dot(hash33(s) - 0.5, x),
                   dot(hash33(s + i1) - 0.5, x1),
            	   dot(hash33(s + i2) - 0.5, x2),
                   dot(hash33(s + 1.0) - 0.5, x3));
	 w *= w;
	 w *= w;
	 d *= w;
	 return dot(d, vec4(26)) + 0.5;
}

float worley13(vec3 p) {
    vec3 i = floor(p);
    p -= i;
    float w = 1e6;
    for (float x = -1.0; x <= 1.0; ++x)
    for (float y = -1.0; y <= 1.0; ++y)
    for (float z = -1.0; z <= 1.0; ++z) {
        vec3 c = p - vec3(x, y, z) - hash13(i + vec3(x, y, z));
       	w = min(w, dot(c, c));
    }
    return 1.0 - sqrt(w);
}

vec4 worley13d(vec3 p) {
    vec3 i = floor(p);
    p -= i;
    float w = 1e6;
    vec3 cmin = vec3(0);
    for (float x = -1.0; x <= 1.0; ++x)
    for (float y = -1.0; y <= 1.0; ++y)
    for (float z = -1.0; z <= 1.0; ++z) {
        vec3 c = p - vec3(x, y, z) - hash13(i + vec3(x, y, z));
        float l2 = dot(c, c);
        if (l2 < w) {
            w = l2;
            cmin = c;
        }
    }
    w = sqrt(w);
    return vec4(1.0 - w, -cmin / w);
}

/////////// Visualization Helpers ///////////
// Octaves/lacunarity/gain read the Global uniforms directly (in scope from the shader's own
// top-level declarations, not macro parameters) -- every noiseID branch below that goes
// through this ONE macro (value/perlin/simplex/worley/crater/gabor/wavelet fbm) gets Global's
// octaves/lacunarity/gain for free, with no per-noise-family plumbing.
#define fbm12(uv, noise_fn) do {\
    vec2 p = uv;\
    float s = 0.0, m = 0.0, a = 1.0;\
	for (int i = 0; i < u_octaves; i++) {\
        float n = noise_fn(p);\
		s += a * n;\
		m += a;\
		a *= u_gain;\
		p *= u_lacunarity;\
	}\
	c.rgb += s / m;\
} while(false)

#define fbm12_deriv(uv, noise_fn) do {\
    vec2 p = uv;\
    vec3 s = vec3(0);\
    float m = 0.0, a = 1.0, f = 1.0;\
	for (int i = 0; i < 6; i++) {\
        vec3 n = noise_fn(p * f);\
		s += a * vec3(1, f, f) * n;\
		m += a;\
		a *= 0.25;\
		f *= 2.0;\
	}\
	c.rgb += s / vec3(m, 1, 1);\
} while(false)

// u_waveletScale is Wavelet's own noise-centric control (its ImGui section, not Global) --
// wavelet12() already takes scale as a real argument (examples/pyosg-noise.py's own design
// notes: this needed zero signature surgery, unlike Scratches), so this is the only place a
// literal became a uniform. Default (1.24) lives in build_scene(), matching wavelet12()'s own
// "use scale = 1.24 for best results" comment.
uniform float u_waveletScale;

float wavelet12_helper(vec2 p) {
    return wavelet12(p, u_time, u_waveletScale) * 0.5 + 0.5;
}

// u_worleyJitter is Worley's own noise-centric control. worley12(p) had no jitter parameter at
// all before this pass (unlike wavelet12, which already took scale/phase as real arguments) --
// worley12_helper exists purely so the fbm12 macro's single-argument call convention
// (`noise_fn(p)`) still works once worley12() itself became 2-argument; same shape as
// wavelet12_helper wrapping wavelet12(p, u_time, scale) above.
uniform float u_worleyJitter;

float worley12_helper(vec2 p) {
    return worley12(p, u_worleyJitter);
}

// NOISE_SCALE became the Global u_scale uniform (see build_scene() for its default). LATTICE_SCALE
// stays a fixed const on purpose -- blue/Hilbert-blue/IGN are canonically PIXEL-grid dither
// patterns needing a fine integer lattice regardless of whatever "world zoom" u_scale is set to,
// not the same coarse scale as everything else -- so it deliberately does NOT read u_scale.
const float LATTICE_SCALE = 100.0;

void main() {
	vec3 c = vec3(0);

	// vPos is world-space and globally continuous across the whole grid (see VERTEX_SHADER's
	// own comment) -- this is what actually avoids the SECOND REVISION's seam bug, not
	// gl_FragCoord specifically. The noise no longer depends on the window, viewport, or
	// resolution at all.
	vec2 p = vPos * u_scale;
	vec2 lattice = vPos * LATTICE_SCALE;

	// Global animate/warp -- same one-choke-point shape as u_scale above: every panel (not just
	// the fbm ones) reacts identically, because this runs before noiseID picks a function.
	// animSpeed scrolls the domain; warp reuses curl22() (already defined above, itself built on
	// perlin12) as a generic, noise-agnostic distortion field. Both default to 0 in build_scene()
	// (no motion/warp), so this is a no-op contribution until the Global ImGui section changes
	// them -- no separate enable toggle needed.
	p += u_time * u_animSpeed;
	p += curl22(p) * u_warp;

	if (noiseID ==  0) { c.rgb += value12(p * 1.5); }
	else if (noiseID ==  1) { fbm12(p, value12); }
	else if (noiseID ==  2) { c.rgb += perlin12(p); }
	else if (noiseID ==  3) { fbm12(p, perlin12); }
	else if (noiseID ==  4) { c.rgb += simplex12(p); }
	else if (noiseID ==  5) { fbm12(p, simplex12); }
	else if (noiseID ==  6) { c.rgb += worley12_helper(p); }
	else if (noiseID ==  7) { fbm12(p, worley12_helper); }
	else if (noiseID ==  8) { c.rgb += blue12(floor(lattice)); }
	else if (noiseID ==  9) { c.rgb += hilbert_blue12(floor(lattice)); }
	else if (noiseID == 10) { c.rgb += crater12(p); }
	else if (noiseID == 11) { fbm12(p, crater12); }
	else if (noiseID == 12) { c.rgb += gabor12(p) * .5 + .5; }
	else if (noiseID == 13) { fbm12(p, gabor12); c = c * .5 + .5; }
	else if (noiseID == 14) { c.rgb += scratches12(p); }
	else if (noiseID == 15) { c.rgb += fbm_scratches12(p, u_octaves); }
	else if (noiseID == 16) { c.rgb += wavelet12_helper(p); }
	else if (noiseID == 17) { fbm12(p, wavelet12_helper); }
	else if (noiseID == 18) { c.rgb += erosion12(p).x * .5 + .5; }
	else if (noiseID == 19) { c.rgb += length(curl22(p)) / 1.414; }
	else if (noiseID == 20) { c.rgb += paper12(vPos * 2.0); }
	else if (noiseID == 21) { c.rgb += stone12(p); }
	else if (noiseID == 22) { c.rgb += wool12(p); }
	else if (noiseID == 23) { c.rgb += golden_ign12(floor(lattice)); }

	// Hover feedback (see __main__'s onEnter/onLeave) -- a flat red tint, nothing fancier.
	c = mix(c, vec3(1.0, 0.15, 0.15), tint * 0.35);

	fragColor = vec4(c, 1);
}
"""

# Global/per-noise uniform defaults -- kept as dicts, not inline literals, so build_scene()'s
# initial values and the Reset buttons (see __main__) share exactly one source of truth instead
# of two copies of the same magic numbers drifting apart. Values match the ORIGINAL hardcoded
# shader constants (NOISE_SCALE=3.0, fbm12's old octaves=6/gain=0.5/lacunarity=2.0,
# wavelet12_helper's old scale=1.24).
GLOBAL_DEFAULTS = {
	"u_scale": 3.0,
	"u_octaves": 6,
	"u_lacunarity": 2.0,
	"u_gain": 0.5,
	"u_warp": 0.0,
	"u_animSpeed": 0.0,
}

# Per-family DEFAULTS + PARAMS live together -- DEFAULTS feeds both build_scene()'s initial
# uniform values and __main__'s Reset buttons; PARAMS (uniform name, ImGui label, lo, hi) is the
# ImGui-only half, consumed by make_param_section() in __main__ to build the whole slider-block+
# Reset draw function from data instead of a hand-written function per family. Labels carry their
# own `##scope` suffix (see feedback_osgx_imgui_python_api in memory -- no automatic per-section
# ID scoping) so a future family reusing a common word like "Scale" can't collide with this one.
WAVELET_DEFAULTS = {
	"u_waveletScale": 1.24,
}

WAVELET_PARAMS = [
	("u_waveletScale", "Scale##wavelet", 1.05, 2.0),
]

WORLEY_DEFAULTS = {
	"u_worleyJitter": 1.0,
}

WORLEY_PARAMS = [
	("u_worleyJitter", "Jitter##worley", 0.0, 1.0),
]

# The real pipeline-assembly entrypoint -- returns the root Node, no viewer/window side effects.
# See examples/pyosg-blur.py's own build_scene() for the convention; ../pyosg-cli and
# etc/pyside6-glsl.py both import and call this directly, always as build_scene(w, h) -- w/h are
# kept as parameters to match that contract even though the body no longer uses them (the noise
# domain is world-space now, not screen-resolution-dependent; see FRAGMENT_SHADER_NOISE/
# VERTEX_SHADER). Picking/ImGui are viewer-level concerns and live only in __main__ (see this
# file's own "ARCHITECTURE, THIRD REVISION" docstring section) -- this function returns a Group
# of 24 plain Geodes (children[i] == noiseID i, pickID i + 1), each carrying its own
# noiseID/tint/pickID uniforms on top of the ONE shared Program.
def build_scene(w, h):
	program = osg.Program(name="pyosg-noise", shaders=(
		osg.Shader(osg.Shader.VERTEX, VERTEX_SHADER),
		osg.Shader(osg.Shader.FRAGMENT, FRAGMENT_SHADER_NOISE),
	))

	root = osg.Group(name="pyosg-noise-grid")

	root.stateSet.attributes.append(program)
	root.stateSet.uniforms["u_time"] = 0.0

	# Global/per-noise panel defaults -- set here, not just in __main__'s ImGui wiring, so this
	# shader renders correctly standalone (../pyosg-cli, etc/pyside6-glsl.py both call
	# build_scene(w, h) directly with no ImGui panel attached at all). See GLOBAL_DEFAULTS/
	# WAVELET_DEFAULTS above -- shared with the Reset buttons in __main__.
	for _name, _value in GLOBAL_DEFAULTS.items():
		root.stateSet.uniforms[_name] = _value

	for _name, _value in WAVELET_DEFAULTS.items():
		root.stateSet.uniforms[_name] = _value

	for _name, _value in WORLEY_DEFAULTS.items():
		root.stateSet.uniforms[_name] = _value

	for noise_id, name in enumerate(LEGEND):
		x0, y0, x1, y1 = cell_bounds(noise_id)

		x0 += PANEL_GAP * 0.5
		x1 -= PANEL_GAP * 0.5
		y0 += PANEL_GAP * 0.5
		y1 -= PANEL_GAP * 0.5

		g = osg.Geometry()

		g.vertexArray = osg.Vec3Array((
			osg.Vec3(x0, y0, 0.0),
			osg.Vec3(x1, y0, 0.0),
			osg.Vec3(x1, y1, 0.0),
			osg.Vec3(x0, y1, 0.0),
		))
		g.primitiveSets.append(osg.DrawArrays(osg.PrimitiveSet.TRIANGLE_FAN, 0, 4))

		geode = osg.Geode(name=name, drawables=(g,))
		ss = geode.stateSet

		ss.uniforms["noiseID"] = noise_id
		ss.uniforms["tint"] = 0.0

		pick_id = osg.Uniform(osg.Uniform.Type.UNSIGNED_INT, "pickID")

		pick_id.value = noise_id + 1

		ss.uniforms.extend((pick_id,))

		root.children.append(geode)

	return root

if __name__ == "__main__":
	W, H = 800, 600

	# The ImGui panel sits in a dead strip the 3D camera's viewport never covers, instead of
	# overlapping the grid -- see the viewport setup below. Window is grown by this much so W x H
	# stays the grid's actual on-screen size either way. Kept equal to gui_opts.dock_width below.
	PANEL_WIDTH = 280

	print(f"pyosg-noise: 6 columns x 4 rows, row-major from the bottom-left:")

	for name in LEGEND:
		print(f"  {name}")

	osg.setNotifyLevel(osg.NotifySeverity.NOTICE)

	os.environ["OSG_WINDOW"] = f"50 50 {W + PANEL_WIDTH} {H}"

	viewer = osgViewer.Viewer()
	scene = build_scene(W, H)

	# --- Picking: same 1x1 continuous sub-frustum shape as pyosg-hover.py, so hover tinting is
	# always-on at zero per-frame GPU cost; PickHandler(rb, True) additionally lets a left-click
	# resolve against whatever's currently hovered (see osgx/Picking.hpp's PickHandler doc). --- #
	pick_image = osg.Image()

	pick_image.allocateImage(1, 1, 1, GL_RGBA, GL_UNSIGNED_BYTE)

	pick_cam = osgx.makePickCamera(1, 1, pick_image)

	pick_cam.children.append(scene)

	rb = osgx.PickReadbackSync(
		1, pick_image, W, H,
		rule=osgx.PickRule.SPIRAL,
		mode=osgx.PickReadbackSync.Mode.CONTINUOUS,
	)

	quads = list(scene.children)
	selected = [0]

	# Master animation toggle -- freezes u_time itself (see the main loop below) instead of
	# gating individual shader effects, so it silences EVERY time-based source at once: the
	# Global "Animate Speed" domain scroll AND Wavelet's own phase animation (wavelet12_helper
	# reads u_time directly, independent of Global's u_animSpeed -- freezing u_time is the only
	# single point that covers both without threading a second uniform through wavelet12_helper).
	# Starts OFF: time-based motion makes it hard to tell whether a slider actually changed
	# anything else while live-tuning.
	animate_enabled = [False]

	# --- Inspect mode: two states, "grid" (pick_id 0, full 6x4 framing) and "inspect" (a single
	# panel's cell filling the frame) -- toggled by select() below. No new geometry/camera/shader:
	# since the master camera's viewMatrix looks straight down -z with no x/y rotation (see
	# lookAt() above), an asymmetric ortho(l, r, b, t) directly reframes whatever world-space rect
	# we want, and FRAGMENT_SHADER_NOISE's vPos domain just shows more/less of itself as the
	# bounds shrink/grow -- same reasoning as this file's own "stay flat" design notes. -- #
	INSPECT_MARGIN = 0.08
	INSPECT_SECONDS = 0.3
	FULL_BOUNDS = (-HALF_W, HALF_W, -HALF_H, HALF_H)

	def view_bounds(pick_id):
		if not pick_id:
			return FULL_BOUNDS

		x0, y0, x1, y1 = cell_bounds(pick_id - 1)

		return x0 - INSPECT_MARGIN, x1 + INSPECT_MARGIN, y0 - INSPECT_MARGIN, y1 + INSPECT_MARGIN

	def ease(x):
		return x * x * (3.0 - 2.0 * x)

	view_state = {"from": FULL_BOUNDS, "to": FULL_BOUNDS, "t0": 0.0}

	def current_bounds(now):
		t = ease(min(1.0, (now - view_state["t0"]) / INSPECT_SECONDS))

		return tuple(a + (b - a) * t for a, b in zip(view_state["from"], view_state["to"]))

	def on_enter(pick_id):
		quads[pick_id - 1].stateSet.uniforms["tint"] = 1.0

	def on_leave(pick_id):
		quads[pick_id - 1].stateSet.uniforms["tint"] = 0.0

	rb.onEnter = on_enter
	rb.onLeave = on_leave

	sync = osgx.PickCameraSync(viewer.camera, True, W, H, rb)
	hover = osgx.PickHoverCallback(rb)

	pick_cam.updateCallback = osgx.NodeCallbacksGroup([sync, hover, rb])

	root = osg.Group(name="root")

	root.children.append(pick_cam)
	root.children.append(scene)

	viewer.sceneData = root
	viewer.camera.clearColor = osg.Vec4(0, 0, 0, 1)
	viewer.eventHandlers.append(osgx.PickHandler(rb, True))

	# Realize BEFORE setting the camera's own view/projection, not after -- confirmed live
	# (aipython REPL, 2026-08-22) that OSG's Camera::ProjectionResizePolicy machinery latches
	# its "reference" viewport size the first time realize() establishes a real one. Setting a
	# custom projection matrix before that point (the mistake this file had) gets its horizontal
	# extent silently zeroed out on the very next frame() (vertical extent, set via the same
	# ortho() call, is untouched -- HORIZONTAL is the resize policy's default). Setting it after
	# realize() is completely stable. No osgGA manipulator either -- there's nothing 3D here to
	# orbit around, and a manipulator would fight a fixed camera anyway. projectionMatrix itself
	# is no longer set here -- inspect mode (see view_bounds()/current_bounds() below) owns it
	# every frame from here on, and the first frame() call still happens after this point, so the
	# ordering constraint above still holds.
	viewer.realize()

	viewer.camera.viewMatrix = osg.Matrix.lookAt(osg.Vec3(0, 0, 10), osg.Vec3(0, 0, 0), osg.Vec3(0, 1, 0))

	# Confine the 3D camera to the WxH strip right of the panel, instead of the whole (W +
	# PANEL_WIDTH)-wide window -- the panel's own dock sits in the untouched strip to its left,
	# so the two no longer fight over the same pixels. The noise domain is world-space now (see
	# VERTEX_SHADER/FRAGMENT_SHADER_NOISE), so it doesn't care where the viewport sits -- but
	# picking still does: PickHandler's mouse coordinates are window-absolute while
	# PickCameraSync's sub-frustum math (both set up above) treats them as viewport-local, so
	# hover/click targeting is currently off by PANEL_WIDTH pixels in X. Not yet fixed.
	viewer.camera.viewport = osg.Viewport(PANEL_WIDTH, 0, W, H)

	# All 24 quads sit exactly at z=0 -- a perfectly flat, zero-depth scene. OSG's default
	# COMPUTE_NEAR_FAR_USING_BOUNDING_VOLUME recomputes near/far from the scene bounds every
	# frame during cull; harmless for this exact flat layout (the computed range still contains
	# the geometry) but fragile in general for a zero-thickness bounding volume, and needless
	# work for a camera that never moves. Same fix as
	# examples/pyosg-lighting/09-ibl-animation.py's own custom camera setup.
	viewer.camera.computeNearFarMode = osg.Camera.DO_NOT_COMPUTE_NEAR_FAR

	# --- ImGui panel: docked left, one CollapsingHeader section per noise type plus a pinned
	# "Overview" section holding the button that clears the selection. Selecting/deselecting a
	# panel forces its section open/closed via setSectionOpen() -- see this file's own docstring
	# for why that needed a small osgx addition rather than SectionOptions.default_open alone. -- #
	gui_opts = osgx.imgui.Options()
	gui_opts.dock = osgx.imgui.Dock.LEFT
	gui_opts.dock_width = float(PANEL_WIDTH)

	# No explicit draw_camera -- unlike 11-sketchfab.py, pick_cam renders into its own 1x1 FBO,
	# never the default framebuffer, so there's no downstream POST_RENDER camera to conflict
	# with ImGui's own PostDrawCallback on the master camera; the default guess is enough here.
	gui = osgx.imgui.Widget(viewer, options=gui_opts)

	def select(pick_id):
		if pick_id == selected[0]:
			return

		if selected[0]:
			gui.setSectionOpen(LEGEND[selected[0] - 1], False)

		selected[0] = pick_id

		if pick_id:
			gui.setSectionOpen(LEGEND[pick_id - 1], True)

		now = time.time()

		view_state["from"] = current_bounds(now)
		view_state["to"] = view_bounds(pick_id)
		view_state["t0"] = now

	def on_pick(pick_id, action):
		if action == osgx.ActionType.CLICK:
			select(pick_id)

	rb.onPick = on_pick

	# Right-click anywhere in the 3D viewport is a shortcut for the "Overview##select" button
	# (select(0)) -- osgx's PickHandler only ever reacts to LEFT_MOUSE_BUTTON (see its
	# own handle()), so this doesn't touch/compete with it at all; plain right-click detection is
	# all a standalone osgGA.GUIEventHandler needs. `ea.handled` is checked for the same reason
	# every other handler in this file's chain checks it now (see aipython/09-picking.md) -- a
	# right-click meant for an ImGui widget shouldn't ALSO trigger this.
	class OverviewShortcut(osgGA.GUIEventHandler):
		def handle(self, ea, aa):
			if ea.handled: return False

			if ea.type == osgGA.GUIEventAdapter.PUSH and ea.button == osgGA.GUIEventAdapter.RIGHT_MOUSE_BUTTON:
				select(0)

				return True

			return False

	viewer.eventHandlers.append(OverviewShortcut())

	def draw_overview(ri):
		if selected[0]:
			osgx.imgui.text(f"Selected: {LEGEND[selected[0] - 1]}")
		else:
			osgx.imgui.text("Click a panel below to inspect it.")

		# ##select is load-bearing, not decoration: this section's own CollapsingHeader is ALSO
		# labeled "Overview" (see gui.addSection() below), and a plain (non-expand) section's fn()
		# runs with zero ImGui::PushID scoping (osgx's own Widget::render) -- a control reusing
		# the section's exact label text hashes to the SAME ImGui ID as the header and fights it
		# for click state (see feedback_imgui_section_label_collision in memory; this is that bug,
		# not a hypothetical one -- it's why this button wasn't reliably returning to grid view).
		if osgx.imgui.button("Overview##select"):
			select(0)

		if osgx.imgui.button("Reset##global"):
			for name, value in GLOBAL_DEFAULTS.items():
				scene.stateSet.uniforms[name] = value

	# Forced open every frame (never toggled off) -- this section IS the "Overview" button, so
	# it has no reason to ever collapse.
	gui.addSection("Overview", draw_overview, osgx.imgui.SectionOptions(default_open=True))
	gui.setSectionOpen("Overview", True)

	# Global panel -- one set of uniforms every noiseID branch reads from a single choke point
	# in FRAGMENT_SHADER_NOISE (scale/octaves/lacunarity/gain feed the fbm12 macro; warp/animate
	# apply to the domain before noiseID even picks a function), so this section stays pinned
	# open like Overview instead of being tied to panel selection -- it's relevant regardless of
	# what's selected. `##global` suffixes avoid label collisions with future per-noise sections
	# that might want their own "Scale"-named control (see osgx.imgui's own section/label
	# collision gotcha).
	def draw_global_knobs(ri):
		uniforms = scene.stateSet.uniforms

		changed, value = osgx.imgui.slider_float("Scale##global", uniforms["u_scale"].value, 0.5, 10.0)
		if changed: uniforms["u_scale"] = value

		changed, value = osgx.imgui.slider_float(
			"Octaves##global", float(uniforms["u_octaves"].value), 1.0, 8.0, "%.0f"
		)
		if changed: uniforms["u_octaves"] = int(round(value))

		changed, value = osgx.imgui.slider_float(
			"Lacunarity##global", uniforms["u_lacunarity"].value, 1.0, 4.0
		)
		if changed: uniforms["u_lacunarity"] = value

		changed, value = osgx.imgui.slider_float("Gain##global", uniforms["u_gain"].value, 0.1, 0.9)
		if changed: uniforms["u_gain"] = value

		osgx.imgui.separator()

		changed, value = osgx.imgui.slider_float("Warp##global", uniforms["u_warp"].value, 0.0, 2.0)
		if changed: uniforms["u_warp"] = value

		osgx.imgui.separator()

		# Master toggle -- freezes u_time in the main loop (see animate_enabled's own comment
		# above); distinct label from "Animate Speed" below on purpose, not just an ID suffix,
		# since a checkbox and a slider both meaning slightly different things but both named
		# bare "Animate" would be genuinely confusing, not just an ID collision risk.
		changed, value = osgx.imgui.checkbox("Animate", animate_enabled[0])
		if changed: animate_enabled[0] = value

		changed, value = osgx.imgui.slider_float(
			"Animate Speed##global", uniforms["u_animSpeed"].value, 0.0, 2.0
		)
		if changed: uniforms["u_animSpeed"] = value

	gui.addSection("Global", draw_global_knobs, osgx.imgui.SectionOptions(default_open=True))
	gui.setSectionOpen("Global", True)

	# Per-noise sections -- still placeholders except the families with real PARAMS/DEFAULTS
	# above (Wavelet, Worley). make_param_section() builds a whole slider-block+Reset draw
	# function from a family's PARAMS/DEFAULTS alone -- adding the next family's controls (e.g.
	# Scratches) is a PARAMS list + a CUSTOM_SECTIONS entry, not a new hand-written function.
	def make_noise_section(name):
		def draw(ri):
			osgx.imgui.text("(controls coming soon)")

		return draw

	def make_param_section(defaults, params, scope):
		def draw(ri):
			uniforms = scene.stateSet.uniforms

			for name, label, lo, hi in params:
				changed, value = osgx.imgui.slider_float(label, uniforms[name].value, lo, hi)

				if changed: uniforms[name] = value

			if osgx.imgui.button(f"Reset##{scope}"):
				for name, value in defaults.items():
					uniforms[name] = value

		return draw

	worley_knobs = make_param_section(WORLEY_DEFAULTS, WORLEY_PARAMS, "worley")
	wavelet_knobs = make_param_section(WAVELET_DEFAULTS, WAVELET_PARAMS, "wavelet")

	# Dict, not an if/elif chain -- scales cleanly as more noise families get real sections
	# instead of the placeholder. Both entries per family share the SAME draw function (one
	# make_param_section() call, not two) since raw/fbm read the exact same uniform(s) and
	# should look identical either way.
	CUSTOM_SECTIONS = {
		"6. WORLEY": worley_knobs,
		"7. WORLEY FBM": worley_knobs,
		"16. WAVELET": wavelet_knobs,
		"17. WAVELET FBM": wavelet_knobs,
	}

	for name in LEGEND:
		draw = CUSTOM_SECTIONS.get(name, make_noise_section(name))

		gui.addSection(name, draw, osgx.imgui.SectionOptions(default_open=False))

	# elapsed/last_time (a running accumulator), not the original plain `now - t` epoch delta --
	# accumulating only while animate_enabled[0] is true means u_time genuinely freezes in place
	# while paused and resumes from exactly where it left off, instead of jumping forward by
	# however long the pause lasted the moment it's re-enabled.
	elapsed = [0.0]
	last_time = [time.time()]

	while not viewer.done:
		now = time.time()
		dt = now - last_time[0]
		last_time[0] = now

		if animate_enabled[0]:
			elapsed[0] += dt

		scene.stateSet.uniforms["u_time"] = float(elapsed[0])

		l, r, b, top = current_bounds(now)

		viewer.camera.projectionMatrix = osg.Matrix.ortho(l, r, b, top, 0.1, 100.0)

		viewer.frame()
