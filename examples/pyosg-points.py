#!/usr/bin/env python3
#vimrun! ../examples/pyosg-points.py

import os
import time
import numpy as np

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

// layout(location = 0) in vec3 inVertex;
// layout(location = 1) in vec4 inColor;

uniform mat4 osg_ModelViewProjectionMatrix;

in vec4 osg_Vertex;
out vec4 vColor;

void main(void) {
	// gl_Position = osg_ModelViewProjectionMatrix * vec4(inVertex, 1.0);
	gl_Position = osg_ModelViewProjectionMatrix * osg_Vertex;
	vColor = vec4(1.0, 0.5, 0.0, 1.0);

	// Be sure and call `StateSet::setMode(GL_PROGRAM_POINT_SIZE, osg::StateAttribute::ON)`, or
	// this will be a no-op! IMPORTANT!
	gl_PointSize = 20.0;
}
"""

FRAGMENT_SHADER = """
#version 330 core
in vec4 vColor;

out vec4 color;

void main(void) {
	// Convert to [-1, 1] so (0,0) is the center of the point.
	vec2 p = gl_PointCoord * 2.0 - 1.0;

	// This gives us a radial coordinate without a costly sqrt(), supposedly.
	float r2 = dot(p, p);

	// This explicitly recreates legacy FFP point behavior...
	// float alpha = exp(-r2 * 0.75);
	float alpha = exp(-r2 * 2.5);

	color = vec4(vColor.rgb, vColor.a * alpha);
	// color = vec4(gl_PointCoord, 0.0, 1.0);
}
"""

def create_spiral_point_cloud(count, da=0.08, dr=0.01):
	positions = np.zeros((count, 3), dtype=np.float32)

	for i in range(count):
		a = float(i) * da
		r = float(i) * dr

		positions[i, 0] = r * np.cos(a)
		positions[i, 1] = r * np.sin(a)
		positions[i, 2] = float(i) / float(count)

	return positions

if __name__ == "__main__":
	osg.setNotifyLevel(osg.NotifySeverity.NOTICE)

	# Simulate ML output: positions
	N = 300
	vecs = np.random.rand(N, 3).astype(np.float32) * 0.5

	# Simulate labels (0 = rock, 1 = tree)
	labels = np.random.randint(0, 2, size=N)

	# Filter like PyTorch/NumPy workflow
	treevecs = vecs[labels == 1]
	rockvecs = vecs[labels == 0]

	print("trees:", treevecs.shape)
	print("rocks:", rockvecs.shape)

	# Feed into OSG
	tree_arr = osg.Vec3Array(treevecs)
	rock_arr = osg.Vec3Array(rockvecs)

	print(tree_arr.dump())
	print(rock_arr.dump())

	g = osg.Geometry()
	# a = osg.Vec3Array([osg.Vec3(i, i, i) for i in range(10)])
	# a = osg.Vec3Array(create_spiral_point_cloud(1000))
	a = osg.Vec3Array(tree_arr)

	print(f" >> {len(a)}")

	# TODO: Convert to SequenceProxy!
	g.setVertexArray(a)
	g.addPrimitiveSet(osg.DrawArrays(osg.PrimitiveSet.POINTS, 0, len(a)))
	g.useVertexBufferObjects = True

	r = osg.Geode()

	r.drawables.append(g)
	r.stateSet.setMode(GL_PROGRAM_POINT_SIZE, osg.StateAttribute.Values.ON)
	r.stateSet.setMode(GL_VERTEX_PROGRAM_POINT_SIZE, osg.StateAttribute.Values.ON)
	# r.stateSet.setMode(GL_POINT_SPRITE, osg.StateAttribute.Values.ON)
	r.stateSet.setMode(GL_BLEND, osg.StateAttribute.Values.ON)
	# r.stateSet.setMode(GL_DEPTH_TEST, osg.StateAttribute.Values.OFF)
	r.stateSet.setAttributeAndModes(osg.Program(name="NumPy Points DEMO", shaders=(
		osg.Shader(osg.Shader.VERTEX, VERTEX_SHADER),
		osg.Shader(osg.Shader.FRAGMENT, FRAGMENT_SHADER)
	)))
	r.stateSet.setAttributeAndModes(
		osg.BlendFunc(GL_SRC_ALPHA, GL_ONE),
		# osg.BlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA),
		osg.StateAttribute.Values.ON
	)
	r.stateSet.setAttributeAndModes(
		osg.Depth(osg.Depth.LESS, 0.0, 1.0, False),
		osg.StateAttribute.Values.ON
	)

	v = osgViewer.Viewer()

	v.sceneData = r
	v.cameraManipulator = osgGA.TrackballManipulator()

	while not v.done:
		v.frame()

		time.sleep(0.1)
