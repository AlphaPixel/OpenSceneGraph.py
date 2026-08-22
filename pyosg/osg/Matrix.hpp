#pragma once

#include "../pyosg.hpp"

OSGX_DISABLE_WARNINGS

#include <osg/Matrix>

OSGX_ENABLE_WARNINGS

namespace pyosg {

namespace detail {
	template<typename T> struct MatrixTraits;

	template<> struct MatrixTraits<osg::Matrixf> {
		using Vec3 = osg::Vec3f;
	};

	template<> struct MatrixTraits<osg::Matrixd> {
		using Vec3 = osg::Vec3d;
	};

	template<typename T>
	auto bind_Matrix(py::module_& m, const char* name) {
		using value_type = typename T::value_type;

		auto mat = py::class_<T>(m, name)
			.def(py::init<>())
			.def(py::init<const T&>())
		;

		// So, it turns out that constructor order IS IMPORTANT! There's really way around these
		// checks on the "type" of `T` unless we moved the more aggressive `std::array`
		// constructors OUT of this helper...
		if constexpr(std::is_same_v<T, osg::Matrixf>) mat.def(py::init<const osg::Matrixd&>());

		else if constexpr(std::is_same_v<T, osg::Matrixd>) mat.def(py::init<const osg::Matrixf&>());

		mat
			.def(py::init<const osg::Quat&>())
			.def(py::init<
				value_type, value_type, value_type, value_type,
				value_type, value_type, value_type, value_type,
				value_type, value_type, value_type, value_type,
				value_type, value_type, value_type, value_type
			>())
			.def(py::init([](const std::array<value_type, 16>& vals) {
				return T(vals.data());
			}))

			// This is called by the operators below; it seems to return < 0 for "less than", equal
			// to 0 for "equal to", and greater than 0 for "not equal." I think.
			// TODO: Do we NEED this?
			.def("compare", &T::compare)
			.def(py::self < py::self)
			.def(py::self == py::self)
			.def(py::self != py::self)
			.def(py::self * py::self)
			.def("__imul__", [](T& self, const T& other) -> T& {
				self *= other;

				return self;
			}, py::return_value_policy::reference_internal)

			/* .def("preMult", py::overload_cast<const osg::Vec3f&>(&T::preMult))
			.def("preMult", py::overload_cast<const osg::Vec3d&>(&T::preMult))
			.def("preMult", py::overload_cast<const osg::Vec4f&>(&T::preMult))
			.def("preMult", py::overload_cast<const osg::Vec4d&>(&T::preMult))
			.def("postMult", py::overload_cast<const osg::Vec3f&>(&T::postMult))
			.def("preMult", py::overload_cast<const T&>(&T::preMult))
			.def("postMult", py::overload_cast<const T&>(&T::postMult)) */

			// Mirrors the OSG method of operator()(row, col) access.
			.def("__call__", [](T& self, py::ssize_t row, py::ssize_t col) {
				auto [r, c] = n_indices<int>(4, row, col);

				return self(r, c);
			})

			// A far more Pythonic interface where 2 indices are always specified.
			.def("__getitem__", [](const T& self, std::pair<py::ssize_t, py::ssize_t> rc) {
				auto [row, col] = n_indices<int>(4, rc.first, rc.second);

				return self(row, col);
			})

			/* .def("__getitem__", [](const T& self, py::object index) -> py::object {
				// (row, col)
				if(py::isinstance<py::tuple>(index)) {
					auto rc = index.cast<std::pair<size_t, size_t>>();
					auto [row, col] = n_indices<int>(4, rc.first, rc.second);
					return py::cast(self(row, col));
				}

				// row
				if(py::isinstance<py::int_>(index)) {
					int row = index.cast<int>();
					row = n_index<int>(4, row);

					return py::cast(typename MatrixTraits<T>::Vec4(
						self(row, 0),
						self(row, 1),
						self(row, 2),
						self(row, 3)
					));
				}

				throw py::type_error("Index must be int or (row, col)");
			}) */

			.def("__setitem__", [](T& self, std::pair<py::ssize_t, py::ssize_t> rc, value_type value) {
				auto [row, col] = n_indices<int>(4, rc.first, rc.second);

				return self(row, col) = value;
			})

			/* .def("__setitem__", [](T& self, py::object index, py::object value) {
				// (row, col)
				if(py::isinstance<py::tuple>(index)) {
					auto rc = index.cast<std::pair<size_t, size_t>>();
					auto [row, col] = n_indices<int>(4, rc.first, rc.second);

					self(row, col) = value.cast<value_type>();
					return;
				}

				// row
				if(py::isinstance<py::int_>(index)) {
					int row = index.cast<int>();
					row = n_index<int>(4, row);

					auto vec = value.cast<typename MatrixTraits<T>::Vec4>();

					self(row, 0) = vec[0];
					self(row, 1) = vec[1];
					self(row, 2) = vec[2];
					self(row, 3) = vec[3];
					return;
				}

				throw py::type_error("Index must be int or (row, col)");
			})

			.def("__len__", [](const T&) { return 4; }) */

			.def("__repr__", [name](const T& v) {
				return seq_repr<16>(name, [&](size_t i) {
					return v(static_cast<int>(i) / 4, i % 4);
				});
			})

			.def("valid", &T::valid)
			.def("isNaN", &T::isNaN)
			.def("isIdentity", &T::isIdentity)
			.def("makeIdentity", &T::makeIdentity)
			.def("makeScale", py::overload_cast<const osg::Vec3f&>(&T::makeScale))
			.def("makeScale", py::overload_cast<const osg::Vec3d&>(&T::makeScale))
			.def("makeScale", py::overload_cast<value_type, value_type, value_type>(&T::makeScale))
			.def("makeTranslate", py::overload_cast<const osg::Vec3f&>(&T::makeTranslate))
			.def("makeTranslate", py::overload_cast<const osg::Vec3d&>(&T::makeTranslate))
			.def("makeTranslate", py::overload_cast<
				value_type,
				value_type,
				value_type
			>(&T::makeTranslate))
			.def("makeRotate", py::overload_cast<
				const osg::Vec3f&,
				const osg::Vec3f&
			>(&T::makeRotate))
			.def("makeRotate", py::overload_cast<
				const osg::Vec3d&,
				const osg::Vec3d&
			>(&T::makeRotate))
			.def("makeRotate", py::overload_cast<value_type, const osg::Vec3f&>(&T::makeRotate))
			.def("makeRotate", py::overload_cast<value_type, const osg::Vec3d&>(&T::makeRotate))
			.def("makeRotate", py::overload_cast<
				value_type,
				value_type,
				value_type,
				value_type
			>(&T::makeRotate))
			.def("makeRotate", py::overload_cast<const osg::Quat&>(&T::makeRotate))
			.def("makeRotate", py::overload_cast<
				value_type, const osg::Vec3f&,
				value_type, const osg::Vec3f&,
				value_type, const osg::Vec3f&
			>(&T::makeRotate))
			.def("makeRotate", py::overload_cast<
				value_type, const osg::Vec3d&,
				value_type, const osg::Vec3d&,
				value_type, const osg::Vec3d&
			>(&T::makeRotate))
			.def("makeOrtho", py::overload_cast<
				double, double,
				double, double,
				double, double
			>(&T::makeOrtho))
			.def("makeOrtho2D", py::overload_cast<
				double, double,
				double, double
			>(&T::makeOrtho2D))
			.def("makeFrustum", &T::makeFrustum)
			.def("makePerspective", &T::makePerspective)
			.def("makeLookAt", &T::makeLookAt)
			.def("invert", &T::invert)
			.def("invert_4x3", &T::invert_4x3)
			.def("invert_4x4", &T::invert_4x4)
			.def("transpose", &T::transpose)
			.def("transpose3x3", &T::transpose3x3)
			.def("orthoNormalize", &T::orthoNormalize)

			.def("decompose", [](const T& self) {
				typename MatrixTraits<T>::Vec3 translation, scale;
				osg::Quat rotation, so;

				self.decompose(translation, rotation, scale, so);

				return py::make_tuple(translation, rotation, scale, so);
			})
			.def("getOrtho", [](const T& self) {
				value_type left, right, bottom, top, near, far;

				self.getOrtho(left, right, bottom, top, near, far);

				return py::make_tuple(left, right, bottom, top, near, far);
			})
			.def("getFrustum", [](const T& self) {
				value_type left, right, bottom, top, near, far;

				self.getFrustum(left, right, bottom, top, near, far);

				return py::make_tuple(left, right, bottom, top, near, far);
			})
			.def("getPerspective", [](const T& self) {
				value_type fovy, ar, near, far;

				self.getPerspective(fovy, ar, near, far);

				return py::make_tuple(fovy, ar, near, far);
			})
			.def("getLookAt", [](const T& self, value_type distance) {
				typename MatrixTraits<T>::Vec3 eye, center, up;

				self.getLookAt(eye, center, up, distance);

				return py::make_tuple(eye, center, up);
			}, "distance"_a=static_cast<value_type>(1.0))

			.def_static("identity", &T::identity)
			.def_static("scale", py::overload_cast<const osg::Vec3f&>(&T::scale))
			.def_static("scale", py::overload_cast<const osg::Vec3d&>(&T::scale))
			.def_static("scale", py::overload_cast<value_type, value_type, value_type>(&T::scale))
			.def_static("translate", py::overload_cast<const osg::Vec3f&>(&T::translate))
			.def_static("translate", py::overload_cast<const osg::Vec3d&>(&T::translate))
			.def_static("translate", py::overload_cast<
				value_type,
				value_type,
				value_type
			>(&T::translate))
			.def_static("rotate", py::overload_cast<
				const osg::Vec3f&,
				const osg::Vec3f&
			>(&T::rotate))
			.def_static("rotate", py::overload_cast<
				const osg::Vec3d&,
				const osg::Vec3d&
			>(&T::rotate))
			.def_static("rotate", py::overload_cast<value_type, const osg::Vec3f&>(&T::rotate))
			.def_static("rotate", py::overload_cast<value_type, const osg::Vec3d&>(&T::rotate))
			.def_static("rotate", py::overload_cast<
				value_type,
				value_type,
				value_type,
				value_type
			>(&T::rotate))
			.def_static("rotate", py::overload_cast<const osg::Quat&>(&T::rotate))
			.def_static("rotate", py::overload_cast<
				value_type, const osg::Vec3f&,
				value_type, const osg::Vec3f&,
				value_type, const osg::Vec3f&
			>(&T::rotate))
			.def_static("rotate", py::overload_cast<
				value_type, const osg::Vec3d&,
				value_type, const osg::Vec3d&,
				value_type, const osg::Vec3d&
			>(&T::rotate))
			.def_static("inverse", &T::inverse)
			.def_static("orthoNormal", &T::orthoNormal)

			.def_static("ortho", &T::ortho)
			.def_static("ortho2D", &T::ortho2D)
			.def_static("frustum", &T::frustum)
			.def_static("perspective", &T::perspective)
			.def_static("lookAt", py::overload_cast<
				const osg::Vec3f&,
				const osg::Vec3f&,
				const osg::Vec3f&
			>(&T::lookAt))
			.def_static("lookAt", py::overload_cast<
				const osg::Vec3d&,
				const osg::Vec3d&,
				const osg::Vec3d&
			>(&T::lookAt))
		;

		return mat;
	}
}

void bind_Matrix(py::module_& m);

}
