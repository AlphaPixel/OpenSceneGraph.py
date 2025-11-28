#include "../osg.hpp"

PYOSG_DISABLE_WARNINGS

#include <osg/Matrix>

PYOSG_ENABLE_WARNINGS

namespace pyosg {

namespace detail {
	template<size_t N, std::integral... Args>
	constexpr void assert_indices(Args... args) {
		// if(!((args >= 0 && args < static_cast<int>(N)) && ...)) {
		if(!((args >= 0 && args < N) && ...)) {
			throw py::index_error("indices not in range 0-"s + std::to_string(N - 1));
		}
	}

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

		return py::class_<T>(m, name)
			.def(py::init<>())
			.def(py::init([](const std::array<value_type, 16>& vals) {
				return T(vals.data());
			}))
			.def(py::init<
				value_type, value_type, value_type, value_type,
				value_type, value_type, value_type, value_type,
				value_type, value_type, value_type, value_type,
				value_type, value_type, value_type, value_type
			>())
			.def(py::init<const osg::Quat&>())
			.def(py::init<const T&>())

			// This is called by the operators below; it seems to return < 0 for "less than", equal
			// to 0 for "equal to", and greater than 0 for "not equal." I think.
			// TODO: Do we NEED this?
			.def("compare", &T::compare)
			.def(py::self < py::self)
			.def(py::self == py::self)
			.def(py::self != py::self)

			// Mirrors the OSG method of operator()(row, col) access.
			.def("__call__", [](T& self, size_t row, size_t col) {
				assert_indices<4>(row, col);

				return self(static_cast<int>(row), static_cast<int>(col));
			})

			// A far more Pythonic interface where 2 indices are always specified.
			.def("__getitem__", [](const T& self, std::pair<size_t, size_t> rc) {
				auto [row, col] = rc;

				assert_indices<4>(row, col);

				return self(static_cast<int>(row), static_cast<int>(col));
			})

			.def("__setitem__", [](T& self, std::pair<size_t, size_t> rc, value_type value) {
				auto [row, col] = rc;

				assert_indices<4>(row, col);

				self(static_cast<int>(row), static_cast<int>(col)) = value;
			})

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
			/* .def("getOrtho", py::overload_cast<
				value_type&, value_type&,
				value_type&, value_type&,
				value_type&, value_type&
			>(&T::getOrtho)) */

#if 0
			void makeOrtho(double left,   double right,
				double bottom, double top,
				double zNear,  double zFar);

			bool getOrtho(double& left,   double& right,
				double& bottom, double& top,
				double& zNear,  double& zFar) const;

			bool getOrtho(float& left,   float& right,
				float& bottom, float& top,
				float& zNear,  float& zFar) const;

			inline void makeOrtho2D(double left,   double right,
				double bottom, double top)

			void makeFrustum(double left,   double right,
				double bottom, double top,
				double zNear,  double zFar);

			bool getFrustum(double& left,   double& right,
				double& bottom, double& top,
				double& zNear,  double& zFar) const;

			bool getFrustum(float& left,   float& right,
				float& bottom, float& top,
				float& zNear,  float& zFar) const;

			void makePerspective(double fovy,  double aspectRatio,
				double zNear, double zFar);

			bool getPerspective(double& fovy,  double& aspectRatio,
				double& zNear, double& zFar) const;

			bool getPerspective(float& fovy,  float& aspectRatio,
				float& zNear, float& zFar) const;

			void makeLookAt(const Vec3d& eye,const Vec3d& center,const Vec3d& up);

			void getLookAt(Vec3f& eye,Vec3f& center,Vec3f& up,
				value_type lookDistance=1.0f) const;

			void getLookAt(Vec3d& eye,Vec3d& center,Vec3d& up,
				value_type lookDistance=1.0f) const;

			inline bool invert( const Matrixf& rhs)

			bool invert_4x3( const Matrixf& rhs);

			bool invert_4x4( const Matrixf& rhs);

			bool transpose(const Matrixf&rhs);

			bool transpose3x3(const Matrixf&rhs);

			void orthoNormalize(const Matrixf& rhs);
#endif

			/* .def("decompose", py::overload_cast<
				osg::Vec3f&,
				osg::Quat&,
				osg::Vec3f&,
				osg::Quat&
			>(&T::decompose, py::const_))
			.def("decompose", py::overload_cast<
				osg::Vec3d&,
				osg::Quat&,
				osg::Vec3d&,
				osg::Quat&
			>(&T::decompose, py::const_)) */

			.def("decompose", [](const T& self) {
				typename MatrixTraits<T>::Vec3 translation, scale;
				osg::Quat rotation, so;

				self.decompose(translation, rotation, scale, so);

				return py::make_tuple(translation, rotation, scale, so);
			})

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

			// .def_static("ortho", &T::ortho)
			// .def_static("ortho2D", &T::ortho2D)
			// .def_static("frustum", &T::frustum)
			// .def_static("perspective", &T::perspective)
			// .def_static("lookAt", &T::lookAt)
		;
	}
}

void bind_Matrix(py::module_& m) {
	auto mf = detail::bind_Matrix<osg::Matrixf>(m, "Matrixf");
	auto md = detail::bind_Matrix<osg::Matrixd>(m, "Matrixd");

#ifdef OSG_USE_FLOAT_MATRIX
	m.add_object("Matrix", mf);
#else
	m.add_object("Matrix", md);
#endif
}

}
