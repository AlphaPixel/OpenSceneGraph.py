#include "osg.hpp"

#include <limits>

namespace pyosg {

void bind(py::module_& m) {
	m.attr("F32_MAX") = std::numeric_limits<float>::max();
	m.attr("F32_MIN") = std::numeric_limits<float>::lowest(); // most negative
	m.attr("F32_TINY") = std::numeric_limits<float>::min(); // smallest +normal

	m.attr("F64_MAX") = std::numeric_limits<double>::max();
	m.attr("F64_MIN") = std::numeric_limits<double>::lowest();
	m.attr("F64_TINY") = std::numeric_limits<double>::min();

	bind_Notify(m);
	bind_Vec(m);
	bind_Matrix(m);
	bind_Bound(m);
	bind_Object(m);
	bind_Buffer(m);
	bind_Array(m);
	bind_Node(m);
	bind_NodeVisitor(m);
	bind_NodeCallback(m);
	bind_Drawable(m);
	bind_Geometry(m);
	bind_Group(m);
	bind_Geode(m);
	bind_Shape(m);
	bind_View(m);
	bind_State(m);
}

}
