#pragma once

#include "callable.hpp"

PYOSG_DISABLE_WARNINGS

#include <osg/View>
#include <osg/Camera>
#include <osg/RenderInfo>

PYOSG_ENABLE_WARNINGS

#include "pybind11x.hpp"

namespace pyx = pybind11x;

namespace pyosg {

namespace detail {
	using CameraSlots = pyx::PropertySlots<osg::Camera, 4>;
	using CameraStorage = pyx::ProxyStorageOSG<osg::Camera, CameraSlots>;

	constexpr size_t InitialDrawCallbackSlot = 0;
	constexpr size_t PreDrawCallbackSlot = 1;
	constexpr size_t PostDrawCallbackSlot = 2;
	constexpr size_t FinalDrawCallbackSlot = 3;

	using DrawCallbackType = osg::Camera::DrawCallback;
	using DrawCallbackWrapper = CallableCallback<
		osg::Camera::DrawCallback,
		void(osg::RenderInfo&) const,
		false
	>;

	constexpr auto InitialDrawCallbackGetter =
		static_cast<osg::Camera::DrawCallback*(osg::Camera::*)()>(
			&osg::Camera::getInitialDrawCallback
		)
	;

	constexpr auto InitialDrawCallbackSetter =
		static_cast<void(osg::Camera::*)(osg::Camera::DrawCallback*)>(
			&osg::Camera::setInitialDrawCallback
		)
	;

	constexpr auto PreDrawCallbackGetter =
		static_cast<osg::Camera::DrawCallback*(osg::Camera::*)()>(
			&osg::Camera::getPreDrawCallback
		)
	;

	constexpr auto PreDrawCallbackSetter =
		static_cast<void(osg::Camera::*)(osg::Camera::DrawCallback*)>(
			&osg::Camera::setPreDrawCallback
		)
	;

	constexpr auto PostDrawCallbackGetter =
		static_cast<osg::Camera::DrawCallback*(osg::Camera::*)()>(
			&osg::Camera::getPostDrawCallback
		)
	;

	constexpr auto PostDrawCallbackSetter =
		static_cast<void(osg::Camera::*)(osg::Camera::DrawCallback*)>(
			&osg::Camera::setPostDrawCallback
		)
	;

	constexpr auto FinalDrawCallbackGetter =
		static_cast<osg::Camera::DrawCallback*(osg::Camera::*)()>(
			&osg::Camera::getFinalDrawCallback
		)
	;

	constexpr auto FinalDrawCallbackSetter =
		static_cast<void(osg::Camera::*)(osg::Camera::DrawCallback*)>(
			&osg::Camera::setFinalDrawCallback
		)
	;

	// Slot-backed callback setter. We canonicalize the stored pointer via the getter so SlotCache
	// compares the same pointer representation the getter will later return.
	template<size_t I, auto Setter, auto Getter, typename Callback, typename Wrapper>
	auto camera_callback_property_setter() {
		return [](osg::Camera& self, py::object obj) {
			applyCallback<Setter, Callback, Wrapper>(self, obj);

			auto* ptr = (self.*Getter)();
			auto& slots = CameraStorage::get(self)->template proxy<CameraSlots>();

			slots.set(I, obj, ptr);
		};
	}

	template<size_t I, auto Setter, auto Getter>
	inline auto camera_draw_callback_property_setter() {
		return camera_callback_property_setter<
			I,
			Setter,
			Getter,
			DrawCallbackType,
			DrawCallbackWrapper
		>();
	}

	class Camera: public osg::Camera {
	public:
		struct DrawCallback: osg::Camera::DrawCallback {
			using osg::Camera::DrawCallback::DrawCallback;

			void operator()(osg::RenderInfo& ri) const override {
				PYBIND11_OVERRIDE(
					void,
					osg::Camera::DrawCallback,
					operator(),
					ri
				);
			}
		};
	};
}

void bind_Camera(py::module_& m);

}
