#vimrun! pytest -sv ../test/osg_StateSet.py

# from .conftest import f32, floatif, refcmp

import pytest

from OpenSceneGraph.osg import StateSet, StateAttribute, Texture2D, Uniform, Vec3f, Matrixf

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
