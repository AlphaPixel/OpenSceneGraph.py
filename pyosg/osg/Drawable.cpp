#include "Drawable.hpp"

namespace pyosg {

namespace detail {
	template<>
	void kwargs_init(osg::Drawable& self, const py::kwargs& kwargs) {
	}
}

void bind_Drawable(py::module_& m) {
	py::class_<osg::RenderInfo>(m, "RenderInfo")
		.def_property_readonly("contextID", &osg::RenderInfo::getContextID)
		// TODO: Add setter support!?
		.def_property_readonly("state",
			py::overload_cast<>(&osg::RenderInfo::getState),
			py::return_value_policy::reference
		)
		// TODO: Add setter support!?
		.def_property_readonly("view",
			py::overload_cast<>(&osg::RenderInfo::getView),
			py::return_value_policy::reference
		)
	;

	auto drawable = py::class_<
		osg::Drawable,
		detail::Drawable,
		osg::Node,
		osg::ref_ptr<osg::Drawable>
	>(m, "Drawable");

	py::class_<
		osg::Drawable::DrawCallback,
		detail::Drawable::DrawCallback,
		osg::Object,
		osg::ref_ptr<osg::Drawable::DrawCallback>
	>(drawable, "DrawCallback")
		.def(py::init<>())
	;

	drawable
		// .def(py::init_alias<>())
		.def(py::init<>())
		/* .def(py::init([](py::kwargs kwargs) {
			osg::ref_ptr<osg::Drawable> d = new osg::Drawable();

			detail::kwargs_init(*d, kwargs);

			return d;
		})) */
		// TODO: Do I use detail::Drawable here?
		//.def("drawImplementation", [](osg::Drawable& self, osg::RenderInfo& ri) {
		//	self.drawImplementation(ri);
		//})
		.def("computeBound", &osg::Drawable::computeBound)
		.def("computeBoundingBox", &osg::Drawable::computeBoundingBox)
		.def_property(
			"drawCallback",
			detail::DrawableSlots::getter<detail::DrawableCallbackSlot>(
				detail::DrawableCallbackGetter
			),
			detail::draw_callback_property_setter()
		)
		.def_property("initialBound",
			py::cpp_function(
				&osg::Drawable::getInitialBound,
				py::return_value_policy::reference
			),
			py::cpp_function(
				&osg::Drawable::setInitialBound,
				py::keep_alive<1, 2>()
			)
		)
		.def_property("useVertexBufferObjects",
			&osg::Drawable::getUseVertexBufferObjects,
			&osg::Drawable::setUseVertexBufferObjects
		)
		.def_property("useVertexArrayObject",
			&osg::Drawable::getUseVertexArrayObject,
			&osg::Drawable::setUseVertexArrayObject
		)
	;
}

}
