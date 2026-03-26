#include "pyosg.hpp"
#include "pyosgDB.hpp"
#include "pyosgGA.hpp"
#include "pyosgViewer.hpp"

#include <osg/Version>

#include <GL/gl.h>

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

	// ============================================================================================
	// TODO: I add these as I need them! Later, we need to add... all. :(
	auto gl = m.def_submodule("GL");

	gl.attr("GL_POINTS") = GL_POINTS;
	gl.attr("GL_LINES") = GL_LINES;
	gl.attr("GL_LINE_LOOP") = GL_LINE_LOOP;
	gl.attr("GL_LINE_STRIP") = GL_LINE_STRIP;
	gl.attr("GL_TRIANGLES") = GL_TRIANGLES;
	gl.attr("GL_TRIANGLE_STRIP") = GL_TRIANGLE_STRIP;
	gl.attr("GL_TRIANGLE_FAN") = GL_TRIANGLE_FAN;

	gl.attr("GL_RGBA") = GL_RGBA;
	gl.attr("GL_DEPTH_COMPONENT24") = GL_DEPTH_COMPONENT24;
	gl.attr("GL_DEPTH_COMPONENT") = GL_DEPTH_COMPONENT;
	gl.attr("GL_FLOAT") = GL_FLOAT;
	gl.attr("GL_UNSIGNED_INT") = GL_UNSIGNED_INT;
	gl.attr("GL_COLOR_BUFFER_BIT") = GL_COLOR_BUFFER_BIT;
	gl.attr("GL_DEPTH_BUFFER_BIT") = GL_DEPTH_BUFFER_BIT;
	gl.attr("GL_DEPTH_TEST") = GL_DEPTH_TEST;
	gl.attr("GL_SCISSOR_TEST") = GL_SCISSOR_TEST;

	gl.attr("GL_BLEND") = GL_BLEND;
	gl.attr("GL_DEPTH_TEST") = GL_DEPTH_TEST;
	gl.attr("GL_VERTEX_PROGRAM_POINT_SIZE") = GL_VERTEX_PROGRAM_POINT_SIZE;
	gl.attr("GL_PROGRAM_POINT_SIZE") = GL_PROGRAM_POINT_SIZE;
	gl.attr("GL_POINT_SPRITE") = GL_POINT_SPRITE;
	gl.attr("GL_SRC_ALPHA") = GL_SRC_ALPHA;
	gl.attr("GL_ONE_MINUS_SRC_ALPHA") = GL_ONE_MINUS_SRC_ALPHA;
	gl.attr("GL_ONE") = GL_ONE;
	// ============================================================================================

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
