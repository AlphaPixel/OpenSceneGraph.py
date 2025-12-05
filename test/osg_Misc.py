#vimrun! pytest -v ..

from .conftest import f32

import os
import pytest

from OpenSceneGraph import *

import numpy as np

def test_precision():
	assert np.finfo(np.float32).min == osg.F32_MIN
	assert np.finfo(np.float32).max == osg.F32_MAX
	assert np.finfo(np.float64).min == osg.F64_MIN
	assert np.finfo(np.float64).max == osg.F64_MAX
