#include "Drawable.hpp"

namespace pybind11x {
	template<>
	void kwargs_init_own(osg::Drawable& self, const py::kwargs& kwargs) {
		if(kwargs.contains("initialBound")) self.setInitialBound(
			kwargs["initialBound"].cast<osg::BoundingBox>()
		);

		if(kwargs.contains("useVertexBufferObjects")) self.setUseVertexBufferObjects(
			kwargs["useVertexBufferObjects"].cast<bool>()
		);

		if(kwargs.contains("useVertexArrayObject")) self.setUseVertexArrayObject(
			kwargs["useVertexArrayObject"].cast<bool>()
		);
	}
}

namespace pyosg {

void bind_Drawable(py::module_& m) {
	py::class_<osg::RenderInfo>(
		m,
		"RenderInfo",
		"Per-draw-call context (GL context id, osg.State, and current osg.View) passed to "
		"draw and camera callbacks."
	)
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
	>(
		m,
		"Drawable",
		"Base class for anything that can be rendered directly, such as Geometry and ShapeDrawable."
	);

	py::class_<
		osg::Drawable::DrawCallback,
		detail::Drawable::DrawCallback,
		osg::Object,
		osg::ref_ptr<osg::Drawable::DrawCallback>
	>(drawable, "DrawCallback")
		.def(py::init<>())
	;

	drawable
		.def(py::init<>())
		// Dual-factory `py::init(ClassFunc, AliasFunc)`: pybind11 picks ClassFunc for a plain
		// `Drawable(...)` and AliasFunc only when the Python type actually subclasses it, so the
		// `detail::Drawable` trampoline (needed for drawImplementation/computeBound/
		// computeBoundingBox overrides) is built only when something could actually use it.
		.def(py::init(
			[](py::kwargs kwargs) {
				auto* d = new osg::Drawable();

				pyx::kwargs_init(*d, kwargs);

				return d;
			},
			[](py::kwargs kwargs) {
				auto* d = new detail::Drawable();

				// `kwargs_init<T>()` template-deduces T from the argument's STATIC type, and
				// `kwargs_base`/`kwargs_init_own` are only specialized for `osg::Drawable`, not
				// this `detail::Drawable` alias -- deducing T=detail::Drawable here would silently
				// match the empty default template instead and skip every kwarg (including the
				// ones from Object/Node further up the chain).
				pyx::kwargs_init(static_cast<osg::Drawable&>(*d), kwargs);

				return d;
			}
		))
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
