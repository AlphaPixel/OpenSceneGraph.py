#vimrun! pytest -sv ../test/osg_Shape.py

from OpenSceneGraph.osg import Box, ShapeDrawable, Sphere, TessellationHints, Vec3

def test_sphere_construction():
	s = Sphere()

	assert s.center == Vec3(0, 0, 0)
	assert s.radius == 1.0
	assert bool(s) == True

	s = Sphere(Vec3(1, 2, 3), 5.0)

	assert s.center == Vec3(1, 2, 3)
	assert s.radius == 5.0

	s = Sphere(2.5)

	assert s.center == Vec3(0, 0, 0)
	assert s.radius == 2.5

def test_box_construction():
	b = Box()

	assert b.center == Vec3(0, 0, 0)
	assert b.halfLengths == Vec3(0.5, 0.5, 0.5)
	assert bool(b) == True

	b = Box(Vec3(1, 1, 1), 2.0)

	assert b.center == Vec3(1, 1, 1)
	assert b.halfLengths == Vec3(1, 1, 1)

	b = Box(1.0, 2.0, 3.0)

	assert b.halfLengths == Vec3(0.5, 1.0, 1.5)

def test_tessellation_hints():
	th = TessellationHints()

	th.detailRatio = 2.0

	assert th.detailRatio == 2.0

def test_shapedrawable_construction():
	s = Sphere(2.5)
	th = TessellationHints()

	sd = ShapeDrawable(s, th)

	sd.build()

	assert sd.vertexArray is not None
	assert len(sd.vertexArray) > 0
