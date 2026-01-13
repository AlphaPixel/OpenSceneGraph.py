#include "../pyosg.hpp"

PYOSG_DISABLE_WARNINGS

#include <osg/View>
#include <osg/Camera>

PYOSG_ENABLE_WARNINGS

namespace pyosg {

// namespace detail {}

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

	camera
		.def_property("renderOrder", &osg::Camera::getRenderOrder, &osg::Camera::setRenderOrder)
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
	;
}

}
