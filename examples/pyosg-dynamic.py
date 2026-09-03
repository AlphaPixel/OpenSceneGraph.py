#!/usr/bin/env python3

# Standalone, minimal proof of the "stable, controllable object lifetime" pattern this project
# treats as non-negotiable (see aipython/20-object-lifetime.md) -- deliberately with NO async/
# progress-bar scaffolding as a confounding variable, after that scaffolding turned up a real
# bug: an osg::Camera orphaned from the scene graph mid-session (kept alive only by a bare
# Python variable, plus a still-running asyncio task) got destroyed at UNCONTROLLED CPython
# interpreter-shutdown time, relative to osgViewer::Viewer's own GraphicsContext teardown --
# sometimes after the GL context was already gone. Confirmed via coredumpctl: a SIGABRT deep
# inside libGL.so.1's own exit-time cleanup (heap corruption detected late, not at the moment
# of the actual bug) -- not an immediate segfault at the point of the mistake, which is exactly
# why this needs a real proof, not just "it looked fine that one time."
#
# Press 'a' to add a real GL-resource-owning object (a colored sphere -- a genuine
# ShapeDrawable, with its own display-list/VBO state) to the scene at a random position.
# Press 'r' to remove a RANDOM live one (not just the most recent -- exercises Group.children's
# middle-of-sequence removal path, not only the simpler tail case) -- CORRECTLY: dropped from
# the scene graph AND its Python reference cleared (`del`) in the SAME statement, at a point we
# control, while the GL context is definitely still current (mid-session, actively rendering) --
# not left for Python's own GC/refcount teardown to sort out in whatever order it happens to
# pick. `debug=True` on each object proves this: watch for "Destroying" to print IMMEDIATELY on
# 'r', every time, not later, not never. Reference counts print on every add/remove too.
#
# Press 'x' to reproduce the BUGGY pattern instead: remove from the scene graph but do NOT
# `del` -- the object moves into a never-cleared `orphans` list, exactly mirroring `bar` being
# held only by __main__'s bare variable in the original bug, but with zero asyncio/threading
# anywhere in this file. Confirms (or disproves) whether async was ever actually load-bearing to
# the crash, or just how it happened to first get noticed.
#
# Cycle 'a'/'r' many times, then close the window (Escape) -- proves the pattern holds up under
# repetition, not just as a one-shot demonstration.

import itertools
import random

# Import side effect: fills in OSG_WINDOW/OSG_THREADING/OSG_GL_* env var defaults (see
# pyosg_example.py). Deliberately before `from OpenSceneGraph import *`, matching every other
# example -- these need to land before OSG's DisplaySettings reads them.
from pyosg_example import window_size

from OpenSceneGraph import *
from OpenSceneGraph.GL import *

# Same core-profile-safe minimal Lambertian shader as pyosg-hover.py/pyosg-picking.py.
VERTEX_SHADER = """
#version 330 core

in vec4 osg_Vertex;
in vec3 osg_Normal;
in vec4 osg_Color;

uniform mat4 osg_ModelViewProjectionMatrix;
uniform mat3 osg_NormalMatrix;

out vec3 vNormal;
out vec4 vColor;

void main() {
	vNormal = normalize(osg_NormalMatrix * osg_Normal);
	vColor = osg_Color;

	gl_Position = osg_ModelViewProjectionMatrix * osg_Vertex;
}
"""

FRAGMENT_SHADER = """
#version 330 core

in vec3 vNormal;
in vec4 vColor;

out vec4 fragColor;

void main() {
	const vec3 L = vec3(0.4, 0.6, 0.7);

	float diffuse = max(dot(normalize(vNormal), normalize(L)), 0.0);
	float light = 0.35 + 0.65 * diffuse;

	fragColor = vec4(vColor.rgb * light, vColor.a);
}
"""

# Monotonically increasing, never reused even after removals -- unlike len(objects), this gives
# each object a stable, unique name for the life of the process, so log output ("removing '7'")
# unambiguously identifies WHICH object, not just how many are currently live.
_next_id = itertools.count(1)

def make_object():
	"""A single colored sphere on its own MatrixTransform -- a real GL-resource-owning
	Drawable (display list/VBO), unlike ProgressBar's no-vertex-buffer gl_VertexID trick.
	debug=True proves exactly when this gets truly destroyed, not just detached from the graph;
	name=str(num) is what makes the interleaved Observing/Destroying notify lines identifiable.
	"""

	num = next(_next_id)

	pos = osg.Vec3(
		random.uniform(-6.0, 6.0),
		random.uniform(-6.0, 6.0),
		random.uniform(-6.0, 6.0)
	)
	color = osg.Vec4(random.random(), random.random(), random.random(), 1.0)

	mt = osg.MatrixTransform(
		osg.Matrix.translate(pos),
		name=str(num),
		# debug=True
		debug=lambda a, t, n: osg.info(f"[pyosg-dynamic] Destroying: {n} (0x{hex(a)})")
	)
	geode = osg.Geode()
	drawable = osg.ShapeDrawable(osg.Sphere(osg.Vec3(), 1.0))

	drawable.color = color

	geode.drawables.append(drawable)
	mt.children.append(geode)

	return mt

class DynamicHandler(osgGA.GUIEventHandler):
	"""'a' adds an object; 'r' removes a random live one -- CORRECTLY, see the module
	docstring. `objects` is the single source of truth for what's currently live; both the scene
	graph and this list drop their reference to a removed object in the same statement, so its
	destruction happens right here, not whenever Python's GC eventually gets to it.
	"""

	def __init__(self, viewer, root, objects):
		super().__init__()

		self.viewer = viewer
		self.root = root
		self.objects = objects
		# 'x' moves a live object here instead of `del`-ing it -- a real, uncleared Python
		# reference, exactly like pyosg-async-gltf.py's `bar` (held only by __main__'s bare
		# variable, no explicit del). Never cleared on purpose: proves/disproves whether THIS
		# pattern alone -- removed from the scene graph, kept alive by a lingering reference,
		# no asyncio anywhere in this file -- reproduces the same crash.
		self.orphans = []

	def handle(self, ea, aa):
		if ea.type != osgGA.GUIEventAdapter.KEYDOWN:
			return False

		if ea.key == ord("a"):
			obj = make_object()

			self.root.children.append(obj)
			self.objects.append(obj)

			osg.info(f"[pyosg-dynamic] added '{obj.name}' -- {len(self.objects)} live, {obj.referenceCount}")

			self.viewer.cameraManipulator.home(0.0)

			return True

		if ea.key == ord("r"):
			if not self.objects:
				osg.info("[pyosg-dynamic] nothing to remove")

				return True

			# A random index, not always the most recent -- exercises Group.children.remove()
			# removing from the MIDDLE of the sequence, not just the tail. SequenceProxy's del()
			# has to shift every later index's cached slot down by one when that happens (see
			# pybind11x.hpp's SequenceProxy::del() comments) -- worth stress-testing that path
			# specifically, not just the simpler last-element case.
			index = random.randrange(len(self.objects))
			obj = self.objects.pop(index)

			osg.info(f"[pyosg-dynamic] removing '{obj.name}' (index {index}), {obj.referenceCount} before")

			self.root.children.remove(obj)

			osg.info(f"[pyosg-dynamic] '{obj.name}' {obj.referenceCount} after scene removal")

			# The scene graph's ref is gone as of the line above; this drops the last one this
			# function holds. Without it, `obj` (a local variable) would keep the object alive
			# until handle() returns anyway -- harmless here, but the point is being explicit
			# about the moment of destruction, not relying on "it'll get collected eventually."
			del obj

			osg.info(f"[pyosg-dynamic] removed -- {len(self.objects)} live")

			self.viewer.cameraManipulator.home(0.0)

			return True

		if ea.key == ord("x"):
			if not self.objects:
				osg.info("[pyosg-dynamic] nothing to orphan")

				return True

			# Deliberately the BUGGY pattern from pyosg-async-gltf.py: remove from the scene
			# graph, but do NOT drop the Python reference -- just move it to `self.orphans`,
			# which is never cleared. If this alone crashes (with no asyncio, no threads, no
			# progress bar anywhere in this file), the bug is purely about uncontrolled
			# reference lifetime relative to the scene graph, not anything async-specific.
			index = random.randrange(len(self.objects))
			obj = self.objects.pop(index)

			osg.info(f"[pyosg-dynamic] orphaning '{obj.name}' (index {index}), {obj.referenceCount} before")

			self.root.children.remove(obj)

			osg.info(f"[pyosg-dynamic] '{obj.name}' {obj.referenceCount} after scene removal (NOT del'd)")

			self.orphans.append(obj)

			osg.info(f"[pyosg-dynamic] orphaned -- {len(self.objects)} live, {len(self.orphans)} orphaned")

			self.viewer.cameraManipulator.home(0.0)

			return True

		return False

def build_scene(w, h):
	root = osg.Group()

	prog = osg.Program(name="pyosg-dynamic", shaders=(
		osg.Shader(osg.Shader.VERTEX, VERTEX_SHADER),
		osg.Shader(osg.Shader.FRAGMENT, FRAGMENT_SHADER)
	))

	root.stateSet.attributes.append(prog)

	return root

# DynamicHandler needs the live viewer (home() calls, event handler registration), which
# build_scene() never receives. Notify setup lives here too -- it's runtime/interactivity
# behavior, not scene construction, and this runs whether launched standalone or via a runner.
def configure_viewer(viewer, root):
	def notify(sev, msg):
		msg = msg.strip()

		if not msg or msg.startswith("Plenty of space in GLBufferObject pool"):
			return

		if msg.startswith("[pyosg-dynamic]"):
			print(f"\033[32m{msg}\033[0m")

		else:
			print(f"{msg}")

	# INFO (not just NOTICE) so our own osg.info() calls show up, interleaved with OSG's own
	# internal GL object allocation/deallocation logging at the same level -- letting us see the
	# real driver-level alloc/dealloc events alongside our own add/remove trace.
	osg.setNotifyLevel(osg.NotifySeverity.INFO)
	osg.setNotifyHandler(notify)

	print(
		"Press 'a' to add an object, 'r' to remove a random live one CORRECTLY, "
		"'x' to orphan one (remove from scene, DON'T del -- the buggy pattern).",
		flush=True
	)

	objects = []

	viewer.eventHandlers.append(DynamicHandler(viewer, root, objects))

if __name__ == "__main__":
	W, H = window_size()

	viewer = osgViewer.Viewer()
	root = build_scene(W, H)

	viewer.sceneData = root
	viewer.cameraManipulator = osgGA.TrackballManipulator()

	configure_viewer(viewer, root)

	while not viewer.done:
		viewer.frame()
