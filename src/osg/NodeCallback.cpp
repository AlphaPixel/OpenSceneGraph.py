#include "NodeCallback.hpp"

namespace pyosg {

void bind_NodeCallback(py::module_& m) {
	py::class_<
		osg::NodeCallback,
		detail::NodeCallback,
		osg::Object,
		osg::ref_ptr<osg::NodeCallback>
	>(m, "NodeCallback")
		.def(py::init<>())
	;
}

}
