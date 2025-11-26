#include "../OpenSceneGraph-python.hpp"

PYOSG_DISABLE_WARNINGS

#include <osg/Object>

PYOSG_ENABLE_WARNINGS

namespace pyosg {

void bind_Object(py::module_& m) {
	py::class_<osg::Object, osg::ref_ptr<osg::Object>>(m, "Object")
		.def_property_readonly("referenceCount", &osg::Object::referenceCount)
		.def_property("name", &osg::Object::getName, [](osg::Object* self, const std::string& name) {
			self->setName(name);
		})
		.def("ref", [](osg::Object* self) {
			self->ref();

			return self;
		})
		.def("unref", [](osg::Object* self) {
			self->unref();

			return self;
		})
	;
}

}
