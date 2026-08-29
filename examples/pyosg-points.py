#!/usr/bin/env python3

import time
import numpy as np

# Import side effect: fills in OSG_WINDOW/OSG_THREADING/OSG_GL_* env var defaults (see
# pyosg_example.py). Deliberately before `from OpenSceneGraph import *`, matching every other
# example -- these need to land before OSG's DisplaySettings reads them.
from pyosg_example import window_size

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
	float dotGlow = exp(-r2 * 2.5);

	// A thin 360-degree ring around the glow -- pure "bling," proves the point-sprite
	// footprint can carry more than just the dot without any extra geometry/draw calls.
	float r = sqrt(r2);
	float ring = smoothstep(0.12, 0.0, abs(r - 0.85));

	float alpha = max(dotGlow, ring * 0.6);

	color = vec4(vColor.rgb, vColor.a * alpha);
	// color = vec4(gl_PointCoord, 0.0, 1.0);
}
"""

def build_scene(w, h):
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
	a = osg.Vec3Array(tree_arr)

	print(f" >> {len(a)}")

	# TODO: Convert to SequenceProxy!
	g.vertexArray = a
	g.primitiveSets.append(osg.DrawArrays(osg.PrimitiveSet.POINTS, 0, len(a)))
	g.useVertexBufferObjects = True

	r = osg.Geode()

	r.drawables.append(g)
	r.stateSet.modes[GL_PROGRAM_POINT_SIZE] = osg.StateAttribute.Values.ON
	r.stateSet.modes[GL_VERTEX_PROGRAM_POINT_SIZE] = osg.StateAttribute.Values.ON
	# r.stateSet.setMode(GL_POINT_SPRITE, osg.StateAttribute.Values.ON)
	r.stateSet.modes[GL_BLEND] = osg.StateAttribute.Values.ON
	# r.stateSet.setMode(GL_DEPTH_TEST, osg.StateAttribute.Values.OFF)
	r.stateSet.attributes.append(osg.Program(name="NumPy Points DEMO", shaders=(
		osg.Shader(osg.Shader.VERTEX, VERTEX_SHADER),
		osg.Shader(osg.Shader.FRAGMENT, FRAGMENT_SHADER)
	)))
	r.stateSet.attributes[osg.StateAttribute.BLENDFUNC] = (
		osg.BlendFunc(GL_SRC_ALPHA, GL_ONE),
		# osg.BlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA),
		osg.StateAttribute.Values.ON
	)
	r.stateSet.attributes[osg.StateAttribute.DEPTH] = (
		osg.Depth(osg.Depth.LESS, 0.0, 1.0, False),
		osg.StateAttribute.Values.ON
	)

	return r

if __name__ == "__main__":
	# osg.setNotifyLevel(osg.NotifySeverity.NOTICE)

	W, H = window_size()

	v = osgViewer.Viewer()

	v.sceneData = build_scene(W, H)
	v.cameraManipulator = osgGA.TrackballManipulator()

	while not v.done:
		v.frame()

		time.sleep(0.1)
