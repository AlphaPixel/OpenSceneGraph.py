#vimrun! pytest -sv ../test/osg_Geode.py

from .conftest import refcmp

from OpenSceneGraph.osg import Drawable, Geode

def test_construction():
	g = Geode(name="g0")
	d0 = Drawable(name="d0")
	d1 = Drawable(name="d1")

	g.drawables.extend((d0, d1))

	assert len(g.drawables) == 2
	assert refcmp(g, 1, 1)
	assert refcmp(d0, 2, 2)

	for d, c in zip((d0, d1), g.drawables):
		assert d is c

def test_construction_kwargs():
	g = Geode(name="g", drawables=(
		Drawable(name="foo"),
		Drawable(name="bar")
	))

	assert len(g.drawables) == 2
	assert refcmp(g, 1, 1)
	assert g.drawables[0].name == "foo"
	assert g.drawables[1].name == "bar"

def test_destruction():
	deleted = []
	dbg = lambda addr, cls, name: deleted.append(name)

	g = Geode(name="g", debug=dbg, drawables=(
		Drawable(name="foo", debug=dbg),
		Drawable(name="bar", debug=dbg)
	))

	del g

	assert deleted == ["foo", "bar", "g"]
