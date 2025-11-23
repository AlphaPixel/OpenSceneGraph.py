#include "OpenSceneGraph-python.hpp"

#include <osgEarth/MapNode>

PYBIND11_MODULE(osgEarth, m) {
	py::module_::import("OpenSceneGraph");

	py::class_<osgEarth::Map, osg::Object, osg::ref_ptr<osgEarth::Map>>(m, "Map")
		.def(py::init<>())
	;

	py::class_<osgEarth::MapNode, osg::Group, osg::ref_ptr<osgEarth::MapNode>>(m, "MapNode")
		.def(py::init<>())
	;
}
