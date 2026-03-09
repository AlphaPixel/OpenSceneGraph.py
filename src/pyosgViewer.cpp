#include "pyosgViewer.hpp"

PYOSG_DISABLE_WARNINGS

#include <osgGA/TrackballManipulator>
#include <osgViewer/Viewer>

PYOSG_ENABLE_WARNINGS

namespace pyosgViewer {

namespace detail {
	class ViewerBase: public osgViewer::ViewerBase {
	public:
		void frame(double simulationTime=USE_REFERENCE_TIME) override {
			PYBIND11_OVERRIDE(void, osgViewer::ViewerBase, frame, simulationTime);
		}

		// void advance(double simulationTime=USE_REFERENCE_TIME) = 0;

		// void eventTraversal() = 0;

		// void updateTraversal() = 0;

		// void renderingTraversals();

		void viewerInit() override {
			PYBIND11_OVERRIDE_PURE(void, osgViewer::ViewerBase, viewerInit);
		}
	};
}

void bind(py::module_& m) {
	py::class_<osgViewer::Scene, osg::Referenced, osg::ref_ptr<osgViewer::Scene>>(m, "Scene")
		.def_property(
			"data",
			py::cpp_function(
				py::overload_cast<>(&osgViewer::Scene::getSceneData),
				py::return_value_policy::reference_internal
			),
			&osgViewer::Scene::setSceneData
		)

		.def("updateSceneGraph", &osgViewer::Scene::updateSceneGraph)

		// virtual bool requiresUpdateSceneGraph() const;
		// virtual bool requiresRedraw() const;
	;

	py::class_<
		osgViewer::GraphicsWindow,
		osg::GraphicsContext,
		// TODO: This (seemingly) MUST be left out of the base classes, as `osgGA::GUIActionAdapter`
		// does NOT support usage with `osg::ref_ptr` (and causes the pybind11 chain to explode).
		// osgGA::GUIActionAdapter,
		osg::ref_ptr<osgViewer::GraphicsWindow>
	>(m, "GraphicsWindow");

	py::class_<
		osgViewer::GraphicsWindowEmbedded,
		osgViewer::GraphicsWindow,
		osg::ref_ptr<osgViewer::GraphicsWindowEmbedded>
	>(m, "GraphicsWindowEmbedded");

	// We LEAVE OUT osgGA::GUIActionAdapter here as a base class...
	py::class_<osgViewer::View, osg::View, osg::ref_ptr<osgViewer::View>>(m, "View")
		.def(py::init<>())

		// TODO: Convert to SequenceProxy!
		.def("addEventHandler", [](osgViewer::View& self, py::object obj) {
			auto* handler = obj.cast<osgGA::GUIEventHandler*>();

			self.addEventHandler(handler);
		}, py::keep_alive<1, 2>())

		/* .def_property(
			"sceneData",
			[](osgViewer::View& self) { return self.getSceneData(); },
			[](osgViewer::View& self, osg::Node* node) { self.setSceneData(node); },
			py::return_value_policy::reference_internal,
			py::keep_alive<1, 2>()
		) */

		.def_property_readonly(
			"scene",
			py::overload_cast<>(&osgViewer::View::getScene),
			py::return_value_policy::reference_internal
		)

		.def_property(
			"sceneData",
			py::cpp_function(
				[](osgViewer::View& self) { return self.getSceneData(); },
				py::return_value_policy::reference_internal
			),
			py::cpp_function(
				[](osgViewer::View& self, osg::Node* node) { self.setSceneData(node); },
				py::keep_alive<1, 2>()
			)
		)

		.def_property(
			"cameraManipulator",
			py::cpp_function(
				[](osgViewer::View& self) { return self.getCameraManipulator(); },
				py::return_value_policy::reference_internal
			),
			py::cpp_function(
				[](
					osgViewer::View& self,
					osgGA::CameraManipulator* manip,
					bool resetPosition
				) { self.setCameraManipulator(manip, resetPosition); },
				py::keep_alive<1, 2>(),
				"self"_a,
				"manip"_a,
				"resetPosition"_a=true
			)
		)

		.def_property(
			"eventQueue",
			py::cpp_function(
				[](osgViewer::View& self) { return self.getEventQueue(); },
				py::return_value_policy::reference_internal
			),
			py::cpp_function(
				[](osgViewer::View& self, osgGA::EventQueue* eq) { self.setEventQueue(eq); },
				py::keep_alive<1, 2>()
			)
		)

		/* .def_property_readonly(
			"eventQueue",
			py::overload_cast<>(&osgViewer::View::getEventQueue),
			py::return_value_policy::reference_internal
		) */
	;

	auto vb = py::class_<
		osgViewer::ViewerBase,
		detail::ViewerBase,
		osg::Object,
		osg::ref_ptr<osgViewer::ViewerBase>
	>(m, "ViewerBase")
		.def("frame", [](osgViewer::ViewerBase& self) {
			py::gil_scoped_release release;

			self.frame();
		})
	;

	py::enum_<osgViewer::ViewerBase::ThreadingModel>(vb, "ThreadingModel")
		.value("SingleThreaded", osgViewer::ViewerBase::SingleThreaded)
		.value("CullDrawThreadPerContext", osgViewer::ViewerBase::CullDrawThreadPerContext)
		.value("ThreadPerContext", osgViewer::ViewerBase::ThreadPerContext)
		.value("DrawThreadPerContext", osgViewer::ViewerBase::DrawThreadPerContext)
		.value(
			"CullThreadPerCameraDrawThreadPerContext",
			osgViewer::ViewerBase::CullThreadPerCameraDrawThreadPerContext
		)
		.value("ThreadPerCamera", osgViewer::ViewerBase::ThreadPerCamera)
		.value("AutomaticSelection", osgViewer::ViewerBase::AutomaticSelection)
	;

	vb
		// TODO: So, I'm cheating here... C++ will properly virtually dispatch this upwards to
		// subclasses, but a PYTHON SUBCLASS WON't (without a trampoline).
		.def("realize", &osgViewer::ViewerBase::realize)
		.def_property_readonly("realized", &osgViewer::ViewerBase::isRealized)
		.def_property(
			"threadingModel",
			&osgViewer::ViewerBase::getThreadingModel,
			&osgViewer::ViewerBase::setThreadingModel
		)
		.def_property(
			"done",
			&osgViewer::ViewerBase::done,
			&osgViewer::ViewerBase::setDone
		)
		/* .def("frame", [](osgViewer::ViewerBase& self) {
			py::gil_scoped_release release;

			self.frame();
		}) */
	;

	py::class_<
		osgViewer::Viewer,
		osgViewer::ViewerBase,
		osgViewer::View,
		osg::ref_ptr<osgViewer::Viewer>
	>(m, "Viewer")
		.def(py::init<>())
		.def(py::init<osg::ArgumentParser&>())

		.def(
			"setUpViewerAsEmbeddedInWindow",
			&osgViewer::Viewer::setUpViewerAsEmbeddedInWindow,
			py::return_value_policy::reference_internal
		)

		// TODO: This is where I put stuff I NEED to call, but haven't wrapped (YET)!
		.def("TODO", [](osgViewer::Viewer& self, bool glModern) {
			// self.setUpViewInWindow(1970, 50, 800, 600);
			// self.setThreadingModel(osgViewer::Viewer::SingleThreaded);
			// self.setCameraManipulator(new osgGA::TrackballManipulator());

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
