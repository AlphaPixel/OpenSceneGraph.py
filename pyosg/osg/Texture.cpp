#include "Texture.hpp"

namespace pybind11x {
	template<>
	void kwargs_init_own(osg::Texture& self, const py::kwargs& kwargs) {
		if(kwargs.contains("wrap")) pyosg::detail::texture_wrap_property_setter()(
			self,
			kwargs["wrap"]
		);

		if(kwargs.contains("filter")) pyosg::detail::texture_filter_property_setter()(
			self,
			kwargs["filter"]
		);

		if(kwargs.contains("internalFormat")) self.setInternalFormat(
			kwargs["internalFormat"].cast<GLint>()
		);

		if(kwargs.contains("sourceFormat")) self.setSourceFormat(
			kwargs["sourceFormat"].cast<GLenum>()
		);

		if(kwargs.contains("sourceType")) self.setSourceType(
			kwargs["sourceType"].cast<GLenum>()
		);

		if(kwargs.contains("image")) pyosg::detail::texture_image_property_setter()(
			self,
			kwargs["image"]
		);

		if(kwargs.contains("useHardwareMipMapGeneration")) self.setUseHardwareMipMapGeneration(
			kwargs["useHardwareMipMapGeneration"].cast<bool>()
		);
	}

	template<>
	void kwargs_init_own(osg::Texture2D& self, const py::kwargs& kwargs) {
		if(kwargs.contains("size")) {
			auto vals = try_unpack_sequence<int, int>(kwargs["size"]);

			if(!vals) throw py::value_error("size requires (width, height)");

			auto& [width, height] = *vals;

			self.setTextureSize(width, height);
		}

		if(kwargs.contains("numMipmapLevels")) self.setNumMipmapLevels(
			kwargs["numMipmapLevels"].cast<unsigned int>()
		);
	}
}

namespace pyosg {

void bind_Texture(py::module_& m) {
	auto tex = py::class_<
		osg::Texture,
		// detail::Texture
		osg::StateAttribute,
		osg::ref_ptr<osg::Texture>
	>(
		m,
		"Texture",
		"Base class for a StateAttribute wrapping a GL texture object, its image data, and "
		"its wrap/filter/format parameters."
	);

	py::enum_<osg::Texture::WrapParameter>(
		tex,
		"WrapParameter",
		"Which texture coordinate axis (S/T/R) a wrap mode applies to; used as the key for "
		"getWrap()/setWrap()."
	)
		.value("WRAP_S", osg::Texture::WRAP_S)
		.value("WRAP_T", osg::Texture::WRAP_T)
		.value("WRAP_R", osg::Texture::WRAP_R)
		.export_values()
	;

	py::enum_<osg::Texture::WrapMode>(
		tex,
		"WrapMode",
		"How texture coordinates outside [0,1] are handled: clamped, mirrored, or repeated."
	)
		.value("CLAMP", osg::Texture::CLAMP)
		.value("CLAMP_TO_EDGE", osg::Texture::CLAMP_TO_EDGE)
		.value("CLAMP_TO_BORDER", osg::Texture::CLAMP_TO_BORDER)
		.value("REPEAT", osg::Texture::REPEAT)
		.value("MIRROR", osg::Texture::MIRROR)
		.export_values()
	;

	py::enum_<osg::Texture::FilterParameter>(
		tex,
		"FilterParameter",
		"Selects which filter slot (MIN_FILTER or MAG_FILTER) a FilterMode value configures; "
		"used as the key for getFilter()/setFilter()."
	)
		.value("MIN_FILTER", osg::Texture::MIN_FILTER)
		.value("MAG_FILTER", osg::Texture::MAG_FILTER)
		.export_values()
	;

	py::enum_<osg::Texture::FilterMode>(
		tex,
		"FilterMode",
		"Minification/magnification filtering mode, including mipmap variants; note MAG_FILTER "
		"only accepts the non-mipmap LINEAR/NEAREST values (see the `filter` property)."
	)
		.value("LINEAR", osg::Texture::LINEAR)
		.value("LINEAR_MIPMAP_LINEAR", osg::Texture::LINEAR_MIPMAP_LINEAR)
		.value("LINEAR_MIPMAP_NEAREST", osg::Texture::LINEAR_MIPMAP_NEAREST)
		.value("NEAREST", osg::Texture::NEAREST)
		.value("NEAREST_MIPMAP_LINEAR", osg::Texture::NEAREST_MIPMAP_LINEAR)
		.value("NEAREST_MIPMAP_NEAREST", osg::Texture::NEAREST_MIPMAP_NEAREST)
		.export_values()
	;

	py::enum_<osg::Texture::InternalFormatMode>(
		tex,
		"InternalFormatMode",
		"Chooses how the GPU-side internal format is picked: from the source Image's own "
		"format, a user-supplied `internalFormat` value, or a specific compression scheme."
	)
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

	py::enum_<osg::Texture::InternalFormatType>(
		tex,
		"InternalFormatType",
		"The resolved internal format's value category (normalized, float, signed/unsigned "
		"integer); read via `internalFormatType`, derived from `internalFormat`."
	)
		.value("NORMALIZED", osg::Texture::NORMALIZED)
		.value("FLOAT", osg::Texture::FLOAT)
		.value("SIGNED_INTEGER", osg::Texture::SIGNED_INTEGER)
		.value("UNSIGNED_INTEGER", osg::Texture::UNSIGNED_INTEGER)
		.export_values()
	;

	py::enum_<osg::Texture::GenerateMipmapMode>(
		tex,
		"GenerateMipmapMode",
		"How/when mipmaps are auto-generated for this texture: never, on every apply(), or "
		"only via a GL_GENERATE_MIPMAP tex-parameter hint."
	)
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
			detail::texture_wrap_property_setter(),
			"Tuple-valued wrap mode. Read returns (S, T, R) WrapMode values; write accepts "
			"a single WrapMode (applied to all axes) or a 1-3 element sequence in S,T,R "
			"order."
		)
		.def_property(
			"filter",
			[](osg::Texture& self) {
				return py::make_tuple(
					self.getFilter(osg::Texture::MIN_FILTER),
					self.getFilter(osg::Texture::MAG_FILTER)
				);
			},
			detail::texture_filter_property_setter(),
			"Tuple-valued filter mode: read returns (MIN, MAG) FilterMode values; write "
			"accepts a single FilterMode (MAG is auto-clamped to its non-mipmap "
			"LINEAR/NEAREST equivalent) or an explicit (MIN, MAG) pair."
		)
		.def_property(
			"internalFormat",
			&osg::Texture::getInternalFormat,
			&osg::Texture::setInternalFormat,
			"The GL internal (GPU-side) format, e.g. GL_RGBA8 or GL_RGB32F; only takes "
			"effect when internalFormatMode is USE_USER_DEFINED_FORMAT. Prefer GL_RGB32F "
			"over GL_RGB16F for HDR data - half-float silently overflows to +Inf above "
			"65504 and poisons IBL bakes."
		)
		.def_property(
			"internalFormatMode",
			&osg::Texture::getInternalFormatMode,
			&osg::Texture::setInternalFormatMode,
			"Chooses how internalFormat is determined - see InternalFormatMode."
		)
		.def_property_readonly(
			"internalFormatType",
			&osg::Texture::getInternalFormatType,
			"The resolved internal format's value category; only meaningful after "
			"internalFormat has actually been applied at least once."
		)
		.def_property(
			"sourceFormat",
			&osg::Texture::getSourceFormat,
			&osg::Texture::setSourceFormat,
			"The GL pixel format of the source data passed to glTexImage/glTexSubImage "
			"(e.g. GL_RGBA), independent of the GPU-side internalFormat."
		)
		.def_property(
			"sourceType",
			&osg::Texture::getSourceType,
			&osg::Texture::setSourceType,
			"The GL data type of the source pixels passed to glTexImage/glTexSubImage "
			"(e.g. GL_UNSIGNED_BYTE, GL_FLOAT)."
		)
		.def_property(
			"anisotropy",
			&osg::Texture::getMaxAnisotropy,
			&osg::Texture::setMaxAnisotropy,
			"Maximum anisotropic filtering level (1.0 disables it); actually applied value "
			"is clamped to what the driver reports for GL_MAX_TEXTURE_MAX_ANISOTROPY."
		)

		// TODO: Convert to `pyx::*Proxy`!
		.def_property(
			"image",
			py::cpp_function(
				// py::overload_cast<osg::Image*>(&osg::Texture::getImage),
				[](osg::Texture& self) { return self.getImage(0); },
				py::return_value_policy::reference_internal
			),
			detail::texture_image_property_setter(),
			"The Image bound to texture unit/mip level 0; assigning replaces it, sharing "
			"ownership via ref_ptr."
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
			&osg::Texture::setUseHardwareMipMapGeneration,
			"Whether OSG asks the driver to auto-generate mipmaps (glGenerateMipmap) instead "
			"of relying on precomputed levels. FBO render targets need an OSG patch "
			"(etc/patches/) for this flag to actually be honored."
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
			&osg::Texture::setResizeNonPowerOfTwoHint,
			"Whether OSG may resize a non-power-of-two image before upload; irrelevant on GL "
			"contexts with native NPOT texture support."
		)

		// isCompressedInternalFormat
		//
		// selectSizedInternalFormat
	;

	auto tex2d = py::class_<
		osg::Texture2D,
		osg::Texture,
		osg::ref_ptr<osg::Texture2D>
	>(
		m,
		"Texture2D",
		"A 2D GL texture, the most common Texture used for surface color/normal/data maps "
		"and 2D render targets."
	)
		.def(
			py::init<>(),
			"Create an empty Texture2D with no size or image set."
		)
		.def(py::init([](size_t width, size_t height) {
			auto* t = new osg::Texture2D();

			t->setTextureSize(static_cast<int>(width), static_cast<int>(height));

			return t;
		}),
			"Create a Texture2D pre-sized to (width, height) with no image data."
		)
		.def(
			py::init(pyx::kwargs_ctor<osg::Texture2D>()),
			"Create a Texture2D from keyword arguments matching its properties (wrap, "
			"filter, internalFormat, image, size, numMipmapLevels, ...)."
		)
		.def_property(
			"size",
			[](osg::Texture2D& self) {
				return py::make_tuple(self.getTextureWidth(), self.getTextureHeight());
			},
			[](osg::Texture2D& self, py::object obj) {
				auto vals = pyx::try_unpack_sequence<int, int>(obj);

				if(!vals) throw py::value_error("size requires (width, height)");

				auto& [width, height] = *vals;

				self.setTextureSize(width, height);
			},
			"The texture's (width, height) in texels; write calls setTextureSize (no "
			"reallocation happens until apply())."
		)
		.def_property(
			"numMipmapLevels",
			&osg::Texture2D::getNumMipmapLevels,
			&osg::Texture2D::setNumMipmapLevels,
			"Explicit mipmap level count used when useHardwareMipMapGeneration is off; "
			"must be set correctly before first use or FBO mip-level attachment silently "
			"fails."
		)
		.def(
			"apply",
			&osg::Texture2D::apply,
			"Bind and upload this texture's current state to the GL context (normally "
			"called internally by OSG's State, rarely by user code)."
		)
	;

	auto texcm = py::class_<
		osg::TextureCubeMap,
		osg::Texture,
		osg::ref_ptr<osg::TextureCubeMap>
	>(
		m,
		"TextureCubeMap",
		"A 6-faced cube map Texture, used for skyboxes and image-based lighting environments."
	)
		.def(
			py::init<>(),
			"Create an empty TextureCubeMap with no size or face images set."
		)
		.def_property(
			"size",
			[](osg::TextureCubeMap& self) { return self.getTextureWidth(); },
			[](osg::TextureCubeMap& self, int s) { self.setTextureSize(s, s); },
			"The cube map's per-face edge length in texels (all 6 faces are always "
			"square and share the same size)."
		)
		.def_property(
			"numMipmapLevels",
			&osg::TextureCubeMap::getNumMipmapLevels,
			&osg::TextureCubeMap::setNumMipmapLevels,
			"Explicit mipmap level count used when useHardwareMipMapGeneration is off; "
			"must be set correctly before first use or FBO mip-level attachment silently "
			"fails."
		)
		.def(
			"apply",
			&osg::TextureCubeMap::apply,
			"Bind and upload this texture's current state to the GL context (normally "
			"called internally by OSG's State, rarely by user code)."
		)
		.def(
			"setFace",
			[](osg::TextureCubeMap& self, osg::TextureCubeMap::Face face, osg::Image* img) {
				self.setImage(static_cast<unsigned int>(face), img);
			},
			"Assign the Image for one cube face; the texture keeps a reference so the "
			"Image stays alive.",
			py::keep_alive<1, 3>()
		)
		.def(
			"getFace",
			[](osg::TextureCubeMap& self, osg::TextureCubeMap::Face face) {
				return self.getImage(static_cast<unsigned int>(face));
			},
			"Return the Image bound to one cube face, or None if unset.",
			py::return_value_policy::reference_internal
		)
	;

	py::enum_<osg::TextureCubeMap::Face>(
		texcm,
		"Face",
		"Which of the 6 cube faces (+X/-X/+Y/-Y/+Z/-Z) setFace()/getFace() target."
	)
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
