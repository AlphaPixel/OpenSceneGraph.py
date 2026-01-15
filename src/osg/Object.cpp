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
	// auto collections = py::module_::import("collections");
	// m.attr("RefCounts") = collections.attr("namedtuple")("RefCounts", py::make_tuple("cpp", "py"));

	py::object RefCounts = py::module_::import("collections").attr("namedtuple")(
		"RefCounts",
		py::make_tuple("cpp", "py")
	);

	m.attr("RefCounts") = RefCounts;

	py::class_<osg::Referenced, osg::ref_ptr<osg::Referenced>>(m, "Referenced")
		.def("ref", [](osg::Referenced& self) { return self.ref(); })
		.def("unref", [](osg::Referenced& self) { return self.unref(); })
		// .def_property_readonly("referenceCount", &osg::Referenced::referenceCount)
		// This returns both the `osg::Referenced` value AND the value reported by CPython. Remember
		// that the value returned by CPython is always +1 greater than you might expect!
		.def_property_readonly("referenceCount", [RefCounts](py::handle h) {
			auto& self = h.cast<osg::Referenced&>();

			return RefCounts(self.referenceCount(), h.ref_count());
		})
		.def_property_readonly(
			"addr",
			[](const osg::Referenced& self) { return reinterpret_cast<uintptr_t>(&self); }
		);
	;

	py::class_<osg::Object, osg::Referenced, osg::ref_ptr<osg::Object>>(m, "Object")
		.def_property("name",
			&osg::Object::getName,
			py::overload_cast<const char*>(&osg::Object::setName)
		)
	;
}

}
