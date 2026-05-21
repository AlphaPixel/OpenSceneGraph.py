#include "pyosgUtil.hpp"

PYOSG_DISABLE_WARNINGS

#include <osgUtil/UpdateVisitor>

PYOSG_ENABLE_WARNINGS

namespace pyosgUtil {

void bind(py::module_& m) {
	py::class_<
		osgUtil::UpdateVisitor,
		osg::NodeVisitor,
		osg::ref_ptr<osgUtil::UpdateVisitor>
	>(m, "UpdateVisitor")
		.def(py::init<>())
	;
}

}
