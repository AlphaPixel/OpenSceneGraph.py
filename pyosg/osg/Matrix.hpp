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

		auto mat = py::class_<T>(
			m,
			name,
			"A 4x4 row-major transformation matrix; manual GLSL uniform uploads need the "
			"REVERSED multiply order vs plain GL (see feedback_osg_matrix_order)."
		)
			.def(py::init<>(), "Create an uninitialized matrix (NOT identity - call makeIdentity() or use Matrix.identity()).")
			.def(py::init<const T&>(), "Create a copy of another matrix.")
		;

		// So, it turns out that constructor order IS IMPORTANT! There's really way around these
		// checks on the "type" of `T` unless we moved the more aggressive `std::array`
		// constructors OUT of this helper...
		if constexpr(std::is_same_v<T, osg::Matrixf>) mat.def(py::init<const osg::Matrixd&>(),
			"Create a Matrixf by narrowing a Matrixd."
		);

		else if constexpr(std::is_same_v<T, osg::Matrixd>) mat.def(py::init<const osg::Matrixf&>(),
			"Create a Matrixd by widening a Matrixf."
		);

		mat
			.def(py::init<const osg::Quat&>(), "Create a pure-rotation matrix from a quaternion.")
			.def(py::init<
				value_type, value_type, value_type, value_type,
				value_type, value_type, value_type, value_type,
				value_type, value_type, value_type, value_type,
				value_type, value_type, value_type, value_type
			>(), "Create a matrix from its 16 elements in row-major order.")
			.def(py::init([](const std::array<value_type, 16>& vals) {
				return T(vals.data());
			}), "Create a matrix from a flat 16-element sequence in row-major order.")

			// This is called by the operators below; it seems to return < 0 for "less than", equal
			// to 0 for "equal to", and greater than 0 for "not equal." I think.
			// TODO: Do we NEED this?
			.def("compare", &T::compare,
				"Element-wise lexicographic compare; <0/0/>0 for less-than/equal/greater-than, "
				"used to implement the comparison operators below."
			)
			.def(py::self < py::self)
			.def(py::self == py::self)
			.def(py::self != py::self)
			.def(py::self * py::self)
			.def("__imul__", [](T& self, const T& other) -> T& {
				self *= other;

				return self;
			}, py::return_value_policy::reference_internal, "In-place matrix multiply (self *= other).")

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
			}, "Return the element at (row, col), matching OSG's operator()(row, col).")

			// A far more Pythonic interface where 2 indices are always specified.
			.def("__getitem__", [](const T& self, std::pair<py::ssize_t, py::ssize_t> rc) {
				auto [row, col] = n_indices<int>(4, rc.first, rc.second);

				return self(row, col);
			}, "Return the element at mat[row, col] (negative indices count from the end).")

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
			}, "Set mat[row, col] (negative indices count from the end).")

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
			}, "Return a constructor-style representation of this matrix's 16 elements.")

			.def("valid", &T::valid, "Return whether every element is a finite, non-NaN number.")
			.def("isNaN", &T::isNaN, "Return whether any element is NaN.")
			.def("isIdentity", &T::isIdentity, "Return whether this is the identity matrix.")
			.def("makeIdentity", &T::makeIdentity, "Overwrite this matrix in place with the identity.")
			.def("makeScale", py::overload_cast<const osg::Vec3f&>(&T::makeScale),
				"Overwrite this matrix in place with a pure scale transform."
			)
			.def("makeScale", py::overload_cast<const osg::Vec3d&>(&T::makeScale))
			.def("makeScale", py::overload_cast<value_type, value_type, value_type>(&T::makeScale))
			.def("makeTranslate", py::overload_cast<const osg::Vec3f&>(&T::makeTranslate),
				"Overwrite this matrix in place with a pure translation transform."
			)
			.def("makeTranslate", py::overload_cast<const osg::Vec3d&>(&T::makeTranslate))
			.def("makeTranslate", py::overload_cast<
				value_type,
				value_type,
				value_type
			>(&T::makeTranslate))
			.def("makeRotate", py::overload_cast<
				const osg::Vec3f&,
				const osg::Vec3f&
			>(&T::makeRotate), "Overwrite this matrix in place with a pure rotation transform.")
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
			>(&T::makeOrtho), "Overwrite this matrix in place with an orthographic projection.")
			.def("makeOrtho2D", py::overload_cast<
				double, double,
				double, double
			>(&T::makeOrtho2D), "Overwrite this matrix in place with a 2D orthographic projection.")
			.def("makeFrustum", &T::makeFrustum,
				"Overwrite this matrix in place with an off-axis perspective frustum projection."
			)
			.def("makePerspective", &T::makePerspective,
				"Overwrite this matrix in place with a symmetric perspective projection "
				"(fovy in degrees)."
			)
			.def("makeLookAt", &T::makeLookAt,
				"Overwrite this matrix in place with a view matrix looking from eye toward "
				"center, with the given up vector."
			)
			.def("invert", &T::invert, "Overwrite this matrix in place with its general inverse.")
			.def("invert_4x3", &T::invert_4x3,
				"Overwrite this matrix in place with its inverse, assuming it's a pure "
				"rotation/translation (no scale/skew/projection) - cheaper than invert()."
			)
			.def("invert_4x4", &T::invert_4x4,
				"Overwrite this matrix in place with its full general 4x4 inverse."
			)
			.def("transpose", &T::transpose, "Overwrite this matrix in place with its transpose.")
			.def("transpose3x3", &T::transpose3x3,
				"Transpose only the upper-left 3x3 (rotation/scale) block in place, leaving "
				"translation untouched."
			)
			.def("orthoNormalize", &T::orthoNormalize,
				"Overwrite this matrix in place with the orthonormalized version of another "
				"(removes scale/skew, keeping pure rotation + translation)."
			)

			.def("decompose", [](const T& self) {
				typename MatrixTraits<T>::Vec3 translation, scale;
				osg::Quat rotation, so;

				self.decompose(translation, rotation, scale, so);

				return py::make_tuple(translation, rotation, scale, so);
			}, "Decompose this matrix into a (translation, rotation, scale, scaleOrientation) tuple.")
			.def("getOrtho", [](const T& self) {
				value_type left, right, bottom, top, near, far;

				self.getOrtho(left, right, bottom, top, near, far);

				return py::make_tuple(left, right, bottom, top, near, far);
			}, "Return this orthographic projection's (left, right, bottom, top, near, far) planes.")
			.def("getFrustum", [](const T& self) {
				value_type left, right, bottom, top, near, far;

				self.getFrustum(left, right, bottom, top, near, far);

				return py::make_tuple(left, right, bottom, top, near, far);
			}, "Return this frustum projection's (left, right, bottom, top, near, far) planes.")
			.def("getPerspective", [](const T& self) {
				value_type fovy, ar, near, far;

				self.getPerspective(fovy, ar, near, far);

				return py::make_tuple(fovy, ar, near, far);
			}, "Return this perspective projection's (fovy_degrees, aspectRatio, near, far).")
			.def("getLookAt", [](const T& self, value_type distance) {
				typename MatrixTraits<T>::Vec3 eye, center, up;

				self.getLookAt(eye, center, up, distance);

				return py::make_tuple(eye, center, up);
			}, "distance"_a=static_cast<value_type>(1.0),
				"Decompose this view matrix into an (eye, center, up) tuple, placing center "
				"`distance` units in front of eye."
			)

			.def_static("identity", &T::identity, "Return a new identity matrix.")
			.def_static("scale", py::overload_cast<const osg::Vec3f&>(&T::scale),
				"Return a new pure-scale matrix."
			)
			.def_static("scale", py::overload_cast<const osg::Vec3d&>(&T::scale))
			.def_static("scale", py::overload_cast<value_type, value_type, value_type>(&T::scale))
			.def_static("translate", py::overload_cast<const osg::Vec3f&>(&T::translate),
				"Return a new pure-translation matrix."
			)
			.def_static("translate", py::overload_cast<const osg::Vec3d&>(&T::translate))
			.def_static("translate", py::overload_cast<
				value_type,
				value_type,
				value_type
			>(&T::translate))
			.def_static("rotate", py::overload_cast<
				const osg::Vec3f&,
				const osg::Vec3f&
			>(&T::rotate), "Return a new pure-rotation matrix.")
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
			.def_static("inverse", &T::inverse, "Return a new matrix that is the inverse of another.")
			.def_static("orthoNormal", &T::orthoNormal,
				"Return a new orthonormalized copy of another matrix (removes scale/skew)."
			)

			.def_static("ortho", &T::ortho, "Return a new orthographic projection matrix.")
			.def_static("ortho2D", &T::ortho2D, "Return a new 2D orthographic projection matrix.")
			.def_static("frustum", &T::frustum,
				"Return a new off-axis perspective frustum projection matrix."
			)
			.def_static("perspective", &T::perspective,
				"Return a new symmetric perspective projection matrix (fovy in degrees)."
			)
			.def_static("lookAt", py::overload_cast<
				const osg::Vec3f&,
				const osg::Vec3f&,
				const osg::Vec3f&
			>(&T::lookAt), "Return a new view matrix looking from eye toward center, with the given up vector.")
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
