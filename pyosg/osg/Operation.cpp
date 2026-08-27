#include "Operation.hpp"

namespace pyosg {

void bind_Operation(py::module_& m) {
	py::class_<
		osg::Operation,
		detail::Operation,
		osg::Referenced,
		osg::ref_ptr<osg::Operation>
	>(
		m,
		"Operation",
		"A named, one-shot or repeatable unit of work queued for execution, e.g. against a "
		"GraphicsContext's operation queue."
	)
		.def("release", &osg::Operation::release)
		.def_property("name", &osg::Operation::getName, &osg::Operation::setName)
		.def_property("keep", &osg::Operation::getKeep, &osg::Operation::setKeep)
	;

	py::class_<
		osg::GraphicsOperation,
		detail::GraphicsOperation,
		osg::Operation,
		osg::ref_ptr<osg::GraphicsOperation>
	>(
		m,
		"GraphicsOperation",
		"An Operation that runs with a valid GraphicsContext current, for GL work that must "
		"happen on a specific rendering thread."
	)
		.def(py::init_alias<const std::string&, bool>(), "name"_a, "keep"_a)
	;
}

}
