#include "Buffer.hpp"

OSGX_DISABLE_WARNINGS

#include <osg/UserDataContainer>

OSGX_ENABLE_WARNINGS

namespace pyosg {

void bind_Buffer(py::module_& m) {
	py::class_<
		osg::BufferData,
		detail::BufferData,
		osg::Object,
		osg::ref_ptr<osg::BufferData>
	>(
		m,
		"BufferData",
		"Base class for CPU-side data (Array, Image, etc.) that mirrors to a GPU BufferObject."
	)
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

	// The live, per-context GL object (glGenBuffers() name) backing a compiled BufferObject.
	// Needed to hand a raw GL buffer id to anything outside OSG that wants to touch the same
	// GPU memory directly -- e.g. CUDA/GL interop (cudaGraphicsGLRegisterBuffer()) for zero-copy
	// access to tensors already living on the GPU. glObjectID reads 0 until the buffer has
	// actually been compiled (uploaded) at least once by the render backend.
	py::class_<
		osg::GLBufferObject,
		osg::Referenced,
		osg::ref_ptr<osg::GLBufferObject>
	>(
		m,
		"GLBufferObject",
		"The live, per-GL-context buffer object (glGenBuffers() name) backing a compiled BufferObject."
	)
		.def_property_readonly("contextID", &osg::GLBufferObject::getContextID)
		.def_property_readonly(
			"glObjectID",
			static_cast<GLuint(osg::GLBufferObject::*)() const>(&osg::GLBufferObject::getGLObjectID)
		)
		.def_property_readonly("dirty", &osg::GLBufferObject::isDirty)
		.def("compileBuffer", &osg::GLBufferObject::compileBuffer)
	;

	py::class_<
		osg::BufferObject,
		osg::Object,
		osg::ref_ptr<osg::BufferObject>
	>(
		m,
		"BufferObject",
		"Base class for GPU buffer objects (SSBOs, UBOs, etc.) that hold one or more BufferData "
		"arrays uploaded to the GPU."
	)
		// .def(py::init<>())
		.def(
			"glBufferObject",
			&osg::BufferObject::getOrCreateGLBufferObject,
			"contextID"_a,
			py::return_value_policy::reference
		)
	;

	py::class_<
		osg::ShaderStorageBufferObject,
		osg::BufferObject,
		osg::ref_ptr<osg::ShaderStorageBufferObject>
	>(
		m,
		"ShaderStorageBufferObject",
		"A GPU buffer object bound as an SSBO, used for arbitrary read/write shader storage."
	)
		.def(py::init<>())
	;

	py::class_<
		osg::UniformBufferObject,
		osg::BufferObject,
		osg::ref_ptr<osg::UniformBufferObject>
	>(
		m,
		"UniformBufferObject",
		"A GPU buffer object bound as a UBO, used to share a block of uniforms between shader stages."
	)
		.def(py::init<>())
	;
}

}
