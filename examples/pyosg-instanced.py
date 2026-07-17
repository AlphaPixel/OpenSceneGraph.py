#!/usr/bin/env python3
#vimrun! ../examples/pyosg-instanced.py

import os
import time

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
uniform float gridSize = 16.0;

out vec3 vColor;

void main() {
	// Four corners of a centered unit quad...
	vec2 base[4] = vec2[4](
		vec2(-0.5, -0.5),
		vec2( 0.5, -0.5),
		vec2( 0.5, 0.5),
		vec2(-0.5, 0.5)
	);

	vec2 v = base[gl_VertexID % 4];

	// Pick a random-ish color per instance...
	float id = float(gl_InstanceID);

	vColor = vec3(
		fract(sin(id * 12.9898) * 43758.5453),
		fract(sin(id * 78.233) * 43758.5453),
		fract(sin(id * 45.164) * 43758.5453)
	);

	// lay out in a grid; MAKE SURE THIS MATCHES THE "numInstances" for what you
	// pass to PrimitiveSet(DrawArrays())!
	float gx = mod(id, gridSize);
	float gy = floor(id / gridSize);

	vec2 pos = vec2(gx, gy) - vec2(gridSize/2.0);

	// A smidge of padding...
	pos *= 1.2;

	gl_Position = gl_ModelViewProjectionMatrix * vec4(pos.x + v.x, 0.0, pos.y + v.y, 1.0);
}
"""

FRAGMENT_SHADER = """
	#version 330 core
	in vec3 vColor;
	out vec4 fragColor;
	void main() {
		fragColor = vec4(vColor, 1.0);
	}
"""

if __name__ == "__main__":
	osg.setNotifyLevel(osg.NotifySeverity.NOTICE)

	g = osg.Geometry()

	# TODO: Convert to SequenceProxy!
	# g.primitiveSets.append(osg.DrawArrays(GL_TRIANGLE_FAN, 0, 4, 16 * 16))
	g.primitiveSets.append(osg.DrawArrays(osg.PrimitiveSet.TRIANGLE_FAN, 0, 4, 16 * 16))

	g.initialBound = osg.BoundingBox(-10, -1, -10, 10, 1, 10)
	# g.useVertexBufferObjects = True

	p = osg.Program(name="gl_InstanceID_DEMO", shaders=(
		osg.Shader(osg.Shader.VERTEX, VERTEX_SHADER),
		osg.Shader(osg.Shader.FRAGMENT, FRAGMENT_SHADER)
	))

	r = osg.Geode()

	r.drawables.append(g)
	r.stateSet.setAttributeAndModes(p)

	v = osgViewer.Viewer()

	v.sceneData = r
	v.cameraManipulator = osgGA.TrackballManipulator()

	while not v.done:
		v.frame()

		time.sleep(0.1)
