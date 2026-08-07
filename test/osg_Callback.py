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

def test_nested_callbacks_sequence_proxy():
	# osg::Callback::nestedCallback is a singly-linked chain, not an array --
	# Callback.nestedCallbacks (SequenceTraits<osg::Callback, NestedCallbacksTag>, see
	# pyosg/osg/NodeCallback.hpp) flattens it into list semantics. This exercises the splice
	# logic directly rather than just trusting it compiles.
	root = Callback()
	a, b, c = Callback(), Callback(), Callback()

	a.name, b.name, c.name = "a", "b", "c"

	root.nestedCallbacks.append(a)
	root.nestedCallbacks.append(b)
	root.nestedCallbacks.append(c)

	assert [x.name for x in root.nestedCallbacks] == ["a", "b", "c"]
	assert len(root.nestedCallbacks) == 3
	# Each element's OWN nestedCallbacks continues the same chain one step further in --
	# confirms indexing is really walking the real linked chain, not some separate list.
	assert [x.name for x in root.nestedCallbacks[0].nestedCallbacks] == ["b", "c"]

def test_nested_callbacks_del_splices_around_target():
	root = Callback()
	a, b, c = Callback(), Callback(), Callback()

	a.name, b.name, c.name = "a", "b", "c"

	root.nestedCallbacks.append(a)
	root.nestedCallbacks.append(b)
	root.nestedCallbacks.append(c)

	del root.nestedCallbacks[1]

	assert [x.name for x in root.nestedCallbacks] == ["a", "c"]
	# b is fully detached, not just skipped -- it shouldn't still be pointing at c.
	assert len(b.nestedCallbacks) == 0

def test_nested_callbacks_insert_splices_in_front():
	root = Callback()
	a, c, d = Callback(), Callback(), Callback()

	a.name, c.name, d.name = "a", "c", "d"

	root.nestedCallbacks.append(a)
	root.nestedCallbacks.append(c)
	root.nestedCallbacks.insert(1, d)

	assert [x.name for x in root.nestedCallbacks] == ["a", "d", "c"]

def test_nested_callbacks_set_replaces_and_keeps_tail():
	root = Callback()
	a, b, c, e = Callback(), Callback(), Callback(), Callback()

	a.name, b.name, c.name, e.name = "a", "b", "c", "e"

	root.nestedCallbacks.append(a)
	root.nestedCallbacks.append(b)
	root.nestedCallbacks.append(c)

	root.nestedCallbacks[1] = e

	assert [x.name for x in root.nestedCallbacks] == ["a", "e", "c"]
	# b was REPLACED (not spliced past) -- fully detached, same contract as del.
	assert len(b.nestedCallbacks) == 0

def test_nested_callbacks_remove_by_identity():
	root = Callback()
	a, b, c = Callback(), Callback(), Callback()

	a.name, b.name, c.name = "a", "b", "c"

	root.nestedCallbacks.append(a)
	root.nestedCallbacks.append(b)
	root.nestedCallbacks.append(c)
	root.nestedCallbacks.remove(b)

	assert [x.name for x in root.nestedCallbacks] == ["a", "c"]
	assert root.nestedCallbacks.index(c) == 1

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
