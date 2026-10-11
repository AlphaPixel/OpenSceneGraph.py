#pragma once

#include <limits>

#include "../pyosg.hpp"

OSGX_DISABLE_WARNINGS

#include <osg/Array>

OSGX_ENABLE_WARNINGS

#include "pybind11x.hpp"

namespace pyosg {

namespace detail {
	template<typename T>
	class ArraySlice {
	public:
		using element_type = typename T::ElementDataType;

		element_type* data;
		size_t length;
		T* parent;

		ArraySlice(element_type* ptr, size_t len, T* p):
		data(ptr),
		length(len),
		parent(p) {}

		size_t size() const { return length; }

		element_type& operator[](size_t i) { return data[i]; }
		const element_type& operator[](size_t i) const { return data[i]; }
	};

	template<typename T>
	void bind_ArraySlice(py::handle& m, const char* name) {
		using Slice = ArraySlice<T>;
		using element_type = typename T::ElementDataType;

		py::class_<Slice>(m, name)
			.def("__len__", &Slice::size)

			.def("__getitem__", [](Slice& self, py::ssize_t index) {
				return self[n_index(self.size(), index)];
			})

			.def("__setitem__", [](Slice& self, py::ssize_t index, const element_type& value) {
				self[n_index(self.size(), index)] = value;
			})

			// This version supports BROADCAST assignment; that is, you can assigne ONE value to an
			// ENTIRE RANGE of values. For example: `v3a[1:2][:] = osg.Vec3()`
			.def("__setitem__", [](Slice& self, py::slice slice, const element_type& value) {
				size_t start, stop, step, length;

				if(!slice.compute(self.size(), &start, &stop, &step, &length))
					throw py::error_already_set();

				if(step != 1) throw py::value_error("Slice assignment only supports step=1");

				// Broadcast assignment over the slice range
				for(size_t i = start; i < stop; i += step) self[i] = value;
			})

			// TODO: A version that supports NON-BROADCAST assignment!
			// .def("__setitem__", [](Slice& self, py::slice slice, const element_type& value) {

			.def("__iter__", [](Slice& self) {
				return py::make_iterator(self.data, self.data + self.length);
			}, py::keep_alive<0, 1>())

			// TODO: Move this into a traits-like wrapper?
			.def_property_readonly("ptr", [](Slice& self) {
				return reinterpret_cast<uintptr_t>(self.data);
			})
			.def_property_readonly("stride", [](const Slice& self) {
				return sizeof(element_type);
			})
			.def_property_readonly("shape", [](const Slice& self) {
				return py::make_tuple(self.size(), self.parent->getDataSize());
			})
			.def_property_readonly("nbytes", [](const Slice& self) {
				return self.size() * sizeof(element_type);
			})
		;
	}

	// Describes an osg::Array element as `components` scalars of type `scalar`; osg::Vec* types expose
	// both directly (value_type, num_components), plain scalars (GLbyte, float) are one component.
	template<typename E>
	struct element_traits {
		using scalar = E;

		static constexpr size_t components = 1;
	};

	template<typename E> requires requires { E::num_components; }
	struct element_traits<E> {
		using scalar = typename E::value_type;

		static constexpr size_t components = E::num_components;
	};

	template<typename T>
	auto bind_Array(py::module_& m, const char* name) {
		auto arr = py::class_<T, osg::Array, osg::ref_ptr<T>>(
			m,
			name,
			py::buffer_protocol(),
			"A typed osg::Array of elements; supports the Python buffer protocol (so numpy.asarray() "
			"views it with no copy) plus indexing, slicing (step=1 only), iteration, and __repr__."
		);

		bind_ArraySlice<T>(arr, "_Slice");

		arr
			.def(py::init<>(), "Create an empty array with no elements.")
			.def(py::init([](py::ssize_t size) {
				if(size < 0 || size > static_cast<py::ssize_t>(std::numeric_limits<unsigned int>::max())) {
					throw py::value_error("Array size must fit in an unsigned int");
				}

				return new T(static_cast<unsigned int>(size));
			}), "size"_a, "Create an array of size default-constructed elements.")
			// Registered before the sequence ctor below: pybind11 tries overloads in order (first
			// without implicit conversions, then with), and the std::vector caster can also accept numpy
			// arrays by iterating them, which would skip this ctor's type and shape checks.
			.def(py::init([](py::buffer b) {
				using E = typename T::ElementDataType;
				using traits = element_traits<E>;

				static_assert(sizeof(E) == sizeof(typename traits::scalar) * traits::components);

				auto elements = pybind11x::unpack_buffer<typename traits::scalar>(b, traits::components);

				if(elements.count > std::numeric_limits<unsigned int>::max()) throw py::value_error(
					"Array size must fit in an unsigned int"
				);

				auto a = new T(static_cast<unsigned int>(elements.count));

				if(elements.count) std::memcpy(
					const_cast<void*>(a->getDataPointer()),
					elements.data,
					elements.count * sizeof(E)
				);

				return a;
			}),
				"Create an array from a C-contiguous buffer (e.g. a numpy array or array.array) whose "
				"items match this array's scalar type, copying its data; a 1D buffer is grouped into "
				"elements by component count, an N-D buffer's last dimension must equal it."
			)
			// Non-buffer input, e.g. a plain Python list of elements.
			.def(py::init([](const std::vector<typename T::ElementDataType>& vec) {
				auto a = new T();

				a->assign(vec.begin(), vec.end());

				return a;
			}), "Create an array by copying every element from a Python sequence.")

			// .def("append", [](T& self, const T::ElementDataType& v) { self.push_back(v); })

			// https://pybind11.readthedocs.io/en/stable/advanced/pycpp/numpy.html
			.def_buffer([](T& self) -> py::buffer_info {
				using traits = element_traits<typename T::ElementDataType>;
				using S = typename traits::scalar;

				auto n = static_cast<py::ssize_t>(self.size());
				auto itemsize = static_cast<py::ssize_t>(sizeof(S));
				auto comps = static_cast<py::ssize_t>(traits::components);
				auto ptr = const_cast<void*>(self.getDataPointer());

				if(comps == 1) return py::buffer_info(
					ptr,
					itemsize,
					py::format_descriptor<S>::format(),
					1,
					{ n },
					{ itemsize }
				);

				return py::buffer_info(
					ptr,
					itemsize,
					py::format_descriptor<S>::format(),
					2,
					{ n, comps },
					{ itemsize * comps, itemsize }
				);
			})

			.def("__len__", [](const T& self) { return self.size(); },
				"Return the number of elements (not scalar components)."
			)

			.def("__getitem__", [](const T& self, py::ssize_t index) {
				return self[n_index(self.size(), index)];
			}, "Return the element at index (negative indices count from the end).")

			.def("__getitem__", [](T& self, const py::slice& slice) {
				size_t start, stop, step, length;

				if(!slice.compute(
					self.size(),
					&start,
					&stop,
					&step,
					&length
				)) throw py::error_already_set();

				if(step != 1) throw py::index_error("Vec3Array slicing only supports step=1");

				return ArraySlice<T>(
					reinterpret_cast<ArraySlice<T>::element_type*>(
						const_cast<void*>(self.getDataPointer())
					) + start,
					length,
					&self
				);
			}, py::keep_alive<0, 1>(),
				"Return an ArraySlice view (step=1 only) sharing this array's underlying storage; "
				"writes through the slice mutate this array in place."
			)

			.def("__setitem__", [](T& self, py::ssize_t index, const T::ElementDataType& value) {
				self[n_index(self.size(), index)] = value;
			}, "Set the element at index (negative indices count from the end).")

			// TODO: BROADCAST and NON-BROADCAST slice assignment!
			// .def("__setitem__", [](T& self, py::ssize_t index, const T::ElementDataType& value) {

			.def("__repr__", [name](const T& self) {
				return py::str("{}(size={})").format(name, self.size());
			}, "Return a constructor-style representation showing this array's element count.")

			.def("dump", [name](const T& self) {
				py::list items;

				size_t n = self.size();

				// TODO: Why did this fail?
				// items.reserve(n);

				for(size_t i = 0; i < n; ++i) items.append(py::repr(py::cast(self[i])));

				return py::str("{}({})").format( name, py::str(", ").attr("join")(items));
			}, "Return every element's repr, comma-joined and wrapped in the type name.")
		;
	}
}

void bind_Array(py::module_& m);

}
