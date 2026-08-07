#vimrun! pytest -sv ../test/osg_Geometry.py

import pytest

from OpenSceneGraph.osg import Array, Geometry, Vec2Array, Vec3Array, DrawArrays, PrimitiveSet, Vec3


def test_construction_kwargs():
	# `vertexArray`/`colorArray`/`normalArray` share the same `GeometrySlots::setter` functor as
	# the identically-named properties below -- exercising them via the constructor here, not
	# just `g.vertexArray = ...` afterward.
	va = Vec3Array([Vec3(0, 0, 0), Vec3(1, 0, 0), Vec3(0, 1, 0)])
	ca = Vec3Array([Vec3(1, 1, 1)])
	na = Vec3Array([Vec3(0, 0, 1)])
	ps0 = DrawArrays(PrimitiveSet.TRIANGLES, 0, 3)

	g = Geometry(vertexArray=va, colorArray=ca, normalArray=na, primitiveSets=(ps0,))

	assert g.vertexArray is va
	assert g.colorArray is ca
	assert g.normalArray is na
	assert len(g.primitiveSets) == 1
	assert g.primitiveSets[0] is ps0

def test_vertex_attrib_set_get_identity():
	g = Geometry()
	a = Vec3Array()

	assert len(g.vertexAttrib) == 0
	assert g.vertexAttrib.keys() == []

	g.vertexAttrib[0] = a

	assert g.vertexAttrib[0] is a
	assert len(g.vertexAttrib) == 1
	assert g.vertexAttrib.keys() == [0]
	assert 0 in g.vertexAttrib
	assert 1 not in g.vertexAttrib

def test_vertex_attrib_preserves_array_binding_and_normalize():
	g = Geometry()
	a = Vec2Array()

	a.binding = Array.Binding.BIND_PER_VERTEX
	a.normalize = True

	g.vertexAttrib[1] = a

	assert g.vertexAttrib[1] is a
	assert g.vertexAttrib[1].binding == Array.Binding.BIND_PER_VERTEX
	assert g.vertexAttrib[1].normalize == True

def test_vertex_attrib_del_and_key_error():
	g = Geometry()

	g.vertexAttrib[0] = Vec3Array()
	g.vertexAttrib[1] = Vec3Array()

	del g.vertexAttrib[0]

	assert len(g.vertexAttrib) == 1
	assert g.vertexAttrib.keys() == [1]
	assert 0 not in g.vertexAttrib

	with pytest.raises(KeyError):
		g.vertexAttrib[0]

def test_primitive_sets_append_get_iterate():
	g = Geometry()

	ps0 = DrawArrays(PrimitiveSet.TRIANGLES, 0, 3)
	ps1 = DrawArrays(PrimitiveSet.LINES, 0, 2)

	g.primitiveSets.append(ps0)
	g.primitiveSets.append(ps1)

	assert len(g.primitiveSets) == 2
	assert g.primitiveSets[0] is ps0
	assert g.primitiveSets[1] is ps1
	assert list(g.primitiveSets) == [ps0, ps1]

def test_primitive_sets_setitem_and_delitem():
	g = Geometry()

	g.primitiveSets.append(DrawArrays(PrimitiveSet.TRIANGLES, 0, 3))
	g.primitiveSets.append(DrawArrays(PrimitiveSet.LINES, 0, 2))

	replacement = DrawArrays(PrimitiveSet.POINTS, 0, 1)

	g.primitiveSets[0] = replacement

	assert g.primitiveSets[0] is replacement

	del g.primitiveSets[0]

	assert len(g.primitiveSets) == 1
	assert g.primitiveSets[0].mode == PrimitiveSet.LINES

def test_primitive_sets_insert():
	g = Geometry()

	ps0 = DrawArrays(PrimitiveSet.TRIANGLES, 0, 3)
	ps1 = DrawArrays(PrimitiveSet.LINES, 0, 2)
	ps2 = DrawArrays(PrimitiveSet.POINTS, 0, 1)

	g.primitiveSets.extend((ps0, ps2))
	g.primitiveSets.insert(1, ps1)

	assert list(g.primitiveSets) == [ps0, ps1, ps2]

	# Out-of-range indices clamp like list.insert(), rather than raising.
	front = DrawArrays(PrimitiveSet.QUADS, 0, 4)
	back = DrawArrays(PrimitiveSet.LINE_STRIP, 0, 2)

	g.primitiveSets.insert(-100, front)
	g.primitiveSets.insert(100, back)

	assert list(g.primitiveSets) == [front, ps0, ps1, ps2, back]

def test_geometry_has_no_add_primitive_set_method():
	# addPrimitiveSet() was removed once .primitiveSets (SequenceProxy) existed -- use
	# `.primitiveSets.append(...)` instead.
	assert not hasattr(Geometry(), "addPrimitiveSet")
