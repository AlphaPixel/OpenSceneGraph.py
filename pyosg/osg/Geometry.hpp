#pragma once

#include "../pyosg.hpp"

PYOSG_DISABLE_WARNINGS

#include <osg/Geometry>

PYOSG_ENABLE_WARNINGS

// TODO: PrimitiveSet

namespace pyosg {

namespace detail {
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
