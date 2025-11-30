#include "osg.hpp"

namespace pyosg {

void bind(py::module_& m) {
	bind_Notify(m);
	bind_Vec(m);
	bind_Matrix(m);
	bind_Bound(m);
	bind_Object(m);
	bind_Node(m);
	bind_NodeVisitor(m);
	bind_NodeCallback(m);
	bind_Drawable(m);
	bind_Group(m);
	bind_Geode(m);
	bind_Shape(m);
	bind_View(m);
	bind_State(m);
}

}
