#vimrun! pytest -sv ../test/osg_Group.py

import pytest

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

def test_children_insert():
	g = Group(name="g")
	n0 = Node(name="n0")
	n1 = Node(name="n1")
	n2 = Node(name="n2")

	g.children.extend((n0, n2))
	g.children.insert(1, n1)

	assert list(g.children) == [n0, n1, n2]

	# Out-of-range indices clamp like list.insert(), rather than raising.
	front = Node(name="front")
	back = Node(name="back")

	g.children.insert(-100, front)
	g.children.insert(100, back)

	assert list(g.children) == [front, n0, n1, n2, back]

def test_children_del_then_insert_cache_interaction():
	# Catch any interaction between del()'s and insert()'s cache invalidation paths, rather
	# than only exercising each in isolation.
	g = Group(name="g")
	n0 = Node(name="n0")
	n1 = Node(name="n1")
	n2 = Node(name="n2")
	n3 = Node(name="n3")

	g.children.extend((n0, n1, n2))

	del g.children[1]  # [n0, n2]

	assert list(g.children) == [n0, n2]

	g.children.insert(1, n3)  # [n0, n3, n2]

	assert list(g.children) == [n0, n3, n2]
	assert g.children[0] is n0
	assert g.children[1] is n3
	assert g.children[2] is n2

def test_children_index_and_remove():
	g = Group(name="g")
	n0 = Node(name="n0")
	n1 = Node(name="n1")
	n2 = Node(name="n2")

	g.children.extend((n0, n1, n2))

	assert g.children.index(n1) == 1

	g.children.remove(n1)

	assert list(g.children) == [n0, n2]

	with pytest.raises(ValueError):
		g.children.index(n1)

	with pytest.raises(ValueError):
		g.children.remove(n1)

def test_children_pop_and_clear():
	g = Group(name="g")
	n0 = Node(name="n0")
	n1 = Node(name="n1")
	n2 = Node(name="n2")

	g.children.extend((n0, n1, n2))

	assert g.children.pop() is n2
	assert len(g.children) == 2

	assert g.children.pop(0) is n0
	assert len(g.children) == 1
	assert g.children[0] is n1

	g.children.append(n0)
	g.children.append(n2)

	assert len(g.children) == 3

	g.children.clear()

	assert len(g.children) == 0

def test_children_pop_and_clear_release_when_no_other_ref():
	# len() dropping to 0 proves the C++ container emptied, but not that the objects were
	# actually destroyed rather than kept alive by a leaked SlotCache slot -- the exact bug
	# class del()'s own "invalidate up to old_size" comment exists to prevent. No local
	# variables are kept beyond `popped` on purpose, so `deleted` is the only proof.
	deleted = []
	dbg = lambda addr, cls, name: deleted.append(name)

	g = Group(name="g")

	g.children.append(Node(name="n0", debug=dbg))
	g.children.append(Node(name="n1", debug=dbg))
	g.children.append(Node(name="n2", debug=dbg))

	popped = g.children.pop()

	assert popped.name == "n2"
	assert deleted == []  # `popped` is still holding a reference to it

	del popped

	assert deleted == ["n2"]

	g.children.clear()

	assert sorted(deleted) == ["n0", "n1", "n2"]

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
