import pytest

from OpenSceneGraph.osg import (
	BoundingBox,
	BoundingSphere,
	Matrix,
	Plane,
	Vec3,
	Vec3d,
	Vec4d,
	Vec4f,
)

def test_construction_default():
	p = Plane()

	assert list(p) == [0, 0, 0, 0]
	assert p.valid()
	assert not p.isNaN()

def test_construction_coefficients():
	p = Plane(1.0, 0.0, 0.0, -5.0)

	assert p[0] == 1.0
	assert p[1] == 0.0
	assert p[2] == 0.0
	assert p[3] == -5.0
	assert p.normal == Vec3d(1.0, 0.0, 0.0)

def test_construction_from_vec4():
	pf = Plane(Vec4f(1.0, 0.0, 0.0, -5.0))
	pd = Plane(Vec4d(1.0, 0.0, 0.0, -5.0))

	assert pf == pd

def test_construction_from_normal_and_distance():
	n = Vec3d(0.0, 1.0, 0.0)
	p = Plane(n, -2.0)

	assert p.normal == n
	assert p[3] == -2.0

def test_construction_from_three_points():
	v1 = Vec3d(0.0, 0.0, 0.0)
	v2 = Vec3d(1.0, 0.0, 0.0)
	v3 = Vec3d(0.0, 1.0, 0.0)
	p = Plane(v1, v2, v3)

	assert p.normal == Vec3d(0.0, 0.0, 1.0)

def test_construction_from_normal_and_point():
	n = Vec3d(0.0, 0.0, 1.0)
	pt = Vec3d(0.0, 0.0, 5.0)
	p = Plane(n, pt)

	assert p.distance(pt) == pytest.approx(0.0)

def test_equality():
	p1 = Plane(1.0, 2.0, 3.0, 4.0)
	p2 = Plane(1.0, 2.0, 3.0, 4.0)
	p3 = Plane(0.0, 0.0, 0.0, 0.0)

	assert p1 == p2
	assert p1 != p3

def test_set():
	p = Plane()

	p.set(1.0, 2.0, 3.0, 4.0)

	assert list(p) == [1.0, 2.0, 3.0, 4.0]

	p.set(Plane(5.0, 6.0, 7.0, 8.0))

	assert list(p) == [5.0, 6.0, 7.0, 8.0]

	p.set(Vec4f(1.0, 1.0, 1.0, 1.0))

	assert list(p) == pytest.approx([1.0, 1.0, 1.0, 1.0])

	p.set(Vec4d(2.0, 2.0, 2.0, 2.0))

	assert list(p) == [2.0, 2.0, 2.0, 2.0]

	p.set(Vec3d(0.0, 0.0, 1.0), -3.0)

	assert p.normal == Vec3d(0.0, 0.0, 1.0)
	assert p[3] == -3.0

	p.set(Vec3d(0.0, 0.0, 0.0), Vec3d(1.0, 0.0, 0.0), Vec3d(0.0, 1.0, 0.0))

	assert p.normal == Vec3d(0.0, 0.0, 1.0)

	p.set(Vec3d(0.0, 0.0, 1.0), Vec3d(0.0, 0.0, 5.0))

	assert p.distance(Vec3d(0.0, 0.0, 5.0)) == pytest.approx(0.0)

def test_flip():
	p = Plane(1.0, 2.0, 3.0, 4.0)

	p.flip()

	assert list(p) == [-1.0, -2.0, -3.0, -4.0]

def test_make_unit_length():
	p = Plane(3.0, 4.0, 0.0, 10.0)

	p.makeUnitLength()

	assert p[0] == pytest.approx(0.6)
	assert p[1] == pytest.approx(0.8)
	assert p[2] == pytest.approx(0.0)
	assert p[3] == pytest.approx(2.0)
	assert p.normal.length() == pytest.approx(1.0)

def test_valid_and_nan():
	p = Plane()

	assert p.valid()
	assert not p.isNaN()

	p = Plane(float("nan"), 0.0, 0.0, 0.0)

	assert p.isNaN()
	assert not p.valid()

def test_as_vec4():
	p = Plane(1.0, 2.0, 3.0, 4.0)
	v = p.asVec4()

	assert (v.x, v.y, v.z, v.w) == (1.0, 2.0, 3.0, 4.0)

def test_distance_and_dot_product_normal():
	p = Plane(0.0, 0.0, 1.0, 0.0)

	assert p.distance(Vec3(0.0, 0.0, 5.0)) == pytest.approx(5.0)
	assert p.distance(Vec3d(0.0, 0.0, -3.0)) == pytest.approx(-3.0)
	assert p.dotProductNormal(Vec3(1.0, 2.0, 3.0)) == pytest.approx(3.0)
	assert p.dotProductNormal(Vec3d(1.0, 2.0, 3.0)) == pytest.approx(3.0)

def test_intersect_point_lists():
	p = Plane(0.0, 0.0, 1.0, 0.0)

	above = [Vec3(0.0, 0.0, 1.0), Vec3(1.0, 1.0, 2.0)]
	below = [Vec3(0.0, 0.0, -1.0)]
	mixed = [Vec3(0.0, 0.0, 1.0), Vec3(0.0, 0.0, -1.0)]

	assert p.intersect(above) == 1
	assert p.intersect(below) == -1
	assert p.intersect(mixed) == 0

	above_d = [Vec3d(0.0, 0.0, 1.0), Vec3d(1.0, 1.0, 2.0)]
	below_d = [Vec3d(0.0, 0.0, -1.0)]

	assert p.intersect(above_d) == 1
	assert p.intersect(below_d) == -1

def test_intersect_bounding_sphere():
	p = Plane(0.0, 0.0, 1.0, 0.0)

	assert p.intersect(BoundingSphere(Vec3(0.0, 0.0, 5.0), 1.0)) == 1
	assert p.intersect(BoundingSphere(Vec3(0.0, 0.0, -5.0), 1.0)) == -1
	assert p.intersect(BoundingSphere(Vec3(0.0, 0.0, 0.0), 1.0)) == 0

def test_intersect_bounding_box():
	p = Plane(0.0, 0.0, 1.0, 0.0)

	above = BoundingBox(Vec3(-1.0, -1.0, 1.0), Vec3(1.0, 1.0, 2.0))
	below = BoundingBox(Vec3(-1.0, -1.0, -2.0), Vec3(1.0, 1.0, -1.0))
	straddle = BoundingBox(Vec3(-1.0, -1.0, -1.0), Vec3(1.0, 1.0, 1.0))

	assert p.intersect(above) == 1
	assert p.intersect(below) == -1
	assert p.intersect(straddle) == 0

def test_transform():
	p = Plane(0.0, 0.0, 1.0, 0.0)

	p.transform(Matrix.translate(0.0, 0.0, 5.0))

	assert p.distance(Vec3d(0.0, 0.0, 5.0)) == pytest.approx(0.0, abs=1e-6)
	assert p.distance(Vec3d(0.0, 0.0, 0.0)) < 0.0

def test_transform_providing_inverse():
	p = Plane(0.0, 0.0, 1.0, 0.0)
	m = Matrix.translate(0.0, 0.0, 5.0)

	p.transformProvidingInverse(Matrix.inverse(m))

	assert p.distance(Vec3d(0.0, 0.0, 5.0)) == pytest.approx(0.0, abs=1e-6)

def test_indexing_and_iteration():
	p = Plane(1.0, 2.0, 3.0, 4.0)

	assert len(p) == 4
	assert p[0] == 1.0
	assert p[-1] == 4.0
	assert p[-4] == 1.0

	p[0] = 9.0

	assert p[0] == 9.0
	assert list(p) == [9.0, 2.0, 3.0, 4.0]

	with pytest.raises(IndexError):
		p[4]

def test_repr():
	p = Plane(1.0, 2.0, 3.0, 4.0)

	assert repr(p).startswith("Plane(")
