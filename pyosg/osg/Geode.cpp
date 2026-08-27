#include "Geode.hpp"

namespace pybind11x {
	template<>
	void kwargs_init_own(osg::Geode& self, const py::kwargs& kwargs) {
		if(kwargs.contains("drawables")) {
			for(py::handle child : kwargs["drawables"]) {
				self.addDrawable(child.cast<osg::Drawable*>());
			}
		}
	}
}

namespace pyosg {

void bind_Geode(py::module_& m) {
	auto geode = py::class_<osg::Geode, osg::Group, osg::ref_ptr<osg::Geode>>(
		m,
		"Geode",
		"A leaf node that groups one or more Drawable objects for rendering. Drawables are "
		"exposed via the .drawables sequence proxy (indexing, iteration, append/extend) "
		"rather than addDrawable()/removeDrawable()."
	);

	pyx::bind_proxy_property<detail::DrawablesProxy, osg::Geode, detail::DrawablesStorage>(
		geode, "_Drawables", "drawables"
	);

	geode
		.def(py::init<>())
		.def(py::init(pyx::kwargs_ctor<osg::Geode>()))
	;
}

}
