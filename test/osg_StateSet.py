#vimrun! pytest -sv ../test/osg_StateSet.py

# from .conftest import f32, floatif, refcmp

import pytest

from OpenSceneGraph.osg import StateSet, StateAttribute, Program, Texture2D, Uniform, Vec3f, Matrixf

def test_uniforms_append(uniform_init):
	ss = StateSet()

	for ty, val in uniform_init:
		u = Uniform(ty, str(ty).split(".")[-1])

		u.value = val

		ss.uniforms.append(u)

	assert len(ss.uniforms) == len(uniform_init)

def test_uniforms_extend(uniform_init):
	ss = StateSet()

	# Let the values stay at whatever the DEFAULTS are.
	ss.uniforms.extend(Uniform(ty, str(ty).split(".")[-1]) for ty, val in uniform_init)

	assert ss.uniforms["BOOL"].value == False
	assert ss.uniforms["INT"].value == 0
	assert ss.uniforms["FLOAT_VEC3"].value == Vec3f()

def test_uniform_mutation():
	ss = StateSet()

	ss.uniforms["float"] = 1.2

	addr = ss.uniforms["float"].addr

	assert ss.uniforms["float"].value == pytest.approx(1.2)

	ss.uniforms["float"] = 3.4

	assert ss.uniforms["float"].value == pytest.approx(3.4)
	assert ss.uniforms["float"].addr == addr

	ss.uniforms["double"] = (Uniform.DOUBLE, 56.78)

	assert ss.uniforms["double"].value == 56.78
	assert len(ss.uniforms) == 2

def test_uniforms_array_tuple_assignment():
	ss = StateSet()

	ss.uniforms["lights"] = (Vec3f(1, 0, 0), Vec3f(0, 1, 0))

	u = ss.uniforms["lights"]

	assert len(u) == 2
	assert u[0] == Vec3f(1, 0, 0)
	assert u[1] == Vec3f(0, 1, 0)

def test_uniforms_array_tuple_three():
	ss = StateSet()

	ss.uniforms["pts"] = (Vec3f(1, 0, 0), Vec3f(0, 1, 0), Vec3f(0, 0, 1))

	u = ss.uniforms["pts"]

	assert len(u) == 3
	assert u[2] == Vec3f(0, 0, 1)

def test_texture_attributes_mapping():
	ss = StateSet()
	t0 = Texture2D()
	t1 = Texture2D()

	ss.textureAttributes[0] = t0
	ss.textureAttributes[1] = (t1, StateAttribute.ON)

	assert ss.textureAttributes[0] is t0
	assert ss.textureAttributes[1] is t1
	assert len(ss.textureAttributes) == 2
	assert ss.textureAttributes.keys() == [0, 1]
	assert 0 in ss.textureAttributes
	assert 2 not in ss.textureAttributes

	ss.uniforms["u"] = 1.0

	assert ss.uniforms["u"].value == pytest.approx(1.0)

	del ss.textureAttributes[0]

	assert len(ss.textureAttributes) == 1
	assert ss.textureAttributes.keys() == [1]
	assert 0 not in ss.textureAttributes

def test_attributes_mapping():
	ss = StateSet()
	p = Program(name="p")

	# The subscript key is the attribute's OWN `StateAttribute::Type` -- it's not inferred, so
	# it must be repeated even though `p` already knows its own type.
	ss.attributes[StateAttribute.PROGRAM] = p

	assert ss.attributes[StateAttribute.PROGRAM] is p
	assert len(ss.attributes) == 1
	assert ss.attributes.keys() == [StateAttribute.PROGRAM]
	assert StateAttribute.PROGRAM in ss.attributes
	assert StateAttribute.TEXTURE not in ss.attributes

	del ss.attributes[StateAttribute.PROGRAM]

	assert len(ss.attributes) == 0
	assert StateAttribute.PROGRAM not in ss.attributes

def test_attributes_tuple_mode():
	ss = StateSet()
	p = Program(name="p")

	ss.attributes[StateAttribute.PROGRAM] = (p, StateAttribute.OVERRIDE)

	assert ss.attributes[StateAttribute.PROGRAM] is p

def test_attributes_append_infers_key():
	ss = StateSet()
	p = Program(name="p")

	# append()/extend() read the key from `p.type` -- this is the syntax that sidesteps having
	# to name `StateAttribute.PROGRAM` a second time.
	ss.attributes.append(p)

	assert ss.attributes[StateAttribute.PROGRAM] is p
	assert len(ss.attributes) == 1

def test_attributes_key_type_mismatch():
	ss = StateSet()
	p = Program(name="p")

	with pytest.raises(ValueError):
		ss.attributes[StateAttribute.TEXTURE] = p
