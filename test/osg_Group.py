#vimrun! pytest -sv ../test/osg_Group.py

from .conftest import refcmp

from OpenSceneGraph.osg import Group, Node, NodeCallback
from OpenSceneGraph.osgUtil import UpdateVisitor

def test_construction():
	g0 = Group(name="g0")
	n0 = Node(name="n0")
	n1 = Node(name="n1")
	n2 = Node(name="n2")

	g0.children.extend((n0, n1, n2))

	assert len(g0.children) == 3
	assert refcmp(g0, 1, 1)
	assert refcmp(n0, 2, 2)

	for n, c in zip((n0, n1, n2), g0.children):
		assert n is c

	g1 = Group(name="g1", children=(
		Node(name="foo"),
		Node(name="bar"),
		Node(name="baz")
	))

	assert len(g1.children) == 3
	assert refcmp(g1, 1, 1)
	assert refcmp(g1.children[0], 2, 2)
	assert g1.children[1].name == "bar"

def test_destruction():
	deleted = []
	dbg = lambda addr, cls, name: deleted.append(name)

	g = Group(name="g", debug=dbg, children=(
		Node(name="foo", debug=dbg),
		Node(name="bar", debug=dbg),
		Node(name="baz", debug=dbg)
	))

	del g

	assert deleted == ["foo", "bar", "baz", "g"]

def test_updatecallback():
	g0 = Group(name="g0")
	n0 = Node(name="n0")
	n1 = Node(name="n1")
	n2 = Node(name="n2")

	g0.children.extend((n0, n1, n2))

	def cb(obj, data):
		print(obj.name, data)

	class TestCallback(NodeCallback):
		def __call__(self, *args, **kwargs):
			print(f"TestCallback.__call__(self={self}, args={args}, kwargs={kwargs}")

			return True

	for n in (g0, n0, n1, n2):
		n.updateCallback = cb # TestCallback()

	g0.accept(UpdateVisitor())

# def test_updatecallback():
# 	n = Node()
# 	updated = []
#
# 	class UpdateNodeCallback(NodeCallback):
# 		def __call__(self, *args, **kwargs):
# 			nonlocal updated
#
# 			updated.append(1)
#
# 	n.updateCallback = UpdateNodeCallback()
#
# 	# print(n.updateCallback.referenceCount)
# 	# assert refcmp(n.updateCallback, 2, 1)
# 	# n.accept(NodeVisitor(NodeVisitor.TraversalMode.TRAVERSE_ALL_CHILDREN))
#
# 	n.accept(UpdateVisitor())
#
# 	assert updated[-1] == 1
#
# 	n.updateCallback = lambda *a: updated.append(2)
#
# 	n.accept(UpdateVisitor())
#
# 	assert updated[-1] == 2
#
# 	n.updateCallback = None
#
# 	n.accept(UpdateVisitor())
#
# 	# It should STILL only have 2 values, since we removed the `updateCallback`.
# 	assert len(updated) == 2
#
# 	class UpdateCallback(Callback):
# 		def run(self, obj, data):
# 			nonlocal updated
#
# 			updated.append(3)
#
# 	n.updateCallback = UpdateCallback()
#
# 	n.accept(UpdateVisitor())
#
# 	assert updated[-1] == 3
#
# def test_stateset():
# 	n = Node()
# 	ss = StateSet()
#
# 	ss.binName = "BIN"
#
# 	n.stateSet = ss
#
# 	assert n.stateSet is ss
# 	assert n.stateSet.binName == "BIN"
