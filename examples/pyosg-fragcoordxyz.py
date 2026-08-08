#!/usr/bin/env python3
#vimrun! ../examples/pyosg-fragcoordxyz

import os
import time
import random

os.environ.update({
	"OSG_WINDOW": "50 50 800 600",
	"OSG_THREADING": "SingleThreaded",
	"OSG_GL_CONTEXT_PROFILE_MASK": "1",
	"OSG_GL_VERSION": "4.6",
	"OSG_GL_CONTEXT_VERSION": "4.6"
})

from OpenSceneGraph import *
from OpenSceneGraph.GL import *

VERTEX_SHADER = """
#version 330 core
void main() {
	vec2 base[4] = vec2[4](
		vec2(-1.0, -1.0),
		vec2( 1.0, -1.0),
		vec2( 1.0, 1.0),
		vec2(-1.0, 1.0)
	);
	gl_Position = vec4(base[gl_VertexID % 4], 0.0, 1.0);
}
"""

# https://fragcoord.xyz/s/sx3ek521
FRAGMENT_SHADER_SHIELD = """
#version 330 core
uniform vec2 u_resolution;
uniform float u_time;
out vec4 fragColor;

void main() {
	fragColor = vec4(0.0);
	for(float i = 0.0, z; i < 1.0; i += 0.01) {
		vec2 p = (gl_FragCoord.xy * 2.0 - u_resolution) / u_resolution.y * i, v;
		p /= 0.2 + sqrt(z = max(1.0 - dot(p, p), 0.0)) * 0.3;
		p.y += fract(ceil(p.x = p.x / 0.9 + u_time) * 0.5) + u_time * 0.2;
		v = abs(fract(p) - 0.5);
		fragColor += vec4(2, 3, 5, 1) / 2e3 * z / (abs(max(v.x * 1.5 + v, v + v).y - 1.0) + 0.1 - i * 0.09);
	}
	fragColor = tanh(fragColor * fragColor);
}
"""

# https://fragcoord.xyz/s/efuuva8v
FRAGMENT_SHADER_EYE = """
#version 330 core
uniform vec2 u_resolution;
uniform float u_time;
out vec4 fragColor;

void main() {
	fragColor = vec4(0.0);

	vec2 p = (gl_FragCoord.xy * 2.0 - u_resolution) / u_resolution.y;
	vec2 v = p / dot(p, p) / 0.2;

	for (float i = 0.0; i++ < 8.0;) {
		v += sin(v.yx * i + vec2(0.0, i) + u_time) / i;
		fragColor += (sin(v.xyyx + i) + 1.0) * abs(dot(v, v) / 1e2 - 1.0);
	}

	fragColor = tanh(vec4(1, 2, 3, 4) / fragColor);
}
"""

# https://fragcoord.xyz/s/bbjr6uba
FRAGMENT_SHADER_BITSHIFT = """
#version 330 core
uniform vec2 u_resolution;
uniform float u_time;
out vec4 fragColor;

void main() {
	vec2 p = vec2(round((2.0*gl_FragCoord.xy - u_resolution) / u_resolution.y*32.0)/24.0);
	float z = 1.0-dot(p, p);
	fragColor = floor(z*fract(dot(p, vec2(11.0)))+z*6.0/exp(2.0/abs(tan(u_time+p.x-p.y*z*6.0+vec4(0.0, .4, 1.0, 0.0)))))/4.0;
}
"""

# https://fragcoord.xyz/s/bghwsbhr
FRAGMENT_SHADER_BLACKHOLE_PORTAL = """
#version 330 core
uniform vec2 u_resolution;
uniform float u_time;
out vec4 fragColor;

vec4 permute_3d(vec4 x){ return mod(((x*34.0)+1.0)*x, 289.0); }
vec4 taylorInvSqrt3d(vec4 r){ return 1.79284291400159 - 0.85373472095314 * r; }

float simplexNoise3d(vec3 v) {
	const vec2 C = vec2(1.0/6.0, 1.0/3.0) ;
	const vec4 D = vec4(0.0, 0.5, 1.0, 2.0);

	// First corner
	vec3 i = floor(v + dot(v, C.yyy) );
	vec3 x0 = v - i + dot(i, C.xxx) ;

	// Other corners
	vec3 g = step(x0.yzx, x0.xyz);
	vec3 l = 1.0 - g;
	vec3 i1 = min( g.xyz, l.zxy );
	vec3 i2 = max( g.xyz, l.zxy );

	// x0 = x0 - 0. + 0.0 * C
	vec3 x1 = x0 - i1 + 1.0 * C.xxx;
	vec3 x2 = x0 - i2 + 2.0 * C.xxx;
	vec3 x3 = x0 - 1. + 3.0 * C.xxx;

	// Permutations
	i = mod(i, 289.0 );
	vec4 p = permute_3d(
		permute_3d(
			permute_3d(i.z + vec4(0.0, i1.z, i2.z, 1.0 )) + i.y + vec4(0.0, i1.y, i2.y, 1.0)
		) + i.x + vec4(0.0, i1.x, i2.x, 1.0)
	);

	// Gradients
	// ( N*N points uniformly over a square, mapped onto an octahedron.)
	float n_ = 1.0/7.0; // N=7
	vec3 ns = n_ * D.wyz - D.xzx;

	vec4 j = p - 49.0 * floor(p * ns.z *ns.z); // mod(p,N*N)

	vec4 x_ = floor(j * ns.z);
	vec4 y_ = floor(j - 7.0 * x_ ); // mod(j,N)

	vec4 x = x_ *ns.x + ns.yyyy;
	vec4 y = y_ *ns.x + ns.yyyy;
	vec4 h = 1.0 - abs(x) - abs(y);

	vec4 b0 = vec4( x.xy, y.xy );
	vec4 b1 = vec4( x.zw, y.zw );

	vec4 s0 = floor(b0)*2.0 + 1.0;
	vec4 s1 = floor(b1)*2.0 + 1.0;
	vec4 sh = -step(h, vec4(0.0));

	vec4 a0 = b0.xzyw + s0.xzyw*sh.xxyy ;
	vec4 a1 = b1.xzyw + s1.xzyw*sh.zzww ;

	vec3 p0 = vec3(a0.xy,h.x);
	vec3 p1 = vec3(a0.zw,h.y);
	vec3 p2 = vec3(a1.xy,h.z);
	vec3 p3 = vec3(a1.zw,h.w);

	// Normalise gradients
	vec4 norm = taylorInvSqrt3d(vec4(dot(p0,p0), dot(p1,p1), dot(p2, p2), dot(p3,p3)));
	p0 *= norm.x;
	p1 *= norm.y;
	p2 *= norm.z;
	p3 *= norm.w;

	// Mix final noise value
	vec4 m = max(0.6 - vec4(dot(x0,x0), dot(x1,x1), dot(x2,x2), dot(x3,x3)), 0.0);
	m = m * m;
	return 42.0 * dot( m*m, vec4( dot(p0,x0), dot(p1,x1), dot(p2,x2), dot(p3,x3) ) );
}

float fbm3d(vec3 x, const in int it) {
	float v = 0.0;
	float a = 0.5;
	vec3 shift = vec3(100);

	for(int i = 0; i < 32; ++i) {
		if(i < it) {
			v += a * simplexNoise3d(x);
			x = x * 2.0 + shift;
			a *= 0.5;
		}
	}

	return v;
}

vec3 rotateZ(vec3 v, float angle) {
	float cosAngle = cos(angle);
	float sinAngle = sin(angle);
	return vec3(
		v.x * cosAngle - v.y * sinAngle,
		v.x * sinAngle + v.y * cosAngle,
		v.z
	);
}

float facture(vec3 vector) {
	vec3 normalizedVector = normalize(vector);

	return max(max(normalizedVector.x, normalizedVector.y), normalizedVector.z);
}

vec3 emission(vec3 color, float strength) {
	return color * strength;
}

void main() {
	// Normalized pixel coordinates (from 0 to 1) and (from -1 to 1)
	vec2 uv = (gl_FragCoord.xy * 2.0 - u_resolution.xy) / u_resolution.y;

	vec3 color = vec3(uv.xy, 0.0);
	color.z += 0.5;

	color = normalize(color);
	color -= 0.2 * vec3(0.0, 0.0, u_time);

	float angle = -log2(length(uv)); // log base 0.5

	color = rotateZ( color, angle );

	float frequency = 1.4;
	float distortion = 0.01;
	color.x = fbm3d(color * frequency + 0.0, 5) + distortion;
	color.y = fbm3d(color * frequency + 1.0, 5) + distortion;
	color.z = fbm3d(color * frequency + 2.0, 5) + distortion;
	vec3 noise_color = color; // save

	noise_color *= 2.0;
	noise_color -= 0.1;
	noise_color *= 0.188;
	noise_color += vec3(uv.xy, 0.0);

	float noise_color_length = length(noise_color);
	noise_color_length = 0.770 - noise_color_length;
	noise_color_length *= 4.2;
	noise_color_length = pow(noise_color_length, 1.0);

	vec3 emission_color = emission(vec3(0.961, 0.592, 0.078), noise_color_length * 0.4);

	float fac = length(uv) - facture(color + 0.32);
	fac += 0.1;
	fac *= 3.0;

	color = mix(emission_color, vec3(fac), fac + 1.2);

	//color = mix(color, vec3(0), fac); // black style

	// Output to screen
	fragColor = vec4(color, 1.0);
}
"""

# https://fragcoord.xyz/s/l8p2wc5o
FRAGMENT_SHADER_LOADING_ICON = """
#version 330 core
uniform vec2 u_resolution;
uniform float u_time;
out vec4 fragColor;

#define pi 3.14159265359;

const float RAD = 0.5;
const float WIDTH = 0.02;
const float ROT = -30.0;

vec2 rotate(vec2 p, float a) {
	return vec2(p.x * cos(a) - p.y * sin(a),p.x * sin(a) + p.y * cos(a));
}

float trail(vec2 cuv, float time) {
	vec2 rcuv = rotate(cuv, ROT * time);
	float len = length(rcuv);
	float angle = atan(rcuv.y, rcuv.x);
	angle += pi;

	float base = 0.05;
	float trailVal = sign(-abs(len - RAD * time) + (WIDTH * angle) + base);
	float mask = sign(RAD * time - len);
	float outer = max(sign(trailVal - mask), 0.0);
	float inner = max(sign(trailVal + mask), 0.0);

	return outer;
}

void main() {
	vec2 fit = (gl_FragCoord.xy - 0.5 * u_resolution) / min(u_resolution.x, u_resolution.y);
	vec2 cuv = fit;
	float duration = 1.5;
	float time = mod(u_time, duration);

	float posterize = 161.8;
	time *= posterize;
	time = floor(time);
	time /= posterize;

	float decay = 1.5;
	float t1 = trail(cuv, time) / decay;
	float t2 = trail(cuv, time - 0.1) * step(0.1, time) / decay;
	float t3 = trail(cuv, time - 0.5) * step(0.5, time) / decay;
	float t4 = trail(cuv, time - 0.6) * step(0.6, time) / decay;
	float t5 = trail(cuv, time - 0.65) * step(0.65, time) / decay;

	float halftone = 0.0;
	float trails = t1 + t2 + t3 + t4 + t5 - halftone - time * 1.3;

	fragColor = vec4(trails, 0.0, 0.0, 1.0);
}
"""

FRAGMENT_SHADER_PUKUU = """
#version 330 core
uniform vec2 u_resolution;
uniform float u_time;
out vec4 fragColor;

float dot2(vec2 p){
    return dot(p,p);
}

float Sd_heart( in vec2 p )
{
    p.x = abs(p.x);

    if( p.y+p.x>1.0 )
        return sqrt(dot2(p-vec2(0.25,0.75))) - sqrt(2.0)/4.0;
    return sqrt(min(dot2(p-vec2(0.00,1.00)),
                    dot2(p-0.5*max(p.x+p.y,0.0)))) * sign(p.x-p.y);
}

void main() {
    vec2 frag_coord = vec2(gl_FragCoord.x, gl_FragCoord.y);

    vec2 uv =  (frag_coord * 2.0) / u_resolution ;
    uv -= 1.0;
    uv.x *= u_resolution.x / u_resolution.y;

    float dist = Sd_heart(uv - vec2(0, -0.5));
    float heart = abs(dist);

    vec2 lightDirection = normalize(vec2(sin(u_time),cos(u_time)));

    float spotlight = dot(uv, lightDirection);

    vec3 baseColor = vec3(0.8, 0.1, 0.2);

    vec3 finalColor = baseColor * (spotlight + 1.0) * (0.09 / heart);

    fragColor = vec4(finalColor, 1.0);
}
"""

FRAGMENT_SHADER_HALFTONE = """
#version 330 core
uniform vec2 u_resolution;
uniform float u_time;
out vec4 fragColor;

float mod289(float x){return x-floor(x*(1./289.))*289.;}
vec2 mod289(vec2 x){return x-floor(x*(1./289.))*289.;}
vec3 mod289(vec3 x){return x-floor(x*(1./289.))*289.;}
vec4 mod289(vec4 x){return x-floor(x*(1./289.))*289.;}
float permute(float x){return mod289(((x*34.)+1.)*x);}
vec3 permute(vec3 x){return mod289(((x*34.)+1.)*x);}
vec4 permute(vec4 x){return mod289(((x*34.)+1.)*x);}
float taylorInvSqrt(float r){return 1.79284291400159-.85373472095314*r;}
vec4 taylorInvSqrt(vec4 r){return 1.79284291400159-.85373472095314*r;}
float snoise2D(vec2 v){
const vec4 C=vec4(.211324865405187,.366025403784439,-.577350269189626,.024390243902439);
vec2 i=floor(v+dot(v,C.yy));vec2 x0=v-i+dot(i,C.xx);
vec2 i1=(x0.x>x0.y)?vec2(1,0):vec2(0,1);
vec4 x12=x0.xyxy+C.xxzz;x12.xy-=i1;i=mod289(i);
vec3 p=permute(permute(i.y+vec3(0,i1.y,1))+i.x+vec3(0,i1.x,1));
vec3 m=max(.5-vec3(dot(x0,x0),dot(x12.xy,x12.xy),dot(x12.zw,x12.zw)),0.);m=m*m;m=m*m;
vec3 x=2.*fract(p*C.www)-1.;vec3 h=abs(x)-.5;vec3 ox=floor(x+.5);vec3 a0=x-ox;
m*=1.79284291400159-.85373472095314*(a0*a0+h*h);
vec3 g;g.x=a0.x*x0.x+h.x*x0.y;g.yz=a0.yz*x12.xz+h.yz*x12.yw;
return 130.*dot(m,g);}
mat2 rotate2D(float r){return mat2(cos(r),sin(r),-sin(r),cos(r));}

void main() {
	fragColor = vec4(0.0);
	#define L(a)length(f=fract(p=(c/s+u_time)*rotate2D(a))-.5)-min(sin(snoise2D(rotate2D(a)*(p-=f)/3e1)*4.+f.x/3e1+u_time+a),.5)
	vec2 c=gl_FragCoord.xy-u_resolution*.5,s=20.-c.yy/8e1,p,f;fragColor=vec4(L(1.),L(2.),L(3.),1)*.5*s.x+.5;
}
"""

FRAGMENT_SHADER_GLASS = """
#version 330 core
uniform vec2 u_resolution;
uniform float u_time;
out vec4 fragColor;

void main() {
	fragColor = vec4(0.0);
	vec2 p=(gl_FragCoord.xy*2.-u_resolution)/u_resolution.y/.9;float l=length(p)-1.;fragColor=.5+.5*tanh(.1/max(l/.1,-l)-sin(l+p.y*max(1.,-l/.1)+u_time+vec4(0,1,2,0)));
}
"""

class ProgramHandler(osgGA.GUIEventHandler):
	def __init__(self, program):
		super().__init__()

		self.program = program

		self.program.shaders.append(osg.Shader(osg.Shader.VERTEX, VERTEX_SHADER))

		self.fragmentShaders = [
			("shield", FRAGMENT_SHADER_SHIELD),
			("eye", FRAGMENT_SHADER_EYE),
			("bitshift", FRAGMENT_SHADER_BITSHIFT),
			("blackhole_portal", FRAGMENT_SHADER_BLACKHOLE_PORTAL),
			("loading_icon", FRAGMENT_SHADER_LOADING_ICON),
			("pukuu", FRAGMENT_SHADER_PUKUU),
			("halftone", FRAGMENT_SHADER_HALFTONE),
			("glass", FRAGMENT_SHADER_GLASS)
		]

		self.index = random.randrange(len(self.fragmentShaders))

		self.apply()

	def apply(self):
		name, source = self.fragmentShaders[self.index]

		print(f"Using fragment shader: {name}")

		if len(self.program.shaders) == 2:
			del self.program.shaders[1]

		self.program.shaders.append(osg.Shader(osg.Shader.FRAGMENT, source))

	def next(self):
		self.index = (self.index + 1) % len(self.fragmentShaders)

		self.apply()

	def previous(self):
		self.index = (self.index - 1) % len(self.fragmentShaders)

		self.apply()

	def handle(self, ea, aa):
		if ea.handled or ea.type != osgGA.GUIEventAdapter.KEYUP:
			return False

		if ea.key in (ord(" "), ord("n"), ord("N")):
			self.next()

			return True

		if ea.key in (ord("p"), ord("P")):
			self.previous()

			return True

		return False

if __name__ == "__main__":
	osg.setNotifyLevel(osg.NotifySeverity.NOTICE)

	g = osg.Geometry()

	g.primitiveSets.append(osg.DrawArrays(osg.PrimitiveSet.TRIANGLE_FAN, 0, 4))
	g.initialBound = osg.BoundingBox(-1, -1, -1, 1, 1, 1)

	p = osg.Program(name="FragCoord.xyz")
	r = osg.Geode()

	r.drawables.append(g)

	ss = r.stateSet

	ss.attributes.append(p)
	ss.uniforms["u_resolution"] = osg.Vec2(800.0, 600.0)
	ss.uniforms["u_time"] = 0.0

	v = osgViewer.Viewer()

	v.sceneData = r
	v.cameraManipulator = osgGA.TrackballManipulator()
	v.eventHandlers.append(ProgramHandler(p))

	t = time.time()

	while not v.done:
		ss.uniforms["u_time"] = float(time.time() - t)

		v.frame()

		time.sleep(0.01)
