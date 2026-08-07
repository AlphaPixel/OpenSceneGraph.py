#pragma once

#include "lifetime-probe.hpp"

PYOSG_DISABLE_WARNINGS

#include <osg/Group>

PYOSG_ENABLE_WARNINGS

#include "pybind11x.hpp"

namespace pyx = pybind11x;

template<>
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

	static void insert(osg::Group* g, size_t i, value_type n) {
		g->insertChild(static_cast<unsigned int>(i), n);
	}
};

namespace pyosg {

namespace detail {
	using ChildrenProxy = pyx::SequenceProxy<osg::Group>;
	using ChildrenStorage = pyx::ProxyStorageOSG<osg::Group, ChildrenProxy>;
}

void bind_Group(py::module_& m);

}
