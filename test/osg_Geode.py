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

def test_drawables_insert():
	# Geode has no native insert-at-position primitive (only addDrawable/removeDrawables), so
	# this exercises SequenceProxy's del()+append() emulation fallback, not a native traits
	# insert() like Group.children/Geometry.primitiveSets/View.eventHandlers get.
	g = Geode(name="g")
	d0 = Drawable(name="d0")
	d1 = Drawable(name="d1")
	d2 = Drawable(name="d2")

	g.drawables.extend((d0, d2))
	g.drawables.insert(1, d1)

	assert list(g.drawables) == [d0, d1, d2]
	# Identity through the remove/re-add round trip -- not just equal drawables, the SAME
	# cached wrapper objects.
	assert g.drawables[0] is d0
	assert g.drawables[2] is d2

	front = Drawable(name="front")

	g.drawables.insert(-100, front)

	assert list(g.drawables) == [front, d0, d1, d2]

def test_drawables_insert_does_not_prematurely_destroy():
	# The emulation fallback (del()+append() rotation) temporarily removes everything from `i`
	# onward from the C++ container mid-insert(). No local Python variables are kept here on
	# purpose -- the only things that can keep a Drawable alive during that window are the
	# proxy's SlotCache and (briefly) the C++ container itself. If either dropped its reference
	# at the wrong moment, `deleted` would show entries appearing before clear() runs.
	deleted = []
	dbg = lambda addr, cls, name: deleted.append(name)

	g = Geode(name="g")

	g.drawables.append(Drawable(name="d0", debug=dbg))
	g.drawables.append(Drawable(name="d2", debug=dbg))
	g.drawables.insert(1, Drawable(name="d1", debug=dbg))

	assert deleted == []
	assert [d.name for d in g.drawables] == ["d0", "d1", "d2"]

	g.drawables.clear()

	assert sorted(deleted) == ["d0", "d1", "d2"]

def test_destruction():
	deleted = []
	dbg = lambda addr, cls, name: deleted.append(name)

	g = Geode(name="g", debug=dbg, drawables=(
		Drawable(name="foo", debug=dbg),
		Drawable(name="bar", debug=dbg)
	))

	del g

	assert deleted == ["foo", "bar", "g"]
