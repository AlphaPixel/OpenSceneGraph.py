#vimrun! pytest -sv ../test/osg_Node.py

from .conftest import refcmp

from OpenSceneGraph.osg import Callback, Object, Node, NodeCallback, StateSet
from OpenSceneGraph.osgUtil import UpdateVisitor

def test_construction():
	n = Node(name="foo", nodeMask=0xdeadbeef)

	assert n.name == "foo"
	assert n.nodeMask == 0xdeadbeef
	assert refcmp(n, 1, 1)

	n0 = n
	n1 = n0

	assert refcmp(n, 1, 3)

def test_construction_kwargs_cullingactive():
	assert Node().cullingActive == True
	assert Node(cullingActive=False).cullingActive == False

def test_destruction():
	deleted = []

	n = Node(name="NODE", debug=lambda addr, cls, name: deleted.append(addr))
	addr = n.addr

	assert refcmp(n, 1, 1)

	del n

	assert deleted[-1] == addr

def test_inheritance():
	class MyNode(Node):
		pass

	n = MyNode(dataVariance=Object.STATIC)

	assert n.dataVariance == Object.STATIC
	assert refcmp(n, 1, 1)

def test_updatecallback():
	updated = []

	class UpdateNodeCallback(NodeCallback):
		def __call__(self, *args, **kwargs):
			nonlocal updated

			updated.append(1)

	n = Node(updateCallback=UpdateNodeCallback())

	# print(n.updateCallback.referenceCount)
	# assert refcmp(n.updateCallback, 2, 1)
	# n.accept(NodeVisitor(NodeVisitor.TraversalMode.TRAVERSE_ALL_CHILDREN))

	n.accept(UpdateVisitor())

	assert updated[-1] == 1

	n.updateCallback = lambda *a: updated.append(2)

	n.accept(UpdateVisitor())

	assert updated[-1] == 2

	n.updateCallback = None

	n.accept(UpdateVisitor())

	# It should STILL only have 2 values, since we removed the `updateCallback`.
	assert len(updated) == 2

	# A plain Callback (not NodeCallback) works too now: real OSG's Node::setUpdateCallback()
	# already takes a bare osg::Callback*, and run() is the modern, unified entry point that
	# NodeCallback::run() itself is built on top of (adapting it to the "old style" operator()).
	# Deliberately no explicit return (implicit None): call_override<bool> treats that as "no
	# opinion," falling through to the real osg::Callback::run() default (which calls traverse()),
	# so children/nested callbacks still get visited normally -- an explicit True/False here would
	# instead REPLACE that default outcome outright, same as detail::NodeCallback::run()'s existing
	# behavior for its own "run" override.
	class UpdateCallback(Callback):
		def run(self, obj, data):
			nonlocal updated

			updated.append(3)

	n.updateCallback = UpdateCallback()

	n.accept(UpdateVisitor())

	assert updated[-1] == 3

def test_stateset():
	n = Node()
	ss = StateSet()

	ss.binName = "BIN"

	n.stateSet = ss

	assert n.stateSet is ss
	assert n.stateSet.binName == "BIN"
