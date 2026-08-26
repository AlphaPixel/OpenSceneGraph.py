#pragma once

#include "../pyosg.hpp"

OSGX_DISABLE_WARNINGS

#include <osg/Geode>

OSGX_ENABLE_WARNINGS

#include "pybind11x-osg.hpp"

namespace pyx = pybind11x;

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
	using DrawablesProxy = pyx::SequenceProxy<osg::Geode>;
	using DrawablesStorage = pyx::ProxyStorageOSG<osg::Geode, DrawablesProxy>;
}

void bind_Geode(py::module_& m);

}
