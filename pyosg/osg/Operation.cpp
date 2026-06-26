#include "Operation.hpp"

namespace pyosg {

void bind_Operation(py::module_& m) {
	py::class_<
		osg::Operation,
		detail::Operation,
		osg::Referenced,
		osg::ref_ptr<osg::Operation>
	>(m, "Operation")
		.def("release", &osg::Operation::release)
		.def_property("name", &osg::Operation::getName, &osg::Operation::setName)
		.def_property("keep", &osg::Operation::getKeep, &osg::Operation::setKeep)
	;

	py::class_<
		osg::GraphicsOperation,
		detail::GraphicsOperation,
		osg::Operation,
		osg::ref_ptr<osg::GraphicsOperation>
	>(m, "GraphicsOperation")
		.def(py::init_alias<const std::string&, bool>(), "name"_a, "keep"_a)
	;
}

}
