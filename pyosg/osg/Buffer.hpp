#pragma once

#include "../pyosg.hpp"

OSGX_DISABLE_WARNINGS

#include <osg/BufferObject>

OSGX_ENABLE_WARNINGS

#include "pybind11x.hpp"

namespace pyx = pybind11x;

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

	constexpr size_t BufferObjectSlot = 0;
	constexpr size_t BufferIndexSlot = 1;

	using BufferDataSlots = pyx::PropertySlots<osg::BufferData, 2>;
	using BufferDataStorage = pyx::ProxyStorageOSG<osg::BufferData, BufferDataSlots>;
}

void bind_Buffer(py::module_& m);

}
