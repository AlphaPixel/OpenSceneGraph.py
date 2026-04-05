#pragma once

#include "Uniform.hpp"

PYOSG_DISABLE_WARNINGS

#include <osg/Node>
#include <osg/State>
#include <osg/StateAttribute>

PYOSG_ENABLE_WARNINGS

#include <sstream>

PYBIND11_MAKE_OPAQUE(osg::StateSet::ModeList);

#include "pybind11x.hpp"

namespace pyx = pybind11x;

template<>
struct pyx::MappingTraits<osg::StateSet> {
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

			if(t.size() != 2) throw py::type_error("Expected (value, mode) or (type, value)");

			// (value, mode): REPLACE with override!
			if(py::isinstance<osg::StateAttribute::OverrideValue>(t[1])) {
				auto mode = t[1].cast<osg::StateAttribute::OverrideValue>();

				if(k) ss->addUniform(pyosg::detail::make_uniform(*k, t[0]), mode);

				else ss->addUniform( t[0].cast<osg::Uniform*>(), mode);

				return;
			}

			// (type, value): REPLACE with explicit type!
			if(py::isinstance<osg::Uniform::Type>(t[0])) {
				if(!k) throw py::type_error("(type, value) requires a key");

				auto type = t[0].cast<osg::Uniform::Type>();

				// osg::ref_ptr<osg::Uniform> u = new osg::Uniform(type, *k);
				auto* u = new osg::Uniform(type, *k);

				pyosg::detail::uniform_set(*u, 0, py::cast<py::object>(t[1]));

				ss->addUniform(u); // ALWAYS replace

				return;
			}

			throw py::type_error("Invalid tuple form for Uniform assignment");
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

namespace pyosg {

namespace detail {
	using UniformsProxy = pyx::MappingProxy<osg::StateSet>;
	using StateSetStorage = pyx::ProxyStorageOSG<osg::StateSet, UniformsProxy>;
}

void bind_State(py::module_& m);

}
