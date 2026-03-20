#include "../pyosg.hpp"

PYOSG_DISABLE_WARNINGS

#include <osg/View>
#include <osg/Camera>
#include <osg/RenderInfo>

PYOSG_ENABLE_WARNINGS

namespace pyosg {

namespace detail {
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

		// TODO: This is really just a simple helper for using ANYTHING callable, instead of
		// being REQUIRED to override the "__call__" method.
		class PYOSG_INTERNAL CallableDrawCallback: public osg::Camera::DrawCallback {
		public:
			explicit CallableDrawCallback(py::object fn): _fn(std::move(fn)) {}

			void operator()(osg::RenderInfo& ri) const override {
				py::gil_scoped_acquire gil;

				_fn(ri);
			}

		private:
			py::object _fn;
		};
	};

	template<typename Getter>
	auto getDrawCallback(Getter&& getter) {
		return py::cpp_function(
			std::forward<Getter>(getter),
			py::return_value_policy::reference_internal
		);
	}

	template<auto Setter>
	auto setDrawCallback() {
		return py::cpp_function(
			[](osg::Camera& self, py::object obj) {
				if(obj.is_none()) (self.*Setter)(nullptr);

				else if(py::isinstance<osg::Camera::DrawCallback>(obj)) {
					(self.*Setter)(obj.cast<osg::Camera::DrawCallback*>());
				}

				else if(PyCallable_Check(obj.ptr())) {
					auto cb = new Camera::CallableDrawCallback(obj);

					(self.*Setter)(cb);
				}

				else throw py::value_error("Expected DrawCallback, callable, or None");
			},
			py::keep_alive<1, 2>()
		);
	}
}

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
	;

	py::class_<
		osg::Camera::DrawCallback,
		detail::Camera::DrawCallback,
		osg::Object,
		osg::ref_ptr<osg::Camera::DrawCallback>
	>(camera, "DrawCallback")
		.def(py::init<>())
		.def("__call__", [](osg::Camera::DrawCallback& self, osg::RenderInfo* ri) {
			// Manual forwarding; ensures Python sees correct signature.
			return;
		})
	;

	camera
		.def_property("renderOrder", &osg::Camera::getRenderOrder, &osg::Camera::setRenderOrder)
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
			detail::getDrawCallback(py::overload_cast<>(&osg::Camera::getInitialDrawCallback)),
			detail::setDrawCallback<&osg::Camera::setInitialDrawCallback>()
		)
		.def_property(
			"preDrawCallback",
			detail::getDrawCallback(py::overload_cast<>(&osg::Camera::getPreDrawCallback)),
			detail::setDrawCallback<&osg::Camera::setPreDrawCallback>()
		)
		.def_property(
			"postDrawCallback",
			detail::getDrawCallback(py::overload_cast<>(&osg::Camera::getPostDrawCallback)),
			detail::setDrawCallback<&osg::Camera::setPostDrawCallback>()
		)
		.def_property(
			"finalDrawCallback",
			detail::getDrawCallback(py::overload_cast<>(&osg::Camera::getFinalDrawCallback)),
			detail::setDrawCallback<&osg::Camera::setFinalDrawCallback>()
		)
	;
}

}
