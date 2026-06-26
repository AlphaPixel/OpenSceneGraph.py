#include "Texture.hpp"

namespace pyosg {

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
				if(py::isinstance<osg::Texture::WrapMode>(obj)) {
					auto v = obj.cast<osg::Texture::WrapMode>();

					self.setWrap(osg::Texture::WrapParameter::WRAP_S, v);
					self.setWrap(osg::Texture::WrapParameter::WRAP_T, v);
					self.setWrap(osg::Texture::WrapParameter::WRAP_R, v);
				}

				else {
					auto seq = obj.cast<py::sequence>();
					auto n = seq.size();

					if(n >= 1) self.setWrap(
						osg::Texture::WrapParameter::WRAP_S,
						seq[0].cast<osg::Texture::WrapMode>()
					);

					if(n >= 2) self.setWrap(
						osg::Texture::WrapParameter::WRAP_T,
						seq[1].cast<osg::Texture::WrapMode>()
					);

					if(n >= 3) self.setWrap(
						osg::Texture::WrapParameter::WRAP_R,
						seq[2].cast<osg::Texture::WrapMode>()
					);
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
				if(py::isinstance<osg::Texture::FilterMode>(obj)) {
					auto v = obj.cast<osg::Texture::FilterMode>();

					// MAG filter only accepts LINEAR or NEAREST - strip mipmap component
					osg::Texture::FilterMode mag =
						(v == osg::Texture::NEAREST ||
						 v == osg::Texture::NEAREST_MIPMAP_LINEAR ||
						 v == osg::Texture::NEAREST_MIPMAP_NEAREST)
						? osg::Texture::NEAREST
						: osg::Texture::LINEAR
					;

					self.setFilter(osg::Texture::FilterParameter::MIN_FILTER, v);
					self.setFilter(osg::Texture::FilterParameter::MAG_FILTER, mag);
				}

				else {
					auto seq = obj.cast<py::sequence>();
					auto n = seq.size();

					if(n >= 1) self.setFilter(
						osg::Texture::FilterParameter::MIN_FILTER,
						seq[0].cast<osg::Texture::FilterMode>()
					);

					if(n >= 2) self.setFilter(
						osg::Texture::FilterParameter::MAG_FILTER,
						seq[1].cast<osg::Texture::FilterMode>()
					);
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

		// TODO: Convert to `pyx::*Proxy`!
		.def_property(
			"image",
			py::cpp_function(
				// py::overload_cast<osg::Image*>(&osg::Texture::getImage),
				[](osg::Texture& self) { return self.getImage(0); },
				py::return_value_policy::reference_internal
			),
			py::cpp_function(
				/* [](osg::Texture& self, unsigned int face, osg::Image* data) {
					self.setImage(face, data);
				}, py::keep_alive<1, 2>() */
				[](osg::Texture& self, py::object obj) {
					auto seq = obj.cast<py::sequence>();
					auto n = seq.size();

					if(n == 1) self.setImage(0, seq[0].cast<osg::Image*>());

					else if(n == 2) self.setImage(
						seq[0].cast<unsigned int>(),
						seq[1].cast<osg::Image*>()
					);

					else throw py::value_error("Image or face/Image required");
				}
			)
		)

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

		.def_property(
			"useHardwareMipMapGeneration",
			&osg::Texture::getUseHardwareMipMapGeneration,
			&osg::Texture::setUseHardwareMipMapGeneration
		)
		.def(
			"allocateMipmapLevels",
			&osg::Texture::allocateMipmapLevels,
			"Mark all mip levels dirty so OSG calls glTexImage2D for each level "
			"during the next apply(), pre-allocating storage before FBO attachment."
		)

		.def_property(
			"resizeNonPowerOfTwoHint",
			&osg::Texture::getResizeNonPowerOfTwoHint,
			&osg::Texture::setResizeNonPowerOfTwoHint
		)

		// isCompressedInternalFormat
		//
		// selectSizedInternalFormat
	;

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
		.def("apply", &osg::Texture2D::apply)
	;

	auto texcm = py::class_<
		osg::TextureCubeMap,
		osg::Texture,
		osg::ref_ptr<osg::TextureCubeMap>
	>(m, "TextureCubeMap")
		.def(py::init<>())
		.def_property(
			"size",
			[](osg::TextureCubeMap& self) { return self.getTextureWidth(); },
			[](osg::TextureCubeMap& self, int s) { self.setTextureSize(s, s); }
		)
		.def_property(
			"numMipmapLevels",
			&osg::TextureCubeMap::getNumMipmapLevels,
			&osg::TextureCubeMap::setNumMipmapLevels
		)
		.def("apply", &osg::TextureCubeMap::apply)
		.def("setFace", [](osg::TextureCubeMap& self, osg::TextureCubeMap::Face face, osg::Image* img) {
			self.setImage(static_cast<unsigned int>(face), img);
		}, py::keep_alive<1, 3>())
		.def("getFace", [](osg::TextureCubeMap& self, osg::TextureCubeMap::Face face) {
			return self.getImage(static_cast<unsigned int>(face));
		}, py::return_value_policy::reference_internal)
	;

	py::enum_<osg::TextureCubeMap::Face>(texcm, "Face")
		.value("POSITIVE_X", osg::TextureCubeMap::POSITIVE_X)
		.value("NEGATIVE_X", osg::TextureCubeMap::NEGATIVE_X)
		.value("POSITIVE_Y", osg::TextureCubeMap::POSITIVE_Y)
		.value("NEGATIVE_Y", osg::TextureCubeMap::NEGATIVE_Y)
		.value("POSITIVE_Z", osg::TextureCubeMap::POSITIVE_Z)
		.value("NEGATIVE_Z", osg::TextureCubeMap::NEGATIVE_Z)
		.export_values()
	;
}

}
