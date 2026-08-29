from .conftest import f32

import pytest
import math

from OpenSceneGraph.osg import Vec3, Vec3f, Vec3d, Quat

def test_construction():
	q = Quat()

	assert q.x == 0
	assert q.y == 0
	assert q.z == 0
	assert q.w == 1

	assert q.length() == 1.0
	assert q.zeroRotation

def test_access():
	q = Quat()

	q[0] = 1.1
	q[1] = 2.2
	q[2] = 3.3
	q[3] = 4.4

	assert q.x == 1.1
	assert q.y == 2.2
	assert q.z == 3.3
	assert q.w == 4.4

	assert q[-1] == 4.4
	assert q[-2] == 3.3
	assert q[-3] == 2.2
	assert q[-4] == 1.1

def test_length():
	q = Quat()

	q.x = 1
	q.y = 2
	q.z = 3
	q.w = 4

	l2 = q.length2()
	l = q.length()

	assert abs(l * l - l2) < 1e-6

def test_rotation():
	q = Quat(math.pi / 2, Vec3f(0, 0, 1))  # 90° around Z

	v = Vec3f(1, 0, 0)
	r = q * v

	assert abs(r.x) < 1e-5
	assert abs(r.y - 1) < 1e-5
	assert abs(r.z) < 1e-5
