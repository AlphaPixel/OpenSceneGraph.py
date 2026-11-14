from .conftest import refcmp

import pytest

from OpenSceneGraph.osg import BoundingBox, DispatchCompute, Drawable, Vec3f

def test_construction():
	d = Drawable()

	assert refcmp(d, 1, 1)

def test_construction_kwargs():
	# `initialBound`/`useVertexBufferObjects`/`useVertexArrayObject` are handled by
	# `kwargs_init_own<osg::Drawable>()`. This exercises that path directly (a bare `Drawable`),
	# not just through a subclass like `Geometry` whose `kwargs_base` chain happens to reach it.
	bb = BoundingBox(0, 0, 0, 1, 1, 1)

	d = Drawable(
		initialBound=bb,
		useVertexBufferObjects=True,
		useVertexArrayObject=False
	)

	assert d.initialBound.center == bb.center
	assert d.useVertexBufferObjects == True
	assert d.useVertexArrayObject == False

def test_destruction():
	deleted = []

	d = Drawable(debug=lambda addr, cls, name: deleted.append(addr))
	addr = d.addr

	assert refcmp(d, 1, 1)

	del d

	assert deleted[-1] == addr

def test_inheritance():
	class MyDrawable(Drawable):
		def computeBoundingBox(self):
			return BoundingBox(-1, -1, -1, 1, 1, 1)

	d = MyDrawable(name="foo")

	assert d.name == "foo"
	assert refcmp(d, 1, 1)
	assert d.computeBoundingBox().center == Vec3f(0, 0, 0)

def test_drawcallback():
	calls = []

	d = Drawable()

	d.drawCallback = lambda ri, drawable: calls.append(drawable)

	assert d.drawCallback is not None

	d.drawCallback = None

	assert d.drawCallback is None

def test_dispatchcompute():
	d = DispatchCompute()

	assert isinstance(d, Drawable)
	assert d.computeGroups == (0, 0, 0)

	d = DispatchCompute(8, 4, 1)

	assert d.computeGroups == (8, 4, 1)

	d.computeGroups = (2, 3, 4)

	assert d.computeGroups == (2, 3, 4)

	with pytest.raises(ValueError):
		d.computeGroups = (2, 3)
