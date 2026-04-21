#include "pyosg.hpp"
#include "osg/ArgumentParser.hpp"
#include "osg/Notify.hpp"
#include "osg/Array.hpp"
#include "osg/Bound.hpp"
#include "osg/Buffer.hpp"
#include "osg/Camera.hpp"
#include "osg/Drawable.hpp"
#include "osg/Geode.hpp"
#include "osg/Geometry.hpp"
#include "osg/Group.hpp"
#include "osg/Matrix.hpp"
#include "osg/Node.hpp"
#include "osg/NodeVisitor.hpp"
#include "osg/NodeCallback.hpp"
#include "osg/Object.hpp"
#include "osg/Program.hpp"
#include "osg/State.hpp"
#include "osg/Texture.hpp"
#include "osg/Uniform.hpp"
#include "osg/Vec.hpp"

namespace pyosg {

void bind(py::module_& m) {
	bind_ArgumentParser(m);
	bind_Notify(m);
	bind_Vec(m);
	bind_Quat(m);
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
	bind_Texture(m);
	bind_GraphicsContext(m);
}

}
