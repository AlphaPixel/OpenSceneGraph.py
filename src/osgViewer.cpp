#include "OpenSceneGraph-python.hpp"
#include "osgViewer.hpp"

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

	py::class_<osgViewer::ViewerBase, osg::Object, osg::ref_ptr<osgViewer::ViewerBase>>(m, "ViewerBase")
		// .def("done", &osgViewer::ViewerBase::done)
		.def_property(
			"done",
			&osgViewer::ViewerBase::done,
			&osgViewer::ViewerBase::setDone
		)
		.def("frame", [](osgViewer::ViewerBase& self) {
			py::gil_scoped_release release;

			self.frame();
		})
	;

	py::class_<osgViewer::Viewer, osgViewer::ViewerBase, osgViewer::View, osg::ref_ptr<osgViewer::Viewer>>(m, "Viewer")
		.def(py::init<>())
		// TODO: This is where I put stuff I NEED to call, but haven't wrapped (YET)!
		.def("unwrappedSetup", [](osgViewer::Viewer& self) {
			// self.setUpViewInWindow(1970, 50, 800, 600);
			self.setThreadingModel(osgViewer::Viewer::SingleThreaded);
			self.setCameraManipulator(new osgGA::TrackballManipulator());
		})
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
