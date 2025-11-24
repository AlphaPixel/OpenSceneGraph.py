#pragma once

#include "OpenSceneGraph-python.hpp"

namespace pyosg {

namespace detail {
	// This is only useful for raising exceptions pybind11 doesn't ALREADY support or any CUSTOM
	// exceptions you create/bind in C++.
	// TODO: I want to get better about using stuff like: [[noreturn]]
	inline void raise_error(PyObject* exc_type, const std::string& msg) {
		PyErr_SetString(exc_type, msg.c_str());

		throw py::error_already_set();
	}

	// For some reason, pybind11 wraps MOST exceptions EXCEPT this one. Weird.
	// TODO: See above! [[noreturn]]
	inline void file_not_found(const std::string& msg) {
		raise_error(PyExc_FileNotFoundError, msg.c_str());
	}

	// Constructors for pybind11 types cannot call methods of that type until AFTER it is created
	// (obviously). We therefore need SOME unified, predictable way to create "chains" of
	// initialization wherein each type/participant should add their supported keywords and then
	// properly forward the unused arguments into their base classes.
	//
	// For example, both `Node` and `Group` define overrides of this template function (supporting
	// different keyword-based arguments); once `Group` has performed the relevant processing, it
	// necessarily calls its next bases' overide (so forth and so on).
	//
	// TODO: This will almost certainly need to be grouped with the "trampoline" wrappers that
	// eventually go into their own shared "core" library!
	template<typename T>
	void kwargs_init(T& self, const py::kwargs& kwargs) {}

#if 0
	template<typename Container, typename ElementPtr, typename Adder>
	void init_iterable(
		Container& obj,
		const py::kwargs& kw,
		const char* key,
		Adder add // lambda taking (Container&, ElementPtr)
	) {
		if(!kw.contains(key)) return;

		py::object seq = kw[key];

		for(py::handle item : seq) {
			auto element = item.cast<ElementPtr>();

			add(obj, element);
		}
	}

	init_iterable<osg::Group, osg::Node*>(g, kw, "children", [](osg::Group& group, osg::Node* n) {
		group.addChild(n);
	});
#endif

	// Unified helper used by all trampoline classes to safely invoke a Python override for a
	// virtual C++ method; we need this because PYBIND11_OVERRIDE doesn't really jive that well
	// with OSG code. :(
	//
	// It performs the following steps:
	//
	// - Acquires the GIL and calls the Python override if one exists.
	// - Never re-enters Python from inside Python (recursion guard safe).
	// - Correctly supports return types:
	//   - Ret = void, return bool (override called or not)
	//   - Ret != void, return std::optional<Ret>
	// - Distinguishes between:
	//   - override exists
	//   - override exists but returns None
	//   - override does not exist
	// - Preserve default C++ behavior when Python returns None or does not override the method.
	// - Ensures Python receives reference-wrapped arguments, not copies.
	//
	// Return-value rules:
	//   Ret = void
	//       returns bool
	//           true = override exists and was called
	//           false = no override
	//
	//   Ret != void
	//       returns std::optional<Ret>
	//           optional(value) = override returned a concrete value
	//           empty optional = no override OR Python returned None
	//
	// This behavior allows trampoline code to make clear decisions:
	//
	//       if (auto r = call_override<bool>(...)) { ... }
	//       bool was_called = call_override<void>(...)
	//
	// Python returning None is treated as “no opinion/use default behavior”. This (mostly) matches
	// OSG semantics in NodeVisitor, NodeCallback, GUIEventHandler, and all other OSG virtual-call
	// conventions where visitation/continuation can potentially be short-circuited.
	template<typename Ret, typename Self, typename... Args>
	auto call_override(const char* name, const Self* self, Args&&... args) {
		// Always acquire the GIL before touching Python.
		py::gil_scoped_acquire gil;

		// Look up the override on the Python side.
		// py::function ovr = py::get_override(self, name);
		auto ovr = py::get_override(self, name);

		// No override: return default indicator based on Ret.
		if(!ovr) {
			if constexpr(std::is_void_v<Ret>) return false;

			else return std::optional<Ret>{};
		}

		// Call the Python override with reference-return semantics.
		// py::object result = ovr(
		auto result = ovr(
			py::cast(std::forward<Args>(args),
			py::return_value_policy::reference)...
		);

		// Ret = void: override did run.
		if constexpr(std::is_void_v<Ret>) return true;

		// Ret != void
		else {
			// Python returned None → treat as “no value” (default C++ behavior).
			if(result.is_none()) return std::optional<Ret>{};

			// Concrete return → forward it to caller.
			return std::optional<Ret>(result.template cast<Ret>());
		}
	}
}

void bind(py::module_& m);

void bind_Notify(py::module_& m);
void bind_Vec(py::module_& m);
void bind_Object(py::module_& m);
void bind_Node(py::module_& m);
void bind_NodeVisitor(py::module_& m);
void bind_NodeCallback(py::module_& m);
void bind_Group(py::module_& m);
void bind_View(py::module_& m);

}
