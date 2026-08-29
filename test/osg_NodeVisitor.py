from OpenSceneGraph.osg import Group, Node, NodeVisitor

def test_construction_default_traversal_mode():
	nv = NodeVisitor()

	assert nv.traversalMode == NodeVisitor.TraversalMode.TRAVERSE_NONE

def test_construction_explicit_traversal_mode():
	nv = NodeVisitor(traversalMode=NodeVisitor.TraversalMode.TRAVERSE_ALL_CHILDREN)

	assert nv.traversalMode == NodeVisitor.TraversalMode.TRAVERSE_ALL_CHILDREN

def test_visitor_type_enum_values():
	assert NodeVisitor.VisitorType.NODE_VISITOR != NodeVisitor.VisitorType.UPDATE_VISITOR
	assert NodeVisitor.VisitorType.EVENT_VISITOR != NodeVisitor.VisitorType.CULL_VISITOR

def test_properties_roundtrip():
	nv = NodeVisitor()

	nv.traversalMask = 0xf00d
	nv.traversalNumber = 7

	assert nv.traversalMask == 0xf00d
	assert nv.traversalNumber == 7

def test_direct_python_call_is_not_proof_of_real_dispatch():
	# Same methodology trap as test/osg_Callback.py and test/osgGA_CameraManipulator.py: calling
	# visitor.apply(node) directly finds the Python subclass's own method via ordinary attribute
	# lookup, proving nothing about whether node.accept(visitor) -- real C++-side dispatch --
	# actually reaches it.
	visited = []

	class Visitor(NodeVisitor):
		def apply(self, node):
			visited.append(node.name)

	v = Visitor()
	n = Node(name="direct-only")

	v.apply(n) # proves nothing about the trampoline

	assert visited == ["direct-only"]

def test_apply_dispatches_through_real_accept_and_traverses_children():
	# NodeVisitor's own traversalMode -- NOT apply()'s return value -- gates whether traverse()
	# descends into children at all: osg::NodeVisitor::traverse() is a real no-op under the default
	# TRAVERSE_NONE (see osg/NodeVisitor:274-277), regardless of what apply() returns. None/True
	# from apply() only means "don't PRUNE" -- it doesn't override traversalMode.
	#
	# No __init__ override needed: Visitor doesn't define one, so it inherits the bound
	# NodeVisitor.__init__ directly, and traversalMode is a plain constructor kwarg on that.
	visited = []

	class Visitor(NodeVisitor):
		def apply(self, node):
			visited.append(node.name)
			# None/True (implicit here) means "don't prune" -- see the traversalMode note above for
			# why that alone isn't sufficient to reach the children.

	child = Node(name="child")
	root = Group(name="root", children=(child,))

	root.accept(Visitor(traversalMode=NodeVisitor.TraversalMode.TRAVERSE_ALL_CHILDREN))

	assert visited == ["root", "child"]

def test_apply_returning_false_prunes_children():
	# traversalMode=TRAVERSE_ALL_CHILDREN here too -- without it, this "passes" for the wrong
	# reason (TRAVERSE_NONE would never visit the child regardless of apply()'s return value, so it
	# wouldn't actually be exercising pruning at all).
	visited = []

	class Visitor(NodeVisitor):
		def apply(self, node):
			visited.append(node.name)

			return False # prune -- do not traverse this node's children

	child = Node(name="child")
	root = Group(name="root", children=(child,))

	root.accept(Visitor(traversalMode=NodeVisitor.TraversalMode.TRAVERSE_ALL_CHILDREN))

	assert visited == ["root"]
