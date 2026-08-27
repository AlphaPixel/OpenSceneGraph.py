#include "OpenSceneGraph-python.hpp"

#include <osgEarth/MapNode>

PYBIND11_MODULE(osgEarth, m) {
	py::module_::import("OpenSceneGraph");

	py::class_<osgEarth::Map, osg::Object, osg::ref_ptr<osgEarth::Map>>(
		m,
		"Map",
		"An osgEarth terrain/imagery data model: the set of layers a MapNode renders."
	)
		.def(py::init<>(), "Create an empty osgEarth map.")
	;

	py::class_<osgEarth::MapNode, osg::Group, osg::ref_ptr<osgEarth::MapNode>>(
		m,
		"MapNode",
		"A Group node that renders a Map, the entry point for adding osgEarth terrain to a scene."
	)
		.def(py::init<>(), "Create an osgEarth map node.")
	;
}
