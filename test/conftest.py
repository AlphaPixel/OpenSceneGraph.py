import sys
import struct
import os

import pytest

sys.path.append("BUILD-g++-13.3.0-NOASAN")
sys.path.append("BUILD-g++-15.2.1-NOASAN")

os.putenv("OSG_THREADING", "SingleThreaded")

# import etc.nativeio as nativeio

# with nativeio.silence():
from OpenSceneGraph import *

class FrameActions(osgGA.GUIActionAdapter):
	"""Headless GUIActionAdapter that records OSG requests for test assertions."""

	def __init__(self):
		super().__init__()

		self.redraws = 0
		self.continuousUpdates = []
		self.pointerWarps = []

	def requestRedraw(self):
		self.redraws += 1

	def requestContinuousUpdate(self, needed=True):
		self.continuousUpdates.append(needed)

	def requestWarpPointer(self, x, y):
		self.pointerWarps.append((x, y))

class FrameSimulator:
	"""Drive OSG's event and update visitors without a Viewer or graphics context."""

	def __init__(self):
		self.frameStamp = osg.FrameStamp()
		self.events = osgGA.EventQueue()
		self.actions = FrameActions()
		self.eventVisitor = osgGA.EventVisitor()
		self.updateVisitor = osgUtil.UpdateVisitor()

		self.eventVisitor.actionAdapter = self.actions

	def advance(self, simulationTime=0.0):
		self.frameStamp.frameNumber += 1
		self.frameStamp.referenceTime = simulationTime
		self.frameStamp.simulationTime = simulationTime

	def dispatchEvent(self, handler, event):
		"""Use OSG's C++ GUIEventHandler dispatch path for one GUI event."""

		return osgGA.GUIEventHandler.handle(handler, event, self.actions)

	def traverseEvents(self, root):
		self.eventVisitor.frameStamp = self.frameStamp
		self.eventVisitor.traversalNumber = self.frameStamp.frameNumber

		for event in self.events.takeEvents():
			self.eventVisitor.reset()
			self.eventVisitor.addEvent(event)
			root.accept(self.eventVisitor)

	def traverseUpdate(self, root):
		self.updateVisitor.reset()
		self.updateVisitor.frameStamp = self.frameStamp
		self.updateVisitor.traversalNumber = self.frameStamp.frameNumber
		root.accept(self.updateVisitor)

@pytest.fixture
def simulate_frame():
	return FrameSimulator()

def f32(x: float) -> float:
	"""Convert Python float -> IEEE754 float32 -> float64 again."""

	return struct.unpack("!f", struct.pack("!f", x))[0]

def floatif(integral: int, fractional: int) -> (float, float):
	"""
	Construct a decimal float from explicit integer + fractional components.

	Returns:
		(f, f32(f))
	"""

	# Fractional digit count
	digits = len(str(fractional))

	# Construct double first (Python float == IEEE-754 double)
	f = integral + fractional / (10 ** digits)

	return f, f32(f)

def refcmp(obj: osg.Referenced, cpp: int, py: int) -> bool:
	"""
	Compare an object's C++ and Python reference counts.

	The expected Python reference count is adjusted by +2 to account for:
		1) CPython's temporary reference during attribute access, and
		2) the reference held by passing `obj` into this function.

	This helper allows tests to express *logical* ownership expectations
	rather than raw CPython refcount mechanics.
	"""

	return obj.referenceCount == osg.RefCounts(cpp, py + 2)

@pytest.fixture
def emit_notify():
	def _emit_notify():
		osg.fatal("FATAL")
		osg.warn("WARN")
		osg.notice("NOTICE")
		osg.info("INFO")
		osg.debug("DEBUG")
		osg.debug_fp("DEBUG_FP")

	return _emit_notify

@pytest.fixture
def vec3():
	return osg.Vec3(1.1, 2.2, 3.3)

@pytest.fixture
def vec3f():
	return osg.Vec3f(1.1, 2.2, 3.3)

@pytest.fixture
def vec3d():
	return osg.Vec3d(1.1, 2.2, 3.3)

@pytest.fixture
def vec3a():
	return osg.Vec3Array([osg.Vec3(i, i, i) for i in range(8)])

@pytest.fixture
def uniform_init():
	return (
		(osg.Uniform.BOOL, True),
		(osg.Uniform.INT, 1),
		(osg.Uniform.UNSIGNED_INT, 2),
		(osg.Uniform.FLOAT, f32(3.3)),
		(osg.Uniform.DOUBLE, 44.4444),
		(osg.Uniform.FLOAT_VEC3, osg.Vec3f()),
		(osg.Uniform.FLOAT_MAT4, osg.Matrixf())
	)

@pytest.fixture
def scene(Node, Group):
	root = Group()

	n0 = Node(name="n0")
	n1 = Node(name="n1")

	root.addChild(n0)
	root.addChild(n1)

	return root, n0, n1
