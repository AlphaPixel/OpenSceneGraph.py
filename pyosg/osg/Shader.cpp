#include "../pyosg.hpp"

OSGX_DISABLE_WARNINGS

#include <osg/Shader>

OSGX_ENABLE_WARNINGS

#include "pybind11x-osg.hpp"

namespace pyx = pybind11x;

namespace pyosg {

// namespace detail {}

void bind_Shader(py::module_& m) {
	auto shader = py::class_<osg::Shader, osg::Object, osg::ref_ptr<osg::Shader>>(
		m,
		"Shader",
		"A single GLSL shader stage's source code, attached to a Program to build a "
		"complete shader pipeline."
	);

	py::enum_<osg::Shader::Type>(
		shader,
		"Type",
		"Which GLSL pipeline stage this Shader's source targets."
	)
		.value("VERTEX", osg::Shader::VERTEX)
		.value("TESSCONTROL", osg::Shader::TESSCONTROL)
		.value("TESSEVALUATION", osg::Shader::TESSEVALUATION)
		.value("GEOMETRY", osg::Shader::GEOMETRY)
		.value("FRAGMENT", osg::Shader::FRAGMENT)
		.value("COMPUTE", osg::Shader::COMPUTE)
		.value("UNDEFINED", osg::Shader::UNDEFINED)
		.export_values()
	;

	shader
		.def(
			py::init(pyx::kwargs_ctor<osg::Shader, osg::Shader::Type>()),
			"type"_a=osg::Shader::UNDEFINED,
			"Create a Shader of the given stage Type with no source yet assigned."
		)
		.def(
			py::init(pyx::kwargs_ctor<osg::Shader, osg::Shader::Type, const std::string&>()),
			"Create a Shader of the given stage Type with its GLSL source pre-set."
		)
		// .def(py::init<osg::Shader::Type, osg::ShaderBinary*>())
		// .def(py::init<const osg::Shader&>())
		.def_property(
			"type",
			&osg::Shader::getType,
			&osg::Shader::setType,
			"Which GLSL pipeline stage this Shader targets."
		)
		.def_property(
			"file",
			&osg::Shader::getFileName,
			&osg::Shader::setFileName,
			"The file path this Shader's source was loaded from, if any; empty for "
			"in-memory-only source."
		)
		.def_property(
			"source",
			&osg::Shader::getShaderSource,
			&osg::Shader::setShaderSource,
			"This Shader's raw GLSL source text; assigning marks it dirty for recompilation."
		)
	;
}

}
