#pragma once

#include "callable.hpp"

OSGX_DISABLE_WARNINGS

#include <osg/Drawable>

OSGX_ENABLE_WARNINGS

#include "pybind11x.hpp"

namespace pyx = pybind11x;

namespace pyosg {

namespace detail {
	using DrawableSlots = pyx::PropertySlots<osg::Drawable, 1>;
	using DrawableStorage = pyx::ProxyStorageOSG<osg::Drawable, DrawableSlots>;

	constexpr size_t DrawableCallbackSlot = 0;

	using DrawableCallbackType = osg::Drawable::DrawCallback;
	using DrawableCallbackWrapper = CallableCallback<
		osg::Drawable::DrawCallback,
		void(osg::RenderInfo&, const osg::Drawable*) const,
		false
	>;

	constexpr auto DrawableCallbackGetter =
		static_cast<osg::Drawable::DrawCallback*(osg::Drawable::*)()>(
			&osg::Drawable::getDrawCallback
		)
	;

	constexpr auto DrawableCallbackSetter =
		static_cast<void(osg::Drawable::*)(osg::Drawable::DrawCallback*)>(
			&osg::Drawable::setDrawCallback
		)
	;

	template<size_t I, auto Setter, auto Getter, typename Callback, typename Wrapper>
	auto callback_property_setter() {
		return [](osg::Drawable& self, py::object obj) {
			applyCallback<Setter, Callback, Wrapper>(self, obj);

			auto* ptr = (self.*Getter)();
			auto& slots = DrawableStorage::get(self)->template proxy<DrawableSlots>();

			slots.set(I, obj, ptr);
		};
	}

	template<>
	struct CallbackMethod<osg::Drawable::DrawCallback> {
		template<typename Self, typename Fn>
		static void invoke(Self* self, Fn& fn, osg::RenderInfo& ri) {
			py::gil_scoped_acquire gil;

			fn(ri);
		}
	};

	template<>
	class CallableCallback<
		osg::Drawable::DrawCallback,
		void(osg::RenderInfo&, const osg::Drawable*) const,
		false
	>: public osg::Drawable::DrawCallback {
	public:
		explicit CallableCallback(py::object fn): _fn(std::move(fn)) {}

		void drawImplementation(osg::RenderInfo& ri, const osg::Drawable* d) const override {
			py::gil_scoped_acquire gil;

			_fn(ri, d);
		}

	private:
		py::object _fn;
	};

	inline auto draw_callback_property_setter() {
		return callback_property_setter<
			DrawableCallbackSlot,
			DrawableCallbackSetter,
			DrawableCallbackGetter,
			DrawableCallbackType,
			DrawableCallbackWrapper
		>();
	}

	class Drawable: public osg::Drawable {
	public:
		struct DrawCallback: public osg::Drawable::DrawCallback {
			void drawImplementation(osg::RenderInfo& ri, const osg::Drawable* d) const override {
				PYBIND11_OVERRIDE(
					void,
					osg::Drawable::DrawCallback,
					drawImplementation,
					ri,
					d
				);
			}
		};

		void drawImplementation(osg::RenderInfo& ri) const override {
			PYBIND11_OVERRIDE(
				void,
				osg::Drawable,
				drawImplementation,
				ri
			);
		}

		osg::BoundingSphere computeBound() const override {
			PYBIND11_OVERRIDE(
				osg::BoundingSphere,
				osg::Drawable,
				computeBound
			);
		}

		osg::BoundingBox computeBoundingBox() const override {
			PYBIND11_OVERRIDE(
				osg::BoundingBox,
				osg::Drawable,
				computeBoundingBox
			);
		}
	};
}

void bind_Drawable(py::module_& m);

}
