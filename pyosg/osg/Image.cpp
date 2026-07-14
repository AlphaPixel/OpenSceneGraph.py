#include "Image.hpp"

#include <unordered_map>
#include <utility>

namespace pyosg {

namespace detail {
	// itemsize + pybind11 format string per GL data type we know how to expose as a buffer.
	// GL_HALF_FLOAT has no C++ type of its own, so its format code ("e", IEEE 754 half,
	// understood by both Python's struct module and numpy since 3.6) is written by hand.
	static std::unordered_map<GLenum, std::pair<py::ssize_t, std::string>> ImageBufferInfo{
		{GL_UNSIGNED_BYTE, {sizeof(GLubyte), py::format_descriptor<GLubyte>::format()}},
		{GL_FLOAT, {sizeof(GLfloat), py::format_descriptor<GLfloat>::format()}},
		{GL_HALF_FLOAT, {static_cast<py::ssize_t>(2), std::string("e")}},
	};
}

void bind_Image(py::module_& m) {
	auto img = py::class_<
		osg::Image,
		// detail::Image
		osg::BufferData,
		osg::ref_ptr<osg::Image>
	>(m, "Image", py::buffer_protocol())
		.def(py::init<>())
		.def(
			"allocateImage",
			&osg::Image::allocateImage,
			"s"_a,
			"t"_a,
			"r"_a,
			"pixelFormat"_a,
			"type"_a,
			"packing"_a=1
		)
		.def(
			"readPixels",
			&osg::Image::readPixels,
			"x"_a,
			"y"_a,
			"width"_a,
			"height"_a,
			"pixelFormat"_a,
			"type"_a,
			"packing"_a=1,
			py::doc(
				"Read a rectangle from the currently bound framebuffer using glReadPixels.\n\n"
				"Call this only while an OpenGL context is current, normally from a "
				"Camera draw callback."
			)
		)
		.def(
			"readImageFromCurrentTexture",
			&osg::Image::readImageFromCurrentTexture,
			"contextID"_a,
			"copyMipMapsIfAvailable"_a,
			"type"_a=GL_UNSIGNED_BYTE,
			"face"_a=0
		)
		.def_property_readonly("s", &osg::Image::s)
		.def_property_readonly("t", &osg::Image::t)
		.def_property_readonly("r", &osg::Image::r)
		.def_property_readonly("valid", &osg::Image::valid)
		.def_property_readonly("pixelFormat", &osg::Image::getPixelFormat)
		.def_property_readonly("dataType", &osg::Image::getDataType)
		.def_property_readonly("fileName", &osg::Image::getFileName)
		.def_buffer([](osg::Image& self) -> py::buffer_info {
			if(self.r() > 1) throw std::runtime_error(
				"osg.Image buffer protocol only supports 2D images (r() == 1)"
			);

			if(!detail::ImageBufferInfo.contains(self.getDataType())) throw std::runtime_error(
				"Unsupported osg::Image data type for buffer protocol"
			);

			auto [itemsize, fmt] = detail::ImageBufferInfo[self.getDataType()];
			auto comps = static_cast<py::ssize_t>(osg::Image::computeNumComponents(self.getPixelFormat()));
			auto h = static_cast<py::ssize_t>(self.t());
			auto w = static_cast<py::ssize_t>(self.s());
			auto rowStep = static_cast<py::ssize_t>(self.getRowStepInBytes());

			if(comps == 1) return py::buffer_info(
				self.data(),
				itemsize,
				fmt,
				2,
				{ h, w },
				{ rowStep, itemsize }
			);

			return py::buffer_info(
				self.data(),
				itemsize,
				fmt,
				3,
				{ h, w, comps },
				{ rowStep, itemsize * comps, itemsize }
			);
		})
	;

	py::enum_<osg::Image::Origin>(img, "Origin")
		.value("BOTTOM_LEFT", osg::Image::BOTTOM_LEFT)
		.value("TOP_LEFT", osg::Image::TOP_LEFT)
		.export_values()
	;
}

}
