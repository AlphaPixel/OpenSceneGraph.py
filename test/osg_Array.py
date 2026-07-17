#vimrun! pytest -sv ../test/osg_Array.py

from .conftest import f32

import pytest

from OpenSceneGraph.osg import Array, Vec3, Vec3Array

# assert vec3f.x == pytest.approx(1.1)
# assert vec3f.y == f32(2.2)
# assert vec3f.z == f32(3.3)

def test_construction(vec3a):
	assert len(vec3a) == 8
	assert len(Vec3Array(5)) == 5

def test_access(vec3a):
	a = Vec3Array(3)

	a[0] = Vec3(1.1, 2.2, 3.3)

	assert a[0] == Vec3(1.1, 2.2, 3.3)

def test_iteration(vec3a):
	for i in range(8):
		assert vec3a[i] == Vec3(i, i, i)

def test_binding_default():
	a = Vec3Array()

	assert a.binding == Array.Binding.BIND_UNDEFINED
	assert a.normalize == False

def test_binding_roundtrip():
	a = Vec3Array()

	a.binding = Array.Binding.BIND_OVERALL
	a.normalize = True

	assert a.binding == Array.Binding.BIND_OVERALL
	assert a.normalize == True

	a.binding = Array.Binding.BIND_PER_VERTEX

	assert a.binding == Array.Binding.BIND_PER_VERTEX

# def test_math():
# 	a = Vec3d(1.0, 2.0, 3.0)
# 	b = Vec3d(4.0, 5.0, 6.0)
# 	n = Vec3d(3.0, 0.0, 0.0)
#
# 	assert a + b == Vec3d(5.0, 7.0, 9.0)
# 	assert a - b == Vec3d(-3.0, -3.0, -3.0)
# 	assert a * 2 == Vec3d(2.0, 4.0, 6.0)
# 	assert 2 * a == Vec3d(2.0, 4.0, 6.0)
# 	assert -a == Vec3d(-1.0, -2.0, -3.0)
# 	assert a.dot(b) == 32.0
# 	assert a.cross(b) == Vec3d(-3.0, 6.0, -3.0)
# 	assert n.length() == 3.0
# 	assert n.normalized() == Vec3d(1.0, 0.0, 0.0)
#
# 	n.normalize()
#
# 	assert n == Vec3d(1.0, 0.0, 0.0)
