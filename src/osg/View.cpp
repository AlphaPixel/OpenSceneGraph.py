#include "../OpenSceneGraph-python.hpp"

PYOSG_DISABLE_WARNINGS

#include <osg/View>

PYOSG_ENABLE_WARNINGS

namespace pyosg {

void bind_View(py::module_& m) {
	py::class_<osg::View, osg::Object, osg::ref_ptr<osg::View>>(m, "View")
		.def(py::init<>())
	;
}

}
