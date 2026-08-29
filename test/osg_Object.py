from .conftest import refcmp

from OpenSceneGraph.osg import Object

import gc

def test_construction():
	o = Object(name="foo")

	assert o.name == "foo"
	assert refcmp(o, 1, 1)

	o0 = o
	o1 = o

	assert refcmp(o, 1, 3)

def test_destruction():
	deleted = []

	o = Object(name="bar", debug=lambda *a: deleted.append(True))

	del o

	gc.collect()

	assert deleted[0] == True

def test_inheritance():
	class MyObject(Object):
		pass

	o = MyObject(name="foo", dataVariance=Object.DYNAMIC)

	assert o.dataVariance == Object.DYNAMIC
	assert refcmp(o, 1, 1)

def test_userdata():
	o = Object()
	d = Object(name="DATA")

	o.userData = d

	assert o.userData.name == "DATA"
	assert refcmp(o, 1, 1)
	assert refcmp(d, 2, 1)
