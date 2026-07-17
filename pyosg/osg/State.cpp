#include "State.hpp"

namespace pyosg {

void bind_State(py::module_& m) {
	py::class_<osg::FrameStamp, osg::Referenced, osg::ref_ptr<osg::FrameStamp>>(m, "FrameStamp")
		.def(py::init<>())
		.def(py::init<const osg::FrameStamp&>())
		.def_property("frameNumber",
			&osg::FrameStamp::getFrameNumber,
			&osg::FrameStamp::setFrameNumber
		)
		.def_property("referenceTime",
			&osg::FrameStamp::getReferenceTime,
			&osg::FrameStamp::setReferenceTime
		)
		.def_property("simulationTime",
			&osg::FrameStamp::getSimulationTime,
			&osg::FrameStamp::setSimulationTime
		)
		.def_property("calendarTime",
			&osg::FrameStamp::getCalendarTime,
			&osg::FrameStamp::setCalendarTime
		)
	;

	py::class_<osg::State, osg::Referenced, osg::ref_ptr<osg::State>>(m, "State")
		.def_property_readonly("projectionMatrix",
			&osg::State::getProjectionMatrix,
			py::return_value_policy::reference_internal
		)
		.def_property_readonly("contextID", &osg::State::getContextID)
		/* .def("getGraphicsContext",
			&osg::State::getGraphicsContext,
			py::return_value_policy::reference
		) */
		.def_property_readonly("frameStamp",
			py::overload_cast<>(&osg::State::getFrameStamp, py::const_),
			py::return_value_policy::reference
		)
		.def("setUseModelViewAndProjectionUniforms",
			&osg::State::setUseModelViewAndProjectionUniforms
		)
		.def("setUseVertexAttributeAliasing",
			&osg::State::setUseVertexAttributeAliasing
		)
		.def("__repr__", [](const osg::State& self) {
			std::ostringstream oss;

			self.print(oss);

			return py::str(oss.str());
		})
	;

	auto sa = py::class_<
		osg::StateAttribute,
		osg::Object,
		osg::ref_ptr<osg::StateAttribute>
	>(m, "StateAttribute")
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

		.def_property_readonly("type", &osg::StateAttribute::getType)
		.def_property_readonly("member", &osg::StateAttribute::getMember)
		.def_property_readonly("typeMember", &osg::StateAttribute::getTypeMemberPair)
	;

	sa.attr("GLMode") = detail::builtin_int();
	sa.attr("GLModeValue") = detail::builtin_int();
	sa.attr("OverrideValue") = detail::builtin_int();

	py::enum_<osg::StateAttribute::Values>(sa, "Values", py::arithmetic())
		.value("OFF", osg::StateAttribute::Values::OFF)
		.value("ON", osg::StateAttribute::Values::ON)
		.value("OVERRIDE", osg::StateAttribute::Values::OVERRIDE)
		.value("PROTECTED", osg::StateAttribute::Values::PROTECTED)
		.value("INHERIT", osg::StateAttribute::Values::INHERIT)
		.export_values()
	;

	py::enum_<osg::StateAttribute::Type>(sa, "Type")
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
	>(m, "StateSet")
		.def(py::init<>())
		.def(py::init<const osg::StateSet&>())
	;

	// This isn't really NECESSARY to have (as it's so unlikely to be used in common cases), but
	// it's a great DEMO for how this kind of thing is done. NOTE the call to `PYBIND11_MAKE_OPAQUE`
	// in the toplevel of this file.
	py::bind_map<osg::StateSet::ModeList>(ss, "ModeList");

	// TODO: So, this call COULD WORK ... with LOTS of caveats. Explain more!
	// py::bind_vector<std::vector<osg::Node*>>(ss, "ParentList");

	py::enum_<osg::StateSet::RenderingHint>(ss, "RenderingHint")
		.value("DEFAULT_BIN", osg::StateSet::DEFAULT_BIN)
		.value("OPAQUE_BIN", osg::StateSet::OPAQUE_BIN)
		.value("TRANSPARENT_BIN", osg::StateSet::TRANSPARENT_BIN)
		.export_values()
	;

	py::enum_<osg::StateSet::RenderBinMode>(ss, "RenderBinMode")
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
		ss, "_TextureAttributes", "textureAttributes"
	);

	// Not using pyx::bind_proxy_property here (unlike textureAttributes above) -- uniforms needs
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
		})
		.def("extend", [](detail::UniformsProxy& self, py::iterable uniforms) {
			for(auto u : uniforms) pyx::MappingTraits<osg::StateSet, detail::UniformsTag>::apply(
				self.obj,
				std::nullopt,
				u
			);
		})
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
			"mode"_a=osg::StateSet::USE_RENDERBIN_DETAILS
		)
		.def_property_readonly("useRenderBinDetails", &osg::StateSet::useRenderBinDetails)
		.def("setRenderBinToInherit", &osg::StateSet::setRenderBinToInherit)
		.def_property("renderingHint",
			&osg::StateSet::getRenderingHint,
			&osg::StateSet::setRenderingHint
		)
		.def_property("renderBinMode",
			&osg::StateSet::getRenderBinMode,
			&osg::StateSet::setRenderBinMode
		)
		.def_property("binNumber", &osg::StateSet::getBinNumber, &osg::StateSet::setBinNumber)
		.def_property("binName", &osg::StateSet::getBinName, &osg::StateSet::setBinName)
		.def_property("nestRenderBins",
			&osg::StateSet::getNestRenderBins,
			&osg::StateSet::setNestRenderBins
		)
		.def("setAttribute", [](
			osg::StateSet& self,
			osg::StateAttribute* attr,
			osg::StateAttribute::OverrideValue value
		) { self.setAttribute(attr, value); },
			"attr"_a,
			"value"_a=osg::StateAttribute::OFF
		)
		.def("setAttributeAndModes", [](
			osg::StateSet& self,
			osg::StateAttribute* attr,
			osg::StateAttribute::GLModeValue value
		) { self.setAttributeAndModes(attr, value); },
			"attr"_a,
			"value"_a=osg::StateAttribute::ON
		)
		.def("removeAttribute", [](
			osg::StateSet& self,
			osg::StateAttribute::Type type,
			unsigned int member
		) { self.removeAttribute(type, member); },
			"type"_a,
			"member"_a=0
		)
		.def("removeAttribute", [](
			osg::StateSet& self,
			osg::StateAttribute* attr
		) { self.removeAttribute(attr); },
			"attr"_a
		)
		.def("setMode", py::overload_cast<
			osg::StateAttribute::GLMode,
			osg::StateAttribute::GLModeValue
		>(&osg::StateSet::setMode))
		.def("removeMode", &osg::StateSet::removeMode)
		.def("setTextureAttribute", [](osg::StateSet& self,
			unsigned int unit,
			osg::StateAttribute* attr,
			osg::StateAttribute::OverrideValue value
		) { self.setTextureAttribute(unit, attr, value); },
			"unit"_a,
			"attr"_a,
			"value"_a=osg::StateAttribute::OFF
		)
		.def("setTextureAttributeAndModes", [](
			osg::StateSet& self,
			unsigned int unit,
			osg::StateAttribute* attr,
			osg::StateAttribute::GLModeValue value
		) { self.setTextureAttributeAndModes(unit, attr, value); },
			"unit"_a,
			"attr"_a,
			"value"_a=osg::StateAttribute::ON
		)
		.def("removeTextureAttribute", [](
			osg::StateSet& self,
			unsigned int unit,
			osg::StateAttribute::Type type
		) { self.removeTextureAttribute(unit, type); },
			"unit"_a,
			"type"_a
		)
		.def("removeTextureAttribute", [](
			osg::StateSet& self,
			unsigned int unit,
			osg::StateAttribute* attr
		) { self.removeTextureAttribute(unit, attr); },
			"unit"_a,
			"attr"_a
		)
		.def("addUniform", [](
			osg::StateSet& self,
			osg::Uniform* uniform,
			osg::StateAttribute::OverrideValue value
		) { self.addUniform(uniform, value); },
			"uniform"_a,
			"value"_a=osg::StateAttribute::ON
		)
		.def("getUniform", [](osg::StateSet& self, const std::string& name) {
			return self.getUniform(name);
		}, py::return_value_policy::reference)
		.def("getTextureMode", &osg::StateSet::setTextureMode)
		.def("setTextureMode", &osg::StateSet::setTextureMode)
		.def("removeTextureMode", &osg::StateSet::removeTextureMode)
		.def_property_readonly("parents", [](osg::StateSet& self) {
			// return detail::make_list(self.getParents());
			return detail::make_tuple(self.getParents());
		}, py::return_value_policy::reference)

		.def_property_readonly(
			"uniforms",
			[](osg::StateSet& self) -> detail::UniformsProxy& {
				return detail::StateSetStorage::get(self)->template proxy<detail::UniformsProxy>();
			},
			py::return_value_policy::reference_internal
		)
	;
}

}
