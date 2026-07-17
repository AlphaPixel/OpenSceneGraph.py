#include "Program.hpp"

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
