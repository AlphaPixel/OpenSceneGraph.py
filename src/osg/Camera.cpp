#include "../pyosg.hpp"

PYOSG_DISABLE_WARNINGS

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
		.def_property(
			"viewport",
			py::overload_cast<>(&osg::Camera::getViewport),
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
			py::doc(
				"Get or set the camera viewport.\n\n"
				"Setter accepts either:\n"
				"  - osg.Viewport\n"
				"  - (x, y, width, height) tuple"
			)
		)
		// setProjectionMatrixAsPerspective
	;
}

}
