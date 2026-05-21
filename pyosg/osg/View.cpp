#include "../pyosg.hpp"

PYOSG_DISABLE_WARNINGS

#include <osg/View>

PYOSG_ENABLE_WARNINGS

namespace pyosg {

void bind_View(py::module_& m) {
	py::class_<osg::View, osg::Object, osg::ref_ptr<osg::View>>(m, "View")
		.def(py::init<>())
		.def_property(
			"camera",
			py::cpp_function(
				py::overload_cast<>(&osg::View::getCamera),
				py::return_value_policy::reference_internal
			),
			py::cpp_function(
				&osg::View::setCamera,
				py::keep_alive<1, 2>()
			)
		)
		.def_property_readonly("frameStamp",
			py::overload_cast<>(&osg::View::getFrameStamp, py::const_),
			py::return_value_policy::reference
		)
	;
}

}
