#include "Buffer.hpp"

#include <osg/UserDataContainer>

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

		.def_property_readonly("totalDataSize", &osg::BufferData::getTotalDataSize)
		// .def_property_readonly("dataPointer", &osg::BufferData::getTotalDataSize)

		// .def_property("bufferIndex"
		.def_property(
			"bufferObject",
			detail::BufferDataSlots::getter<detail::BufferObjectSlot>(
				static_cast<osg::BufferObject*(osg::BufferData::*)()>(
					&osg::BufferData::getBufferObject
				)
			),
			detail::BufferDataSlots::setter<detail::BufferObjectSlot, osg::BufferObject*>(
				static_cast<void(osg::BufferData::*)(osg::BufferObject*)>(
					&osg::BufferData::setBufferObject
				)
			)
		)
	;

	py::class_<
		osg::BufferObject,
		osg::Object,
		osg::ref_ptr<osg::BufferObject>
	>(m, "BufferObject")
		// .def(py::init<>())
	;

	py::class_<
		osg::ShaderStorageBufferObject,
		osg::BufferObject,
		osg::ref_ptr<osg::ShaderStorageBufferObject>
	>(m, "ShaderStorageBufferObject")
		.def(py::init<>())
	;
}

}
