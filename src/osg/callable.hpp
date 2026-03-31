#pragma once

#include "../pyosg.hpp"

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
	void applyCallback(Self& self, py::object obj) {
		if (obj.is_none()) {
			(self.*Setter)(nullptr);
		}

		else if (py::isinstance<Callback>(obj)) {
			auto* cb = obj.cast<Callback*>();
			(self.*Setter)(cb);
		}

		else if (PyCallable_Check(obj.ptr())) {
			auto* cb = new Wrapper(obj);
			(self.*Setter)(cb);
		}

		else {
			throw py::value_error("Expected callback, callable, or None");
		}
	}

	template<auto Setter, typename Callback, typename Wrapper>
	auto setCallback() {
		using traits_type = CallableCallbackTraits<decltype(Setter)>;
		using self_type = typename traits_type::self_type;

		/* return py::cpp_function(
			[](self_type& self, py::object obj) {
				if(obj.is_none()) (self.*Setter)(nullptr);

				else if(py::isinstance<Callback>(obj)) {
					auto* cb = obj.cast<Callback*>();

					(self.*Setter)(cb);
				}

				else if(PyCallable_Check(obj.ptr())) {
					auto* cb = new Wrapper(obj);

					(self.*Setter)(cb);
				}

				else {
					throw py::value_error("Expected callback, callable, or None");
				}
			},
			py::keep_alive<1, 2>()
		); */

		return py::cpp_function(
			[](self_type& self, py::object obj) {
				applyCallback<Setter, Callback, Wrapper>(self, obj);
			},
			py::keep_alive<1, 2>()
		);
	}
}

}
