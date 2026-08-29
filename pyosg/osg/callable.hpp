#pragma once

#include "../pyosg.hpp"
#include "pybind11x.hpp"

// OSG's callback system mixes:
//
//   - virtual inheritance (Callback)
//   - derived callback types (NodeCallback, DrawCallback, etc.)
//   - inconsistent pointer usage (Callback* vs derived*)
//   - differing execution semantics (traversal vs non-traversal)
//
// Because of this, pointer identity is not stable across API boundaries (e.g. NodeCallback* vs
// Callback* may refer to the same object but have different addresses due to virtual inheritance).
//
// To ensure correct Python identity and behavior:
//
//   1. Callback conversion (None / instance / callable) is handled explicitly.
//   2. PropertySlots are used to preserve Python object identity.
//   3. Stored pointers are *canonicalized via the getter* (e.g. getUpdateCallback()) before being
//      cached, ensuring stable comparisons.
//
// This is not a workaround for a bug, but an adaptation to OSG's design.
// Do not "simplify" this without understanding pointer adjustment semantics.

namespace pyosg {

namespace detail {
	template<typename T>
	struct CallableCallbackTraits;

	template<typename Self, typename CallbackArg>
	struct CallableCallbackTraits<void(Self::*)(CallbackArg)> {
		using self_type = Self;
	};

	template<typename Self, typename CallbackArg>
	struct CallableCallbackTraits<void(Self::*)(CallbackArg) const> {
		using self_type = Self;
	};

	template<typename Base, typename Signature, bool Traverse>
	class PYOSG_INTERNAL CallableCallback;

	template<typename Base, bool Traverse>
	struct CallableImpl {
		template<typename... Args>
		static void call(Base* self, const py::object& fn, Args&&... args) {
			py::gil_scoped_acquire gil;

			auto result = fn(std::forward<Args>(args)...);

			if constexpr(Traverse) {
				if(!result.is_none() && !result.template cast<bool>()) return;

				self->traverse(std::forward<Args>(args)...);
			}
		}
	};

	template<typename Base>
	struct CallbackMethod;

	// Decides exactly what method is called (`operator(), run(), drawImplementation(), etc) by
	// the `CallableCallback` wrapper class.
	//
	// See the source for `osg::Drawable::DrawCallback` for an example on how to specialize an
	// an instance.
	template<typename Base>
	struct CallbackMethod {
		template<typename Self, typename Fn, typename... Args>
		static void invoke(Self* self, Fn& fn, Args&&... args) {
			CallableImpl<Base, false>::call(self, fn, std::forward<Args>(args)...);
		}
	};

	template<typename Base, typename... Args, bool Traverse>
	class CallableCallback<Base, void(Args...), Traverse>: public Base {
	public:
		explicit CallableCallback(py::object fn): _fn(std::move(fn)) {}

		~CallableCallback() override { pybind11x::release_with_gil(_fn); }

		void operator()(Args... args) override {
			CallbackMethod<Base>::invoke(this, _fn, std::forward<Args>(args)...);
		}

	private:
		py::object _fn;
	};

	// This is the actual wrapper class that makes it possible to use the traditional OSG API for
	// your callback OR some other kind of more generic "callable" Python object. By default, this
	// specialization expects to override `operator()`.
	//
	// If you use a specialized `CallbackMethod`, you will also need to specialize a corresponding
	// version of this class as well.
	template<typename Base, typename... Args, bool Traverse>
	class CallableCallback<Base, void(Args...) const, Traverse>: public Base {
	public:
		explicit CallableCallback(py::object fn): _fn(std::move(fn)) {}

		~CallableCallback() override { pybind11x::release_with_gil(_fn); }

		void operator()(Args... args) const override {
			CallableImpl<Base, Traverse>::call(
				const_cast<Base*>(static_cast<const Base*>(this)),
				_fn,
				std::forward<Args>(args)...
			);
		}

	private:
		py::object _fn;
	};

	template<typename Getter>
	auto getCallback(Getter&& getter) {
		return py::cpp_function(
			std::forward<Getter>(getter),
			py::return_value_policy::reference_internal
		);
	}

	template<auto Setter, typename Callback, typename Wrapper, typename Self>
	Callback* applyCallback(Self& self, py::object obj) {
		Callback* result = nullptr;

		if(obj.is_none()) result = nullptr;

		else if(py::isinstance<Callback>(obj)) result = obj.cast<Callback*>();

		else if(PyCallable_Check(obj.ptr())) result = new Wrapper(obj);

		else {
			throw py::value_error("Expected compatible callback, callable, or None");
		}

		(self.*Setter)(result);

		return result;
	}

	template<auto Setter, typename Callback, typename Wrapper>
	auto setCallback() {
		using traits_type = CallableCallbackTraits<decltype(Setter)>;
		using self_type = typename traits_type::self_type;

		return py::cpp_function(
			[](self_type& self, py::object obj) {
				applyCallback<Setter, Callback, Wrapper>(self, obj);
			},
			py::keep_alive<1, 2>()
		);
	}

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
	//   if(auto r = call_override<bool>(...)) { ... }
	//   bool was_called = call_override<void>(...)
	//
	// Python returning None is treated as "no opinion/use default behavior". This (mostly) matches
	// OSG semantics in NodeVisitor, NodeCallback, GUIEventHandler, and all other OSG virtual-call
	// conventions where visitation/continuation can potentially be short-circuited.
	template<typename Ret, typename Self, typename... Args>
	auto call_override(const char* name, const Self* self, Args&&... args) {
		// Always acquire the GIL before touching Python.
		py::gil_scoped_acquire gil;

		// Look up the override on the Python side.
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
			// Python returned None: treat as "no value" (default C++ behavior).
			if(result.is_none()) return std::optional<Ret>{};

			// Concrete return: send it back to caller.
			return std::optional<Ret>(result.template cast<Ret>());
		}
	}
}

}
