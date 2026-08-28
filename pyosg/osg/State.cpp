#include "State.hpp"

namespace pyosg {

void bind_State(py::module_& m) {
	py::class_<osg::FrameStamp, osg::Referenced, osg::ref_ptr<osg::FrameStamp>>(
		m,
		"FrameStamp",
		"Timing information (frame number, reference/simulation/calendar time) for a single "
		"traversal, shared by NodeVisitor and State."
	)
		.def(py::init<>(), "Create a FrameStamp with frame/time fields all zeroed.")
		.def(py::init<const osg::FrameStamp&>(), "Create a copy of another FrameStamp.")
		.def_property("frameNumber",
			&osg::FrameStamp::getFrameNumber,
			&osg::FrameStamp::setFrameNumber,
			"The traversal's integer frame count, incremented once per Viewer.frame()."
		)
		.def_property("referenceTime",
			&osg::FrameStamp::getReferenceTime,
			&osg::FrameStamp::setReferenceTime,
			"Wall-clock seconds since the Viewer started, unaffected by simulation "
			"pause/scale."
		)
		.def_property("simulationTime",
			&osg::FrameStamp::getSimulationTime,
			&osg::FrameStamp::setSimulationTime,
			"Seconds of simulated time, which animation/update callbacks should read "
			"instead of referenceTime; it can be paused, scaled, or reset independent "
			"of the wall clock."
		)
		.def_property("calendarTime",
			&osg::FrameStamp::getCalendarTime,
			&osg::FrameStamp::setCalendarTime,
			"An optional tm-style wall-clock timestamp for this frame; unset unless "
			"something explicitly assigns it."
		)
	;

	// Per-context capability/version info, populated by OSG itself from the live driver once a
	// GraphicsContext has been realized -- the answer to "what GL version/profile did this
	// context actually negotiate", as opposed to what OSG was compiled to SUPPORT (a fixed,
	// build-time property that doesn't vary per install of this project's own GL3/CORE-only
	// wheels). Only the plain informational fields are bound here, not the ~300 raw GL function
	// pointers GLExtensions also carries -- those aren't meaningfully callable from Python and
	// are out of scope for what this binding is for.
	py::class_<
		osg::GLExtensions,
		osg::Referenced,
		osg::ref_ptr<osg::GLExtensions>
	>(
		m,
		"GLExtensions",
		"Per-GL-context capability/version info, reached via State.glExtensions."
	)
		.def_readonly("contextID", &osg::GLExtensions::contextID,
			"The graphics-context index these capability flags were queried for; matches "
			"State.contextID/GraphicsContext.state.contextID."
		)
		.def_readonly("glVersion", &osg::GLExtensions::glVersion,
			"The context's negotiated OpenGL version as a float, e.g. 4.3."
		)
		.def_readonly("glslLanguageVersion", &osg::GLExtensions::glslLanguageVersion,
			"The context's supported GLSL language version as a float, e.g. 4.3."
		)
		.def_readonly("isGlslSupported", &osg::GLExtensions::isGlslSupported,
			"Whether the GL_ARB_shading_language_100 extension (or core GLSL) is available."
		)
		.def_readonly("isShaderObjectsSupported", &osg::GLExtensions::isShaderObjectsSupported,
			"Whether GL_ARB_shader_objects (or core shader-object support) is available."
		)
		.def_readonly("isVertexShaderSupported", &osg::GLExtensions::isVertexShaderSupported,
			"Whether vertex shaders are supported by this context."
		)
		.def_readonly("isFragmentShaderSupported", &osg::GLExtensions::isFragmentShaderSupported,
			"Whether fragment shaders are supported by this context."
		)
		.def_readonly("isLanguage100Supported", &osg::GLExtensions::isLanguage100Supported,
			"Whether GLSL 1.00 (the original ARB shading language) is supported."
		)
		.def_readonly(
			"isGeometryShader4Supported",
			&osg::GLExtensions::isGeometryShader4Supported,
			"Whether GL_EXT_geometry_shader4-style geometry shaders are supported."
		)
		.def_readonly(
			"areTessellationShadersSupported",
			&osg::GLExtensions::areTessellationShadersSupported,
			"Whether tessellation control/evaluation shader stages are supported."
		)
		.def_readonly("isGpuShader4Supported", &osg::GLExtensions::isGpuShader4Supported,
			"Whether GL_EXT_gpu_shader4 integer/bitwise GLSL operations are supported."
		)
		.def_readonly(
			"isUniformBufferObjectSupported",
			&osg::GLExtensions::isUniformBufferObjectSupported,
			"Whether Uniform Buffer Objects (UBOs) are supported by this context."
		)
		.def_readonly(
			"isGetProgramBinarySupported",
			&osg::GLExtensions::isGetProgramBinarySupported,
			"Whether glGetProgramBinary (compiled-program caching) is supported."
		)
		.def_readonly("isGpuShaderFp64Supported", &osg::GLExtensions::isGpuShaderFp64Supported,
			"Whether double-precision (fp64) GLSL types/operations are supported."
		)
		.def_readonly(
			"isShaderAtomicCountersSupported",
			&osg::GLExtensions::isShaderAtomicCountersSupported,
			"Whether GLSL atomic counters are supported."
		)
		.def_readonly("isRectangleSupported", &osg::GLExtensions::isRectangleSupported,
			"Whether GL_ARB_texture_rectangle (non-power-of-two, non-normalized-coord "
			"textures) is supported."
		)
		.def_readonly("isCubeMapSupported", &osg::GLExtensions::isCubeMapSupported,
			"Whether cube map textures are supported."
		)
		.def_readonly("isClipControlSupported", &osg::GLExtensions::isClipControlSupported,
			"Whether glClipControl (reversed/zero-to-one depth ranges) is supported."
		)
	;

	py::class_<osg::State, osg::Referenced, osg::ref_ptr<osg::State>>(
		m,
		"State",
		"The per-GL-context render state (current matrices, contextID, FrameStamp) tracked "
		"during a draw traversal."
	)
		.def_property_readonly("projectionMatrix",
			&osg::State::getProjectionMatrix,
			py::return_value_policy::reference_internal,
			"The current top-of-stack projection matrix for this State."
		)
		.def_property_readonly("contextID", &osg::State::getContextID,
			"The index of the GL context this State belongs to; the key used to look up "
			"per-context resources like GLExtensions."
		)
		// Not cached via a PropertySlot like most other ref_ptr-returning properties here --
		// osg::GLExtensions::Get() already IS the per-contextID cache (a static registry OSG
		// itself owns), a second identity cache on top of it would only add complexity for no
		// benefit.
		.def_property_readonly("glExtensions", [](osg::State& self) {
			return osg::GLExtensions::Get(self.getContextID(), true);
		},
			"This State's GLExtensions capability/version info, resolved via the shared "
			"per-contextID registry (not a per-State copy)."
		)
		/* .def("getGraphicsContext",
			&osg::State::getGraphicsContext,
			py::return_value_policy::reference
		) */
		.def_property_readonly("frameStamp",
			py::overload_cast<>(&osg::State::getFrameStamp, py::const_),
			py::return_value_policy::reference,
			"The FrameStamp for the frame currently being drawn, or None if not set."
		)
		.def("setUseModelViewAndProjectionUniforms",
			&osg::State::setUseModelViewAndProjectionUniforms,
			"Enable/disable OSG automatically supplying osg_ModelViewMatrix/"
			"osg_ProjectionMatrix (and related) uniforms to shaders."
		)
		.def("setUseVertexAttributeAliasing",
			&osg::State::setUseVertexAttributeAliasing,
			"Enable/disable binding the fixed-function vertex attributes (osg_Vertex, "
			"osg_Normal, osg_Color, etc.) to generic vertex attribute locations for use "
			"in shaders."
		)
		.def("__repr__", [](const osg::State& self) {
			std::ostringstream oss;

			self.print(oss);

			return py::str(oss.str());
		}, "Return OSG's own State.print() dump (attribute/mode stacks) as the repr.")
	;

	auto sa = py::class_<
		osg::StateAttribute,
		osg::Object,
		osg::ref_ptr<osg::StateAttribute>
	>(
		m,
		"StateAttribute",
		"Base class for a single piece of OpenGL state (Texture, BlendFunc, Depth, Program, "
		"etc.) that can be attached to a StateSet."
	)
		// .def(py::init<>())
		// .def(py::init<const osg::StateAttribute&>())

		// TODO: OSG uses -1, 0, 1 to define more than just what Python calls true/false. How do we
		// handle this in a Pythonic way, though?
		/* .def("__eq__", [](const osg::StateAttribute& a, const osg::StateAttribute& b) {
			// Different dynamic types are not equal! I think this might be the first time I've EVER
			// used `typeid` in my OWN CODE!?
			if(typeid(a) != typeid(b)) return false;

			return !a.compare(b);
		})
		.def("__ne__", [](const osg::StateAttribute& a, const osg::StateAttribute& b) {
			if(typeid(a) != typeid(b)) return true;

			return a.compare(b);
		}); */

		// TODO: Implement `.def(py::self < py::self)`, etc for these! However, I need to solve the
		// `compare` issue above before I can address these...
		// bool operator < (const StateAttribute& rhs) const { return compare(rhs)<0; }
		// bool operator == (const StateAttribute& rhs) const { return compare(rhs)==0; }
		// bool operator != (const StateAttribute& rhs) const { return compare(rhs)!=0; }

		.def_property_readonly("type", &osg::StateAttribute::getType,
			"This attribute's StateAttribute.Type (TEXTURE, DEPTH, BLENDFUNC, etc.), used "
			"as the key in StateSet.attributes."
		)
		.def_property_readonly("member", &osg::StateAttribute::getMember,
			"The sub-index within `type` this instance occupies - e.g. which light number "
			"or clip plane number - 0 for attributes that aren't multi-instanced."
		)
		.def_property_readonly("typeMember", &osg::StateAttribute::getTypeMemberPair,
			"The (type, member) pair that together uniquely identify this attribute's slot "
			"in a StateSet."
		)
	;

	sa.attr("GLMode") = detail::builtin_int();
	sa.attr("GLModeValue") = detail::builtin_int();
	sa.attr("OverrideValue") = detail::builtin_int();

	py::enum_<osg::StateAttribute::Values>(sa, "Values", py::arithmetic(),
		"GL mode flags (ON/OFF plus the OVERRIDE/PROTECTED/INHERIT modifiers) used "
		"throughout StateSet.modes and StateSet.attributes - combine with `|` since this "
		"enum is arithmetic."
	)
		.value("OFF", osg::StateAttribute::Values::OFF)
		.value("ON", osg::StateAttribute::Values::ON)
		.value("OVERRIDE", osg::StateAttribute::Values::OVERRIDE)
		.value("PROTECTED", osg::StateAttribute::Values::PROTECTED)
		.value("INHERIT", osg::StateAttribute::Values::INHERIT)
		.export_values()
	;

	py::enum_<osg::StateAttribute::Type>(sa, "Type",
		"The kind of GL state a StateAttribute controls (TEXTURE, DEPTH, PROGRAM, "
		"BLENDFUNC, etc.); the key type for StateSet.attributes/StateSet.textureAttributes."
	)
		.value("TEXTURE", osg::StateAttribute::TEXTURE)
		.value("POLYGONMODE", osg::StateAttribute::POLYGONMODE)
		.value("POLYGONOFFSET", osg::StateAttribute::POLYGONOFFSET)
		.value("MATERIAL", osg::StateAttribute::MATERIAL)
		.value("ALPHAFUNC", osg::StateAttribute::ALPHAFUNC)
		.value("ANTIALIAS", osg::StateAttribute::ANTIALIAS)
		.value("COLORTABLE", osg::StateAttribute::COLORTABLE)
		.value("CULLFACE", osg::StateAttribute::CULLFACE)
		.value("FOG", osg::StateAttribute::FOG)
		.value("FRONTFACE", osg::StateAttribute::FRONTFACE)
		.value("LIGHT", osg::StateAttribute::LIGHT)
		.value("POINT", osg::StateAttribute::POINT)
		.value("LINEWIDTH", osg::StateAttribute::LINEWIDTH)
		.value("LINESTIPPLE", osg::StateAttribute::LINESTIPPLE)
		.value("POLYGONSTIPPLE", osg::StateAttribute::POLYGONSTIPPLE)
		.value("SHADEMODEL", osg::StateAttribute::SHADEMODEL)
		.value("TEXENV", osg::StateAttribute::TEXENV)
		.value("TEXENVFILTER", osg::StateAttribute::TEXENVFILTER)
		.value("TEXGEN", osg::StateAttribute::TEXGEN)
		.value("TEXMAT", osg::StateAttribute::TEXMAT)
		.value("LIGHTMODEL", osg::StateAttribute::LIGHTMODEL)
		.value("BLENDFUNC", osg::StateAttribute::BLENDFUNC)
		.value("BLENDEQUATION", osg::StateAttribute::BLENDEQUATION)
		.value("LOGICOP", osg::StateAttribute::LOGICOP)
		.value("STENCIL", osg::StateAttribute::STENCIL)
		.value("COLORMASK", osg::StateAttribute::COLORMASK)
		.value("DEPTH", osg::StateAttribute::DEPTH)
		.value("VIEWPORT", osg::StateAttribute::VIEWPORT)
		.value("SCISSOR", osg::StateAttribute::SCISSOR)
		.value("BLENDCOLOR", osg::StateAttribute::BLENDCOLOR)
		.value("MULTISAMPLE", osg::StateAttribute::MULTISAMPLE)
		.value("CLIPPLANE", osg::StateAttribute::CLIPPLANE)
		.value("COLORMATRIX", osg::StateAttribute::COLORMATRIX)
		.value("VERTEXPROGRAM", osg::StateAttribute::VERTEXPROGRAM)
		.value("FRAGMENTPROGRAM", osg::StateAttribute::FRAGMENTPROGRAM)
		.value("POINTSPRITE", osg::StateAttribute::POINTSPRITE)
		.value("PROGRAM", osg::StateAttribute::PROGRAM)
		.value("CLAMPCOLOR", osg::StateAttribute::CLAMPCOLOR)
		.value("HINT", osg::StateAttribute::HINT)
		.value("SAMPLEMASKI", osg::StateAttribute::SAMPLEMASKI)
		.value("PRIMITIVERESTARTINDEX", osg::StateAttribute::PRIMITIVERESTARTINDEX)
		.value("CLIPCONTROL", osg::StateAttribute::CLIPCONTROL)
		.value("VALIDATOR", osg::StateAttribute::VALIDATOR)
		.value("VIEWMATRIXEXTRACTOR", osg::StateAttribute::VIEWMATRIXEXTRACTOR)
		.value("OSGNV_PARAMETER_BLOCK", osg::StateAttribute::OSGNV_PARAMETER_BLOCK)
		.value("OSGNVEXT_TEXTURE_SHADER", osg::StateAttribute::OSGNVEXT_TEXTURE_SHADER)
		.value("OSGNVEXT_VERTEX_PROGRAM", osg::StateAttribute::OSGNVEXT_VERTEX_PROGRAM)
		.value("OSGNVEXT_REGISTER_COMBINERS", osg::StateAttribute::OSGNVEXT_REGISTER_COMBINERS)
		.value("OSGNVCG_PROGRAM", osg::StateAttribute::OSGNVCG_PROGRAM)
		.value("OSGNVSLANG_PROGRAM", osg::StateAttribute::OSGNVSLANG_PROGRAM)
		.value("OSGNVPARSE_PROGRAM_PARSER", osg::StateAttribute::OSGNVPARSE_PROGRAM_PARSER)
		.value("UNIFORMBUFFERBINDING", osg::StateAttribute::UNIFORMBUFFERBINDING)
		.value("TRANSFORMFEEDBACKBUFFERBINDING", osg::StateAttribute::TRANSFORMFEEDBACKBUFFERBINDING)
		.value("ATOMICCOUNTERBUFFERBINDING", osg::StateAttribute::ATOMICCOUNTERBUFFERBINDING)
		.value("PATCH_PARAMETER", osg::StateAttribute::PATCH_PARAMETER)
		.value("FRAME_BUFFER_OBJECT", osg::StateAttribute::FRAME_BUFFER_OBJECT)
		.value("VERTEX_ATTRIB_DIVISOR", osg::StateAttribute::VERTEX_ATTRIB_DIVISOR)
		.value("SHADERSTORAGEBUFFERBINDING", osg::StateAttribute::SHADERSTORAGEBUFFERBINDING)
		.value("INDIRECTDRAWBUFFERBINDING", osg::StateAttribute::INDIRECTDRAWBUFFERBINDING)
		.value("VIEWPORTINDEXED", osg::StateAttribute::VIEWPORTINDEXED)
		.value("DEPTHRANGEINDEXED", osg::StateAttribute::DEPTHRANGEINDEXED)
		.value("SCISSORINDEXED", osg::StateAttribute::SCISSORINDEXED)
		.value("BINDIMAGETEXTURE", osg::StateAttribute::BINDIMAGETEXTURE)
		.value("SAMPLER", osg::StateAttribute::SAMPLER)
		.value("CAPABILITY", osg::StateAttribute::CAPABILITY)
		.export_values()
	;

	auto ss = py::class_<
		osg::StateSet,
		osg::Object,
		osg::ref_ptr<osg::StateSet>
	>(
		m,
		"StateSet",
		"A collection of StateAttributes, GL modes, uniforms, and defines attached to a Node "
		"or Drawable to control how it renders. .attributes/.textureAttributes/.uniforms/"
		".modes/.defines are dict-like mapping proxies (e.g. stateSet.uniforms[\"name\"] = ...) "
		"replacing the set/get/remove*Attribute()/*Uniform()/*Mode() method sprawl."
	)
		.def(py::init<>(), "Create an empty StateSet with no attributes, modes, or uniforms.")
		.def(py::init<const osg::StateSet&>(), "Create a copy of another StateSet.")
	;

	// TODO: So, this call COULD WORK ... with LOTS of caveats. Explain more!
	// py::bind_vector<std::vector<osg::Node*>>(ss, "ParentList");

	py::enum_<osg::StateSet::RenderingHint>(ss, "RenderingHint",
		"A hint for which render bin group (opaque vs. transparent) a StateSet's Drawables "
		"should sort into, used by the default RenderBin setup."
	)
		.value("DEFAULT_BIN", osg::StateSet::DEFAULT_BIN)
		.value("OPAQUE_BIN", osg::StateSet::OPAQUE_BIN)
		.value("TRANSPARENT_BIN", osg::StateSet::TRANSPARENT_BIN)
		.export_values()
	;

	py::enum_<osg::StateSet::RenderBinMode>(ss, "RenderBinMode",
		"How this StateSet's explicit binNumber/binName should combine with values "
		"inherited from parent StateSets - see setRenderBinDetails()/renderBinMode."
	)
		.value("INHERIT_RENDERBIN_DETAILS", osg::StateSet::INHERIT_RENDERBIN_DETAILS)
		.value("USE_RENDERBIN_DETAILS", osg::StateSet::USE_RENDERBIN_DETAILS)
		.value("OVERRIDE_RENDERBIN_DETAILS", osg::StateSet::OVERRIDE_RENDERBIN_DETAILS)
		.value("PROTECTED_RENDERBIN_DETAILS", osg::StateSet::PROTECTED_RENDERBIN_DETAILS)
		.value(
			"OVERRIDE_PROTECTED_RENDERBIN_DETAILS",
			osg::StateSet::OVERRIDE_PROTECTED_RENDERBIN_DETAILS
		)
		.export_values()
	;

	pyx::bind_proxy_property<detail::TextureAttributesProxy, osg::StateSet, detail::StateSetStorage>(
		ss, "_TextureAttributes", "textureAttributes",
		"Mapping proxy from texture unit to that unit's StateAttribute set, keyed like "
		"StateSet.attributes but per-texture-unit."
	);

	pyx::bind_proxy_property<detail::ModesProxy, osg::StateSet, detail::StateSetStorage>(
		ss, "_Modes", "modes",
		"Mapping proxy from a GL mode enum (e.g. GL_BLEND) to its ON/OFF/OVERRIDE/PROTECTED "
		"osg::StateAttribute::Values; assign to enable/disable, `del` to inherit."
	);

	pyx::bind_proxy_property<detail::DefinesProxy, osg::StateSet, detail::StateSetStorage>(
		ss, "_Defines", "defines",
		"Mapping proxy from a GLSL #define name to its (value, override) pair, injected into "
		"shader source at compile time."
	);

	// Not using pyx::bind_proxy_property here (unlike textureAttributes above) - uniforms needs
	// its own append()/extend() beyond what MappingProxy provides generically, so it keeps direct
	// access to the bound proxy class (`up`) to chain those onto.
	auto up = detail::UniformsProxy::bind(ss, "_Uniforms");

	up
		.def("append", [](detail::UniformsProxy& self, py::object u) {
			pyx::MappingTraits<osg::StateSet, detail::UniformsTag>::apply(
				self.obj,
				std::nullopt,
				u
			);
		}, "Add a Uniform, keyed by its own .name - equivalent to stateSet.uniforms[u.name] = u.")
		.def("extend", [](detail::UniformsProxy& self, py::iterable uniforms) {
			for(auto u : uniforms) pyx::MappingTraits<osg::StateSet, detail::UniformsTag>::apply(
				self.obj,
				std::nullopt,
				u
			);
		}, "Add each Uniform in an iterable, keyed by its own .name.")
	;

	// Same shape as `uniforms` above - the attribute's own `getType()` supplies the key, so
	// `append()`/`extend()` work without requiring the type to be named twice.
	auto ap = detail::AttributesProxy::bind(ss, "_Attributes");

	ap
		.def("append", [](detail::AttributesProxy& self, py::object attr) {
			pyx::MappingTraits<osg::StateSet, detail::AttributesTag>::apply(
				self.obj,
				std::nullopt,
				attr
			);
		}, "Add a StateAttribute, keyed by its own .type - equivalent to "
			"stateSet.attributes[attr.type] = attr."
		)
		.def("extend", [](detail::AttributesProxy& self, py::iterable attrs) {
			for(auto attr : attrs) pyx::MappingTraits<osg::StateSet, detail::AttributesTag>::apply(
				self.obj,
				std::nullopt,
				attr
			);
		}, "Add each StateAttribute in an iterable, keyed by its own .type.")
	;

	ss
		.def("setRenderBinDetails", [](
			osg::StateSet& self,
			int binNum,
			const std::string& binName,
			osg::StateSet::RenderBinMode mode
		) { self.setRenderBinDetails(binNum, binName, mode); },
			"binNum"_a,
			"binName"_a,
			"mode"_a=osg::StateSet::USE_RENDERBIN_DETAILS,
			"Set the render bin number/name for this StateSet's Drawables in one call, "
			"also setting renderBinMode to USE_RENDERBIN_DETAILS unless overridden."
		)
		.def_property_readonly("useRenderBinDetails", &osg::StateSet::useRenderBinDetails,
			"Whether this StateSet's explicit render bin number/name are set and in "
			"effect (renderBinMode is not INHERIT_RENDERBIN_DETAILS)."
		)
		.def("setRenderBinToInherit", &osg::StateSet::setRenderBinToInherit,
			"Reset renderBinMode to INHERIT_RENDERBIN_DETAILS, so this StateSet's "
			"Drawables use the bin their parent's StateSet resolves to."
		)
		.def_property("renderingHint",
			&osg::StateSet::getRenderingHint,
			&osg::StateSet::setRenderingHint,
			"Which default RenderingHint bin group (opaque vs. transparent) this "
			"StateSet's Drawables sort into."
		)
		.def_property("renderBinMode",
			&osg::StateSet::getRenderBinMode,
			&osg::StateSet::setRenderBinMode,
			"How binNumber/binName combine with values inherited from parent StateSets."
		)
		.def_property("binNumber", &osg::StateSet::getBinNumber, &osg::StateSet::setBinNumber,
			"The explicit render bin number for this StateSet's Drawables (lower draws "
			"first); only in effect when renderBinMode isn't INHERIT_RENDERBIN_DETAILS."
		)
		.def_property("binName", &osg::StateSet::getBinName, &osg::StateSet::setBinName,
			"The name of the explicit render bin ('RenderBin', 'DepthSortedBin', etc.) "
			"this StateSet's Drawables are placed into."
		)
		.def_property("nestRenderBins",
			&osg::StateSet::getNestRenderBins,
			&osg::StateSet::setNestRenderBins,
			"Whether this StateSet's render bin nests inside its parent's bin (true) or "
			"replaces it entirely (false)."
		)
		// No setMode()/removeMode() - .modes[mode] = value / del .modes[mode] (ModesTag/
		// ModesProxy above) already covers this, same shape as .attributes[]/.textureAttributes[]
		// replacing setAttribute()/setAttributeAndModes()/removeAttribute()/setTextureAttribute()/
		// No addUniform() - .uniforms.append()/.uniforms[name]=... (UniformsTag/UniformsProxy
		// above) already covers this, same as .attributes[]/.textureAttributes[] replaced
		// setAttribute()/setAttributeAndModes()/removeAttribute()/setTextureAttribute()/
		// setTextureAttributeAndModes()/removeTextureAttribute().
		//
		// No getUniform() - .uniforms[name] (a MappingProxy, see UniformsTag above) already
		// covers this with proper dict semantics (__getitem__/__contains__/KeyError), same as
		// .attributes[] replaced getAttribute()/setAttribute() (see aipython/02-inspect.md).
		//
		// No {get,set,remove}TextureMode() either - GL_TEXTURE_GEN_*/GL_TEXTURE_1D/2D/3D
		// per-unit fixed-function-pipeline toggles, same vintage as the rest of the FFP surface
		// this project deliberately doesn't bind. (setTextureMode/getTextureMode/getUniform were
		// all pulled at once, so this file's diff also fixes a real bug that lived alongside
		// them: getTextureMode used to be bound to &osg::StateSet::setTextureMode, a copy-paste
		// from the line below it - calling it silently called the SETTER instead of reading
		// anything back.)
		.def_property_readonly("parents", [](osg::StateSet& self) {
			// return detail::make_list(self.getParents());
			return detail::make_tuple(self.getParents());
		}, py::return_value_policy::reference,
			"A tuple of every Node/Drawable currently referencing this StateSet as their "
			"own stateSet."
		)

		.def_property_readonly(
			"uniforms",
			[](osg::StateSet& self) -> detail::UniformsProxy& {
				return detail::StateSetStorage::get(self)->template proxy<detail::UniformsProxy>();
			},
			py::return_value_policy::reference_internal,
			"A dict-like mapping proxy of this StateSet's Uniforms, keyed by name - "
			"supports __getitem__/__setitem__/__contains__/append()/extend(), replacing "
			"getUniform()/addUniform()/removeUniform()."
		)
		.def_property_readonly(
			"attributes",
			[](osg::StateSet& self) -> detail::AttributesProxy& {
				return detail::StateSetStorage::get(self)->template proxy<detail::AttributesProxy>();
			},
			py::return_value_policy::reference_internal,
			"A dict-like mapping proxy of this StateSet's StateAttributes, keyed by "
			"StateAttribute.Type - supports __getitem__/__setitem__/__contains__/"
			"append()/extend(), replacing getAttribute()/setAttribute()/removeAttribute()."
		)
	;
}

}
