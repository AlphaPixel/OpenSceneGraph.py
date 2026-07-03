#vimrun! pytest -sv ../test/osg_Image.py

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

	# A fresh view over the SAME image must see the write -- proves the
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
