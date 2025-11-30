#pragma once

#include "OpenSceneGraph-python.hpp"

namespace pyosg {

namespace detail {
	// This is only useful for raising exceptions pybind11 doesn't ALREADY support or any CUSTOM
	// exceptions you create/bind in C++.
	//
	// TODO: I want to get better about using stuff like: [[noreturn]]
	inline void raise_error(PyObject* exc_type, const std::string& msg) {
		PyErr_SetString(exc_type, msg.c_str());

		throw py::error_already_set();
	}

	// For some reason, pybind11 wraps MOST exceptions EXCEPT this one. Weird.
	//
	// TODO: See above! [[noreturn]]
	inline void file_not_found(const std::string& msg) {
		raise_error(PyExc_FileNotFoundError, msg.c_str());
	}

	// This is just a simple helper for generating consistent, more informative `py::index_error`
	// messages.
	//
	// TODO: See above! [[noreturn]]
	inline void index_error(auto i) {
		throw py::index_error("not in range 0-"s + std::to_string(i));
	}

	template<size_t N, typename Getter>
	py::str seq_repr(const char* name, Getter get) {
		py::list items;

		for(size_t i = 0; i < N; i++) {
			auto val = py::float_(static_cast<double>(get(i)));

			items.append(py::repr(val));
		}

		return py::str("{}({})").format(
			name,
			py::str(", ").attr("join")(items)
		);
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

	/* template<typename T, typename... Args>
	static T* kwargs_ctor(py::kwargs& kwargs, Args&&... args) {
		auto* obj = new T(std::forward<Args>(args)...);
		init_kwargs(obj, kw);
		return obj;
	} */

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
	//       if(auto r = call_override<bool>(...)) { ... }
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
			// Python returned None: treat as “no value” (default C++ behavior).
			if(result.is_none()) return std::optional<Ret>{};

			// Concrete return: send it back to caller.
			return std::optional<Ret>(result.template cast<Ret>());
		}
	}

	// This is used to unify sequence-like access to `Group.children`, `Geode.drawable`, etc.
	template<typename T>
	struct ContainerTraits;

	// This might look intimdating at first, BUT FEAR NOT! It is used in conjuction with the above
	// in order to simplify/unify Pythonic access to sequences of objects. To see an example of it
	// "in action", have a look at the source for Group or Geode.
	template<typename T>
	struct ContainerProxy {
		using traits = ContainerTraits<T>;
		using element_type = typename traits::element_type;

		T* obj = nullptr;

		explicit ContainerProxy(T* o): obj(o) {}

		size_t size() const {
			return traits::size(obj);
		}

		size_t _index(int index) const {
			const int n = static_cast<int>(size());

			if(index < 0) index += n;
			if(index < 0 || index >= n) index_error(n);

			return static_cast<size_t>(index);
		}

		element_type* get(int index) const {
			return traits::get(obj, _index(index));
		}

		void set(int index, element_type* elem) {
			traits::set(obj, _index(index), elem);
		}

		void del(int index) {
			traits::remove(obj, _index(index));
		}

		void append(element_type* elem) {
			// Call Python-level `add*` for `keep_alive<>` behavior.
			py::cast(obj).attr(traits::add_method)(elem);
		}

		void extend(py::object iterable) {
			for(py::handle item : iterable) {
				append(item.cast<element_type*>());
			}
		}

		static void bind(py::handle parent, const char* name) {
			py::class_<ContainerProxy<T>>(parent, name, py::module_local())
				.def("__len__", &ContainerProxy<T>::size)
				.def("__getitem__", &ContainerProxy<T>::get)
				.def("__setitem__", &ContainerProxy<T>::set)
				.def("__delitem__", &ContainerProxy<T>::del)
				.def("append", &ContainerProxy<T>::append)
				.def("extend", &ContainerProxy<T>::extend)
			;
		}
	};
}

void bind(py::module_& m);

void bind_Notify(py::module_& m);
void bind_Vec(py::module_& m);
void bind_Matrix(py::module_& m);
void bind_Bound(py::module_& m);
void bind_Object(py::module_& m);
void bind_Node(py::module_& m);
void bind_NodeVisitor(py::module_& m);
void bind_NodeCallback(py::module_& m);
void bind_Drawable(py::module_& m);
void bind_Group(py::module_& m);
void bind_Geode(py::module_& m);
void bind_Shape(py::module_& m);
void bind_View(py::module_& m);
void bind_State(py::module_& m);

}
