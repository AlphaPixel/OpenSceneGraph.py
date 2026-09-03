#!/usr/bin/env python3

# Answers one question: "how do I change vertex data every frame, when there's
# no way around it?" (procedural geometry, skinning, particles, ...) The
# answer is to mutate an EXISTING osg.Array's elements in place (arr[i] =
# value) and call arr.dirty() -- never reallocate a new Array/Geometry per
# frame just to move a vertex; see make_point()/UpdateCallback below.
#
# Under a core-profile context, mutate-in-place alone isn't enough: it also
# needs (1) an explicit vertex-attrib binding (geom.vertexAttrib[0] = arr +
# Program.bindAttribLocation) instead of relying on OSG's implicit/legacy
# vertex-array aliasing, and (2) geom.dataVariance = DYNAMIC on the Geometry
# ITSELF, not just the array -- see the comment in make_point() for why.

import math
import time

# Import side effect: fills in OSG_THREADING/OSG_GL_* env var defaults (see pyosg_example.py).
# Deliberately before `from OpenSceneGraph import *`, matching every other example -- these need
# to land before OSG's DisplaySettings reads them.
import os

from pyosg_example import window_size

from OpenSceneGraph import *
from OpenSceneGraph.GL import *

VERTEX_SHADER = """
#version 330 core
in vec4 osg_Vertex;
uniform mat4 osg_ModelViewProjectionMatrix;
void main() {
	gl_Position = osg_ModelViewProjectionMatrix * osg_Vertex;
	gl_PointSize = 24.0;
}
"""

FRAGMENT_SHADER = """
#version 330 core
uniform vec3 pointColor;
out vec4 fragColor;
void main() {
	vec2 p = gl_PointCoord * 2.0 - 1.0;
	if(dot(p, p) > 1.0) discard;
	fragColor = vec4(pointColor, 1.0);
}
"""

def orbit_pos(t):
	return osg.Vec3(math.cos(t), math.sin(t), 0.0)

class DataVarianceToggleHandler(osgGA.GUIEventHandler):
	"""Press D to flip the point's Geometry between DYNAMIC and STATIC live,
	demonstrating the exact mechanism make_point() relies on: switching to
	STATIC doesn't touch dirty()/vertexAttrib at all, it just tells
	VertexArrayState to stop ever re-checking them -- so the point freezes in
	place one frame later, at whatever position it happened to be at."""

	def __init__(self, geom):
		super().__init__()

		self.geom = geom

	def handle(self, ea, aa):
		if ea.handled or ea.type != osgGA.GUIEventAdapter.KEYUP:
			return False

		if ea.key not in (ord("d"), ord("D")):
			return False

		dynamic = self.geom.dataVariance == osg.Object.DataVariance.DYNAMIC

		self.geom.dataVariance = (
			osg.Object.DataVariance.STATIC if dynamic else osg.Object.DataVariance.DYNAMIC
		)

		print("dataVariance -> STATIC (frozen next frame)" if dynamic else "dataVariance -> DYNAMIC (resuming)")

		return True

class LiveUpdateCallback:
	"""Mutates the existing Vec3Array in place + dirty() -- the recommended
	pattern. Relies on make_point() having already bound this same array as
	vertex-attrib 0 (not just .vertexArray); no dirtyBound() needed here since
	make_point() sets a fixed, generous initialBound up front instead."""

	def __init__(self, geom):
		self.geom = geom
		self.t0 = time.time()

	def __call__(self, node, nv):
		t = time.time() - self.t0
		arr = self.geom.vertexArray

		arr[0] = orbit_pos(t)
		arr.dirty()

		return True

def make_point():
	geom = osg.Geometry()

	arr = osg.Vec3Array([orbit_pos(0.0)])
	arr.dataVariance = osg.Object.DataVariance.DYNAMIC

	geom.vertexArray = arr
	geom.primitiveSets.append(osg.DrawArrays(osg.PrimitiveSet.POINTS, 0, 1))
	geom.useVertexBufferObjects = True

	# The GEOMETRY's own dataVariance, not just the array's, matters: Drawable::draw() sets
	# VertexArrayState::_requiresSetArrays = (this->getDataVariance()==DYNAMIC) right after every
	# draw. If left STATIC (the default), frame 2 onward skips re-binding vertex-attrib arrays
	# entirely (Geometry::drawVertexArraysImplementation() returns early before ever reaching
	# setVertexAttribArray()) -- the point renders once at its initial position and freezes
	# forever, no matter how many times arr.dirty() fires on the CPU side.
	geom.dataVariance = osg.Object.DataVariance.DYNAMIC

	# Under a core-profile context, feeding a mutated array to a shader's
	# osg_Vertex input needs an explicit attrib binding -- OSG's implicit/
	# legacy vertex-array aliasing doesn't reliably pick up in-place mutation
	# otherwise. Binding the same array identity here means LiveUpdateCallback
	# never has to re-bind it -- only mutate + dirty() every frame.
	geom.vertexAttrib[0] = arr

	# Fixed, generous bound covering the whole orbit -- rules out small-feature/
	# frustum culling entirely as a variable. A single-vertex geometry's AUTO
	# bound is always zero-radius (it's one point), which sits right at the edge
	# of small-feature culling and can flicker frame to frame from float noise
	# even with dirtyBound() forcing a recompute every frame; an explicit
	# initialBound disables auto-recomputation entirely, so this can't happen.
	geom.initialBound = osg.BoundingBox(-1.5, -1.5, -1.5, 1.5, 1.5, 1.5)

	geode = osg.Geode()
	geode.drawables.append(geom)
	geode.cullingActive = False
	geode.updateCallback = LiveUpdateCallback(geom)

	ss = geode.stateSet
	p = osg.Program(shaders=(
		osg.Shader(osg.Shader.VERTEX, VERTEX_SHADER),
		osg.Shader(osg.Shader.FRAGMENT, FRAGMENT_SHADER),
	))
	p.bindAttribLocation["osg_Vertex"] = 0
	ss.attributes.append(p)
	ss.uniforms.extend((osg.Uniform("pointColor", osg.Vec3(1.0, 0.2, 0.2)),))
	ss.modes[GL_PROGRAM_POINT_SIZE] = osg.StateAttribute.ON
	ss.modes[GL_VERTEX_PROGRAM_POINT_SIZE] = osg.StateAttribute.ON

	return geode

def build_scene(w, h):
	root = osg.Group()
	root.children.append(make_point())

	return root

# viewMatrix/projectionMatrix need viewer.camera, which build_scene() never receives.
# DataVarianceToggleHandler needs the live viewer to register as an event handler, which
# build_scene() never receives -- the Geometry itself is recovered straight back out of the
# returned root's scene graph, same as pyosg-fragcoordxyz.py's own Program recovery.
def configure_viewer(viewer, root):
	viewer.camera.viewMatrix = osg.Matrix.lookAt(osg.Vec3(0, -10, 0), osg.Vec3(0, 0, 0), osg.Vec3(0, 0, 1))
	viewer.camera.projectionMatrix = osg.Matrix.perspective(40.0, 4.0 / 3.0, 0.1, 100.0)

	geom = root.children[0].drawables[0]

	viewer.eventHandlers.append(DataVarianceToggleHandler(geom))

	print("Press D to toggle dataVariance between DYNAMIC and STATIC.")

if __name__ == "__main__":
	osg.setNotifyLevel(osg.NotifySeverity.NOTICE)

	W, H = window_size()

	v = osgViewer.Viewer()
	root = build_scene(W, H)

	v.sceneData = root

	configure_viewer(v, root)

	while not v.done:
		v.frame()

		time.sleep(1.0 / 60.0)
