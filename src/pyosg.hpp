#pragma once

// TODO: Remove me!
#include <iostream>

#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <pybind11/operators.h>
#include <pybind11/embed.h>

#define PYOSG_DISABLE_WARNINGS \
	_Pragma("GCC diagnostic push") \
	_Pragma("GCC diagnostic ignored \"-Wconversion\"") \
	_Pragma("GCC diagnostic ignored \"-Wsign-conversion\"") \
	_Pragma("GCC diagnostic ignored \"-Wdeprecated-copy\"") \
	_Pragma("GCC diagnostic ignored \"-Wfloat-conversion\"") \
	_Pragma("GCC diagnostic ignored \"-Wsign-compare\"") \
	_Pragma("GCC diagnostic ignored \"-Woverloaded-virtual\"") \
	_Pragma("GCC diagnostic ignored \"-Wshadow\"") \
	_Pragma("GCC diagnostic ignored \"-Wunused-but-set-variable\"")

#define PYOSG_ENABLE_WARNINGS \
	_Pragma("GCC diagnostic pop")

PYOSG_DISABLE_WARNINGS

#include <osg/ref_ptr>

PYOSG_ENABLE_WARNINGS

namespace py = pybind11;

using namespace std::string_literals;
using namespace py::literals;

// Tell pybind11 that osg::ref_ptr<T> is a holder type for T.  The 3rd argument = true because
// osg::ref_ptr<T> can safely be constructed from a raw T* (intrusive refcounting).
PYBIND11_DECLARE_HOLDER_TYPE(T, osg::ref_ptr<T>, true);

// Forward-declare the pybind11-generated init function.
extern "C" PyObject* PyInit_OpenSceneGraph();

#define OPENSCENEGRAPH_PYTHON_MODULE "OpenSceneGraph"

#ifdef _MSC_VER
	// Make MSVC run our function before any global/static initializers
	#pragma section(".CRT$XCU", read)
	#define PYOSG_CONSTRUCTOR(func) \
		static void __cdecl func(void); \
		__declspec(allocate(".CRT$XCU")) void (__cdecl* func##_)(void) = func; \
		static void __cdecl func(void)

	#define PYOSG_INTERNAL

#else
	// GCC/Clang
	#define PYOSG_CONSTRUCTOR(func) __attribute__((constructor)) static void func(void)

	#define PYOSG_INTERNAL __attribute__((visibility("hidden")))
	// #define PYOSG_INTERNAL [[gnu::visibility("hidden")]]
#endif

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

	// Unified helper used by trampoline classes to safely invoke a Python override for a
	// virtual C++ method; we need this because PYBIND11_OVERRIDE doesn't really jive that well
	// with OSG code. It does exactly what PYBIND11_OVERRIDE does, while adding a few extra bits:
	//
	// - Acquires the GIL and calls the Python override if one exists.
	// - Never re-enters Python from inside Python (recursion guard safe).
	// - Correctly supports return types:
	//   - If Ret == void, return bool (override called or not)
	//   - If Ret != void, return std::optional<Ret>
	// - Distinguishes between:
	//   - The override exists
	//   - The override exists but returns None
	//   - override does not exist
	// - Preserves default C++ behavior when Python returns None or does not override the method.
	// - Ensures Python receives reference-wrapped arguments, not copies.
	//
	// Return-value rules are as follows:
	//
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
		// TODO: Is this version NOT using `py::cast` equivalent?
		//
		// auto result = ovr(std::forward<Args>(args)...);
		auto result = ovr(
			py::cast(std::forward<Args>(args), py::return_value_policy::reference)...
		);

		// Ret = void: override did run.
		if constexpr(std::is_void_v<Ret>) return true;

		// Ret != void, so...
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

#if 1
class PYOSG_INTERNAL Interpreter {
public:
	// TODO: This needs MORE LOGIC go guard against people creating instances of this object WITHOUT
	// having first called this method!
	static void init() {
		PyImport_AppendInittab(OPENSCENEGRAPH_PYTHON_MODULE, &PyInit_OpenSceneGraph);
	}

	explicit Interpreter():
	_guard{},
	_globals(py::dict(py::globals())) {
		/* try {
			_root = py::module_::import(OPENSCENEGRAPH_PYTHON_MODULE);
		}

		catch(const py::error_already_set &e) {
			throw;
		} */

		// import into our persistent namespace
		_globals["OpenSceneGraph"] = py::module_::import("OpenSceneGraph");
	}

	/* py::module_& root() {
		if(!_root) throw std::runtime_error(OPENSCENEGRAPH_PYTHON_MODULE " not imported");

		return _root;
	}

	py::module_ osg() { return root().attr("osg"); }
	py::module_ osgDB() { return root().attr("osgDB"); }
	py::module_ osgGA() { return root().attr("osgGA"); }
	py::module_ osgViewer() { return root().attr("osgViewer"); } */

	void exec(const std::string& code) {
		py::exec(code, _globals, _globals);
	}

	py::object eval(const std::string& expr) {
		return py::eval(expr, _globals, _globals);
	}

	/* void exec(const std::string& code, py::dict locals) {
		py::exec(code, py::globals(), locals);
	} */

	template<class T>
	py::object to_py(T&& value) {
		return py::cast(std::forward<T>(value));
	}

private:
	py::scoped_interpreter _guard;
	py::dict _globals;
	// py::module_ _root;
};
#endif

void bind(py::module_& m);

void bind_Notify(py::module_& m);
void bind_Vec(py::module_& m);
void bind_Matrix(py::module_& m);
void bind_Bound(py::module_& m);
void bind_Object(py::module_& m);
void bind_Buffer(py::module_& m);
void bind_Array(py::module_& m);
void bind_Node(py::module_& m);
void bind_NodeVisitor(py::module_& m);
void bind_NodeCallback(py::module_& m);
void bind_Drawable(py::module_& m);
void bind_Geometry(py::module_& m);
void bind_Group(py::module_& m);
void bind_Geode(py::module_& m);
void bind_Shape(py::module_& m);
void bind_View(py::module_& m);
void bind_State(py::module_& m);

}
