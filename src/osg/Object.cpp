#include "../pyosg.hpp"

PYOSG_DISABLE_WARNINGS

#include <osg/Object>

PYOSG_ENABLE_WARNINGS

namespace pyosg {

namespace detail {
	template<>
	void kwargs_init(osg::Object& self, const py::kwargs& kwargs) {
		if(kwargs.contains("name")) self.setName(kwargs["name"].cast<std::string>());
	}
}

void bind_Object(py::module_& m) {
	py::class_<osg::Referenced, osg::ref_ptr<osg::Referenced>>(m, "Referenced")
		.def_property_readonly("referenceCount", &osg::Referenced::referenceCount)
		.def("ref", [](osg::Referenced& self) { return self.ref(); })
		.def("unref", [](osg::Referenced& self) { return self.unref(); })
	;

	py::class_<osg::Object, osg::Referenced, osg::ref_ptr<osg::Object>>(m, "Object")
		/* .def_property("name", &osg::Object::getName, [](osg::Object& self, const std::string& name) {
			self.setName(name);
		}) */
		.def_property("name",
			&osg::Object::getName,
			py::overload_cast<const char*>(&osg::Object::setName)
		)
	;
}

}
