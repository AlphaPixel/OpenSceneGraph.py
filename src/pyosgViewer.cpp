#include "pyosgViewer.hpp"

PYOSG_DISABLE_WARNINGS

#include <osgGA/TrackballManipulator>
#include <osgViewer/Viewer>

PYOSG_ENABLE_WARNINGS

namespace pyosgViewer {

void bind(py::module_& m) {
	// We LEAVE OUT osgGA::GUIActionAdapter here as a base class...
	py::class_<osgViewer::View, osg::View, osg::ref_ptr<osgViewer::View>>(m, "View")
		.def(py::init<>())
		// .def("addEventHandler", &osgViewer::View::addEventHandler)
		.def("addEventHandler", [](osgViewer::View& self, py::object obj) {
			auto* handler = obj.cast<osgGA::GUIEventHandler*>();

			self.addEventHandler(handler);
		}, py::keep_alive<1, 2>())
		.def("setSceneData", [](osgViewer::View& self, osg::Node* node) {
			self.setSceneData(node);
		}, py::keep_alive<1, 2>())
	;

	py::class_<
		osgViewer::ViewerBase,
		osg::Object,
		osg::ref_ptr<osgViewer::ViewerBase>
	>(m, "ViewerBase")
		.def_property(
			"done",
			&osgViewer::ViewerBase::done,
			&osgViewer::ViewerBase::setDone
		)
		// TODO: So, I'm cheating here... C++ will properly virtually dispatch this upwards to
		// subclasses, but a PYTHON SUBCLASS WON't (without a trampoline).
		.def("realize", &osgViewer::ViewerBase::realize)
		.def_property_readonly("realized", &osgViewer::ViewerBase::isRealized)
		.def("frame", [](osgViewer::ViewerBase& self) {
			py::gil_scoped_release release;

			self.frame();
		})
	;

	py::class_<
		osgViewer::Viewer,
		osgViewer::ViewerBase,
		osgViewer::View,
		osg::ref_ptr<osgViewer::Viewer>
	>(m, "Viewer")
		.def(py::init<>())

		// .def("realize", &osgViewer::Viewer::realize)
		// .def_property_readonly("realized", &osgViewer::Viewer::isRealized)

		// TODO: This is where I put stuff I NEED to call, but haven't wrapped (YET)!
		.def("unwrappedSetup", [](osgViewer::Viewer& self, bool glModern) {
			// self.setUpViewInWindow(1970, 50, 800, 600);
			self.setThreadingModel(osgViewer::Viewer::SingleThreaded);
			self.setCameraManipulator(new osgGA::TrackballManipulator());

			if(glModern) {
				if(auto* state = self.getCamera()->getGraphicsContext()->getState(); state) {
					state->setUseModelViewAndProjectionUniforms(true);
					state->setUseVertexAttributeAliasing(true);
				}
			}
		}, "glModern"_a=false)
		.def("close", [](osgViewer::Viewer& self) {
			if(auto* gc = self.getCamera()->getGraphicsContext(); gc) {
				OSG_WARN << "Calling (Python-only) close!" << std::endl;

				self.setDone(true);

				gc->closeImplementation();
			}
		})
	;
}

}
