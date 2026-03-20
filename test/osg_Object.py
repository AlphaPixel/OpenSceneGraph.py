#vimrun! pytest -v ../test/osg_Object.py

from .conftest import refcmp

from OpenSceneGraph.osg import Object

class MyObject(Object):
	pass

def test_construction():
	o = Object(name="foo")

	assert o.name == "foo"
	assert refcmp(o, 1, 1)

	o0 = o
	o1 = o

	assert refcmp(o, 1, 3)

def test_destruction(capsys):
	o = Object(name="bar")

	o.debug_del = True

	del o

	assert capsys.readouterr() == "debug_del"

def test_inheritance():
	o = MyObject(name="foo", dataVariance=Object.DYNAMIC)

	assert o.name == "foo"
	assert o.dataVariance == Object.DYNAMIC
	assert refcmp(o, 1, 1)

def test_userdata():
	o = Object()
	d = Object(name="DATA")

	o.userData = d

	assert o.userData.name == "DATA"
	assert refcmp(o, 1, 1)
	assert refcmp(d, 2, 1)
