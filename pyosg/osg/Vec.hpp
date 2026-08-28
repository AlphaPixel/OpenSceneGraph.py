#pragma once

#include "../pyosg.hpp"

OSGX_DISABLE_WARNINGS

#include <osg/Vec4f>
#include <osg/Vec4d>

OSGX_ENABLE_WARNINGS

namespace pyosg {

namespace detail {
	template<typename T, size_t I>
	constexpr auto vec_get() { return [](const T& v) -> typename T::value_type { return v[I]; }; }

	template<typename T, size_t I>
	constexpr auto vec_set() { return [](T& v, typename T::value_type val) { v[I] = val; }; }

	template<typename T, size_t N>
	auto bind_Vec(py::module_& m, const char* name) {
		using value_type = typename T::value_type;

		auto vec = py::class_<T>(
			m,
			name,
			"A fixed-size float/double vector (2, 3, or 4 components); the workhorse type for "
			"positions, directions, and colors throughout this library."
		)
			.def(py::init<>(), "Create a zero vector.")
			.def(py::init<const T&>(), "Create a copy of another vector.")
		;

		vec
			.def(py::self + py::self)
			.def(py::self - py::self)
			.def(py::self * value_type())
			.def(py::self / value_type())
			.def(py::self += py::self)
			.def(py::self -= py::self)
			.def(py::self *= value_type())
			.def(py::self /= value_type())
			.def(-py::self)

			.def("length", &T::length, "Return the vector's Euclidean length.")
			.def("length2", &T::length2, "Return the square of the vector's Euclidean length.")
			.def("normalize", &T::normalize, "Scale this vector in place to unit length.")
			.def("normalized", [](const T& v) {
				T tmp = v;

				tmp.normalize();

				return tmp;
			}, "Return a unit-length copy of this vector, leaving it unmodified.")

			// Here's some Python-only syntactic sugar for allowing stuff like `2 * vec`, which is
			// normally NOT allowed in OSG. :)
			.def("__rmul__", [](const T& v, value_type s) {
				return v * s;
			}, "Support scalar * vector (OSG itself only defines vector * scalar).")

			.def("__eq__", [](const T& a, const T& b) { return a == b; },
				"Return whether every component equals those of another vector."
			)

			.def("__len__", [](const T&){ return N; }, "Return the number of components.")

			.def("__iter__", [](const T& v){
				py::tuple t(N);

				OSGX_DISABLE_WARNINGS

					for(size_t i = 0; i < N; i++) t[i] = v[i];

				OSGX_ENABLE_WARNINGS

				return py::iter(t);
			}, "Iterate over the vector's components in order.")

			.def("__repr__", [name](const T& v) {
				return seq_repr<N>(name, [&](size_t i) {
					OSGX_DISABLE_WARNINGS

						return v[i];

					OSGX_ENABLE_WARNINGS
				});

				/* py::list items;

				for(size_t i = 0; i < N; i++) {
					OSGX_DISABLE_WARNINGS

						// No matter WHAT the value_type is, lets give Python a double... a nice
						// side-effect of how Python handles float-point numbers is that the
						// `repr()` value of any true float-based type will CLEARLY indicate how a
						// true 32bit float will look to the GPU!
						auto val = py::float_(static_cast<double>(v[i]));

					OSGX_ENABLE_WARNINGS

					items.append(py::repr(val));
				}

				return py::str("{}({})").format(name, py::str(", ").attr("join")(items)); */
			}, "Return a constructor-style representation of this vector.")

			// XXX: It turns out that `Vec * Vec` returns a SCALAR in C++, which is all fine and
			// dandy. HOWEVER, in pybind11, if we wanted to emulate this syntax, we'd need to add a
			// non-trivial amount of `py::args` logic, which adds unacceptable runtime overhead.
			// Yes, we COULD do it by overriding `__mul__`, but pybind11 only allows PYTHON OBJECTS
			// to be passed into those overloads, and we really don't want to be dealing with that
			// every single time someone needs a dot-product.
			.def("dot", [](const T& a, const T& b) {
				return a * b;
			}, "Return the dot product with another vector.")
		;

		OSGX_DISABLE_WARNINGS

			vec
				.def("__getitem__", [](const T& v, py::ssize_t i) {
					return v[n_index(N, i)];
				}, "Return the component at index (negative indices count from the end).")

				.def("__setitem__", [](T& v, py::ssize_t i, value_type val){
					v[n_index(N, i)] = val;
				}, "Set the component at index (negative indices count from the end).")
			;

		OSGX_ENABLE_WARNINGS

		// Now we're going to start defining CONDITIONAL comile-time methods, based on the value of
		// the template parameter N; I really love modern C++.

		// First, we'll add some properties; everything has an `x`.
		// vec.def_property("x", [](T& v){ return v[0]; }, [](T& v, value_type val){ v[0] = val; })
		vec.def_property("x", vec_get<T, 0>(), vec_set<T, 0>(), "The vector's first component.");
		vec.def_property("y", vec_get<T, 1>(), vec_set<T, 1>(), "The vector's second component.");

		/* // Add a `y` when there's at least 2 elements.
		if constexpr(N > 1) {
			vec.def_property("y", vec_get<T, 1>(), vec_set<T, 1>());
		} */

		// Add a `z` when there's at least 3 elements.
		if constexpr(N > 2) {
			vec.def_property("z", vec_get<T, 2>(), vec_set<T, 2>(), "The vector's third component.");
		}

		// Add a `w` when there's at least 4 elements.
		if constexpr(N > 3) {
			vec.def_property("w", vec_get<T, 3>(), vec_set<T, 3>(), "The vector's fourth component.");
		}

		// Now we're going to add UNIQUE methods based on the number of elements...
		if constexpr(N == 2) {
			vec.def(py::init<value_type, value_type>(), "Create a vector from its x, y components.");

			if constexpr(std::is_same_v<T, osg::Vec2d>) vec.def(py::init<const osg::Vec2f>(),
				"Create a Vec2d by widening a Vec2f."
			);

			else if constexpr(std::is_same_v<T, osg::Vec2f>) vec.def(py::init<const osg::Vec2d&>(),
				"Create a Vec2f by narrowing a Vec2d."
			);
		}

		else if constexpr(N == 3) {
			vec.def(py::init<value_type, value_type, value_type>(),
				"Create a vector from its x, y, z components."
			);

			if constexpr(std::is_same_v<T, osg::Vec3d>) vec.def(py::init<const osg::Vec3f>(),
				"Create a Vec3d by widening a Vec3f."
			);

			else if constexpr(std::is_same_v<T, osg::Vec3f>) vec.def(py::init<const osg::Vec3d&>(),
				"Create a Vec3f by narrowing a Vec3d."
			);

			vec.def("cross", [](const T& a, const T& b) {
				// OSG defines operator^(Vec3) as cross product...
				return a ^ b;
			}, "Return the cross product with another 3-vector.");

			// TODO: This imitates OSG's dot product behavior, but feels weird because `dot` already
			// exists! We COULD make a `__mult__` override for `dot`, but that would add some crazy
			// overhead... I just don't know.
			// .def("__xor__", [](const T& a, const T& b) {
			// 	return a ^ b;
			// })
		}

		else if constexpr(N == 4) {
			vec.def(py::init<value_type, value_type, value_type, value_type>(),
				"Create a vector from its x, y, z, w components."
			);

			if constexpr(std::is_same_v<T, osg::Vec4d>) vec.def(py::init<const osg::Vec4f>(),
				"Create a Vec4d by widening a Vec4f."
			);

			else if constexpr(std::is_same_v<T, osg::Vec4f>) vec.def(py::init<const osg::Vec4d&>(),
				"Create a Vec4f by narrowing a Vec4d."
			);
		}

		return vec;
	}

	template<typename T, size_t N>
	auto bind_alias_Vec(py::module_& m, const char* name, const char* alias) {
		auto v = bind_Vec<T, N>(m, name);

		m.add_object(alias, v);
	}
}

void bind_Vec(py::module_& m);

}
