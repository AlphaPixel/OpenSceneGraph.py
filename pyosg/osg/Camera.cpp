#include "Camera.hpp"

namespace pyosg {

void bind_Camera(py::module_& m) {
	auto camera = py::class_<
		osg::Camera,
		osg::Transform,
		// TODO: Implement this!
		// osg::CullSettings,
		osg::ref_ptr<osg::Camera>
	>(m, "Camera")
		.def(py::init<>())
	;

	py::enum_<osg::Camera::RenderOrder>(camera, "RenderOrder")
		.value("PRE_RENDER", osg::Camera::PRE_RENDER)
		.value("NESTED_RENDER", osg::Camera::NESTED_RENDER)
		.value("POST_RENDER", osg::Camera::POST_RENDER)
		.export_values()
	;

	py::enum_<osg::Camera::BufferComponent>(camera, "BufferComponent")
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

	py::enum_<osg::Camera::RenderTargetImplementation>(camera, "RenderTargetImplementation")
		.value("FRAME_BUFFER_OBJECT", osg::Camera::FRAME_BUFFER_OBJECT)
		.value("PIXEL_BUFFER_RTT", osg::Camera::PIXEL_BUFFER_RTT)
		.value("PIXEL_BUFFER", osg::Camera::PIXEL_BUFFER)
		.value("FRAME_BUFFER", osg::Camera::FRAME_BUFFER)
		.value("SEPARATE_WINDOW", osg::Camera::SEPARATE_WINDOW)
		.export_values()
	;

	py::class_<
		osg::Camera::DrawCallback,
		detail::Camera::DrawCallback,
		osg::Object,
		osg::ref_ptr<osg::Camera::DrawCallback>
	>(camera, "DrawCallback")
		.def(py::init<>())
	;

	camera
		.def_property(
			"renderOrder",
			&osg::Camera::getRenderOrder,
			[](osg::Camera& self, py::object obj) {
				if(py::isinstance<osg::Camera::RenderOrder>(obj)) {
					self.setRenderOrder(obj.cast<osg::Camera::RenderOrder>());
				}

				else if(py::isinstance<py::sequence>(obj)) {
					auto seq = obj.cast<py::sequence>();

					if(seq.size() != 2) throw py::value_error("Expected (RenderOrder, int)");

					self.setRenderOrder(
						seq[0].cast<osg::Camera::RenderOrder>(),
						seq[1].cast<int>()
					);
				}

				else throw py::value_error("Expected RenderOrder or (RenderOrder, int)");
			}
		)
		.def_property("clearMask", &osg::Camera::getClearMask, &osg::Camera::setClearMask)
		.def_property("clearColor", &osg::Camera::getClearColor, &osg::Camera::setClearColor)
		.def_property(
			"allowEventFocus",
			&osg::Camera::getAllowEventFocus,
			&osg::Camera::setAllowEventFocus
		)
		.def_property(
			"view",
			py::overload_cast<>(&osg::Camera::getView, py::const_),
			&osg::Camera::setView,
			py::return_value_policy::reference_internal
		)
		.def_property(
			"viewport",
			py::overload_cast<>(&osg::Camera::getViewport, py::const_),
			// TODO: This should really just accept `osg.Viewpoint` (ONLY), but it's nice to know
			// HOW to parse different types of args, so we'll leave it as an example...
			// TODO: We should either settle on ONLY using `py::args` or `py::object`!
			[](osg::Camera& self, const py::args& args) {
				if(args.size() == 1) {
					// camera.viewport = viewport
					if(py::isinstance<osg::Viewport>(args[0])) {
						auto* vp = args[0].cast<osg::Viewport*>();

						self.setViewport(vp);

						return;
					}

					// camera.viewport = (x, y, w, h)
					if(py::isinstance<py::sequence>(args[0])) {
						auto seq = args[0].cast<py::sequence>();

						if(seq.size() != 4) throw py::value_error("viewport must have 4 elements");

						self.setViewport(
							seq[0].cast<int>(),
							seq[1].cast<int>(),
							seq[2].cast<int>(),
							seq[3].cast<int>()
						);

						return;
					}
				}

				throw py::type_error("viewport must be set to osg.Viewport or sequence");
			},
			py::return_value_policy::reference_internal,
			py::doc(
				"Get or set the camera viewport.\n\n"
				"Setter accepts either:\n"
				"  - osg.Viewport\n"
				"  - (x, y, width, height) tuple"
			)
		)

		.def_property(
			"projectionMatrix",
			py::overload_cast<>(&osg::Camera::getProjectionMatrix, py::const_),
			[](osg::Camera& self, py::handle matrix) {
				if(py::isinstance<osg::Matrixd>(matrix)) self.setProjectionMatrix(
					matrix.cast<osg::Matrixd>()
				);

				else if(py::isinstance<osg::Matrixf>(matrix)) self.setProjectionMatrix(
					matrix.cast<osg::Matrixf>()
				);

				else throw py::type_error("projectionMatrix must be osg.Matrixd or osg.Matrixf");
			},
			py::return_value_policy::reference_internal
		)

		.def_property(
			"viewMatrix",
			py::overload_cast<>(&osg::Camera::getViewMatrix, py::const_),
			[](osg::Camera& self, py::handle matrix) {
				if(py::isinstance<osg::Matrixd>(matrix)) self.setViewMatrix(
					matrix.cast<osg::Matrixd>()
				);

				else if(py::isinstance<osg::Matrixf>(matrix)) self.setViewMatrix(
					matrix.cast<osg::Matrixf>()
				);

				else throw py::type_error("viewMatrix must be osg.Matrixd or osg.Matrixf");
			},
			py::return_value_policy::reference_internal
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
			>()
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
			>()
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
			>()
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
			>()
		)

		.def(
			"attach",
			py::overload_cast<osg::Camera::BufferComponent, GLenum>(&osg::Camera::attach)
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
			"buffer"_a,
			"image"_a,
			"multisampleSamples"_a=0,
			"multisampleColorSamples"_a=0
		)
		.def("detach", &osg::Camera::detach)

		.def_property(
			"renderTargetImplementation",
			[](const osg::Camera& self) {
				return py::make_tuple(
					self.getRenderTargetImplementation(),
					self.getRenderTargetFallback()
				);
			},
			[](osg::Camera& self, py::object obj) {
				if(py::isinstance<osg::Camera::RenderTargetImplementation>(obj)) {
					self.setRenderTargetImplementation(obj.cast<osg::Camera::RenderTargetImplementation>());
				}

				else if(py::isinstance<py::sequence>(obj)) {
					auto seq = obj.cast<py::sequence>();

					if(seq.size() != 2) throw py::value_error("Expected (impl, fallback)");

					self.setRenderTargetImplementation(
						seq[0].cast<osg::Camera::RenderTargetImplementation>(),
						seq[1].cast<osg::Camera::RenderTargetImplementation>()
					);
				}

				else throw py::value_error("Expected RenderTargetImplementation or (impl, fallback)");
			}
		)
	;
}

}
