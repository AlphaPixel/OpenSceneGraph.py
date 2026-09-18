#pragma once

#include "../pyosg.hpp"

OSGX_DISABLE_WARNINGS

#include <osg/Plane>

OSGX_ENABLE_WARNINGS

namespace pyosg {

void bind_Plane(py::module_& m);

}
