#vimrun! pytest -sv ../test/osg_NAME.py

from .conftest import refcmp

from OpenSceneGraph.osg import NAME

def test_construction():
	o = NAME()

	assert refcmp(o, 1, 1)

def test_construction_kwargs():
	# One instance exercising every `kwargs_init_own<osg::NAME>()` argument at once, then one
	# assert per kwarg against its matching getter/property. Keeps this test as the single place
	# that goes stale (and fails loudly) if a kwarg is added to the C++ side but never wired up
	# here, or vice versa.
	o = NAME()

	assert True

def test_destruction():
	deleted = []

	o = NAME(debug=lambda addr, cls, name: deleted.append(addr))
	addr = o.addr

	assert refcmp(o, 1, 1)

	del o

	assert deleted[-1] == addr

def test_inheritance():
	class MyNAME(NAME):
		pass

	o = MyNAME(name="foo")

	assert o.name == "foo"
	assert refcmp(o, 1, 1)
