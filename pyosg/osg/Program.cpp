#include "Program.hpp"

namespace pybind11x {
	template<>
	void kwargs_init_own(osg::Program& self, const py::kwargs& kwargs) {
		if(kwargs.contains("shaders")) {
			for(py::handle shader : kwargs["shaders"]) {
				self.addShader(shader.cast<osg::Shader*>());
			}
		}
	}
}

namespace pyosg {

void bind_Program(py::module_& m) {
	auto program = py::class_<
		osg::Program,
		osg::StateAttribute,
		osg::ref_ptr<osg::Program
	>>(
		m,
		"Program",
		"A StateAttribute wrapping a linked GLSL shader program, built from one or more "
		"attached Shader objects. .shaders is a sequence proxy (append() instead of "
		"addShader()); .bindAttribLocation/.bindFragDataLocation/.bindUniformBlock are "
		"mapping proxies over the equivalent bind*() call pairs."
	)
		.def(py::init<>(), "Create an empty Program with no shaders attached.")
		// .def(py::init<const osg::Program&>())
		.def(
			py::init(pyx::kwargs_ctor<osg::Program>()),
			"Create a Program from keyword arguments; `shaders` accepts an iterable of "
			"Shader objects to attach immediately."
		)
	;

	// Shaders can be added via `.shaders.append(shader)` (SequenceProxy, below) -- no need for a
	// dedicated addShader() method.
	pyx::bind_proxy_property<detail::ShadersProxy, osg::Program, detail::ProgramStorage>(
		program,
		"_Shaders",
		"shaders",
		"SequenceProxy over this Program's attached Shaders; use append()/extend()/del "
		"instead of addShader()/removeShader()."
	);
	pyx::bind_proxy_property<
		detail::BindAttribLocationProxy, osg::Program, detail::ProgramStorage
	>(
		program,
		"_BindAttribLocation",
		"bindAttribLocation",
		"Mapping proxy over addBindAttribLocation()/removeBindAttribLocation(): attribute "
		"name (str) -> bound GLuint location."
	);
	pyx::bind_proxy_property<
		detail::BindFragDataLocationProxy, osg::Program, detail::ProgramStorage
	>(
		program,
		"_BindFragDataLocation",
		"bindFragDataLocation",
		"Mapping proxy over addBindFragDataLocation()/removeBindFragDataLocation(): output "
		"variable name (str) -> bound GLuint draw buffer location."
	);
	pyx::bind_proxy_property<
		detail::BindUniformBlockProxy, osg::Program, detail::ProgramStorage
	>(
		program,
		"_BindUniformBlock",
		"bindUniformBlock",
		"Mapping proxy over addBindUniformBlock()/removeBindUniformBlock(): uniform block "
		"name (str) -> bound GLuint binding point."
	);
}

}
