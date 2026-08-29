from .conftest import f32

import pytest

from OpenSceneGraph.osg import Vec3, Vec3f, Vec3d

def test_construction(vec3f):
	assert vec3f.x == pytest.approx(1.1)
	assert vec3f.y == f32(2.2)
	assert vec3f.z == f32(3.3)

def test_access(vec3d):
	vec3d.x = 10.005

	assert vec3d.x == 10.005
	assert len(vec3d) == 3

def test_iteration(vec3d):
	assert sum(vec3d) == 1.1 + 2.2 + 3.3

def test_math():
	a = Vec3d(1.0, 2.0, 3.0)
	b = Vec3d(4.0, 5.0, 6.0)
	n = Vec3d(3.0, 0.0, 0.0)

	assert a + b == Vec3d(5.0, 7.0, 9.0)
	assert a - b == Vec3d(-3.0, -3.0, -3.0)
	assert a * 2 == Vec3d(2.0, 4.0, 6.0)
	assert 2 * a == Vec3d(2.0, 4.0, 6.0)
	assert -a == Vec3d(-1.0, -2.0, -3.0)
	assert a.dot(b) == 32.0
	assert a.cross(b) == Vec3d(-3.0, 6.0, -3.0)
	assert n.length() == 3.0
	assert n.normalized() == Vec3d(1.0, 0.0, 0.0)

	n.normalize()

	assert n == Vec3d(1.0, 0.0, 0.0)
