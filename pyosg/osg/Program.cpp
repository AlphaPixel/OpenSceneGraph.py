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
		.def(py::init<>())
		// .def(py::init<const osg::Program&>())
		.def(py::init(pyx::kwargs_ctor<osg::Program>()))
	;

	// Shaders can be added via `.shaders.append(shader)` (SequenceProxy, below) -- no need for a
	// dedicated addShader() method.
	pyx::bind_proxy_property<detail::ShadersProxy, osg::Program, detail::ProgramStorage>(
		program, "_Shaders", "shaders"
	);
	pyx::bind_proxy_property<
		detail::BindAttribLocationProxy, osg::Program, detail::ProgramStorage
	>(program, "_BindAttribLocation", "bindAttribLocation");
	pyx::bind_proxy_property<
		detail::BindFragDataLocationProxy, osg::Program, detail::ProgramStorage
	>(program, "_BindFragDataLocation", "bindFragDataLocation");
	pyx::bind_proxy_property<
		detail::BindUniformBlockProxy, osg::Program, detail::ProgramStorage
	>(program, "_BindUniformBlock", "bindUniformBlock");
}

}
