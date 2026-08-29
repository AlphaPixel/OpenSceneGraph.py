import pytest

from .conftest import f32, floatif, refcmp

from OpenSceneGraph.osg import StateSet, Uniform, Vec3f, Matrixf


def test_kwargs_init_debug_and_name():
	# Uniform's constructor used to bypass kwargs_init entirely (~20 raw py::init<...>
	# overloads) -- debug=/name=/etc. failed with a pybind11 "incompatible constructor
	# arguments" error on every overload. Fixed by routing them all through
	# pyx::kwargs_ctor<osg::Uniform, ...>() (kwargs_base<osg::Uniform> -> osg::Object in
	# pyosg.hpp), except the copy constructor, which deliberately stays kwargs-free (see
	# below). Cover a representative spread of overloads, not all ~19.
	deleted = []
	dbg = lambda addr, cls, name: deleted.append(name)

	u0 = Uniform(Uniform.Type.FLOAT, "u0", debug=dbg)  # (type, name, numElements=1) overload
	u1 = Uniform("u1", 1.5, debug=dbg)  # (name, value) overload
	u2 = Uniform(Uniform.Type.FLOAT_VEC3, "u2", (Vec3f(1, 0, 0), Vec3f(0, 1, 0)), debug=dbg)  # (type, name, elements)
	u3 = Uniform(debug=dbg, name="renamed")  # default ctor, name= override via kwargs_init

	assert u0.name == "u0"
	assert u1.name == "u1" and pytest.approx(u1.value) == 1.5
	assert len(u2) == 2
	assert u3.name == "renamed"

	del u0, u1, u2, u3

	assert sorted(deleted) == ["renamed", "u0", "u1", "u2"]

def test_copy_constructor_rejects_kwargs():
	# Deliberate: a copy already fully initializes every field from the source object, so
	# debug=/name= on TOP of a copy would mean overriding specific post-copy fields -- a
	# different feature from what kwargs_ctor provides, matching the same convention already
	# established for MatrixTransform/PositionAttitudeTransform's copy constructors.
	src = Uniform("x", 1)

	with pytest.raises(TypeError):
		Uniform(src, debug=lambda *a: None)

def test_uniform_mapping_update():
	ss = StateSet()

	ss.uniforms.update({"integer": 7}, floating=1.5)
	ss.uniforms.update((("color", Vec3f(1, 2, 3)),))

	assert ss.uniforms["integer"].value == 7
	assert ss.uniforms["floating"].value == pytest.approx(1.5)
	assert ss.uniforms["color"].value == Vec3f(1, 2, 3)

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
