#include "../pyosg.hpp"

PYOSG_DISABLE_WARNINGS

#include <osg/Texture2D>

PYOSG_ENABLE_WARNINGS

namespace pyosg {

namespace detail {
	class Texture: public osg::Texture {
	public:
		// Texture(): osg::Texture() {}

		// getType
		// isTextureAttribute
        //
		// getTextureTarget (pure virtual)
        //
		// getTextureWidth
		// getTextureHeight
		// getTextureDepth
        //
		// setImage (pure virtual)
		// getImage (pure virtual)
		// getImage const (pure virtual)
		// getNumImages (pure virtual)
        //
		// apply (pure virtual)
        //
		// compileGLObjects
		// resizeGLObjectBuffers
		// releaseGLObjects
        //
		// isDirty
	};
}

void bind_Texture(py::module_& m) {
	auto tex = py::class_<
		osg::Texture,
		// detail::Texture
		osg::StateAttribute,
		osg::ref_ptr<osg::Texture>
	>(m, "Texture");

	py::enum_<osg::Texture::WrapParameter>(tex, "WrapParameter")
		.value("WRAP_S", osg::Texture::WRAP_S)
		.value("WRAP_T", osg::Texture::WRAP_T)
		.value("WRAP_R", osg::Texture::WRAP_R)
		.export_values()
	;

	py::enum_<osg::Texture::WrapMode>(tex, "WrapMode")
		.value("CLAMP", osg::Texture::CLAMP)
		.value("CLAMP_TO_EDGE", osg::Texture::CLAMP_TO_EDGE)
		.value("CLAMP_TO_BORDER", osg::Texture::CLAMP_TO_BORDER)
		.value("REPEAT", osg::Texture::REPEAT)
		.value("MIRROR", osg::Texture::MIRROR)
		.export_values()
	;

	py::enum_<osg::Texture::FilterParameter>(tex, "FilterParameter")
		.value("MIN_FILTER", osg::Texture::MIN_FILTER)
		.value("MAG_FILTER", osg::Texture::MAG_FILTER)
		.export_values()
	;

	py::enum_<osg::Texture::FilterMode>(tex, "FilterMode")
		.value("LINEAR", osg::Texture::LINEAR)
		.value("LINEAR_MIPMAP_LINEAR", osg::Texture::LINEAR_MIPMAP_LINEAR)
		.value("LINEAR_MIPMAP_NEAREST", osg::Texture::LINEAR_MIPMAP_NEAREST)
		.value("NEAREST", osg::Texture::NEAREST)
		.value("NEAREST_MIPMAP_LINEAR", osg::Texture::NEAREST_MIPMAP_LINEAR)
		.value("NEAREST_MIPMAP_NEAREST", osg::Texture::NEAREST_MIPMAP_NEAREST)
		.export_values()
	;

	py::enum_<osg::Texture::InternalFormatMode>(tex, "InternalFormatMode")
		.value("USE_IMAGE_DATA_FORMAT", osg::Texture::USE_IMAGE_DATA_FORMAT)
		.value("USE_USER_DEFINED_FORMAT", osg::Texture::USE_USER_DEFINED_FORMAT)
		.value("USE_ARB_COMPRESSION", osg::Texture::USE_ARB_COMPRESSION)
		.value("USE_S3TC_DXT1_COMPRESSION", osg::Texture::USE_S3TC_DXT1_COMPRESSION)
		.value("USE_S3TC_DXT3_COMPRESSION", osg::Texture::USE_S3TC_DXT3_COMPRESSION)
		.value("USE_S3TC_DXT5_COMPRESSION", osg::Texture::USE_S3TC_DXT5_COMPRESSION)
		.value("USE_PVRTC_2BPP_COMPRESSION", osg::Texture::USE_PVRTC_2BPP_COMPRESSION)
		.value("USE_PVRTC_4BPP_COMPRESSION", osg::Texture::USE_PVRTC_4BPP_COMPRESSION)
		.value("USE_ETC_COMPRESSION", osg::Texture::USE_ETC_COMPRESSION)
		.value("USE_ETC2_COMPRESSION", osg::Texture::USE_ETC2_COMPRESSION)
		.value("USE_RGTC1_COMPRESSION", osg::Texture::USE_RGTC1_COMPRESSION)
		.value("USE_RGTC2_COMPRESSION", osg::Texture::USE_RGTC2_COMPRESSION)
		.value("USE_S3TC_DXT1c_COMPRESSION", osg::Texture::USE_S3TC_DXT1c_COMPRESSION)
		.value("USE_S3TC_DXT1a_COMPRESSION", osg::Texture::USE_S3TC_DXT1a_COMPRESSION)
		.export_values()
	;

	py::enum_<osg::Texture::InternalFormatType>(tex, "InternalFormatType")
		.value("NORMALIZED", osg::Texture::NORMALIZED)
		.value("FLOAT", osg::Texture::FLOAT)
		.value("SIGNED_INTEGER", osg::Texture::SIGNED_INTEGER)
		.value("UNSIGNED_INTEGER", osg::Texture::UNSIGNED_INTEGER)
		.export_values()
	;

	py::enum_<osg::Texture::GenerateMipmapMode>(tex, "GenerateMipmapMode")
		.value("GENERATE_MIPMAP_NONE", osg::Texture::GENERATE_MIPMAP_NONE)
		.value("GENERATE_MIPMAP", osg::Texture::GENERATE_MIPMAP)
		.value("GENERATE_MIPMAP_TEX_PARAMETER", osg::Texture::GENERATE_MIPMAP_TEX_PARAMETER)
		.export_values()
	;

	tex
		.def_property(
			"wrap",
			[](osg::Texture& self) {
				return py::make_tuple(
					self.getWrap(osg::Texture::WRAP_S),
					self.getWrap(osg::Texture::WRAP_T),
					self.getWrap(osg::Texture::WRAP_R)
				);
			},
			[](osg::Texture& self, py::object obj) {
				using WP = osg::Texture::WrapParameter;
				using WM = osg::Texture::WrapMode;

				if(py::isinstance<WM>(obj)) {
					auto v = obj.cast<WM>();

					self.setWrap(WP::WRAP_S, v);
					self.setWrap(WP::WRAP_T, v);
					self.setWrap(WP::WRAP_R, v);
				}

				else {
					auto seq = obj.cast<py::sequence>();
					auto n = seq.size();

					if(n >= 1) self.setWrap(WP::WRAP_S, seq[0].cast<WM>());
					if(n >= 2) self.setWrap(WP::WRAP_T, seq[1].cast<WM>());
					if(n >= 3) self.setWrap(WP::WRAP_R, seq[2].cast<WM>());
				}
			}
		)
		.def_property(
			"filter",
			[](osg::Texture& self) {
				return py::make_tuple(
					self.getFilter(osg::Texture::MIN_FILTER),
					self.getFilter(osg::Texture::MAG_FILTER)
				);
			},
			[](osg::Texture& self, py::object obj) {
				using FP = osg::Texture::FilterParameter;
				using FM = osg::Texture::FilterMode;

				if(py::isinstance<FM>(obj)) {
					auto v = obj.cast<FM>();

					self.setFilter(FP::MIN_FILTER, v);
					self.setFilter(FP::MAG_FILTER, v);
				}

				else {
					auto seq = obj.cast<py::sequence>();
					auto n = seq.size();

					if(n >= 1) self.setFilter(FP::MIN_FILTER, seq[0].cast<FM>());
					if(n >= 2) self.setFilter(FP::MAG_FILTER, seq[1].cast<FM>());
				}
			}
		)
		.def_property(
			"internalFormat",
			&osg::Texture::getInternalFormat,
			&osg::Texture::setInternalFormat
		)
		.def_property(
			"internalFormatMode",
			&osg::Texture::getInternalFormatMode,
			&osg::Texture::setInternalFormatMode
		)
		.def_property_readonly("internalFormatType", &osg::Texture::getInternalFormatType)
		.def_property(
			"sourceFormat",
			&osg::Texture::getSourceFormat,
			&osg::Texture::setSourceFormat
		)
		.def_property(
			"sourceType",
			&osg::Texture::getSourceType,
			&osg::Texture::setSourceType
		)
		.def_property(
			"anisotropy",
			&osg::Texture::getMaxAnisotropy,
			&osg::Texture::setMaxAnisotropy
		)
	;

	// setBorderColor
	// getBorderColor
    //
	// setBorderWidth
	// getBorderWidth
    //
	// setMinLOD
	// getMinLOD
    //
	// setMaxLOD
	// getMaxLOD
    //
	// setLODBias
	// getLODBias
    //
	// setSwizzle
	// getSwizzle
    //
	// setUseHardwareMipMapGeneration
	// getUseHardwareMipMapGeneration
    //
	// setResizeNonPowerOfTwoHint
	// getResizeNonPowerOfTwoHint
    //
	// isCompressedInternalFormat
    //
	// selectSizedInternalFormat
    //
	// allocateMipmapLevels

	auto tex2d = py::class_<
		osg::Texture2D,
		osg::Texture,
		osg::ref_ptr<osg::Texture2D>
	>(m, "Texture2D")
		.def(py::init<>())
		.def(py::init([](size_t width, size_t height) {
			auto* t = new osg::Texture2D();

			t->setTextureSize(static_cast<int>(width), static_cast<int>(height));

			return t;
		}))
		.def_property(
			"size",
			[](osg::Texture2D& self) {
				return py::make_tuple(self.getTextureWidth(), self.getTextureHeight());
			},
			[](osg::Texture2D& self, py::object obj) {
				auto seq = obj.cast<py::sequence>();

				if(seq.size() != 2) throw py::value_error("size requires width/height");

				self.setTextureSize(seq[0].cast<int>(), seq[1].cast<int>());
			}
		)
	;
}

}
