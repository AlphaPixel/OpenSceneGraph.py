#include "../pyosg.hpp"

PYOSG_DISABLE_WARNINGS

#include <osg/Viewport>

PYOSG_ENABLE_WARNINGS

namespace pyosg {

// namespace detail {}

void bind_StateAttributes(py::module_& m) {
	py::class_<
		osg::Viewport,
		osg::StateAttribute,
		osg::ref_ptr<osg::Viewport>
	>(m, "Viewport")
		.def(py::init<>())
		.def(py::init<
			osg::Viewport::value_type,
			osg::Viewport::value_type,
			osg::Viewport::value_type,
			osg::Viewport::value_type
		>())
		.def(py::init<const osg::Viewport&>())
		.def_property(
			"x",
			py::overload_cast<>(&osg::Viewport::x, py::const_),
			[](osg::Viewport& self, osg::Viewport::value_type x) { self.x() = x; }
		)
		.def_property(
			"y",
			py::overload_cast<>(&osg::Viewport::y, py::const_),
			[](osg::Viewport& self, osg::Viewport::value_type y) { self.y() = y; }
		)
		.def_property(
			"width",
			py::overload_cast<>(&osg::Viewport::width, py::const_),
			[](osg::Viewport& self, osg::Viewport::value_type w) { self.width() = w; }
		)
		.def_property(
			"height",
			py::overload_cast<>(&osg::Viewport::height, py::const_),
			[](osg::Viewport& self, osg::Viewport::value_type h) { self.height() = h; }
		)
		.def_property_readonly("valid", &osg::Viewport::valid)
		.def_property_readonly("aspectRatio", &osg::Viewport::aspectRatio)
		.def("computeWindowMatrix", &osg::Viewport::computeWindowMatrix)
		.def("__repr__", [](const osg::Viewport& self) {
			return py::str("Viewport({}, {}, {}, {})").format(
				self.x(),
				self.y(),
				self.width(),
				self.height()
			);
		})
	;
}

}
