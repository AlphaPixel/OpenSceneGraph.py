import pytest
import numpy as np

from OpenSceneGraph.osg import Image
from OpenSceneGraph.GL import GL_RED, GL_RGB, GL_RGBA, GL_FLOAT, GL_UNSIGNED_BYTE, GL_HALF_FLOAT

def test_default_construction():
	img = Image()

	assert img.s == 0
	assert img.t == 0
	assert img.r == 0
	assert img.valid is False
	assert img.fileName == ""

def test_allocate_rgba_float():
	img = Image()
	img.allocateImage(4, 3, 1, GL_RGBA, GL_FLOAT)

	assert img.s == 4
	assert img.t == 3
	assert img.r == 1
	assert img.valid is True
	assert img.pixelFormat == GL_RGBA
	assert img.dataType == GL_FLOAT

def test_allocate_rgb_unsigned_byte():
	img = Image()
	img.allocateImage(8, 6, 1, GL_RGB, GL_UNSIGNED_BYTE)

	assert img.pixelFormat == GL_RGB
	assert img.dataType == GL_UNSIGNED_BYTE

def test_origin_enum():
	assert Image.Origin.BOTTOM_LEFT != Image.Origin.TOP_LEFT

def test_buffer_shape_rgba_float():
	img = Image()
	img.allocateImage(4, 3, 1, GL_RGBA, GL_FLOAT)

	arr = np.asarray(img)

	assert arr.shape == (3, 4, 4)
	assert arr.dtype == np.float32

def test_buffer_shape_single_channel():
	# Single-component formats (GL_RED here) collapse to a 2D (t, s) buffer,
	# with no trailing components axis.
	img = Image()
	img.allocateImage(5, 2, 1, GL_RED, GL_UNSIGNED_BYTE)

	arr = np.asarray(img)

	assert arr.shape == (2, 5)
	assert arr.dtype == np.uint8

def test_buffer_shape_half_float():
	# GL_HALF_FLOAT has no native C++ type; the binding hand-writes the "e"
	# format code, which numpy maps to float16.
	img = Image()
	img.allocateImage(2, 2, 1, GL_RGB, GL_HALF_FLOAT)

	arr = np.asarray(img)

	assert arr.shape == (2, 2, 3)
	assert arr.dtype == np.float16

def test_buffer_write_is_zero_copy():
	img = Image()
	img.allocateImage(4, 3, 1, GL_RGBA, GL_FLOAT)

	np.asarray(img)[1, 2] = (1.0, 2.0, 3.0, 4.0)

	# A fresh view over the SAME image must see the write - proves the
	# buffer is a live view over osg::Image's own pixel storage, not a copy.
	assert tuple(np.asarray(img)[1, 2]) == (1.0, 2.0, 3.0, 4.0)

def test_buffer_row_stride_respects_padding():
	# Width 3 * 1 byte/pixel is not a multiple of GL's default 4-byte row
	# alignment, so OSG pads each row. If the binding used a naive
	# `width * itemsize` stride instead of `getRowStepInBytes()`, row 1 would
	# be misaligned and this write/read would land on the wrong pixel.
	img = Image()
	img.allocateImage(3, 2, 1, GL_RED, GL_UNSIGNED_BYTE)

	arr = np.asarray(img)
	arr[:] = 0
	arr[1, 0] = 42

	assert np.asarray(img)[1, 0] == 42
	assert np.asarray(img)[0, 0] == 0

def test_buffer_readonly_false():
	img = Image()
	img.allocateImage(2, 2, 1, GL_RGBA, GL_FLOAT)

	assert np.asarray(img).flags.writeable is True

def make_rgb(s, t, fill):
	img = Image()
	img.allocateImage(s, t, 1, GL_RGB, GL_UNSIGNED_BYTE)

	np.asarray(img)[:] = fill

	return img

def test_scale_image_averages_blocks():
	# Four uniform 2x2 blocks halve to exactly one pixel per block, on the CPU.
	img = make_rgb(4, 4, 0)
	arr = np.asarray(img)
	colors = ((10, 20, 30), (200, 100, 50), (0, 255, 0), (90, 90, 90))

	for i, color in enumerate(colors):
		y, x = divmod(i, 2)
		arr[y * 2:y * 2 + 2, x * 2:x * 2 + 2] = color

	img.scaleImage(2, 2)

	assert (img.s, img.t, img.r) == (2, 2, 1)
	assert [tuple(np.asarray(img)[y, x]) for y in range(2) for x in range(2)] == list(colors)

def test_scale_image_converts_data_type():
	img = make_rgb(2, 2, 255)

	img.scaleImage(1, 1, dataType=GL_FLOAT)

	assert img.dataType == GL_FLOAT
	assert np.allclose(np.asarray(img)[0, 0], 1.0)

def test_copy_and_deepcopy_are_independent():
	import copy

	original = make_rgb(2, 2, 7)

	for duplicate in (copy.copy(original), copy.deepcopy(original)):
		assert (duplicate.s, duplicate.t, duplicate.pixelFormat) == (2, 2, GL_RGB)

		np.asarray(original)[0, 0] = 99

		assert tuple(np.asarray(duplicate)[0, 0]) == (7, 7, 7)

		np.asarray(original)[0, 0] = 7

def test_copy_sub_image():
	target = make_rgb(3, 3, 0)
	patch = make_rgb(1, 1, 50)

	target.copySubImage(2, 1, 0, patch)

	arr = np.asarray(target)

	assert tuple(arr[1, 2]) == (50, 50, 50)
	assert arr.sum() == 150
