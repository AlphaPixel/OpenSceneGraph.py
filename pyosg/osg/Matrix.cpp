#include "Matrix.hpp"

namespace pyosg {

void bind_Matrix(py::module_& m) {
	auto md = detail::bind_Matrix<osg::Matrixd>(m, "Matrixd");
	auto mf = detail::bind_Matrix<osg::Matrixf>(m, "Matrixf");

#ifdef OSG_USE_FLOAT_MATRIX
	m.add_object("Matrix", mf);
#else
	m.add_object("Matrix", md);
#endif
}

}
