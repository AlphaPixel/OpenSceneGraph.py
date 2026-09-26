#include "Image.hpp"

#include <optional>
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
	>(
		m,
		"Image",
		py::buffer_protocol(),
		"Raw pixel data plus format/type metadata, used for textures, framebuffer readback, "
		"and file I/O."
	)
		.def(py::init<>(), "Create an empty Image with no dimensions or data allocated.")
		.def(
			"allocateImage",
			&osg::Image::allocateImage,
			"s"_a,
			"t"_a,
			"r"_a,
			"pixelFormat"_a,
			"type"_a,
			"packing"_a=1,
			"Allocate (or reallocate) this Image's own pixel storage to (s, t, r) with the "
			"given format/type, discarding any previous contents."
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
			"Read a rectangle of pixels back from the currently-bound GL framebuffer into "
			"this Image (glReadPixels), reallocating storage as needed."
		)
		.def(
			"readImageFromCurrentTexture",
			&osg::Image::readImageFromCurrentTexture,
			"contextID"_a,
			"copyMipMapsIfAvailable"_a,
			"type"_a=GL_UNSIGNED_BYTE,
			"face"_a=0,
			"Read this Image's data back from the currently-bound GL texture object for the "
			"given context; result may be GPU-async-stale if read immediately after a render, "
			"so prefer shader hot-swap for live inspection where possible."
		)
		// CPU-side (OSG's bundled software gluScaleImage), so no GL context is needed; averages
		// each destination pixel over the source area it covers when shrinking.
		.def(
			"scaleImage",
			[](osg::Image& self, int s, int t, int r, std::optional<GLenum> dataType) {
				self.scaleImage(s, t, r, dataType.value_or(self.getDataType()));
			},
			"s"_a,
			"t"_a,
			"r"_a=1,
			"dataType"_a=py::none(),
			"Resample this Image in place to (s, t, r), optionally converting to dataType. Runs "
			"on the CPU; no GL context is needed. 3D (r > 1) images are not supported by OSG."
		)
		.def(
			"copySubImage",
			&osg::Image::copySubImage,
			"s_offset"_a,
			"t_offset"_a,
			"r_offset"_a,
			"source"_a,
			"Copy all of source into this Image at the given offset; both must share the same "
			"pixel format and data type, and source must fit."
		)
		// osg::Image's copy constructor always copies the pixel data; the CopyOp only decides
		// how the inherited osg::Object state (user data, etc.) is copied.
		.def("__copy__", [](const osg::Image& self) {
			return osg::ref_ptr<osg::Image>(new osg::Image(self, osg::CopyOp::SHALLOW_COPY));
		}, "copy.copy(): an independent copy of the pixel data; Object state shared shallowly.")
		.def("__deepcopy__", [](const osg::Image& self, py::dict) {
			return osg::ref_ptr<osg::Image>(new osg::Image(self, osg::CopyOp::DEEP_COPY_ALL));
		}, "memo"_a, "copy.deepcopy(): an independent copy of the pixel data and Object state.")
		.def_property_readonly("s", &osg::Image::s, "Image width in texels/pixels.")
		.def_property_readonly("t", &osg::Image::t, "Image height in texels/pixels.")
		.def_property_readonly(
			"r",
			&osg::Image::r,
			"Image depth in texels/pixels (1 for a plain 2D image, >1 for a 3D image/atlas)."
		)
		.def_property_readonly(
			"valid",
			&osg::Image::valid,
			"Whether this Image currently holds allocated pixel data."
		)
		.def_property_readonly(
			"pixelFormat",
			&osg::Image::getPixelFormat,
			"The GL pixel format of the stored data (e.g. GL_RGBA)."
		)
		.def_property_readonly(
			"dataType",
			&osg::Image::getDataType,
			"The GL data type of the stored data (e.g. GL_UNSIGNED_BYTE, GL_FLOAT)."
		)
		.def_property_readonly(
			"fileName",
			&osg::Image::getFileName,
			"The file path this Image was loaded from, or empty if it was created in memory."
		)
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

	py::enum_<osg::Image::Origin>(
		img,
		"Origin",
		"Which corner row 0 of the pixel data represents; most image loaders produce "
		"BOTTOM_LEFT to match GL's texture coordinate convention."
	)
		.value("BOTTOM_LEFT", osg::Image::BOTTOM_LEFT)
		.value("TOP_LEFT", osg::Image::TOP_LEFT)
		.export_values()
	;
}

}
