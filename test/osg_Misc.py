#vimrun! pytest -v ..

from .conftest import f32, floatif

import os
import pytest

from OpenSceneGraph import *

import numpy as np

def test_precision():
	# It's frustrating that the C++ `<limits>` constants use the name `LOWEST` to match `min`.
	assert np.finfo(np.float32).min == F32_LOWEST
	assert np.finfo(np.float32).max == F32_MAX
	assert np.finfo(np.float64).min == F64_LOWEST
	assert np.finfo(np.float64).max == F64_MAX

def test_helpers():
	f_64, f_32 = floatif(123, 4567)

	assert f_64 == 123.4567
	assert f_32 == pytest.approx(123.4567)
