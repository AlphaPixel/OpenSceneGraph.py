#include "../pyosg.hpp"

PYOSG_DISABLE_WARNINGS

#include <osg/Program>

PYOSG_ENABLE_WARNINGS

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

	template<>
	struct SequenceTraits<osg::Program> {
		using element_type = osg::Shader;

		static size_t size(const osg::Program* p) {
			return p->getNumShaders();
		}

		static element_type* get(osg::Program* p, size_t i) {
			return p->getShader(static_cast<unsigned int>(i));
		}

		static void set(osg::Program* p, size_t i, element_type* n) {
			// g->replaceShader(g->getShader(static_cast<unsigned int>(i)), n);

			throw std::runtime_error("Index-based replacement of Shaders not supported");
		}

		static void remove(osg::Program* p, size_t i) {
			p->removeShader(p->getShader(static_cast<unsigned int>(i)));
		}

		static void append(osg::Program* p, element_type* s) {
			p->addShader(s);
		}

		static constexpr const char* add_method = "addShader";
	};

	using ShadersProxy = SequenceProxy<osg::Program>;
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
		.def("addShader", [](osg::Program& self, osg::Shader* shader) {
			return self.addShader(shader);
		}, "shader"_a, py::keep_alive<1, 2>())
		.def_property_readonly("shaders", [](osg::Program& self) {
			return detail::ShadersProxy(&self);
		})
	;
}

}
