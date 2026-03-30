#vimrun! pytest -sv ../test/osg_Node.py

from .conftest import refcmp

from OpenSceneGraph.osg import Object, Node, NodeCallback, StateSet
from OpenSceneGraph.osgUtil import UpdateVisitor

class MyNode(Node):
	pass

def test_construction():
	n = Node(name="foo", nodeMask=0xdeadbeef)

	assert n.name == "foo"
	assert n.nodeMask == 0xdeadbeef
	assert refcmp(n, 1, 1)

	n0 = n
	n1 = n0

	assert refcmp(n, 1, 3)

def test_inheritance():
	n = MyNode(dataVariance=Object.STATIC)

	assert n.dataVariance == Object.STATIC
	assert refcmp(n, 1, 1)

def test_updatecallback():
	updated = []

	class UpdateCallback(NodeCallback):
		def __call__(self, *args, **kwargs):
			nonlocal updated

			updated.append(1)

	n = Node()

	n.updateCallback = UpdateCallback()

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

def test_stateset():
	n = Node()
	ss = StateSet()

	ss.binName = "BIN"

	n.stateSet = ss

	assert n.stateSet is ss
	assert n.stateSet.binName == "BIN"
