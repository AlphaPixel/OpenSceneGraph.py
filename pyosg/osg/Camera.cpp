#include "Camera.hpp"

namespace pybind11x {
	template<>
	void kwargs_init_own(osg::Camera& self, const py::kwargs& kwargs) {
		if(kwargs.contains("viewport")) pyosg::detail::camera_viewport_property_setter()(
			self,
			kwargs["viewport"]
		);

		if(kwargs.contains("clearColor")) self.setClearColor(
			kwargs["clearColor"].cast<osg::Vec4>()
		);

		if(kwargs.contains("clearMask")) self.setClearMask(
			kwargs["clearMask"].cast<GLbitfield>()
		);

		if(kwargs.contains("projectionMatrix")) {
			pyosg::detail::camera_projection_matrix_property_setter()(
				self,
				kwargs["projectionMatrix"]
			);
		}

		if(kwargs.contains("viewMatrix")) pyosg::detail::camera_view_matrix_property_setter()(
			self,
			kwargs["viewMatrix"]
		);

		if(kwargs.contains("renderOrder")) pyosg::detail::camera_render_order_property_setter()(
			self,
			kwargs["renderOrder"]
		);

		if(kwargs.contains("graphicsContext")) self.setGraphicsContext(
			kwargs["graphicsContext"].cast<osg::GraphicsContext*>()
		);

		if(kwargs.contains("renderTargetImplementation")) {
			pyosg::detail::camera_render_target_implementation_property_setter()(
				self,
				kwargs["renderTargetImplementation"]
			);
		}

		if(kwargs.contains("allowEventFocus")) self.setAllowEventFocus(
			kwargs["allowEventFocus"].cast<bool>()
		);

		if(kwargs.contains("computeNearFarMode")) self.setComputeNearFarMode(
			kwargs["computeNearFarMode"].cast<osg::CullSettings::ComputeNearFarMode>()
		);

		if(kwargs.contains("nearFarRatio")) self.setNearFarRatio(
			kwargs["nearFarRatio"].cast<double>()
		);

		if(kwargs.contains("initialDrawCallback")) pyosg::detail::camera_draw_callback_property_setter<
			pyosg::detail::InitialDrawCallbackSlot,
			pyosg::detail::InitialDrawCallbackSetter,
			pyosg::detail::InitialDrawCallbackGetter
		>()(self, kwargs["initialDrawCallback"]);

		if(kwargs.contains("preDrawCallback")) pyosg::detail::camera_draw_callback_property_setter<
			pyosg::detail::PreDrawCallbackSlot,
			pyosg::detail::PreDrawCallbackSetter,
			pyosg::detail::PreDrawCallbackGetter
		>()(self, kwargs["preDrawCallback"]);

		if(kwargs.contains("postDrawCallback")) pyosg::detail::camera_draw_callback_property_setter<
			pyosg::detail::PostDrawCallbackSlot,
			pyosg::detail::PostDrawCallbackSetter,
			pyosg::detail::PostDrawCallbackGetter
		>()(self, kwargs["postDrawCallback"]);

		if(kwargs.contains("finalDrawCallback")) pyosg::detail::camera_draw_callback_property_setter<
			pyosg::detail::FinalDrawCallbackSlot,
			pyosg::detail::FinalDrawCallbackSetter,
			pyosg::detail::FinalDrawCallbackGetter
		>()(self, kwargs["finalDrawCallback"]);
	}
}

namespace pyosg {

void bind_Camera(py::module_& m) {
	auto camera = py::class_<
		osg::Camera,
		osg::Transform,
		// TODO: Implement this!
		// osg::CullSettings,
		osg::ref_ptr<osg::Camera>
	>(
		m,
		"Camera",
		"A Transform node that renders its subgraph from its own view/projection matrices, "
		"optionally into an off-screen render target (FBO, PBuffer, etc.). "
		".initialDrawCallback/.preDrawCallback/.postDrawCallback/.finalDrawCallback each "
		"accept either a DrawCallback subclass instance or a plain Python callable."
	)
		.def(py::init<>(), "Create a Camera with default view/projection matrices and no render target.")
		.def(
			py::init(pyx::kwargs_ctor<osg::Camera>()),
			"Create a Camera, setting any of viewport/clearColor/clearMask/projectionMatrix/"
			"viewMatrix/renderOrder/graphicsContext/renderTargetImplementation/allowEventFocus/"
			"computeNearFarMode/nearFarRatio/initialDrawCallback/preDrawCallback/"
			"postDrawCallback/finalDrawCallback from keyword arguments."
		)
	;

	py::enum_<osg::Camera::RenderOrder>(
		camera,
		"RenderOrder",
		"When this Camera's subgraph renders relative to its parent View's main scene: "
		"PRE_RENDER and POST_RENDER run outside the main render (ordered by .renderOrder's "
		"secondary sort key), NESTED_RENDER runs inline at the Camera's position in the graph."
	)
		.value("PRE_RENDER", osg::Camera::PRE_RENDER)
		.value("NESTED_RENDER", osg::Camera::NESTED_RENDER)
		.value("POST_RENDER", osg::Camera::POST_RENDER)
		.export_values()
	;

	py::enum_<osg::Camera::BufferComponent>(
		camera,
		"BufferComponent",
		"Which framebuffer attachment point .attach()/.detach() target; COLOR_BUFFER is an "
		"alias for COLOR_BUFFER0."
	)
		.value("DEPTH_BUFFER", osg::Camera::DEPTH_BUFFER)
		.value("STENCIL_BUFFER", osg::Camera::STENCIL_BUFFER)
		.value("PACKED_DEPTH_STENCIL_BUFFER", osg::Camera::PACKED_DEPTH_STENCIL_BUFFER)
		.value("COLOR_BUFFER", osg::Camera::COLOR_BUFFER)
		.value("COLOR_BUFFER0", osg::Camera::COLOR_BUFFER0)
		.value("COLOR_BUFFER1", osg::Camera::COLOR_BUFFER1)
		.value("COLOR_BUFFER2", osg::Camera::COLOR_BUFFER2)
		.value("COLOR_BUFFER3", osg::Camera::COLOR_BUFFER3)
		.value("COLOR_BUFFER4", osg::Camera::COLOR_BUFFER4)
		.value("COLOR_BUFFER5", osg::Camera::COLOR_BUFFER5)
		.value("COLOR_BUFFER6", osg::Camera::COLOR_BUFFER6)
		.value("COLOR_BUFFER7", osg::Camera::COLOR_BUFFER7)
		.value("COLOR_BUFFER8", osg::Camera::COLOR_BUFFER8)
		.value("COLOR_BUFFER9", osg::Camera::COLOR_BUFFER9)
		.value("COLOR_BUFFER10", osg::Camera::COLOR_BUFFER10)
		.value("COLOR_BUFFER11", osg::Camera::COLOR_BUFFER11)
		.value("COLOR_BUFFER12", osg::Camera::COLOR_BUFFER12)
		.value("COLOR_BUFFER13", osg::Camera::COLOR_BUFFER13)
		.value("COLOR_BUFFER14", osg::Camera::COLOR_BUFFER14)
		.value("COLOR_BUFFER15", osg::Camera::COLOR_BUFFER15)
		.export_values()
	;

	py::enum_<osg::Camera::RenderTargetImplementation>(
		camera,
		"RenderTargetImplementation",
		"How .renderTargetImplementation renders off-screen: FRAME_BUFFER_OBJECT is the usual "
		"modern choice; the others are legacy pbuffer/window fallbacks."
	)
		.value("FRAME_BUFFER_OBJECT", osg::Camera::FRAME_BUFFER_OBJECT)
		.value("PIXEL_BUFFER_RTT", osg::Camera::PIXEL_BUFFER_RTT)
		.value("PIXEL_BUFFER", osg::Camera::PIXEL_BUFFER)
		.value("FRAME_BUFFER", osg::Camera::FRAME_BUFFER)
		.value("SEPARATE_WINDOW", osg::Camera::SEPARATE_WINDOW)
		.export_values()
	;

	py::enum_<osg::CullSettings::ComputeNearFarMode>(
		camera,
		"ComputeNearFarMode",
		"How .computeNearFarMode derives near/far clip planes each frame: from the scene's "
		"bounding volumes, from actual primitives (tighter but slower), or not at all."
	)
		.value("DO_NOT_COMPUTE_NEAR_FAR", osg::CullSettings::DO_NOT_COMPUTE_NEAR_FAR)
		.value(
			"COMPUTE_NEAR_FAR_USING_BOUNDING_VOLUMES",
			osg::CullSettings::COMPUTE_NEAR_FAR_USING_BOUNDING_VOLUMES
		)
		.value(
			"COMPUTE_NEAR_FAR_USING_PRIMITIVES",
			osg::CullSettings::COMPUTE_NEAR_FAR_USING_PRIMITIVES
		)
		.value(
			"COMPUTE_NEAR_USING_PRIMITIVES",
			osg::CullSettings::COMPUTE_NEAR_USING_PRIMITIVES
		)
		.export_values()
	;

	py::class_<
		osg::Camera::DrawCallback,
		detail::Camera::DrawCallback,
		osg::Object,
		osg::ref_ptr<osg::Camera::DrawCallback>
	>(
		camera,
		"DrawCallback",
		"Base class for Camera's initialDrawCallback/preDrawCallback/postDrawCallback/"
		"finalDrawCallback - subclass and override run(renderInfo), or pass a plain callable "
		"to those properties instead."
	)
		.def(py::init<>(), "Create a DrawCallback; subclasses override run(renderInfo).")
	;

	camera
		.def_property(
			"computeNearFarMode",
			&osg::Camera::getComputeNearFarMode,
			&osg::Camera::setComputeNearFarMode,
			"How near/far clip planes are derived each frame; see ComputeNearFarMode."
		)
		.def_property(
			"nearFarRatio",
			&osg::Camera::getNearFarRatio,
			&osg::Camera::setNearFarRatio,
			"Minimum near/far ratio the auto-computed near plane is clamped to, guarding "
			"against depth-buffer precision loss."
		)
		.def_property(
			"renderOrder",
			&osg::Camera::getRenderOrder,
			detail::camera_render_order_property_setter(),
			"Set as (RenderOrder, order_num) to also set the secondary sort key among "
			"PRE_RENDER/POST_RENDER cameras, or just a RenderOrder to keep order_num at 0."
		)
		.def_property(
			"clearMask",
			&osg::Camera::getClearMask,
			&osg::Camera::setClearMask,
			"Bitwise-OR of GL_COLOR_BUFFER_BIT/GL_DEPTH_BUFFER_BIT/GL_STENCIL_BUFFER_BIT "
			"cleared at the start of this Camera's render."
		)
		.def_property(
			"clearColor",
			&osg::Camera::getClearColor,
			&osg::Camera::setClearColor,
			"Vec4 RGBA color used to clear the color buffer when clearMask includes "
			"GL_COLOR_BUFFER_BIT."
		)
		.def_property(
			"allowEventFocus",
			&osg::Camera::getAllowEventFocus,
			&osg::Camera::setAllowEventFocus,
			"Whether event handlers/manipulators attached to this Camera's View receive "
			"events that occur within its viewport."
		)
		.def_property(
			"view",
			py::overload_cast<>(&osg::Camera::getView, py::const_),
			&osg::Camera::setView,
			py::return_value_policy::reference_internal,
			"The View this Camera belongs to, or None if unattached."
		)
		.def_property(
			"graphicsContext",
			py::overload_cast<>(&osg::Camera::getGraphicsContext),
			&osg::Camera::setGraphicsContext,
			py::return_value_policy::reference_internal,
			"The GraphicsContext (window/FBO surface) this Camera renders into."
		)
		.def_property(
			"viewport",
			py::overload_cast<>(&osg::Camera::getViewport, py::const_),
			detail::camera_viewport_property_setter(),
			py::return_value_policy::reference_internal,
			"The Viewport (pixel x/y/width/height) this Camera renders into; settable from "
			"a Viewport instance or an (x, y, width, height) tuple."
		)

		.def_property(
			"projectionMatrix",
			py::overload_cast<>(&osg::Camera::getProjectionMatrix, py::const_),
			detail::camera_projection_matrix_property_setter(),
			py::return_value_policy::reference_internal,
			"The projection matrix; settable from a Matrixd or a flat 16-value sequence."
		)

		.def_property(
			"viewMatrix",
			py::overload_cast<>(&osg::Camera::getViewMatrix, py::const_),
			detail::camera_view_matrix_property_setter(),
			py::return_value_policy::reference_internal,
			"The view (world-to-eye) matrix; settable from a Matrixd or a flat 16-value sequence."
		)

		.def_property(
			"initialDrawCallback",
			detail::CameraSlots::getter<detail::InitialDrawCallbackSlot>(
				detail::InitialDrawCallbackGetter
			),
			detail::camera_draw_callback_property_setter<
				detail::InitialDrawCallbackSlot,
				detail::InitialDrawCallbackSetter,
				detail::InitialDrawCallbackGetter
			>(),
			"Callback (DrawCallback subclass instance or plain callable) invoked before any "
			"rendering for this Camera, once per graphics context."
		)
		.def_property(
			"preDrawCallback",
			detail::CameraSlots::getter<detail::PreDrawCallbackSlot>(
				detail::PreDrawCallbackGetter
			),
			detail::camera_draw_callback_property_setter<
				detail::PreDrawCallbackSlot,
				detail::PreDrawCallbackSetter,
				detail::PreDrawCallbackGetter
			>(),
			"Callback invoked immediately before this Camera's subgraph is drawn."
		)
		.def_property(
			"postDrawCallback",
			detail::CameraSlots::getter<detail::PostDrawCallbackSlot>(
				detail::PostDrawCallbackGetter
			),
			detail::camera_draw_callback_property_setter<
				detail::PostDrawCallbackSlot,
				detail::PostDrawCallbackSetter,
				detail::PostDrawCallbackGetter
			>(),
			"Callback invoked immediately after this Camera's subgraph is drawn."
		)
		.def_property(
			"finalDrawCallback",
			detail::CameraSlots::getter<detail::FinalDrawCallbackSlot>(
				detail::FinalDrawCallbackGetter
			),
			detail::camera_draw_callback_property_setter<
				detail::FinalDrawCallbackSlot,
				detail::FinalDrawCallbackSetter,
				detail::FinalDrawCallbackGetter
			>(),
			"Callback invoked after all rendering for this Camera has completed, once per "
			"graphics context."
		)

		.def(
			"attach",
			py::overload_cast<osg::Camera::BufferComponent, GLenum>(&osg::Camera::attach),
			"Attach a raw GL buffer (e.g. GL_FRONT) to the given BufferComponent, for "
			"non-FBO render targets."
		)
		.def(
			"attach",
			py::overload_cast<
				osg::Camera::BufferComponent,
				osg::Texture*,
				unsigned int,
				unsigned int,
				bool,
				unsigned int,
				unsigned int
			>(&osg::Camera::attach),
			"Attach a Texture as the render target for the given BufferComponent (RTT).",
			"buffer"_a,
			"texture"_a,
			"level"_a=0,
			"face"_a=0,
			"mipMapGeneration"_a=false,
			"multisampleSamples"_a=0,
			"multisampleColorSamples"_a=0
		)
		.def(
			"attach",
			py::overload_cast<
				osg::Camera::BufferComponent,
				osg::Image*,
				unsigned int,
				unsigned int
			>(&osg::Camera::attach),
			"Attach an Image as the render target for the given BufferComponent, so the "
			"rendered pixels are read back into it (e.g. for screenshots or CPU readback).",
			"buffer"_a,
			"image"_a,
			"multisampleSamples"_a=0,
			"multisampleColorSamples"_a=0
		)
		.def("detach", &osg::Camera::detach, "Remove any attachment previously set on the given BufferComponent.")

		.def_property(
			"renderTargetImplementation",
			[](const osg::Camera& self) {
				return py::make_tuple(
					self.getRenderTargetImplementation(),
					self.getRenderTargetFallback()
				);
			},
			detail::camera_render_target_implementation_property_setter(),
			"Read as (implementation, fallback); settable from a single RenderTargetImplementation "
			"or an (implementation, fallback) tuple used if the primary choice is unavailable."
		)
	;
}

}
