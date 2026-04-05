#pragma once

#include "../pyosg.hpp"

PYOSG_DISABLE_WARNINGS

#include <osg/Program>

PYOSG_ENABLE_WARNINGS

#include "pybind11x.hpp"

namespace pyx = pybind11x;

template<>
struct pyx::SequenceTraits<osg::Program> {
	using element_type = osg::Shader;
	using value_type = element_type*;

	static value_type from_python(py::handle h) {
		return h.cast<value_type>();
	}

	static size_t size(const osg::Program* p) {
		return p->getNumShaders();
	}

	static element_type* get(osg::Program* p, size_t i) {
		return p->getShader(static_cast<unsigned int>(i));
	}

	// static void set(osg::Program* p, size_t i, element_type* d) {}

	static void del(osg::Program* p, size_t i) {
		p->removeShader(p->getShader(static_cast<unsigned int>(i)));
	}

	static void append(osg::Program* p, element_type* s) {
		p->addShader(s);
	}
};

namespace pyosg {

namespace detail {
	using ShadersProxy = pyx::SequenceProxy<osg::Program>;
	using ProgramStorage = pyx::ProxyStorageOSG<osg::Program, ShadersProxy>;
}

void bind_Program(py::module_& m);

}
