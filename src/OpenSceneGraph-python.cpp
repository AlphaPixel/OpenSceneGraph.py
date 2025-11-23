#include "OpenSceneGraph-python.hpp"
#include "osg.hpp"
#include "osgDB.hpp"
#include "osgGA.hpp"
#include "osgViewer.hpp"

PYBIND11_MODULE(OpenSceneGraph, m) {
	auto osg = m.def_submodule("osg", "osg namespace");

	pyosg::bind(osg);

	auto osgDB = m.def_submodule("osgDB", "osgDB namespace");

	pyosgDB::bind(osgDB);

	auto osgGA = m.def_submodule("osgGA", "osgGA namespace");

	pyosgGA::bind(osgGA);

	auto osgViewer = m.def_submodule("osgViewer", "osgViewer namespace");

	pyosgViewer::bind(osgViewer);
}
