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

	template<typename T>
	auto bind_Matrix(py::module_& m, const char* name) {
		using value_type = typename T::value_type;

		return py::class_<T>(m, name)
			.def(py::init<>())
			// .def(py::init<const std::array<value_type, 16>&>())
			.def(py::init([](const std::array<value_type, 16>& vals) {
				return T(vals.data());
			}))
			.def(py::init<
				value_type, value_type, value_type, value_type,
				value_type, value_type, value_type, value_type,
				value_type, value_type, value_type, value_type,
				value_type, value_type, value_type, value_type
			>())
			.def(py::init<const T&>())
			// init: from Quat

			// compare
			// operator<
			// operator==
			// operator!=

			// element access [][]
			.def("__call__", [](T& self, size_t row, size_t col) {
				assert_indices<4>(row, col);

				return self(static_cast<int>(row), static_cast<int>(col));
			})

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

			// valid
			// isNan

			// make{Identity,Scale,Translate,Rotate
			// decompose

			// .def_static("identity"
			// .def_static("scale"
			// .def_static("translate"
			// .def_static("rotate"
			// .def_static("inverse"
			// .def_static("orthoNormal"
			// .def_static("ortho"
			// .def_static("ortho2D"
			// .def_static("frustum"
			// .def_static("perspective"
			// .def_static("lookAt"
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
