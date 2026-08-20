#pragma once

#include "Uniform.hpp"

PYOSG_DISABLE_WARNINGS

#include <osg/Node>
#include <osg/State>
#include <osg/StateAttribute>

PYOSG_ENABLE_WARNINGS

#include <sstream>

#include "pybind11x.hpp"

namespace pyx = pybind11x;

namespace pyosg::detail {
	struct UniformsTag;
	struct TextureAttributesTag;
	struct AttributesTag;
	struct ModesTag;
	struct DefinesTag;
}

template<>
struct pyx::MappingTraits<osg::StateSet, pyosg::detail::UniformsTag> {
	using element_type = osg::Uniform;
	using key_type = std::string;
	using value_type = element_type*;

	static value_type from_python(py::handle h) {
		return h.cast<value_type>();
	}

	static size_t size(osg::StateSet* ss) {
		return ss->getUniformList().size();
	}

	static element_type* get(osg::StateSet* ss, key_type k) {
		return dynamic_cast<element_type*>(ss->getUniform(k));
	}

	// TODO: I think this can be REMOVED!
	/* static void apply(osg::StateSet* ss, std::optional<key_type> k, py::handle h) {
		// This is the ... weirdest ... path; users should avoid it.
		if(py::isinstance<osg::Uniform>(h)) {
			auto* u = h.cast<osg::Uniform*>();

			if(k && u->getName() != *k) throw py::value_error(
				"Cannot assign Uniform with different name; use append() instead."
			);

			ss->addUniform(u);
		}

		// Here we expect both a valid `pyosg::detail::UniformVariant` value and a correspond
		// `osg::StateAttribute::OverrideValue`, and only ONE pair at a time.
		else if(py::isinstance<py::tuple>(h)) {
			auto t = h.cast<py::tuple>();

			if(t.size() != 2) throw py::type_error("Expected (value, mode)");

			auto mode = t[1].cast<osg::StateAttribute::OverrideValue>();

			if(k) ss->addUniform(pyosg::detail::make_uniform(*k, t[0]), mode);

			else ss->addUniform(t[0].cast<osg::Uniform*>(), mode);
		}

		// This is the simplest, most COMMON method: `stateSet.uniforms["foo"] = osg.Matrixd()`,
		// which uses the default `osg::StateAttribute::ON` value.
		else {
			if(!k) throw py::type_error("append() requires Uniform or (Uniform, mode)");

			ss->addUniform(pyosg::detail::make_uniform(*k, h));
		}
	} */

	static void apply(osg::StateSet* ss, std::optional<key_type> k, py::handle h) {
		// osg::Uniform* existing = k ? ss->getUniform(*k) : nullptr;

		// CASE 1: Explicit Uniform object REPLACEMENT!
		if(py::isinstance<osg::Uniform>(h)) {
			auto* u = h.cast<osg::Uniform*>();

			if(k && u->getName() != *k) throw py::value_error(
				"Cannot assign Uniform with different name; use append() instead."
			);

			ss->addUniform(u);

			return;
		}

		// CASE 2: Tuple handling...
		if(py::isinstance<py::tuple>(h)) {
			auto t = h.cast<py::tuple>();

			if(!t.size()) throw py::type_error("Cannot assign empty tuple as Uniform value");

			// (value, mode): REPLACE with override!
			if(t.size() == 2 && py::isinstance<osg::StateAttribute::OverrideValue>(t[1])) {
				auto mode = t[1].cast<osg::StateAttribute::OverrideValue>();

				if(k) ss->addUniform(pyosg::detail::make_uniform(*k, t[0]), mode);

				else ss->addUniform(t[0].cast<osg::Uniform*>(), mode);

				return;
			}

			// (type, value): REPLACE with explicit type!
			if(t.size() == 2 && py::isinstance<osg::Uniform::Type>(t[0])) {
				if(!k) throw py::type_error("(type, value) requires a key");

				auto type = t[0].cast<osg::Uniform::Type>();

				auto* u = new osg::Uniform(type, *k);

				pyosg::detail::uniform_set(*u, 0, py::cast<py::object>(t[1]));

				ss->addUniform(u); // ALWAYS replace

				return;
			}

			// Array of values: infer type from first element, set all
			if(!k) throw py::type_error("Array Uniform assignment requires a key");

			ss->addUniform(pyosg::detail::make_uniform_array_infer(*k, t));

			return;
		}

		// CASE 3: Simple value MUTATATION or CREATION!
		if(!k) throw py::type_error("append() requires Uniform or (Uniform, mode)");

		// if(existing) {
		if(auto* existing = k ? ss->getUniform(*k) : nullptr; existing) {
			if(existing->getNumElements() != 1) throw py::value_error(
				"Cannot assign scalar value to array Uniform"
			);

			// Delegate type enforcement to uniform_set
			pyosg::detail::uniform_set(*existing, 0, py::cast<py::object>(h));
		}

		else ss->addUniform(pyosg::detail::make_uniform(*k, h));
	}

	static void set(osg::StateSet* ss, key_type k, py::handle h) {
		apply(ss, k, h);
	}

	static void del(osg::StateSet* ss, key_type k) {
		ss->removeUniform(k);
	}

	// static bool contains(osg::StateSet* ss, key_type k) { return false; }

	static std::vector<key_type> keys(osg::StateSet* ss) {
		std::vector<key_type> out;

		const auto& uniforms = ss->getUniformList();

		out.reserve(uniforms.size());

		for(const auto& [name, _] : uniforms) out.push_back(name);

		return out;
	}
};

template<>
struct pyx::MappingTraits<osg::StateSet, pyosg::detail::TextureAttributesTag> {
	using element_type = osg::StateAttribute;
	using key_type = unsigned int;
	using value_type = element_type*;

	static value_type from_python(py::handle h) {
		return h.cast<value_type>();
	}

	static size_t size(osg::StateSet* ss) {
		size_t out = 0;
		const auto& texture_attributes = ss->getTextureAttributeList();

		for(unsigned int unit = 0; unit < texture_attributes.size(); unit++) {
			if(ss->getTextureAttribute(unit, osg::StateAttribute::TEXTURE)) out++;
		}

		return out;
	}

	static element_type* get(osg::StateSet* ss, key_type unit) {
		return ss->getTextureAttribute(unit, osg::StateAttribute::TEXTURE);
	}

	static void apply(osg::StateSet* ss, key_type unit, py::handle h) {
		if(py::isinstance<osg::StateAttribute>(h)) {
			auto* attr = h.cast<osg::StateAttribute*>();

			if(attr->getType() != osg::StateAttribute::TEXTURE) throw py::type_error(
				"Integer textureAttributes keys currently accept only TEXTURE attributes"
			);

			ss->setTextureAttributeAndModes(unit, attr, osg::StateAttribute::ON);

			return;
		}

		if(py::isinstance<py::tuple>(h)) {
			auto t = h.cast<py::tuple>();

			if(t.size() != 2) throw py::type_error("Expected (attribute, mode)");

			auto* attr = t[0].cast<osg::StateAttribute*>();

			if(attr->getType() != osg::StateAttribute::TEXTURE) throw py::type_error(
				"Integer textureAttributes keys currently accept only TEXTURE attributes"
			);

			auto mode = t[1].cast<osg::StateAttribute::GLModeValue>();

			ss->setTextureAttributeAndModes(unit, attr, mode);

			return;
		}

		throw py::type_error("Expected StateAttribute or (StateAttribute, mode)");
	}

	static void set(osg::StateSet* ss, key_type unit, py::handle h) {
		apply(ss, unit, h);
	}

	static void del(osg::StateSet* ss, key_type unit) {
		ss->removeTextureAttribute(unit, osg::StateAttribute::TEXTURE);
	}

	static std::vector<key_type> keys(osg::StateSet* ss) {
		std::vector<key_type> out;

		const auto& texture_attributes = ss->getTextureAttributeList();

		for(unsigned int unit = 0; unit < texture_attributes.size(); unit++) {
			if(ss->getTextureAttribute(unit, osg::StateAttribute::TEXTURE)) out.push_back(unit);
		}

		return out;
	}
};

// The main (non-texture) `StateAttribute` list, keyed by `StateAttribute::Type` - e.g.
// `stateSet.attributes[osg.StateAttribute.PROGRAM]`. Real OSG additionally keys this list by a
// "member" index (`StateAttribute::TypeMemberPair`) to allow multiple attributes of the SAME type
// (e.g. stacked ClipPlanes); this proxy only ever addresses member 0, matching the member=0
// default every other Python-facing attribute method here already assumes.
template<>
struct pyx::MappingTraits<osg::StateSet, pyosg::detail::AttributesTag> {
	using element_type = osg::StateAttribute;
	using key_type = osg::StateAttribute::Type;
	using value_type = element_type*;

	static value_type from_python(py::handle h) {
		return h.cast<value_type>();
	}

	static size_t size(osg::StateSet* ss) {
		return ss->getAttributeList().size();
	}

	static element_type* get(osg::StateSet* ss, key_type type) {
		return ss->getAttribute(type);
	}

	static void apply(osg::StateSet* ss, std::optional<key_type> k, py::handle h) {
		auto obj = py::reinterpret_borrow<py::object>(h);

		osg::StateAttribute* attr = nullptr;
		auto mode = osg::StateAttribute::GLModeValue(osg::StateAttribute::ON);

		if(py::isinstance<osg::StateAttribute>(obj)) attr = obj.cast<osg::StateAttribute*>();

		else if(auto vals = pyx::try_unpack_sequence<
			osg::StateAttribute*, osg::StateAttribute::GLModeValue
		>(obj)) std::tie(attr, mode) = *vals;

		else throw py::type_error("Expected StateAttribute or (StateAttribute, mode)");

		if(k && attr->getType() != *k) throw py::value_error(
			"Cannot assign StateAttribute with mismatched type; use append() instead."
		);

		// setAttributeAndModes() (not plain setAttribute()) so any GL mode the attribute owns
		// (e.g. BlendFunc -> GL_BLEND) gets enabled too, via StateAttribute::getModeUsage() --
		// the same mechanism the old setAttributeAndModes() Python binding relied on. A bare
		// `.attributes.append(attr)` now defaults `value` to ON, matching that old binding's
		// own default rather than silently doing nothing to the mode.
		ss->setAttributeAndModes(attr, mode);
	}

	static void set(osg::StateSet* ss, key_type k, py::handle h) {
		apply(ss, k, h);
	}

	static void del(osg::StateSet* ss, key_type k) {
		ss->removeAttribute(k);
	}

	static std::vector<key_type> keys(osg::StateSet* ss) {
		std::vector<key_type> out;
		const auto& attrs = ss->getAttributeList();

		out.reserve(attrs.size());

		for(const auto& [typeMember, _] : attrs) out.push_back(typeMember.first);

		return out;
	}
};

// The plain GL mode toggle list - e.g. `stateSet.modes[GL_DEPTH_TEST] = osg.StateAttribute.OFF`.
// Unlike `.attributes`/`.textureAttributes`, values here are bare `GLModeValue` ints rather than
// `StateAttribute*`, so this is a `ValueMappingTraits` (see `Program.hpp`'s BindAttribLocationTag
// for the same shape) rather than a `MappingTraits`. `contains()`/`get()` are KeyError-on-missing
// against `getModeList()` directly, matching `.attributes[]`'s semantics - NOT the same as real
// OSG's own `StateSet::getMode()`, which returns the `INHERIT` sentinel for an unset mode instead
// of throwing.
template<>
struct pyx::ValueMappingTraits<osg::StateSet, pyosg::detail::ModesTag> {
	using key_type = osg::StateAttribute::GLMode;
	using value_type = osg::StateAttribute::GLModeValue;

	static value_type from_python(py::handle h) {
		return h.cast<value_type>();
	}

	static size_t size(osg::StateSet* ss) {
		return ss->getModeList().size();
	}

	static bool contains(osg::StateSet* ss, key_type key) {
		const auto& modes = ss->getModeList();

		return modes.find(key) != modes.end();
	}

	static value_type get(osg::StateSet* ss, key_type key) {
		const auto& modes = ss->getModeList();
		auto it = modes.find(key);

		if(it == modes.end()) throw py::key_error("key not found");

		return it->second;
	}

	static void set(osg::StateSet* ss, key_type key, value_type value) {
		ss->setMode(key, value);
	}

	static void del(osg::StateSet* ss, key_type key) {
		ss->removeMode(key);
	}

	static std::vector<key_type> keys(osg::StateSet* ss) {
		std::vector<key_type> out;
		const auto& modes = ss->getModeList();

		out.reserve(modes.size());

		for(const auto& [mode, _] : modes) out.push_back(mode);

		return out;
	}
};

// The shader-define list -- e.g. `stateSet.defines["OSGX_PBRIBL_AO"] = osg.StateAttribute.ON`
// (matches osg::StateSet::setDefine(name, value)'s single-arg overload -- sets the define's own
// value string to "", i.e. a flag-style #ifdef-tested define, not a `#define NAME value`
// substitution; OSG's OTHER setDefine(name, valueString, mode) overload for a real value string
// has no Python-facing shorthand yet). Same ValueMappingTraits shape as ModesTag above (a named
// flag toggle, not an object with real identity, so no MappingTraits/element-pointer caching
// needed) -- `contains()`/`get()` go through getDefineList() directly, matching ModesTag's own
// style, rather than getDefinePair()'s pointer-returning overload.
template<>
struct pyx::ValueMappingTraits<osg::StateSet, pyosg::detail::DefinesTag> {
	using key_type = std::string;
	using value_type = osg::StateAttribute::OverrideValue;

	static value_type from_python(py::handle h) {
		return h.cast<value_type>();
	}

	static size_t size(osg::StateSet* ss) {
		return ss->getDefineList().size();
	}

	static bool contains(osg::StateSet* ss, key_type key) {
		const auto& defines = ss->getDefineList();

		return defines.find(key) != defines.end();
	}

	static value_type get(osg::StateSet* ss, key_type key) {
		const auto& defines = ss->getDefineList();
		auto it = defines.find(key);

		if(it == defines.end()) throw py::key_error("key not found");

		return it->second.second;
	}

	static void set(osg::StateSet* ss, key_type key, value_type value) {
		ss->setDefine(key, value);
	}

	static void del(osg::StateSet* ss, key_type key) {
		ss->removeDefine(key);
	}

	static std::vector<key_type> keys(osg::StateSet* ss) {
		std::vector<key_type> out;
		const auto& defines = ss->getDefineList();

		out.reserve(defines.size());

		for(const auto& [name, _] : defines) out.push_back(name);

		return out;
	}
};

namespace pyosg {

namespace detail {
	using UniformsProxy = pyx::MappingProxy<osg::StateSet, UniformsTag>;
	using TextureAttributesProxy = pyx::MappingProxy<osg::StateSet, TextureAttributesTag>;
	using AttributesProxy = pyx::MappingProxy<osg::StateSet, AttributesTag>;
	using ModesProxy = pyx::ValueMappingProxy<osg::StateSet, ModesTag>;
	using DefinesProxy = pyx::ValueMappingProxy<osg::StateSet, DefinesTag>;
	using StateSetStorage = pyx::ProxyStorageOSG<
		osg::StateSet,
		UniformsProxy,
		TextureAttributesProxy,
		AttributesProxy,
		ModesProxy,
		DefinesProxy
	>;
}

void bind_State(py::module_& m);

}
