#include "Buffer.hpp"

namespace pyosg {

void bind_Buffer(py::module_& m) {
	py::class_<
		osg::BufferData,
		detail::BufferData,
		osg::Object,
		osg::ref_ptr<osg::BufferData>
	>(m, "BufferData")
		// .def(py::init_alias<>())
		// .def(py::init<const osg::BufferData&>())

		// .def_propert("bufferObject"
		// .def_propert("bufferIndex"
	;

	py::class_<
		osg::BufferObject,
		osg::Object,
		osg::ref_ptr<osg::BufferObject>
	>(m, "BufferObject")
		// .def(py::init<>())
	;
}

}
