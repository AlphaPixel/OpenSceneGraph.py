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

		// Increments the modified count, telling the render backend a buffer object needs
		// re-uploading. Mutating an osg.Array's elements in place (e.g. via __setitem__) does
		// NOT call this automatically -- without it, GLBufferObject::compileBuffer() has no way
		// to know the CPU-side data changed, so the GPU-side buffer silently goes stale. Needed
		// for any per-frame in-place array mutation to actually show up on screen; reusing the
		// same Array object (rather than constructing a new one every frame, which forces an
		// expensive full glBufferData() reallocation instead of a cheap glBufferSubData()
		// update) plus calling dirty() is the correct, efficient pattern.
		.def("dirty", &osg::BufferData::dirty)

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

	py::class_<
		osg::UniformBufferObject,
		osg::BufferObject,
		osg::ref_ptr<osg::UniformBufferObject>
	>(m, "UniformBufferObject")
		.def(py::init<>())
	;
}

}
