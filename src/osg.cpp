#include "osg.hpp"

namespace pyosg {

void bind(py::module_& m) {
	bind_Object(m);
	bind_Node(m);
	bind_NodeVisitor(m);
	bind_NodeCallback(m);
	bind_Group(m);
	bind_View(m);
}

}
