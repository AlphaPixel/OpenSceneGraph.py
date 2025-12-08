#include "pyosg.hpp"
#include "pyosgDB.hpp"
#include "pyosgGA.hpp"
#include "pyosgViewer.hpp"

#include <osg/Version>

#include <limits>

#ifdef PYOSG_EMBEDDED
	extern "C" PYBIND11_EXPORT PyObject* PyInit_OpenSceneGraph();
#endif

PYOSG_CONSTRUCTOR(pyosg_preinit) {
	// OSG_INFO << "PYOSG_CONSTRUCTOR: You can do your static init here..." << std::endl;
}

PYBIND11_MODULE(OpenSceneGraph, m) {
	auto osg = m.def_submodule("osg", "osg namespace");

	pyosg::bind(osg);

	auto osgDB = m.def_submodule("osgDB", "osgDB namespace");

	pyosgDB::bind(osgDB);

	auto osgGA = m.def_submodule("osgGA", "osgGA namespace");

	pyosgGA::bind(osgGA);

	auto osgViewer = m.def_submodule("osgViewer", "osgViewer namespace");

	pyosgViewer::bind(osgViewer);

	m.def("build_info", []() {
		py::dict info;

		info["osg"] = osgGetVersion();

		info["pybind"] = py::str("{}.{}.{}").format(
			PYBIND11_VERSION_MAJOR,
			PYBIND11_VERSION_MINOR,
			PYBIND11_VERSION_MICRO
		);

		info["date"] = __DATE__ " " __TIME__;

		info["compiler"] =
#ifdef __clang__
		"Clang " __clang_version__
#elif defined(__GNUC__)
		"GCC " __VERSION__
#elif defined(_MSC_VER)
		std::string("MSVC ") + std::to_string(_MSC_VER)
#else
		"Unknown compiler"
#endif
		;

		return info;
	});

	m.attr("F32_MIN") = std::numeric_limits<float>::min();
	m.attr("F32_MAX") = std::numeric_limits<float>::max();
	m.attr("F32_LOWEST") = std::numeric_limits<float>::lowest();

	m.attr("F64_MIN") = std::numeric_limits<double>::min();
	m.attr("F64_MAX") = std::numeric_limits<double>::max();
	m.attr("F64_LOWEST") = std::numeric_limits<double>::lowest();

	/* py::module_ atexit = py::module_::import("atexit");

	atexit.attr("register")(
		py::cpp_function([]() {
		})
	); */
}
