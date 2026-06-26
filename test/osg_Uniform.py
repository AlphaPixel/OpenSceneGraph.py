#vimrun! pytest -sv ../test/osg_Uniform.py

import pytest

from .conftest import f32, floatif, refcmp

from OpenSceneGraph.osg import Uniform, Vec3f, Matrixf

def test_construction(uniform_init):
	for ty, val in uniform_init:
		u = Uniform(ty, "tmp")

		assert u.type == ty

		u.value = val

		assert u.value == val

def test_create_int():
	u = Uniform("x", 1)

	assert u.type == Uniform.Type.INT
	assert u.value == 1

def test_create_float():
	u = Uniform("x", 1.5)

	assert u.type == Uniform.Type.FLOAT
	assert pytest.approx(u.value) == 1.5

def test_create_bool():
	u = Uniform("x", True)
	assert u.type == Uniform.Type.BOOL
	assert u.value is True

def test_set_int_value():
	u = Uniform("x", 1)

	u.value = 42

	assert u.value == 42
	assert u.type == Uniform.Type.INT

def test_set_float_into_int_rejected():
	u = Uniform("x", 1)

	with pytest.raises(TypeError):
		u.value = 2.9

def test_set_int_into_float():
	u = Uniform("x", 1.5)
	u.value = 2

	assert pytest.approx(u.value) == 2.0
	assert u.type == Uniform.Type.FLOAT

def test_unsigned_basic():
	u = Uniform(Uniform.Type.UNSIGNED_INT, "u")

	u.value = 123

	assert u.value == 123

def test_unsigned_negative_rejected():
	u = Uniform(Uniform.Type.UNSIGNED_INT, "u")

	with pytest.raises(TypeError):
		u.value = -1

def test_array_set_get():
	u = Uniform(Uniform.Type.INT, "x", 3)

	u[0] = 1
	u[1] = 2
	u[2] = 3

	assert u[0] == 1
	assert u[1] == 2
	assert u[2] == 3

def test_array_len():
	u = Uniform(Uniform.Type.FLOAT, "x", 5)

	assert len(u) == 5

def test_iteration():
	u = Uniform(Uniform.Type.INT, "x", 3)

	u[0] = 10
	u[1] = 20
	u[2] = 30

	assert list(u) == [10, 20, 30]

def test_invalid_type_assignment():
	u = Uniform("x", 1)

	with pytest.raises(TypeError):
		u.value = "not a number"

def test_value_on_multi_element_rejected():
	u = Uniform(Uniform.Type.INT, "x", 2)

	with pytest.raises(ValueError):
		_ = u.value

	with pytest.raises(ValueError):
		u.value = 1

def test_array_init_from_tuple():
	from OpenSceneGraph.osg import Vec3f

	u = Uniform(Uniform.Type.FLOAT_VEC3, "colors", (Vec3f(1, 0, 0), Vec3f(0, 1, 0)))

	assert len(u) == 2
	assert u[0] == Vec3f(1, 0, 0)
	assert u[1] == Vec3f(0, 1, 0)

def test_array_init_from_list():
	from OpenSceneGraph.osg import Vec3f

	u = Uniform(Uniform.Type.FLOAT_VEC3, "colors", [Vec3f(1, 0, 0), Vec3f(0, 0, 1)])

	assert len(u) == 2
	assert u[0] == Vec3f(1, 0, 0)
	assert u[1] == Vec3f(0, 0, 1)

def test_array_init_empty_rejected():
	with pytest.raises((ValueError, TypeError)):
		Uniform(Uniform.Type.FLOAT_VEC3, "x", ())
