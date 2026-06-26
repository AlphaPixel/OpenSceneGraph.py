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

	detail::ShadersProxy::bind(program, "_Shaders");
	detail::BindAttribLocationProxy::bind(program, "_BindAttribLocation");
	detail::BindFragDataLocationProxy::bind(program, "_BindFragDataLocation");
	detail::BindUniformBlockProxy::bind(program, "_BindUniformBlock");

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

		.def_property_readonly(
			"bindAttribLocation",
			[](osg::Program& self) -> detail::BindAttribLocationProxy& {
				return detail::ProgramStorage::get(self)->template proxy<
					detail::BindAttribLocationProxy
				>();
			},
			py::return_value_policy::reference_internal
		)
		.def_property_readonly(
			"bindFragDataLocation",
			[](osg::Program& self) -> detail::BindFragDataLocationProxy& {
				return detail::ProgramStorage::get(self)->template proxy<
					detail::BindFragDataLocationProxy
				>();
			},
			py::return_value_policy::reference_internal
		)
		.def_property_readonly(
			"bindUniformBlock",
			[](osg::Program& self) -> detail::BindUniformBlockProxy& {
				return detail::ProgramStorage::get(self)->template proxy<
					detail::BindUniformBlockProxy
				>();
			},
			py::return_value_policy::reference_internal
		)
	;
}

}
