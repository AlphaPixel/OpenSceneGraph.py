#include "../pyosg.hpp"

OSGX_DISABLE_WARNINGS

#include <osg/Viewport>
#include <osg/BlendFunc>
#include <osg/BlendEquation>
#include <osg/Depth>
#include <osg/BufferIndexBinding>
#include <osg/BindImageTexture>
#include <osg/Texture>

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

	auto blendEquation = py::class_<
		osg::BlendEquation,
		osg::StateAttribute,
		osg::ref_ptr<osg::BlendEquation>
	>(
		m,
		"BlendEquation",
		"A StateAttribute controlling glBlendEquation: how the (BlendFunc-weighted) source and "
		"destination colors are combined, e.g. RGBA_MIN/RGBA_MAX to keep the smaller/larger value."
	);

	// Core-profile equations only: osg::BlendEquation's ALPHA_MIN/ALPHA_MAX (SGIX extension) and
	// LOGIC_OP (glLogicOp, not a blend equation) are GL_INVALID_ENUM on a core context.
	py::enum_<osg::BlendEquation::Equation>(blendEquation, "Equation",
		"The combining operation passed to glBlendEquation(Separate)."
	)
		.value("RGBA_MIN", osg::BlendEquation::RGBA_MIN)
		.value("RGBA_MAX", osg::BlendEquation::RGBA_MAX)
		.value("FUNC_ADD", osg::BlendEquation::FUNC_ADD)
		.value("FUNC_SUBTRACT", osg::BlendEquation::FUNC_SUBTRACT)
		.value("FUNC_REVERSE_SUBTRACT", osg::BlendEquation::FUNC_REVERSE_SUBTRACT)
		.export_values()
	;

	blendEquation
		.def(py::init<>(), "Create a BlendEquation with the default FUNC_ADD equation.")
		.def(py::init<osg::BlendEquation::Equation>(),
			"Create a BlendEquation using one equation for both the RGB and alpha channels."
		)
		.def(py::init<osg::BlendEquation::Equation, osg::BlendEquation::Equation>(),
			"Create a BlendEquation with separate RGB and alpha equations."
		)
		.def_property(
			"equation",
			&osg::BlendEquation::getEquation,
			&osg::BlendEquation::setEquation,
			"The RGB equation; assigning sets both the RGB and alpha equations."
		)
		.def_property(
			"equationRGB",
			&osg::BlendEquation::getEquationRGB,
			&osg::BlendEquation::setEquationRGB,
			"The equation applied to the RGB channels."
		)
		.def_property(
			"equationAlpha",
			&osg::BlendEquation::getEquationAlpha,
			&osg::BlendEquation::setEquationAlpha,
			"The equation applied to the alpha channel."
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

	auto bindImage = py::class_<
		osg::BindImageTexture,
		osg::StateAttribute,
		osg::ref_ptr<osg::BindImageTexture>
	>(
		m,
		"BindImageTexture",
		"A StateAttribute binding one level of a Texture to an image unit (glBindImageTexture), "
		"for shader image load/store - e.g. a compute shader's `layout(binding = N, r8) uniform "
		"image2D` output. One attribute per image unit (its member is the unit)."
	);

	py::enum_<osg::BindImageTexture::Access>(
		bindImage,
		"Access",
		"How the shader accesses the image: READ_ONLY, WRITE_ONLY or READ_WRITE."
	)
		.value("READ_ONLY", osg::BindImageTexture::READ_ONLY)
		.value("WRITE_ONLY", osg::BindImageTexture::WRITE_ONLY)
		.value("READ_WRITE", osg::BindImageTexture::READ_WRITE)
		.export_values()
	;

	bindImage
		.def(
			py::init([](
				GLuint imageUnit,
				osg::Texture* texture,
				osg::BindImageTexture::Access access,
				GLenum format,
				int level,
				bool layered,
				int layer
			) {
				return new osg::BindImageTexture(
					imageUnit,
					texture,
					access,
					format,
					level,
					layered ? GL_TRUE : GL_FALSE,
					layer
				);
			}),
			"imageUnit"_a=0,
			"texture"_a=nullptr,
			"access"_a=osg::BindImageTexture::READ_ONLY,
			"format"_a=GL_RGBA8,
			"level"_a=0,
			"layered"_a=false,
			"layer"_a=0,
			"Bind mip `level` of `texture` to image unit `imageUnit`. `format` is the GL internal "
			"format the shader's image declaration uses (e.g. GL_R8 for `r8`), which must be "
			"size-compatible with the texture's own. `layered`/`layer` select all layers or one "
			"layer of an array/3D/cube texture."
		)
		.def_property(
			"imageUnit",
			&osg::BindImageTexture::getImageUnit,
			&osg::BindImageTexture::setImageUnit,
			"The image unit (the shader's `layout(binding = N)`)."
		)
		.def_property(
			"texture",
			[](osg::BindImageTexture& self) { return self.getTexture(); },
			&osg::BindImageTexture::setTexture,
			"The bound Texture."
		)
		.def_property(
			"access",
			&osg::BindImageTexture::getAccess,
			&osg::BindImageTexture::setAccess,
			"The BindImageTexture.Access mode."
		)
		.def_property(
			"format",
			&osg::BindImageTexture::getFormat,
			&osg::BindImageTexture::setFormat,
			"The GL internal format the shader reads/writes the image as."
		)
		.def_property(
			"level",
			&osg::BindImageTexture::getLevel,
			&osg::BindImageTexture::setLevel,
			"The bound mip level."
		)
		.def_property(
			"layered",
			[](const osg::BindImageTexture& self) { return self.getIsLayered() != GL_FALSE; },
			[](osg::BindImageTexture& self, bool layered) { self.setIsLayered(layered ? GL_TRUE : GL_FALSE); },
			"True binds every layer of an array/3D/cube texture; False binds only `layer`."
		)
		.def_property(
			"layer",
			&osg::BindImageTexture::getLayer,
			&osg::BindImageTexture::setLayer,
			"The bound layer when `layered` is False."
		)
	;
}

}
