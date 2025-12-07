#vimrun! pytest -v ..

from .conftest import f32, floatif

import os
import pytest

from OpenSceneGraph import *

import numpy as np

def test_precision():
	assert np.finfo(np.float32).min == osg.F32_MIN
	assert np.finfo(np.float32).max == osg.F32_MAX
	assert np.finfo(np.float64).min == osg.F64_MIN
	assert np.finfo(np.float64).max == osg.F64_MAX

def test_helpers():
	f_64, f_32 = floatif(123, 4567)

	assert f_64 == 123.4567
	assert f_32 == pytest.approx(123.4567)
