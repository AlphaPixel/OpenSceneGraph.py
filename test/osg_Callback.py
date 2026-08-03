#vimrun! pytest -sv ../test/osg_Callback.py

from .conftest import refcmp

from OpenSceneGraph.osg import Callback, Node, NodeCallback, Object
from OpenSceneGraph.osgUtil import UpdateVisitor

def test_construction():
	cb = Callback()

	assert refcmp(cb, 1, 1)

def test_nodecallback_is_a_callback():
	# osg::NodeCallback : public virtual osg::Callback in real OSG -- confirms the pybind11
	# hierarchy actually reflects that (NodeCallback's py::class_ declares Callback as its base,
	# not just osg::Object), not merely that both happen to be Referenced-derived.
	nc = NodeCallback()

	assert isinstance(nc, Callback)
	assert isinstance(nc, Object)

def test_direct_python_call_is_not_proof_of_real_dispatch():
	# Methodology trap, same shape as the one documented in test/osgGA_CameraManipulator.py for
	# CameraManipulator: calling cb.run(...) directly on a Python object ALWAYS finds the
	# subclass's own Python-level method via ordinary attribute lookup, regardless of whether the
	# pybind11 trampoline actually routes a real C++-side virtual call there. Preserved
	# deliberately so it isn't "cleaned up" as redundant later.
	calls = []

	class DirectCallback(Callback):
		def run(self, obj, data):
			calls.append((obj, data))

	cb = DirectCallback()

	cb.run(None, None) # proves nothing about the trampoline

	assert len(calls) == 1

def test_run_dispatches_through_real_traversal():
	# The real test: drive it through actual C++-side dispatch (Node's internal update-traversal
	# machinery calling the stored osg::Callback*'s run(), not a direct Python call).
	calls = []

	class RealCallback(Callback):
		def run(self, obj, data):
			calls.append((obj, data))

	n = Node()

	n.updateCallback = RealCallback()

	n.accept(UpdateVisitor())

	assert len(calls) == 1
	assert calls[0][0] is n
