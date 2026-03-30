#pragma once

#include "../pyosg.hpp"

namespace pyosg {

namespace detail {
	template<typename T>
	struct CallableCallbackTraits;

	template<typename Self, typename CallbackArg>
	struct CallableCallbackTraits<void (Self::*)(CallbackArg)> {
		using self_type = Self;
		using cb_arg_type = CallbackArg;
	};

	template<typename Self, typename CallbackArg>
	struct CallableCallbackTraits<void (Self::*)(CallbackArg) const> {
		using self_type = Self;
		using cb_arg_type = CallbackArg;
	};

	template<typename Base, typename Signature>
	class PYOSG_INTERNAL CallableCallback;

	template<typename Base, typename... Args>
	class CallableCallback<Base, void(Args...)>: public Base {
	public:
		explicit CallableCallback(py::object fn): _fn(std::move(fn)) {}

		void operator()(Args... args) override {
			py::gil_scoped_acquire gil;

			_fn(std::forward<Args>(args)...);
		}

	private:
		py::object _fn;
	};

	template<typename Base, typename... Args>
	class CallableCallback<Base, void(Args...) const>: public Base {
	public:
		explicit CallableCallback(py::object fn): _fn(std::move(fn)) {}

		void operator()(Args... args) const override {
			py::gil_scoped_acquire gil;

			_fn(std::forward<Args>(args)...);
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

	template<auto Setter, typename Wrapper>
	auto setCallback() {
		using traits_type = CallableCallbackTraits<decltype(Setter)>;
		using cb_base_type = std::remove_pointer_t<typename traits_type::cb_arg_type>;

		return py::cpp_function(
			[](typename traits_type::self_type& self, py::object obj) {
				if(obj.is_none()) (self.*Setter)(nullptr);

				else if(py::isinstance<cb_base_type>(obj)) (self.*Setter)(obj.cast<cb_base_type*>());

				else if(PyCallable_Check(obj.ptr())) {
					auto cb = new Wrapper(obj);

					(self.*Setter)(cb);
				}

				else {
					throw py::value_error("Expected callback, callable, or None");
				}
			},
			py::keep_alive<1, 2>()
		);
	}
}

}
