#include "../pyosg.hpp"

PYOSG_DISABLE_WARNINGS

#include <osg/Geode>

PYOSG_ENABLE_WARNINGS

#include "pybind11x.hpp"

namespace pyx = pybind11x;

/* template<>
struct pyx::SequenceTraits<osg::Group> {
	using element_type = osg::Node;
	using value_type = element_type*;

	static value_type from_python(py::handle h) {
		return h.cast<value_type>();
	}

	static size_t size(const osg::Group* g) {
		return g->getNumChildren();
	}

	static element_type* get(osg::Group* g, size_t i) {
		return g->getChild(static_cast<unsigned int>(i));
	}

	static void set(osg::Group* g, size_t i, value_type n) {
		g->replaceChild(g->getChild(static_cast<unsigned int>(i)), n);
	}

	static void del(osg::Group* g, size_t i) {
		g->removeChild(static_cast<unsigned int>(i));
	}

	static void append(osg::Group* g, value_type n) {
		g->addChild(n);
	}
}; */

template<>
struct pyx::SequenceTraits<osg::Geode> {
	using element_type = osg::Drawable;
	using value_type = element_type*;

	static value_type from_python(py::handle h) {
		return h.cast<value_type>();
	}

	static size_t size(const osg::Geode* g) {
		return g->getNumDrawables();
	}

	static element_type* get(osg::Geode* g, size_t i) {
		return g->getDrawable(static_cast<unsigned int>(i));
	}

	static void set(osg::Geode* g, size_t i, element_type* d) {
		g->replaceDrawable(g->getDrawable(static_cast<unsigned int>(i)), d);
	}

	static void del(osg::Geode* g, size_t i) {
		g->removeDrawables(static_cast<unsigned int>(i));
	}

	static void append(osg::Geode* g, element_type* d) {
		g->addDrawable(d);
	}
};

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

	using DrawablesProxy = pyx::SequenceProxy<osg::Geode>;
	using DrawablesStorage = pyx::ProxyStorageOSG<osg::Geode, DrawablesProxy>;
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
