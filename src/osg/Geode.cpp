#include "Geode.hpp"

namespace pyosg {

namespace detail {
	template<>
	void kwargs_init(osg::Geode& self, const py::kwargs& kwargs) {
		kwargs_init(static_cast<osg::Group&>(self), kwargs);

		if(kwargs.contains("drawables")) {
			for(py::handle child : kwargs["drawables"]) {
				self.addDrawable(child.cast<osg::Drawable*>());
			}
		}
	}
}

void bind_Geode(py::module_& m) {
	auto geode = py::class_<osg::Geode, osg::Group, osg::ref_ptr<osg::Geode>>(m, "Geode");

	detail::DrawablesProxy::bind(geode, "_Drawables");

	geode
		.def(py::init<>())
		.def(py::init([](py::args args, py::kwargs kwargs) {
			osg::ref_ptr<osg::Geode> g = new osg::Geode();

			detail::kwargs_init(*g, kwargs);

			return g;
		}))

		.def_property_readonly("drawables", [](osg::Geode& self) -> detail::DrawablesProxy& {
			return detail::DrawablesStorage::get(self)->template proxy<detail::DrawablesProxy>();
		}, py::return_value_policy::reference_internal)
	;
}

}
