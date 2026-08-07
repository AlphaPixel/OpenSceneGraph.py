#pragma once

#include "../pyosg.hpp"

PYOSG_DISABLE_WARNINGS

#include <osg/Array>

PYOSG_ENABLE_WARNINGS

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

			.def("__getitem__", [](Slice& self, ssize_t index) {
				return self[n_index(self.size(), index)];
			})

			.def("__setitem__", [](Slice& self, ssize_t index, const element_type& value) {
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

	static std::unordered_map<
		// decltype(std::declval<const osg::Array>().getDataType()),
		GLenum,
		std::pair<py::ssize_t, std::string>
	> BufferInfo{
		{GL_FLOAT, {sizeof(GLfloat), py::format_descriptor<GLfloat>::format()}},
		{GL_DOUBLE, {sizeof(GLdouble), py::format_descriptor<GLdouble>::format()}},
		// {GL_BYTE, {sizeof(GLbyte), py::format_descriptor<GLbyte>::format()}},
		{GL_INT, {sizeof(GLint), py::format_descriptor<GLint>::format()}},
		{GL_UNSIGNED_INT, {sizeof(GLuint), py::format_descriptor<GLuint>::format()}}
	};

	// I really HATE that this MUST EXIST! OSG, whyyyy!????
	template<typename T>
	inline size_t array_components() {
		static auto comps = []{
			osg::ref_ptr<T> tmp = new T();

			return static_cast<size_t>(tmp->getDataSize());
		}();

		return comps;
	}

	template<typename T>
	auto bind_Array(py::module_& m, const char* name) {
		auto arr = py::class_<T, osg::Array, osg::ref_ptr<T>>(m, name, py::buffer_protocol());

		bind_ArraySlice<T>(arr, "_Slice");

		arr
			.def(py::init<>())
			.def(py::init<size_t>(), "size"_a)
			.def(py::init([](const std::vector<typename T::ElementDataType>& vec) {
				auto a = new T();

				a->assign(vec.begin(), vec.end());

				return a;
			}))
			.def(py::init([](py::buffer b) {
				py::buffer_info info = b.request();

				if(info.format != py::format_descriptor<float>::format()) throw py::type_error(
					"Expected float32 buffer"
				);

				// HATE...
				auto comps = static_cast<py::ssize_t>(array_components<T>());

				if(info.ndim == 1) {
					if(info.shape[0] % comps) throw py::value_error(
						"Flat array size must be divisible by component count"
					);
				}

				else if(info.ndim == 2) {
					if(info.shape[1] != comps) throw py::value_error(
						"Expected shape (N, " + std::to_string(comps) + ")"
					);
				}

				else throw py::type_error("Expected 1D or 2D buffer");

				auto count = static_cast<unsigned int>(
					(info.ndim == 1) ? info.shape[0] / comps : info.shape[0]
				);

				auto a = new T();

				a->resize(count);

				std::memcpy(
					const_cast<void*>(a->getDataPointer()),
					info.ptr,
					count * sizeof(typename T::ElementDataType)
				);

				return a;
			}))

			// .def("append", [](T& self, const T::ElementDataType& v) { self.push_back(v); })

			// https://pybind11.readthedocs.io/en/stable/advanced/pycpp/numpy.html
			.def_buffer([](T& self) -> py::buffer_info {
				auto n = static_cast<py::ssize_t>(self.size());

				// Number of components for each value of `n` above; for example, 1 if it's a "flat"
				// array of floats, 2 for Vec2, 3 for Vec3, etc.
				auto comps = static_cast<py::ssize_t>(self.getDataSize());

				// TODO: Why does this code SEGFAULT when this exception is thrown!? EVERY TIME.
				if(!BufferInfo.contains(self.getDataType())) {
					throw std::runtime_error("Unsupported osg::Array data type");

					// PyErr_SetString(PyExc_RuntimeError, "Unsupported Array data type");

					// return py::buffer_info();
				}

				auto [itemsize, fmt] = BufferInfo[self.getDataType()];

				if(comps == 1) return py::buffer_info(
					const_cast<void*>(self.getDataPointer()),
					itemsize,
					fmt,
					1,
					{ n },
					{ itemsize }
				);

				return py::buffer_info(
					const_cast<void*>(self.getDataPointer()),
					itemsize,
					fmt,
					2,
					{ n, comps },
					{ itemsize * comps, itemsize }
				);
			})

			.def("__len__", [](const T& self) { return self.size(); })

			.def("__getitem__", [](const T& self, py::ssize_t index) {
				return self[n_index(self.size(), index)];
			})

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
			}, py::keep_alive<0, 1>())

			.def("__setitem__", [](T& self, py::ssize_t index, const T::ElementDataType& value) {
				self[n_index(self.size(), index)] = value;
			})

			// TODO: BROADCAST and NON-BROADCAST slice assignment!
			// .def("__setitem__", [](T& self, py::ssize_t index, const T::ElementDataType& value) {

			.def("__repr__", [name](const T& self) {
				return py::str("{}(size={})").format(name, self.size());
			})

			.def("dump", [name](const T& self) {
				py::list items;

				size_t n = self.size();

				// TODO: Why did this fail?
				// items.reserve(n);

				for(size_t i = 0; i < n; ++i) items.append(py::repr(py::cast(self[i])));

				return py::str("{}({})").format( name, py::str(", ").attr("join")(items));
			})
		;
	}
}

void bind_Array(py::module_& m);

}
