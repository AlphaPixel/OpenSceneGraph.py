#pragma once

#include "../pyosg.hpp"

OSGX_DISABLE_WARNINGS

#include <osg/Program>

OSGX_ENABLE_WARNINGS

#include "pybind11x-osg.hpp"

namespace pyx = pybind11x;

namespace pyosg::detail {
	struct BindAttribLocationTag;
	struct BindFragDataLocationTag;
	struct BindUniformBlockTag;
}

template<>
struct pyx::SequenceTraits<osg::Program> {
	using element_type = osg::Shader;
	using value_type = element_type*;

	static value_type from_python(py::handle h) {
		return h.cast<value_type>();
	}

	static size_t size(const osg::Program* p) {
		return p->getNumShaders();
	}

	static element_type* get(osg::Program* p, size_t i) {
		return p->getShader(static_cast<unsigned int>(i));
	}

	// static void set(osg::Program* p, size_t i, element_type* d) {}

	static void del(osg::Program* p, size_t i) {
		p->removeShader(p->getShader(static_cast<unsigned int>(i)));
	}

	static void append(osg::Program* p, element_type* s) {
		p->addShader(s);
	}
};

template<>
struct pyx::ValueMappingTraits<osg::Program, pyosg::detail::BindAttribLocationTag> {
	using key_type = std::string;
	using value_type = GLuint;

	static value_type from_python(py::handle h) {
		return h.cast<value_type>();
	}

	static size_t size(osg::Program* p) {
		return p->getAttribBindingList().size();
	}

	static bool contains(osg::Program* p, key_type key) {
		const auto& bindings = p->getAttribBindingList();

		return bindings.find(key) != bindings.end();
	}

	static value_type get(osg::Program* p, key_type key) {
		const auto& bindings = p->getAttribBindingList();
		auto it = bindings.find(key);

		if(it == bindings.end()) throw py::key_error("key not found");

		return it->second;
	}

	static void set(osg::Program* p, key_type key, value_type value) {
		p->addBindAttribLocation(key, value);
	}

	static void del(osg::Program* p, key_type key) {
		p->removeBindAttribLocation(key);
	}

	static std::vector<key_type> keys(osg::Program* p) {
		std::vector<key_type> out;
		const auto& bindings = p->getAttribBindingList();

		out.reserve(bindings.size());

		for(const auto& [name, _] : bindings) out.push_back(name);

		return out;
	}
};

template<>
struct pyx::ValueMappingTraits<osg::Program, pyosg::detail::BindFragDataLocationTag> {
	using key_type = std::string;
	using value_type = GLuint;

	static value_type from_python(py::handle h) {
		return h.cast<value_type>();
	}

	static size_t size(osg::Program* p) {
		return p->getFragDataBindingList().size();
	}

	static bool contains(osg::Program* p, key_type key) {
		const auto& bindings = p->getFragDataBindingList();

		return bindings.find(key) != bindings.end();
	}

	static value_type get(osg::Program* p, key_type key) {
		const auto& bindings = p->getFragDataBindingList();
		auto it = bindings.find(key);

		if(it == bindings.end()) throw py::key_error("key not found");

		return it->second;
	}

	static void set(osg::Program* p, key_type key, value_type value) {
		p->addBindFragDataLocation(key, value);
	}

	static void del(osg::Program* p, key_type key) {
		p->removeBindFragDataLocation(key);
	}

	static std::vector<key_type> keys(osg::Program* p) {
		std::vector<key_type> out;
		const auto& bindings = p->getFragDataBindingList();

		out.reserve(bindings.size());

		for(const auto& [name, _] : bindings) out.push_back(name);

		return out;
	}
};

template<>
struct pyx::ValueMappingTraits<osg::Program, pyosg::detail::BindUniformBlockTag> {
	using key_type = std::string;
	using value_type = GLuint;

	static value_type from_python(py::handle h) {
		return h.cast<value_type>();
	}

	static size_t size(osg::Program* p) {
		return p->getUniformBlockBindingList().size();
	}

	static bool contains(osg::Program* p, key_type key) {
		const auto& bindings = p->getUniformBlockBindingList();

		return bindings.find(key) != bindings.end();
	}

	static value_type get(osg::Program* p, key_type key) {
		const auto& bindings = p->getUniformBlockBindingList();
		auto it = bindings.find(key);

		if(it == bindings.end()) throw py::key_error("key not found");

		return it->second;
	}

	static void set(osg::Program* p, key_type key, value_type value) {
		p->addBindUniformBlock(key, value);
	}

	static void del(osg::Program* p, key_type key) {
		p->removeBindUniformBlock(key);
	}

	static std::vector<key_type> keys(osg::Program* p) {
		std::vector<key_type> out;
		const auto& bindings = p->getUniformBlockBindingList();

		out.reserve(bindings.size());

		for(const auto& [name, _] : bindings) out.push_back(name);

		return out;
	}
};

namespace pyosg {

namespace detail {
	using ShadersProxy = pyx::SequenceProxy<osg::Program>;
	using BindAttribLocationProxy = pyx::ValueMappingProxy<
		osg::Program,
		BindAttribLocationTag
	>;
	using BindFragDataLocationProxy = pyx::ValueMappingProxy<
		osg::Program,
		BindFragDataLocationTag
	>;
	using BindUniformBlockProxy = pyx::ValueMappingProxy<
		osg::Program,
		BindUniformBlockTag
	>;
	using ProgramStorage = pyx::ProxyStorageOSG<
		osg::Program,
		ShadersProxy,
		BindAttribLocationProxy,
		BindFragDataLocationProxy,
		BindUniformBlockProxy
	>;
}

void bind_Program(py::module_& m);

}
