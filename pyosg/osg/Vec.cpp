#include "Vec.hpp"

namespace pyosg {

void bind_Vec(py::module_& m) {
	detail::bind_Vec<osg::Vec2d, 2>(m, "Vec2d");
	detail::bind_Vec<osg::Vec3d, 3>(m, "Vec3d");
	detail::bind_Vec<osg::Vec4d, 4>(m, "Vec4d");

	detail::bind_alias_Vec<osg::Vec2f, 2>(m, "Vec2f", "Vec2");
	detail::bind_alias_Vec<osg::Vec3f, 3>(m, "Vec3f", "Vec3");
	detail::bind_alias_Vec<osg::Vec4f, 4>(m, "Vec4f", "Vec4");
}

}
