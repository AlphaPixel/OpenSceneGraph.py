#include "Image.hpp"

namespace pyosg {

void bind_Image(py::module_& m) {
	auto img = py::class_<
		osg::Image,
		// detail::Image
		osg::BufferData,
		osg::ref_ptr<osg::Image>
	>(m, "Image")
		.def(py::init<>())
		.def(
			"readImageFromCurrentTexture",
			&osg::Image::readImageFromCurrentTexture,
			"contextID"_a,
			"copyMipMapsIfAvailable"_a,
			"type"_a=GL_UNSIGNED_BYTE,
			"face"_a=0
		)
	;

	py::enum_<osg::Image::Origin>(img, "Origin")
		.value("BOTTOM_LEFT", osg::Image::BOTTOM_LEFT)
		.value("TOP_LEFT", osg::Image::TOP_LEFT)
		.export_values()
	;
}

}
