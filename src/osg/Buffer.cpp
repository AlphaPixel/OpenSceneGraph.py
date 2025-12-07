#include "../pyosg.hpp"

PYOSG_DISABLE_WARNINGS

#include <osg/BufferObject>

PYOSG_ENABLE_WARNINGS

namespace pyosg {

namespace detail {
	class BufferData: public osg::BufferData {
	public:
		const GLvoid* getDataPointer() const override {
			PYBIND11_OVERRIDE_PURE(
				const GLvoid*,
				osg::BufferData,
				getDataPointer
			);
		}

		unsigned int getTotalDataSize() const override {
			PYBIND11_OVERRIDE_PURE(
				unsigned int,
				osg::BufferData,
				getTotalDataSize
			);
		}
	};
}

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
