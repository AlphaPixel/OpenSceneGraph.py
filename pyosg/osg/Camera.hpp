#pragma once

#include "callable.hpp"

OSGX_DISABLE_WARNINGS

#include <osg/View>
#include <osg/Camera>
#include <osg/RenderInfo>

OSGX_ENABLE_WARNINGS

#include "pybind11x-osg.hpp"

namespace pyx = pybind11x;

namespace pyosg {

namespace detail {
	constexpr size_t InitialDrawCallbackSlot = 0;
	constexpr size_t PreDrawCallbackSlot = 1;
	constexpr size_t PostDrawCallbackSlot = 2;
	constexpr size_t FinalDrawCallbackSlot = 3;

	using CameraSlots = pyx::PropertySlots<osg::Camera, 4>;
	using CameraStorage = pyx::ProxyStorageOSG<osg::Camera, CameraSlots>;
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

	// Shared setters used by both `bind_Camera()`'s `.def_property()` calls and
	// `kwargs_init_own()` -- keeps the parsing/validation logic for each property in one place.
	inline auto camera_viewport_property_setter() {
		return [](osg::Camera& self, py::object obj) {
			if(py::isinstance<osg::Viewport>(obj)) {
				self.setViewport(obj.cast<osg::Viewport*>());
			}

			else if(auto vals = pyx::try_unpack_sequence<int, int, int, int>(obj)) {
				auto& [x, y, w, h] = *vals;

				self.setViewport(x, y, w, h);
			}

			else throw py::type_error("viewport must be osg.Viewport or (x, y, width, height)");
		};
	}

	inline auto camera_projection_matrix_property_setter() {
		return [](osg::Camera& self, py::handle matrix) {
			if(py::isinstance<osg::Matrixd>(matrix)) self.setProjectionMatrix(
				matrix.cast<osg::Matrixd>()
			);

			else if(py::isinstance<osg::Matrixf>(matrix)) self.setProjectionMatrix(
				matrix.cast<osg::Matrixf>()
			);

			else throw py::type_error("projectionMatrix must be osg.Matrixd or osg.Matrixf");
		};
	}

	inline auto camera_view_matrix_property_setter() {
		return [](osg::Camera& self, py::handle matrix) {
			if(py::isinstance<osg::Matrixd>(matrix)) self.setViewMatrix(matrix.cast<osg::Matrixd>());

			else if(py::isinstance<osg::Matrixf>(matrix)) self.setViewMatrix(
				matrix.cast<osg::Matrixf>()
			);

			else throw py::type_error("viewMatrix must be osg.Matrixd or osg.Matrixf");
		};
	}

	inline auto camera_render_order_property_setter() {
		return [](osg::Camera& self, py::object obj) {
			if(py::isinstance<osg::Camera::RenderOrder>(obj)) {
				self.setRenderOrder(obj.cast<osg::Camera::RenderOrder>());
			}

			else if(auto vals = pyx::try_unpack_sequence<osg::Camera::RenderOrder, int>(obj)) {
				auto& [order, num] = *vals;

				self.setRenderOrder(order, num);
			}

			else throw py::value_error("renderOrder must be RenderOrder or (RenderOrder, int)");
		};
	}

	inline auto camera_render_target_implementation_property_setter() {
		return [](osg::Camera& self, py::object obj) {
			if(py::isinstance<osg::Camera::RenderTargetImplementation>(obj)) {
				self.setRenderTargetImplementation(
					obj.cast<osg::Camera::RenderTargetImplementation>()
				);
			}

			else if(auto vals = pyx::try_unpack_sequence<
				osg::Camera::RenderTargetImplementation, osg::Camera::RenderTargetImplementation
			>(obj)) {
				auto& [impl, fallback] = *vals;

				self.setRenderTargetImplementation(impl, fallback);
			}

			else throw py::value_error(
				"renderTargetImplementation must be RenderTargetImplementation or (impl, fallback)"
			);
		};
	}

	class Camera: public osg::Camera {
	public:
		struct DrawCallback: osg::Camera::DrawCallback {
			using osg::Camera::DrawCallback::DrawCallback;

			void operator()(osg::RenderInfo& ri) const override {
				call_override<void>("__call__", this, ri);
			}
		};
	};
}

void bind_Camera(py::module_& m);

}
