#include "OpenSceneGraph-python.hpp"
#include "osg.hpp"
#include "osgDB.hpp"
#include "osgGA.hpp"
#include "osgViewer.hpp"

PYOSG_CONSTRUCTOR(pyosg_preinit) {
	// std::cout << "PYOSG_CONSTRUCTOR: You can do your static init here..." << std::endl;
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

	/* py::module_ atexit = py::module_::import("atexit");

	atexit.attr("register")(
		py::cpp_function([]() {
		})
	); */
}
