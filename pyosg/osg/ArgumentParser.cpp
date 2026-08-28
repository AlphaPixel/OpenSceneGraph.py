#include "ArgumentParser.hpp"

namespace pyosg {

void bind_ArgumentParser(py::module_& m) {
	py::class_<detail::ArgumentParser>(m, "ArgumentParser", detail::ArgumentParser::DOCSTRING)
		.def(py::init<const std::string&, const py::sequence&>(),
			"program_name"_a=OPENSCENEGRAPH_PYTHON_MODULE,
			"args"_a=py::list(),
			"Build an osg::ArgumentParser from a program name and a sequence of argument "
			"strings, owning stable argc/argv storage for OSG's lifetime requirements."
		)
		// .def("ptr", [](detail::ArgumentParser& self) {
		// 	return py::capsule(&self.parser, "osg::ArgumentParser&");
		// })
		.def_readonly("argc", &detail::ArgumentParser::argc,
			"The synthesized argc, i.e. len(argv) including the program name at index 0."
		)
		.def_property_readonly("argv", [](detail::ArgumentParser& self) {
			return detail::make_tuple(self.argv);
		}, "Tuple of argument strings, program name first, mirroring C argv[].")
		.def("__repr__", [](detail::ArgumentParser& self) {
			return py::str("ArgumentParser(argc={}, argv={})").format(
				self.argc,
				detail::make_tuple(self.argv)
			);
		}, "Return a constructor-style representation of this ArgumentParser.")
	;
}

}
