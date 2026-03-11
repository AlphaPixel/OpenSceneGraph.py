#include "pyosg.hpp"

namespace pyosg {

void bind(py::module_& m) {
	bind_ArgumentParser(m);
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
	bind_Transform(m);
	bind_Geode(m);
	bind_Shape(m);
	bind_View(m);
	bind_Camera(m);
	bind_State(m);
	bind_StateAttributes(m);
	bind_Uniform(m);
	bind_Shader(m);
	bind_Program(m);
	bind_GraphicsContext(m);
}

}
