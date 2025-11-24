#pragma once

// TODO: Remove me!
#include <iostream>

#include <pybind11/pybind11.h>
#include <pybind11/operators.h>

#define PYOSG_DISABLE_WARNINGS \
	_Pragma("GCC diagnostic push") \
	_Pragma("GCC diagnostic ignored \"-Wconversion\"") \
	_Pragma("GCC diagnostic ignored \"-Wsign-conversion\"") \
	_Pragma("GCC diagnostic ignored \"-Wdeprecated-copy\"") \
	_Pragma("GCC diagnostic ignored \"-Wfloat-conversion\"") \
	_Pragma("GCC diagnostic ignored \"-Wsign-compare\"") \
	_Pragma("GCC diagnostic ignored \"-Woverloaded-virtual\"") \
	_Pragma("GCC diagnostic ignored \"-Wshadow\"") \
	_Pragma("GCC diagnostic ignored \"-Wunused-but-set-variable\"")

#define PYOSG_ENABLE_WARNINGS \
	_Pragma("GCC diagnostic pop")

PYOSG_DISABLE_WARNINGS

#include <osg/ref_ptr>

PYOSG_ENABLE_WARNINGS

namespace py = pybind11;

// Tell pybind11 that osg::ref_ptr<T> is a holder type for T.  The 3rd argument = true because
// osg::ref_ptr<T> can safely be constructed from a raw T* (intrusive refcounting).
PYBIND11_DECLARE_HOLDER_TYPE(T, osg::ref_ptr<T>, true);
