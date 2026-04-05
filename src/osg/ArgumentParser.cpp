#include "ArgumentParser.hpp"

namespace pyosg {

void bind_ArgumentParser(py::module_& m) {
	py::class_<detail::ArgumentParser>(m, "ArgumentParser", detail::ArgumentParser::DOCSTRING)
		.def(py::init<const std::string&, const py::sequence&>(),
			"program_name"_a=OPENSCENEGRAPH_PYTHON_MODULE,
			"args"_a=py::list()
		)
		// .def("ptr", [](detail::ArgumentParser& self) {
		// 	return py::capsule(&self.parser, "osg::ArgumentParser&");
		// })
	;
}

}
