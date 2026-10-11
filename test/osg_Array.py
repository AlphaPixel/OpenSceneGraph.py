from .conftest import f32

import array

import numpy as np
import pytest

from OpenSceneGraph.osg import (
	Array, ByteArray, FloatArray, Vec2Array, Vec3, Vec3Array, Vec4Array,
)

# (class, matching numpy dtype, components per element, matching array.array typecode)
ARRAY_TYPES = (
	(ByteArray, np.int8, 1, "b"),
	(FloatArray, np.float32, 1, "f"),
	(Vec2Array, np.float32, 2, "f"),
	(Vec3Array, np.float32, 3, "f"),
	(Vec4Array, np.float32, 4, "f"),
)

def values(a, components):
	"""Read an osg Array back as nested Python lists via indexing (not the buffer protocol)."""

	if components == 1:
		return [a[i] for i in range(len(a))]

	return [list(a[i]) for i in range(len(a))]

def expected(data, components):
	"""The same nesting as values(), computed from the source data."""

	flat = np.asarray(data).ravel().tolist()

	if components == 1:
		return flat

	return [flat[i:i + components] for i in range(0, len(flat), components)]

# assert vec3f.x == pytest.approx(1.1)
# assert vec3f.y == f32(2.2)
# assert vec3f.z == f32(3.3)

def test_construction(vec3a):
	assert len(vec3a) == 8
	assert len(Vec3Array(5)) == 5

def test_access(vec3a):
	a = Vec3Array(3)

	a[0] = Vec3(1.1, 2.2, 3.3)

	assert a[0] == Vec3(1.1, 2.2, 3.3)

def test_iteration(vec3a):
	for i in range(8):
		assert vec3a[i] == Vec3(i, i, i)

def test_binding_default():
	a = Vec3Array()

	assert a.binding == Array.Binding.BIND_UNDEFINED
	assert a.normalize == False

def test_binding_roundtrip():
	a = Vec3Array()

	a.binding = Array.Binding.BIND_OVERALL
	a.normalize = True

	assert a.binding == Array.Binding.BIND_OVERALL
	assert a.normalize == True

	a.binding = Array.Binding.BIND_PER_VERTEX

	assert a.binding == Array.Binding.BIND_PER_VERTEX

@pytest.mark.parametrize("cls,dtype,components,typecode", ARRAY_TYPES)
def test_from_flat_buffer(cls, dtype, components, typecode):
	data = np.arange(4 * components, dtype=dtype)
	a = cls(data)

	assert len(a) == 4
	assert values(a, components) == expected(data, components)

@pytest.mark.parametrize("cls,dtype,components,typecode", ARRAY_TYPES)
def test_from_2d_buffer(cls, dtype, components, typecode):
	data = np.arange(4 * components, dtype=dtype).reshape(4, components)
	a = cls(data)

	assert len(a) == 4
	assert values(a, components) == expected(data, components)

@pytest.mark.parametrize("cls,dtype,components,typecode", ARRAY_TYPES)
def test_from_empty_buffer(cls, dtype, components, typecode):
	assert len(cls(np.zeros((0, components), dtype=dtype))) == 0

@pytest.mark.parametrize("cls,dtype,components,typecode", ARRAY_TYPES)
def test_from_array_module_buffer(cls, dtype, components, typecode):
	# The buffer ctor uses only the raw buffer protocol, so non-numpy producers work too.
	data = array.array(typecode, range(2 * components))
	a = cls(data)

	assert len(a) == 2
	assert values(a, components) == expected(data, components)

@pytest.mark.parametrize("cls,dtype,components,typecode", ARRAY_TYPES)
def test_wrong_dtype_raises(cls, dtype, components, typecode):
	wrong = np.float64 if dtype == np.float32 else np.float32

	with pytest.raises(TypeError):
		cls(np.zeros(components, dtype=wrong))

@pytest.mark.parametrize("cls,dtype,components,typecode", ARRAY_TYPES)
def test_non_contiguous_1d_raises(cls, dtype, components, typecode):
	with pytest.raises(ValueError):
		cls(np.arange(8 * components, dtype=dtype)[::2])

@pytest.mark.parametrize("cls,dtype,components,typecode", ARRAY_TYPES)
def test_non_contiguous_2d_raises(cls, dtype, components, typecode):
	# A column slice of a wider array: correct shape, but rows are strided.
	with pytest.raises(ValueError):
		cls(np.zeros((4, components + 1), dtype=dtype)[:, :components])

@pytest.mark.parametrize("cls,dtype,components,typecode", [t for t in ARRAY_TYPES if t[2] > 1])
def test_flat_not_divisible_raises(cls, dtype, components, typecode):
	with pytest.raises(ValueError):
		cls(np.zeros(components + 1, dtype=dtype))

@pytest.mark.parametrize("cls,dtype,components,typecode", [t for t in ARRAY_TYPES if t[2] > 1])
def test_wrong_last_dimension_raises(cls, dtype, components, typecode):
	with pytest.raises(ValueError):
		cls(np.zeros((2, components + 1), dtype=dtype))

@pytest.mark.parametrize("cls,dtype,components,typecode", ARRAY_TYPES)
def test_buffer_export_roundtrip(cls, dtype, components, typecode):
	data = np.arange(4 * components, dtype=dtype).reshape(4, components)
	view = np.asarray(cls(data))

	assert view.dtype == dtype
	assert view.shape == ((4,) if components == 1 else (4, components))
	assert view.ravel().tolist() == data.ravel().tolist()

@pytest.mark.parametrize("cls,dtype,components,typecode", ARRAY_TYPES)
def test_buffer_export_is_zero_copy(cls, dtype, components, typecode):
	a = cls(np.zeros((2, components), dtype=dtype))
	view = np.asarray(a)

	view.reshape(-1)[0] = 7

	assert values(a, components)[0] == (7 if components == 1 else [7] + [0] * (components - 1))

@pytest.mark.parametrize("cls,dtype,components,typecode", ARRAY_TYPES)
def test_buffer_export_empty(cls, dtype, components, typecode):
	assert np.asarray(cls()).size == 0

@pytest.mark.parametrize("cls,dtype,components,typecode", ARRAY_TYPES)
def test_buffer_export_memoryview(cls, dtype, components, typecode):
	# The raw buffer protocol, no numpy involved on the consuming side either.
	m = memoryview(cls(np.arange(2 * components, dtype=dtype)))

	assert m.format == typecode
	assert m.itemsize == np.dtype(dtype).itemsize

def test_from_sequence():
	assert values(FloatArray([1.5, 2.5]), 1) == [1.5, 2.5]
	assert values(ByteArray([1, -2, 3]), 1) == [1, -2, 3]
	assert values(Vec3Array([Vec3(1, 2, 3), Vec3(4, 5, 6)]), 3) == [[1, 2, 3], [4, 5, 6]]

# def test_math():
# 	a = Vec3d(1.0, 2.0, 3.0)
# 	b = Vec3d(4.0, 5.0, 6.0)
# 	n = Vec3d(3.0, 0.0, 0.0)
#
# 	assert a + b == Vec3d(5.0, 7.0, 9.0)
# 	assert a - b == Vec3d(-3.0, -3.0, -3.0)
# 	assert a * 2 == Vec3d(2.0, 4.0, 6.0)
# 	assert 2 * a == Vec3d(2.0, 4.0, 6.0)
# 	assert -a == Vec3d(-1.0, -2.0, -3.0)
# 	assert a.dot(b) == 32.0
# 	assert a.cross(b) == Vec3d(-3.0, 6.0, -3.0)
# 	assert n.length() == 3.0
# 	assert n.normalized() == Vec3d(1.0, 0.0, 0.0)
#
# 	n.normalize()
#
# 	assert n == Vec3d(1.0, 0.0, 0.0)
