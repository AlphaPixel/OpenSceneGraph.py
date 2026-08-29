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
		.def("release", &osg::Operation::release,
			"Called when this Operation is removed from its queue, e.g. to release resources "
			"it held; the default implementation does nothing."
		)
		.def_property("name", &osg::Operation::getName, &osg::Operation::setName,
			"Identifying name, useful for debugging an operation queue."
		)
		.def_property("keep", &osg::Operation::getKeep, &osg::Operation::setKeep,
			"Whether this Operation stays queued and runs again every frame (True) or is "
			"removed after a single run (False)."
		)
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
		.def(py::init_alias<const std::string&, bool>(), "name"_a, "keep"_a,
			"Construct with a name and whether the operation should be re-run every frame "
			"(keep=True) or run once and be discarded (keep=False)."
		)
	;
}

}
