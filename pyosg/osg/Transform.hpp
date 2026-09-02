#pragma once

#include "../pyosg.hpp"

OSGX_DISABLE_WARNINGS

#include <osg/AutoTransform>
#include <osg/MatrixTransform>
#include <osg/PositionAttitudeTransform>

OSGX_ENABLE_WARNINGS

#include "pybind11x-osg.hpp"

namespace pyx = pybind11x;

namespace pyosg {

namespace detail {
	// TODO: We'll need a `Transform` trampoline here for these!
	/* virtual bool computeLocalToWorldMatrix(Matrix& matrix,NodeVisitor*) const
	virtual bool computeWorldToLocalMatrix(Matrix& matrix,NodeVisitor*) const */
}

void bind_Transform(py::module_& m);

}
