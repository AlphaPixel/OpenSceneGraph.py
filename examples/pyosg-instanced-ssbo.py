#!/usr/bin/env python3
#vimrun! ../examples/pyosg-instanced-ssbo.py --samples 4 --clear-color 0.1,0.2,0.3

import sys
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

GRID_SIZE = 10
NUM_INSTANCES = GRID_SIZE ** 2

VERTEX_SHADER = """
	#version 430 core

	uniform float gridSize = %d.0;

	flat out int instanceID;

	void main() {
		vec2 base[4] = vec2[4](
			vec2(-0.5, -0.5),
			vec2( 0.5, -0.5),
			vec2( 0.5, 0.5),
			vec2(-0.5, 0.5)
		);

		vec2 v = base[gl_VertexID %% 4];

		float id = float(gl_InstanceID);

		float gx = mod(id, gridSize);
		float gy = floor(id / gridSize);

		vec2 pos = vec2(gx, gy) - vec2(gridSize / 2.0);
		pos *= 1.2;

		instanceID = gl_InstanceID;

		gl_Position = gl_ModelViewProjectionMatrix * vec4(pos.x + v.x, 0.0, pos.y + v.y, 1.0);
	}
""" % GRID_SIZE

FRAGMENT_SHADER = """
	#version 430 core

	layout(std430, binding = 0) buffer ColorData {
		vec4 colors[];
	};

	flat in int instanceID;
	out vec4 fragColor;

	void main() {
		fragColor = colors[instanceID];
	}
"""

if __name__ == "__main__":
	osg.setNotifyLevel(osg.NotifySeverity.NOTICE)

	c = osg.Vec4Array(NUM_INSTANCES)

	# TODO: Do this in the constructor!
	for i in range(NUM_INSTANCES):
		gx = (i % GRID_SIZE) / (GRID_SIZE - 1)
		gy = (i / GRID_SIZE) / (GRID_SIZE - 1)

		c[i] = osg.Vec4(gx, gy, 1.0 - gx, 1.0)

	ssbo = osg.ShaderStorageBufferObject()

	c.bufferObject = ssbo

	ssbb = osg.ShaderStorageBufferBinding(0, c, 0, c.totalDataSize)

	g = osg.Geometry()

	# TODO: Convert to SequenceProxy!
	g.primitiveSets.append(osg.DrawArrays(osg.PrimitiveSet.TRIANGLE_FAN, 0, 4, NUM_INSTANCES))

	g.initialBound = osg.BoundingBox(-10, -1, -10, 10, 1, 10)
	# g.useVertexBufferObjects = True

	p = osg.Program(name="gl_InstanceID_SSBO_DEMO", shaders=(
		osg.Shader(osg.Shader.VERTEX, VERTEX_SHADER),
		osg.Shader(osg.Shader.FRAGMENT, FRAGMENT_SHADER)
	))

	g.stateSet.attributes.append(p)
	g.stateSet.attributes.append(ssbb)

	v = osgViewer.Viewer(osg.ArgumentParser("pyosg-instanced-ssbo.py", sys.argv))

	v.sceneData = g
	v.cameraManipulator = osgGA.TrackballManipulator()

	while not v.done:
		v.frame()

		time.sleep(1.0 / 30.0)
