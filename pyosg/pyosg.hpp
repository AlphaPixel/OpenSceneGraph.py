#pragma once

// TODO: Remove me!
#include <iostream>

#include <osgx/Warnings.hpp>

#include "pybind11/pybind11.h"
#include "pybind11/stl.h"
#include "pybind11/stl_bind.h"
#include "pybind11/operators.h"
#include "pybind11/embed.h"

#if !defined(PYBIND11_VERSION_MAJOR) || \
	!defined(PYBIND11_VERSION_MINOR) || \
	!defined(PYBIND11_VERSION_MICRO)

	#error "pybind11 version macros not found (wrong headers?)"
#endif

#if (PYBIND11_VERSION_MAJOR < 3) || \
	(PYBIND11_VERSION_MAJOR == 3 && PYBIND11_VERSION_MINOR < 0) || \
	(PYBIND11_VERSION_MAJOR == 3 && PYBIND11_VERSION_MINOR == 0 && PYBIND11_VERSION_MICRO < 2)

	#error "pybind11 >= 3.0.2 is required"
#endif

// Everything I read assures me that this will be "optimized away" when it matters.
#define PYOSG_SUPPRESS_WARNINGS(stmt) \
	do { \
		OSGX_DISABLE_WARNINGS \
		stmt; \
		OSGX_ENABLE_WARNINGS \
	} while(0)

OSGX_DISABLE_WARNINGS

#include <osg/ref_ptr>

OSGX_ENABLE_WARNINGS

namespace py = pybind11;

using namespace std::string_literals;
using namespace py::literals;

// Tell pybind11 that osg::ref_ptr<T> is a holder type for T. The 3rd argument is true because
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

// Bare forward declarations -- just enough to name these types below, without dragging in their
// (heavy) real headers, which each binding .cpp includes on its own before this manifest matters.
namespace osg {
	class Object;
	class Node;
	class Group;
	class Geode;
	class Drawable;
	class StateAttribute;
	class Program;
	class Shader;
	class Uniform;
	class Transform;
	class MatrixTransform;
	class PositionAttitudeTransform;
	class Camera;
	class Texture;
	class Texture2D;
	class Geometry;
}

// Central manifest for `pybind11x::kwargs_init` (the constructor-kwargs chaining mechanism defined
// in pybind11x.hpp): every participating type needs its REAL immediate C++ base named here via
// `kwargs_base`, whether or not that base defines any kwargs of its own -- that's what lets the
// walk in `kwargs_init<T>` reach it automatically instead of every subclass having to manually
// re-derive (and keep in sync) what its actual next base is. `kwargs_init_own<T>` is declared here
// too (its real body lives next to that type's bind_X() in its own .cpp) -- this header is included
// by nearly every binding TU, which is what makes each specialization visible wherever the walk
// might instantiate it; skipping an entry here doesn't fail to compile, it just silently falls back
// to the no-op default in whichever TU forgot to declare it, so keep this list in sync with reality.
namespace pybind11x {
	template<typename T> struct kwargs_base;
	template<typename T> void kwargs_init_own(T& self, const py::kwargs& kwargs);

	template<> struct kwargs_base<osg::Node> { using type = osg::Object; };
	template<> struct kwargs_base<osg::Group> { using type = osg::Node; };
	template<> struct kwargs_base<osg::Geode> { using type = osg::Group; };
	template<> struct kwargs_base<osg::Drawable> { using type = osg::Node; };
	template<> struct kwargs_base<osg::StateAttribute> { using type = osg::Object; };
	template<> struct kwargs_base<osg::Program> { using type = osg::StateAttribute; };
	template<> struct kwargs_base<osg::Shader> { using type = osg::Object; };
	template<> struct kwargs_base<osg::Uniform> { using type = osg::Object; };
	template<> struct kwargs_base<osg::Transform> { using type = osg::Group; };
	template<> struct kwargs_base<osg::MatrixTransform> { using type = osg::Transform; };
	template<> struct kwargs_base<osg::PositionAttitudeTransform> { using type = osg::Transform; };
	template<> struct kwargs_base<osg::Camera> { using type = osg::Transform; };
	template<> struct kwargs_base<osg::Texture> { using type = osg::StateAttribute; };
	template<> struct kwargs_base<osg::Texture2D> { using type = osg::Texture; };
	template<> struct kwargs_base<osg::Geometry> { using type = osg::Drawable; };

	template<> void kwargs_init_own(osg::Object& self, const py::kwargs& kwargs);
	template<> void kwargs_init_own(osg::Node& self, const py::kwargs& kwargs);
	template<> void kwargs_init_own(osg::Group& self, const py::kwargs& kwargs);
	template<> void kwargs_init_own(osg::Geode& self, const py::kwargs& kwargs);
	template<> void kwargs_init_own(osg::Drawable& self, const py::kwargs& kwargs);
	template<> void kwargs_init_own(osg::Program& self, const py::kwargs& kwargs);
	template<> void kwargs_init_own(osg::Transform& self, const py::kwargs& kwargs);
	template<> void kwargs_init_own(osg::MatrixTransform& self, const py::kwargs& kwargs);
	template<> void kwargs_init_own(osg::PositionAttitudeTransform& self, const py::kwargs& kwargs);
	template<> void kwargs_init_own(osg::Camera& self, const py::kwargs& kwargs);
	template<> void kwargs_init_own(osg::Texture& self, const py::kwargs& kwargs);
	template<> void kwargs_init_own(osg::Texture2D& self, const py::kwargs& kwargs);
	template<> void kwargs_init_own(osg::Geometry& self, const py::kwargs& kwargs);
}

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

	// Builds a `py::list` by invoking the `Getter` once for every `N`'th item (useful for
	// sequential containers); requires that size be known AT COMPILE TIME.
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

	// For standard Pythonic indexing, NEGATIVE INDICES should be allowed. This helper handles
	// converting those (if possible) into positive index values usable by the caller, throwing
	// `py::index_error` otherwise. In those cases where the caller needs something OTHER than a
	// `size_t` type, the optional `R` template paramter can be used; this is extremely helpful in
	// OSG, where each class seems to use ... whatever it wants. Frustrating.
	template<typename R=std::size_t>
	auto n_index(size_t size, py::ssize_t index) {
		// Convert negatives to Python-style indexing.
		if(index < 0) index += static_cast<py::ssize_t>(size);

		if(index < 0 || static_cast<std::size_t>(index) >= size) throw py::index_error(
			"Index " + std::to_string(index) +
			" out of range for container of size " + std::to_string(size)
		);

		return static_cast<R>(index);
	}

	// A "concept" to enforce `py::ssize_t` constraints.
	template<typename T>
	concept PyIndex = std::convertible_to<T, py::ssize_t>;

	// This is a helper for converting multiple indices at once; e.g.:
	//
	// `auto [nrow, ncol] = n_indices<unsigned int>(N, row, col);`
	template<typename R=std::size_t, PyIndex... Indices>
	auto n_indices(std::size_t size, Indices... idxs) {
		// Normalize each index using the existing helper above!
		return std::make_tuple(n_index<R>(size, static_cast<py::ssize_t>(idxs))...);
	}

	/* template<typename T>
	concept OSGObject =
		std::is_pointer_v<T> &&
		std::is_base_of_v<osg::Object, std::remove_pointer_t<T>>
	; */

	// Builds a `py::list` from any single thing that can be iterated over.
	template<typename T>
	// requires OSGObject<typename T::value_type>
	auto make_list(const T& seq) {
		py::list list;

		for(auto* obj : seq) list.append(obj);

		return list;
	}

	// Builds a `py::tuple` from any single thing that can be iterated over; this differs from
	// `py::make_tuple` in that is both runtime/non-constexpr and only expects a SINGLE argument.
	template<typename T>
	// requires OSGObject<typename T::value_type>
	auto make_tuple(const T& seq) {
		// TODO: This is a cleaner implementation, so investigate the COST later!
		// return py::tuple(make_list(seq));

		py::tuple tuple(seq.size());

		size_t i = 0;

		for(auto* obj : seq) tuple[i++] = obj;

		return tuple;
	}

	// Small helpers for creating ALIASES (usually) for types that are already built into Python;
	// for example, if you had something like `using Foo = uint32_t` and wanted to expose the `Foo`
	// type in your bindings, you'd call: `m.attr("Foo") = pyosg::detail::builtin_int()`.
	inline py::handle builtin_type(const char* name) {
		// return py::reinterpret_borrow<py::dict>(PyEval_GetBuiltins())[name];
		return py::module_::import("builtins").attr(name);
	}

	inline py::handle builtin_int() { return builtin_type("int"); }
	inline py::handle builtin_float() { return builtin_type("float"); }
	inline py::handle builtin_bool() { return builtin_type("bool"); }
}

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

	auto& globals() { return _globals; }

private:
	py::scoped_interpreter _guard;
	py::dict _globals;
};

void bind(py::module_& m);

// void bind_ArgumentParser(py::module_& m);
// void bind_Notify(py::module_& m);
// void bind_Vec(py::module_& m);
void bind_Quat(py::module_& m);
// void bind_Matrix(py::module_& m);
// void bind_Bound(py::module_& m);
// void bind_Object(py::module_& m);
// void bind_Buffer(py::module_& m);
// void bind_Array(py::module_& m);
// void bind_Node(py::module_& m);
// void bind_NodeVisitor(py::module_& m);
// void bind_NodeCallback(py::module_& m);
// void bind_Drawable(py::module_& m);
// void bind_Geometry(py::module_& m);
// void bind_Group(py::module_& m);
void bind_Transform(py::module_& m);
// void bind_Geode(py::module_& m);
void bind_Shape(py::module_& m);
void bind_View(py::module_& m);
// void bind_Camera(py::module_& m);
// void bind_State(py::module_& m);
void bind_StateAttributes(py::module_& m);
void bind_Shader(py::module_& m);
// void bind_Program(py::module_& m);
// void bind_Texture(py::module_& m);
void bind_GraphicsContext(py::module_& m);

}
