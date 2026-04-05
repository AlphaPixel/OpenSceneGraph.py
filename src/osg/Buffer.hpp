#pragma once

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

void bind_Buffer(py::module_& m);

}
