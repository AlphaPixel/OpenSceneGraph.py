#pragma once

#include "../pyosg.hpp"

PYOSG_DISABLE_WARNINGS

#include <osg/Geometry>

PYOSG_ENABLE_WARNINGS

#include "pybind11x.hpp"

namespace pyx = pybind11x;

// TODO: PrimitiveSet

namespace pyosg {

namespace detail {
	constexpr size_t VertexArraySlot = 0;
	constexpr size_t ColorArraySlot = 1;
	constexpr size_t NormalArraySlot = 2;

	using GeometrySlots = pyx::PropertySlots<osg::Geometry, 3>;
	using GeometryStorage = pyx::ProxyStorageOSG<osg::Geometry, GeometrySlots>;

	// colorArray/normalArray both have a `(Array*, Array::Binding)` setter overload alongside
	// the plain `(Array*)` one -- PropertySlots::setter<I,T>() only fits the single-value
	// shape, so this covers the 2-arg one, sharing the same slot as the property/1-arg method.
	template<size_t Slot, void (osg::Geometry::*Setter)(osg::Array*, osg::Array::Binding)>
	auto geometry_array_binding_setter() {
		return [](osg::Geometry& self, py::object obj, osg::Array::Binding binding) {
			auto* array = obj.is_none() ? nullptr : obj.cast<osg::Array*>();

			(self.*Setter)(array, binding);

			auto& slots = GeometryStorage::get(self)->template proxy<GeometrySlots>();

			slots.set(Slot, obj, array);
		};
	}

	/* template<>
	void kwargs_init(osg::Object& self, const py::kwargs& kwargs) {
		if(kwargs.contains("name")) self.setName(kwargs["name"].cast<std::string>());
	} */

	class PrimitiveSet: public osg::PrimitiveSet {
	public:
		using osg::PrimitiveSet::PrimitiveSet;

		void draw(osg::State& state, bool useVertexBufferObjects) const override {
			PYBIND11_OVERRIDE_PURE(
				void,
				osg::PrimitiveSet,
				draw,
				state,
				useVertexBufferObjects
			);
		}

		void accept(osg::PrimitiveFunctor& functor) const override {
			PYBIND11_OVERRIDE_PURE(
				void,
				osg::PrimitiveSet,
				accept,
				functor
			);
		}

		void accept(osg::PrimitiveIndexFunctor& functor) const override {
			PYBIND11_OVERRIDE_PURE(
				void,
				osg::PrimitiveSet,
				accept,
				functor
			);
		}

		unsigned int index(unsigned int pos) const override {
			PYBIND11_OVERRIDE_PURE(
				unsigned int,
				osg::PrimitiveSet,
				index,
				pos
			);
		}

		unsigned int getNumIndices() const override {
			PYBIND11_OVERRIDE_PURE(
				unsigned int,
				osg::PrimitiveSet,
				getNumIndices
			);
		}

		void offsetIndices(int offset) override {
			PYBIND11_OVERRIDE_PURE(
				void,
				osg::PrimitiveSet,
				offsetIndices,
				offset
			);
		}
	};
}

void bind_Geometry(py::module_& m);

}
