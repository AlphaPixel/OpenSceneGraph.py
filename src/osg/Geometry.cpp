#include "../pyosg.hpp"

PYOSG_DISABLE_WARNINGS

#include <osg/Geometry>

PYOSG_ENABLE_WARNINGS

namespace pyosg {

namespace detail {
	/* template<>
	void kwargs_init(osg::Object& self, const py::kwargs& kwargs) {
		if(kwargs.contains("name")) self.setName(kwargs["name"].cast<std::string>());
	} */
}

void bind_Geometry(py::module_& m) {
	py::class_<osg::Geometry, osg::Drawable, osg::ref_ptr<osg::Geometry>>(m, "Geometry")
		.def(py::init<>())
	;
}

}
