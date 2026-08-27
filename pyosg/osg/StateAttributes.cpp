#include "../pyosg.hpp"

OSGX_DISABLE_WARNINGS

#include <osg/Viewport>
#include <osg/BlendFunc>
#include <osg/Depth>
#include <osg/BufferIndexBinding>

OSGX_ENABLE_WARNINGS

namespace pyosg {

// namespace detail {}

void bind_StateAttributes(py::module_& m) {
	py::class_<
		osg::Viewport,
		osg::StateAttribute,
		osg::ref_ptr<osg::Viewport>
	>(
		m,
		"Viewport",
		"A StateAttribute mapping normalized device coordinates to a pixel rectangle "
		"(x, y, width, height) of the target framebuffer."
	)
		.def(py::init<>())
		.def(py::init<
			osg::Viewport::value_type,
			osg::Viewport::value_type,
			osg::Viewport::value_type,
			osg::Viewport::value_type
		>())
		.def(py::init<const osg::Viewport&>())
		.def_property(
			"x",
			py::overload_cast<>(&osg::Viewport::x, py::const_),
			[](osg::Viewport& self, osg::Viewport::value_type x) { self.x() = x; }
		)
		.def_property(
			"y",
			py::overload_cast<>(&osg::Viewport::y, py::const_),
			[](osg::Viewport& self, osg::Viewport::value_type y) { self.y() = y; }
		)
		.def_property(
			"width",
			py::overload_cast<>(&osg::Viewport::width, py::const_),
			[](osg::Viewport& self, osg::Viewport::value_type w) { self.width() = w; }
		)
		.def_property(
			"height",
			py::overload_cast<>(&osg::Viewport::height, py::const_),
			[](osg::Viewport& self, osg::Viewport::value_type h) { self.height() = h; }
		)
		.def_property_readonly("valid", &osg::Viewport::valid)
		.def_property_readonly("aspectRatio", &osg::Viewport::aspectRatio)
		.def("computeWindowMatrix", &osg::Viewport::computeWindowMatrix)
		.def("__repr__", [](const osg::Viewport& self) {
			return py::str("Viewport({}, {}, {}, {})").format(
				self.x(),
				self.y(),
				self.width(),
				self.height()
			);
		})
	;

	py::class_<
		osg::BlendFunc,
		osg::StateAttribute,
		osg::ref_ptr<osg::BlendFunc>
	>(
		m,
		"BlendFunc",
		"A StateAttribute controlling glBlendFunc's source/destination blending factors."
	)
		.def(py::init<>())
		.def(py::init<GLenum, GLenum>())
		.def(py::init<GLenum, GLenum, GLenum, GLenum>())
	;

	auto depth = py::class_<
		osg::Depth,
		osg::StateAttribute,
		osg::ref_ptr<osg::Depth>
	>(
		m,
		"Depth",
		"A StateAttribute controlling the depth test function, near/far range, and depth "
		"write mask."
	);


	py::enum_<osg::Depth::Function>(depth, "Function")
		.value("NEVER", osg::Depth::NEVER)
		.value("LESS", osg::Depth::LESS)
		.value("EQUAL", osg::Depth::EQUAL)
		.value("LEQUAL", osg::Depth::LEQUAL)
		.value("GREATER", osg::Depth::GREATER)
		.value("NOTEQUAL", osg::Depth::NOTEQUAL)
		.value("GEQUAL", osg::Depth::GEQUAL)
		.value("ALWAYS", osg::Depth::ALWAYS)
		.export_values()
	;

	depth
		.def(py::init<osg::Depth::Function, double, double, bool>(),
			"func"_a=osg::Depth::LESS,
			"zNear"_a=0.0,
			"zFar"_a=1.0,
			"writeMask"_a=true
		)
	;

	py::class_<
		osg::BufferIndexBinding,
		osg::StateAttribute,
		osg::ref_ptr<osg::BufferIndexBinding>
	>(
		m,
		"BufferIndexBinding",
		"Base class for a StateAttribute that binds a BufferObject to an indexed GL binding "
		"point (SSBO, UBO, etc.)."
	)
		// .def(py::init<GLenum, GLuint>())
		// .def(py::init<GLenum, GLuint, osg::BufferData*, GLintptr, GLsizeiptr>(),
		// 	"target"_a,
		// 	"index"_a,
		// 	"bd"_a,
		// 	"offset"_a=0,
		// 	"size"_a=0
		// )
	;

	py::class_<
		osg::ShaderStorageBufferBinding,
		osg::BufferIndexBinding,
		osg::ref_ptr<osg::ShaderStorageBufferBinding>
	>(
		m,
		"ShaderStorageBufferBinding",
		"A BufferIndexBinding that binds a ShaderStorageBufferObject to a shader's SSBO "
		"binding point."
	)
		.def(py::init<GLuint, osg::BufferData*, GLintptr, GLsizeiptr>(),
			"index"_a,
			"bd"_a,
			"offset"_a=0,
			"size"_a=0
		)
	;

	py::class_<
		osg::UniformBufferBinding,
		osg::BufferIndexBinding,
		osg::ref_ptr<osg::UniformBufferBinding>
	>(
		m,
		"UniformBufferBinding",
		"A BufferIndexBinding that binds a UniformBufferObject to a shader's UBO binding point."
	)
		.def(py::init<GLuint, osg::BufferData*, GLintptr, GLsizeiptr>(),
			"index"_a,
			"bd"_a,
			"offset"_a=0,
			"size"_a=0
		)
	;
}

}
