#include "pyosgDB.hpp"

PYOSG_DISABLE_WARNINGS

#include <osgDB/ReadFile>

PYOSG_ENABLE_WARNINGS

namespace pyosgDB {

void bind(py::module_& m) {
	m.def(
		"readNodeFile", [](const std::string& filename) {
			auto* node = osgDB::readNodeFile(filename);

			if(!node) pyosg::detail::file_not_found(filename);

			return node;
		},
		py::arg("filename"),
		"Read an OSG node from a file and return it as an osg.Node"
	);

	// m.def("readNodeFile", py::overload_cast<const std::string&>(&osgDB::readNodeFile));

	/* m.def(
		"readNodeFile",
		py::overload_cast<const std::string&, const osgDB::Options*>(&osgDB::readNodeFile),
		py::arg("filename"),
		py::arg("options")
	); */
}

}
