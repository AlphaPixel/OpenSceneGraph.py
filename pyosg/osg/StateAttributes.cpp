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
		.def(py::init<>(), "Create a zero-sized Viewport (invalid until x/y/width/height are set).")
		.def(py::init<
			osg::Viewport::value_type,
			osg::Viewport::value_type,
			osg::Viewport::value_type,
			osg::Viewport::value_type
		>(), "Create a Viewport from pixel x, y, width, height.")
		.def(py::init<const osg::Viewport&>(), "Create a copy of another Viewport.")
		.def_property(
			"x",
			py::overload_cast<>(&osg::Viewport::x, py::const_),
			[](osg::Viewport& self, osg::Viewport::value_type x) { self.x() = x; },
			"The pixel x-origin of the viewport rectangle."
		)
		.def_property(
			"y",
			py::overload_cast<>(&osg::Viewport::y, py::const_),
			[](osg::Viewport& self, osg::Viewport::value_type y) { self.y() = y; },
			"The pixel y-origin of the viewport rectangle."
		)
		.def_property(
			"width",
			py::overload_cast<>(&osg::Viewport::width, py::const_),
			[](osg::Viewport& self, osg::Viewport::value_type w) { self.width() = w; },
			"The pixel width of the viewport rectangle."
		)
		.def_property(
			"height",
			py::overload_cast<>(&osg::Viewport::height, py::const_),
			[](osg::Viewport& self, osg::Viewport::value_type h) { self.height() = h; },
			"The pixel height of the viewport rectangle."
		)
		.def_property_readonly("valid", &osg::Viewport::valid,
			"Whether width and height are both greater than zero."
		)
		.def_property_readonly("aspectRatio", &osg::Viewport::aspectRatio,
			"width / height as a float."
		)
		.def("computeWindowMatrix", &osg::Viewport::computeWindowMatrix,
			"Return the Matrixd mapping clip-space coordinates ([-1,1]) to this viewport's "
			"pixel rectangle."
		)
		.def("__repr__", [](const osg::Viewport& self) {
			return py::str("Viewport({}, {}, {}, {})").format(
				self.x(),
				self.y(),
				self.width(),
				self.height()
			);
		}, "Return a constructor-style representation of this viewport.")
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
		.def(py::init<>(), "Create a BlendFunc with the default SRC_ALPHA/ONE_MINUS_SRC_ALPHA "
			"source/destination factors."
		)
		.def(py::init<GLenum, GLenum>(),
			"Create a BlendFunc with the same source/destination factors for both the RGB "
			"and alpha channels."
		)
		.def(py::init<GLenum, GLenum, GLenum, GLenum>(),
			"Create a BlendFunc with separate source/destination factors for the RGB and "
			"alpha channels."
		)
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


	py::enum_<osg::Depth::Function>(depth, "Function",
		"The comparison function used by the depth test (glDepthFunc)."
	)
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
			"writeMask"_a=true,
			"Create a Depth attribute with a comparison function, near/far depth range "
			"mapping, and whether depth writes are enabled."
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
			"size"_a=0,
			"Bind a ShaderStorageBufferObject to SSBO binding point `index`, optionally "
			"only a byte [offset, offset+size) range of it (size=0 binds the whole buffer)."
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
			"size"_a=0,
			"Bind a UniformBufferObject to UBO binding point `index`, optionally only a "
			"byte [offset, offset+size) range of it (size=0 binds the whole buffer)."
		)
	;
}

}
