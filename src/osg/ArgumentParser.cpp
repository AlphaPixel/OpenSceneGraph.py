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
		.def_readonly("argc", &detail::ArgumentParser::argc)
		.def_property_readonly("argv", [](detail::ArgumentParser& self) {
			return detail::make_tuple(self.argv);
		})
		.def("__repr__", [](detail::ArgumentParser& self) {
			return py::str("ArgumentParser(argc={}, argv={})").format(
				self.argc,
				detail::make_tuple(self.argv)
			);
		})
	;
}

}
