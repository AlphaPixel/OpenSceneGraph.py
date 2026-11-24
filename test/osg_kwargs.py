import pytest

from OpenSceneGraph.osg import (
	Drawable,
	Group,
	Matrixd,
	MatrixTransform,
	Node,
	Object,
	Texture2D,
	Transform,
	Uniform
)

# pybind11x::kwargs_init() walks a type's kwargs_base chain, each kwargs_init_own<T> consuming the
# keys it understands; any key still unconsumed at the end raises TypeError with Python's own
# wording, instead of being silently ignored.

def test_unknown_keyword_raises():
	with pytest.raises(TypeError, match=r"^Node\(\) got an unexpected keyword argument 'nodeMsk'$"):
		Node(nodeMsk=1)

def test_unknown_keywords_all_listed():
	with pytest.raises(
		TypeError,
		match=r"^Group\(\) got unexpected keyword arguments 'bogus', 'nodeMsk'$"
	):
		Group(name="g", bogus=1, nodeMsk=2)

def test_keys_from_every_base_are_consumed():
	child = Node()

	mt = MatrixTransform(
		name="mt", # Object
		nodeMask=0x2, # Node
		children=[child], # Group
		referenceFrame=Transform.ABSOLUTE_RF, # Transform
		matrix=Matrixd.translate(1.0, 2.0, 3.0) # MatrixTransform
	)

	assert mt.name == "mt"
	assert mt.nodeMask == 0x2
	assert mt.children[0] is child
	assert mt.referenceFrame == Transform.ABSOLUTE_RF
	assert mt.matrix[3, 2] == 3.0

def test_sibling_class_keys_are_rejected():
	# `matrix` belongs to MatrixTransform, which is not in Group's chain.
	with pytest.raises(TypeError, match="'matrix'"):
		Group(matrix=Matrixd.identity())

def test_explicit_none_is_consumed():
	# An explicit None is a real value (it clears the callback), not an absent key.
	n = Node(updateCallback=None)

	assert n.updateCallback is None

def test_python_subclass_rejects_unknown():
	class MyNode(Node):
		pass

	assert MyNode(name="ok").name == "ok"

	with pytest.raises(TypeError, match="unexpected keyword argument 'nmae'"):
		MyNode(nmae="typo")

def test_python_subclass_init_forwarding():
	class Labeled(Group):
		def __init__(self, label, **kwargs):
			super().__init__(**kwargs)

			self.label = label

	g = Labeled("L", name="g", nodeMask=0x4)

	assert (g.label, g.name, g.nodeMask) == ("L", "g", 0x4)

	with pytest.raises(TypeError, match="'bogus'"):
		Labeled("L", bogus=1)

def test_drawable_alias_factory_rejects_unknown():
	# A Python subclass of Drawable goes through the trampoline (alias) factory, which calls
	# kwargs_init() separately from the plain-Drawable factory.
	class MyDrawable(Drawable):
		pass

	d = MyDrawable(name="d", useVertexBufferObjects=True)

	assert d.name == "d"

	with pytest.raises(TypeError, match="'useVBOs'"):
		MyDrawable(useVBOs=True)

def test_direct_kwargs_init_call_sites_reject_unknown():
	# Object and Uniform build their objects by hand and call kwargs_init() directly, rather
	# than going through kwargs_ctor().
	assert Object(name="o").name == "o"

	with pytest.raises(TypeError, match=r"^Object\(\) got an unexpected keyword argument 'nmae'$"):
		Object(nmae="o")

	with pytest.raises(TypeError, match=r"^Uniform\(\)"):
		Uniform(Uniform.FLOAT, "u", [1.0, 2.0], bogus=1)

def test_texture_keys_still_apply():
	t = Texture2D(size=(4, 8), numMipmapLevels=3, name="t")

	assert t.name == "t"

	with pytest.raises(TypeError, match="'mipmapLevels'"):
		Texture2D(mipmapLevels=3)

def test_wrong_value_type_names_the_keyword():
	# kwargs_consumer::pop<T>() turns pybind11's RuntimeError cast failure into a TypeError naming
	# the constructed class, the keyword, the value's type and the target type.
	with pytest.raises(
		TypeError,
		match=r"^Node\(\) keyword argument 'nodeMask' got str, which can't be converted to unsigned int$"
	):
		Node(nodeMask="x")

def test_wrong_value_type_uses_bound_class_names():
	# A bound target type is reported by its Python name, not its C++ one (osg::Matrixd).
	with pytest.raises(
		TypeError,
		match=(
			r"^MatrixTransform\(\) keyword argument 'matrix' got Node, "
			r"which can't be converted to Matrixd$"
		)
	):
		MatrixTransform(matrix=Node())

def test_wrong_value_type_reported_by_the_class_being_built():
	# `name` is consumed by Object's kwargs_init_own, but the message names the class actually
	# being constructed.
	with pytest.raises(TypeError, match=r"^Group\(\) keyword argument 'name' got int"):
		Group(name=5)
