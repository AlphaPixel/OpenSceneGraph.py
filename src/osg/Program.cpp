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
	template<>
	void kwargs_init(osg::Program& self, const py::kwargs& kwargs) {
		kwargs_init(static_cast<osg::Object&>(self), kwargs);

		if(kwargs.contains("shaders")) {
			for(py::handle shader : kwargs["shaders"]) {
				self.addShader(shader.cast<osg::Shader*>());
			}
		}
	}

	using ShadersProxy = pyx::SequenceProxy<osg::Program>;
	using ProgramStorage = pyx::ProxyStorageOSG<osg::Program, ShadersProxy>;
}

void bind_Program(py::module_& m) {
	auto program = py::class_<
		osg::Program,
		osg::StateAttribute,
		osg::ref_ptr<osg::Program
	>>(m, "Program")
		.def(py::init<>())
		// .def(py::init<const osg::Program&>())
		.def(py::init([](py::args args, py::kwargs kwargs) {
			osg::ref_ptr<osg::Program> p = new osg::Program();

			detail::kwargs_init(*p, kwargs);

			return p;
		}))
	;

	detail::ShadersProxy::bind(program, "_Shaders");

	program
		/* .def("addShader", [](osg::Program& self, osg::Shader* shader) {
			return self.addShader(shader);
		}, "shader"_a, py::keep_alive<1, 2>())
		.def_property_readonly("shaders", [](osg::Program& self) {
			return detail::ShadersProxy(&self);
		}) */

		.def_property_readonly("shaders", [](osg::Program& self) -> detail::ShadersProxy& {
			return detail::ProgramStorage::get(self)->template proxy<detail::ShadersProxy>();
		}, py::return_value_policy::reference_internal)
	;
}

}
