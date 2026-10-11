#pragma once

#include <limits>

#include "../pyosg.hpp"

OSGX_DISABLE_WARNINGS

#include <osg/Geometry>

OSGX_ENABLE_WARNINGS

#include "pybind11x-osg.hpp"

namespace pyx = pybind11x;

namespace pyosg::detail {
	struct VertexAttribTag;
}

// Keyed by the same `unsigned int index` osg::Geometry's own setVertexAttribArray/
// getVertexAttribArray use. Binding and normalize are deliberately NOT part of this proxy's
// value_type: the modern (non-deprecated) osg::Geometry API only takes an optional binding
// alongside the array purely to forward it into `array->setBinding(...)` (see
// Geometry::setVertexAttribArray's implementation) - binding and normalize are properties of
// the osg::Array itself (osg.Array.binding/.normalize, see Array.cpp), not per-index state on
// Geometry. The old `Geometry::setVertexAttribBinding`/`setVertexAttribNormalize` methods that
// would have suggested otherwise are deprecated shims to the same array-side calls. So the
// setter here just accepts a bare `osg.Array` - no sequence-unpack tuple form needed at all.
template<>
struct pyx::MappingTraits<osg::Geometry, pyosg::detail::VertexAttribTag> {
	using element_type = osg::Array;
	using key_type = unsigned int;
	using value_type = element_type*;

	static value_type from_python(py::handle h) {
		return h.cast<value_type>();
	}

	// Counts populated slots, not the raw (possibly sparse) list length - matches
	// StateSet.textureAttributes's TextureAttributesTag convention.
	static size_t size(osg::Geometry* g) {
		size_t out = 0;
		auto n = g->getNumVertexAttribArrays();

		for(unsigned int i = 0; i < n; i++) if(g->getVertexAttribArray(i)) out++;

		return out;
	}

	static element_type* get(osg::Geometry* g, key_type index) {
		return g->getVertexAttribArray(index);
	}

	static void set(osg::Geometry* g, key_type index, value_type array) {
		g->setVertexAttribArray(index, array);
	}

	static void del(osg::Geometry* g, key_type index) {
		g->setVertexAttribArray(index, nullptr);
	}

	static std::vector<key_type> keys(osg::Geometry* g) {
		std::vector<key_type> out;
		auto n = g->getNumVertexAttribArrays();

		for(unsigned int i = 0; i < n; i++) if(g->getVertexAttribArray(i)) out.push_back(i);

		return out;
	}
};

// Default tag - Geometry only needs one SequenceProxy, matching Program's ShadersProxy.
template<>
struct pyx::SequenceTraits<osg::Geometry> {
	using element_type = osg::PrimitiveSet;
	using value_type = element_type*;

	static value_type from_python(py::handle h) {
		return h.cast<value_type>();
	}

	static size_t size(const osg::Geometry* g) {
		return g->getNumPrimitiveSets();
	}

	static element_type* get(osg::Geometry* g, size_t i) {
		return g->getPrimitiveSet(static_cast<unsigned int>(i));
	}

	// getPrimitiveSetList() returns a mutable reference, so item assignment is a direct index
	// write - no OSG-side "replace at index" method needed, unlike `del`/`append` below.
	static void set(osg::Geometry* g, size_t i, element_type* ps) {
		g->getPrimitiveSetList()[i] = ps;
	}

	static void del(osg::Geometry* g, size_t i) {
		g->removePrimitiveSet(static_cast<unsigned int>(i), 1);
	}

	static void append(osg::Geometry* g, element_type* ps) {
		g->addPrimitiveSet(ps);
	}

	static void insert(osg::Geometry* g, size_t i, element_type* ps) {
		g->insertPrimitiveSet(static_cast<unsigned int>(i), ps);
	}
};

namespace pyosg {

namespace detail {
	constexpr size_t VertexArraySlot = 0;
	constexpr size_t ColorArraySlot = 1;
	constexpr size_t NormalArraySlot = 2;

	using GeometrySlots = pyx::PropertySlots<osg::Geometry, 3>;
	using VertexAttribProxy = pyx::MappingProxy<osg::Geometry, VertexAttribTag>;
	using PrimitiveSetsProxy = pyx::SequenceProxy<osg::Geometry>;

	// One canonical storage alias per owner type: splitting this into per-proxy storage aliases would attach
	// independent sidecars to the same OSG object instead of one shared one.
	using GeometryStorage = pyx::ProxyStorageOSG<
		osg::Geometry,
		GeometrySlots,
		VertexAttribProxy,
		PrimitiveSetsProxy
	>;

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

	// Shared by every DrawElements{UByte,UShort,UInt} binding, mirroring bind_Array<T>'s shape
	// (Array.hpp) for the same reason: one generic buffer-backed constructor instead of three
	// near-identical hand-written ones. The (mode, count, ptr) constructor every DrawElements
	// subclass already defines is what makes this work with no DrawElements-level virtual
	// needed, and no manual resize()+copy on our end - OSG's own ctor does that.
	template<typename T>
	auto bind_DrawElements(py::module_& m, const char* name) {
		using ElementT = typename T::vector_type::value_type;

		return py::class_<T, osg::PrimitiveSet, osg::ref_ptr<T>>(
			m,
			name,
			"A PrimitiveSet that draws explicit vertex indices rather than a contiguous run."
		)
			.def(py::init<GLenum>(), "mode"_a=0, "Create an empty set with the given draw mode.")
			// Registered before the sequence ctor below for the same reason as bind_Array<T>'s buffer
			// ctor: numpy integer scalars pass pybind11's no-conversion int check, so the std::vector
			// caster would otherwise claim numpy input element by element.
			.def(py::init([](GLenum mode, py::buffer data) {
				auto elements = pyx::unpack_buffer<ElementT>(data);

				if(elements.count > std::numeric_limits<unsigned int>::max()) throw py::value_error(
					"Index count must fit in an unsigned int"
				);

				return new T(mode, static_cast<unsigned int>(elements.count), elements.data);
			}), "mode"_a, "data"_a,
				"Create a set with the given draw mode, copying every index from a C-contiguous buffer "
				"(e.g. a numpy array or array.array, any shape) matching this type's index width."
			)
			// Non-buffer input, e.g. a plain Python list of ints. Every DrawElementsU* subclass derives
			// its vector_type (osg::MixinVector<ElementT>), so assign() is available directly.
			.def(py::init([](GLenum mode, const std::vector<ElementT>& indices) {
				auto d = new T(mode);

				d->assign(indices.begin(), indices.end());

				return d;
			}), "mode"_a, "indices"_a,
				"Create a set with the given draw mode, copying every index from a Python sequence."
			)
		;
	}
}

void bind_Geometry(py::module_& m);

}
