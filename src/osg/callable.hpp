#pragma once

#include "../pyosg.hpp"

// NOTE: OSG callback bindings
//
// OSG’s callback system mixes:
//   - virtual inheritance (Callback)
//   - derived callback types (NodeCallback, DrawCallback, etc.)
//   - inconsistent pointer usage (Callback* vs derived*)
//   - differing execution semantics (traversal vs non-traversal)
//
// Because of this, pointer identity is not stable across API boundaries
// (e.g. NodeCallback* vs Callback* may refer to the same object but have
// different addresses due to virtual inheritance).
//
// To ensure correct Python identity and behavior:
//
//   1. Callback conversion (None / instance / callable) is handled explicitly.
//   2. PropertySlots are used to preserve Python object identity.
//   3. Stored pointers are *canonicalized via the getter* (e.g. getUpdateCallback())
//      before being cached, ensuring stable comparisons.
//
// This is not a workaround for a bug, but an adaptation to OSG’s design.
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

	template<typename Base, typename... Args, bool Traverse>
	class CallableCallback<Base, void(Args...), Traverse>: public Base {
	public:
		explicit CallableCallback(py::object fn): _fn(std::move(fn)) {}

		void operator()(Args... args) override {
			CallableImpl<Base, Traverse>::call(this, _fn, std::forward<Args>(args)...);
		}

	private:
		py::object _fn;
	};

	template<typename Base, typename... Args, bool Traverse>
	class CallableCallback<Base, void(Args...) const, Traverse>: public Base {
	public:
		explicit CallableCallback(py::object fn): _fn(std::move(fn)) {}

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
			throw py::value_error("Expected callback, callable, or None");
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
}

}
