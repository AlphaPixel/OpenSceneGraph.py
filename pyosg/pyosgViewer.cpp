#include "pyosgViewer.hpp"
#include "pyosgGA.hpp"

#include "osg/ArgumentParser.hpp"

OSGX_DISABLE_WARNINGS

#include <osgGA/TrackballManipulator>
#include <osgViewer/Viewer>
#include <osgViewer/ViewerEventHandlers>

OSGX_ENABLE_WARNINGS

#include "pybind11x.hpp"

namespace pyx = pybind11x;

template<>
struct pyx::SequenceTraits<osgViewer::View> {
	using element_type = osgGA::GUIEventHandler;
	using value_type = osgGA::GUIEventHandler*;

	using list_type = osgViewer::View::EventHandlers;
	using iterator = list_type::iterator;

	/* static value_type from_python(py::handle h) {
		if(h.is_none()) {
			throw py::type_error("EventHandler cannot be None");
		}

		return h.cast<value_type>();
	} */

	static value_type from_python(py::handle h) {
		if(h.is_none()) {
			throw py::type_error("EventHandler cannot be None");
		}

		if(py::isinstance<osgGA::GUIEventHandler>(h)) {
			return h.cast<osgGA::GUIEventHandler*>();
		}

		if(PyCallable_Check(h.ptr())) {
			return new pyosgGA::detail::CallableGUIEventHandler(
				py::reinterpret_borrow<py::object>(h)
			);
		}

		throw py::type_error("Expected osgGA.GUIEventHandler or callable");
	}

	static size_t size(const osgViewer::View* v) {
		return v->getEventHandlers().size();
	}

	static iterator nth(osgViewer::View* v, size_t i) {
		auto& ehs = v->getEventHandlers();

		if(i >= ehs.size()) {
			throw py::index_error("event handler index out of range");
		}

		auto it = ehs.begin();

		std::advance(it, static_cast<list_type::difference_type>(i));

		return it;
	}

	static element_type* get(osgViewer::View* v, size_t i) {
		auto* eh = nth(v, i)->get();
		auto* gui = dynamic_cast<osgGA::GUIEventHandler*>(eh);

		if(!gui) {
			throw py::type_error(
				"View event handler is not an osgGA::GUIEventHandler; "
				"osgGA::EventHandler is not registered in Python"
			);
		}

		return gui;
	}

	static void set(osgViewer::View* v, size_t i, value_type eh) {
		if(!eh) {
			throw py::type_error("EventHandler cannot be None");
		}

		auto it = nth(v, i);

		*it = eh;
	}

	static void del(osgViewer::View* v, size_t i) {
		auto& ehs = v->getEventHandlers();
		auto it = nth(v, i);

		ehs.erase(it);
	}

	static void append(osgViewer::View* v, value_type eh) {
		if(!eh) {
			throw py::type_error("EventHandler cannot be None");
		}

		v->addEventHandler(eh);
	}

	// std::list::insert(), so this is the actual native primitive the original
	// eventHandlers.insert(0, handler) request wanted -- not an append()/del() emulation.
	// Unlike nth() above, `i == size()` (insert-at-end) is a valid, in-range request here,
	// so this walks to ehs.end() itself instead of reusing nth()'s stricter bounds check.
	static void insert(osgViewer::View* v, size_t i, value_type eh) {
		if(!eh) {
			throw py::type_error("EventHandler cannot be None");
		}

		auto& ehs = v->getEventHandlers();
		auto it = ehs.begin();

		std::advance(it, static_cast<list_type::difference_type>(i));

		ehs.insert(it, eh);
	}
};

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

	using EventHandlersProxy = pyx::SequenceProxy<osgViewer::View>;

	constexpr size_t SceneDataSlot = 0;
	constexpr size_t CameraManipulatorSlot = 1;
	constexpr size_t EventQueueSlot = 2;

	using ViewSlots = pyx::PropertySlots<osgViewer::View, 3>;
	using ViewStorage = pyx::ProxyStorageOSG<osgViewer::View, EventHandlersProxy, ViewSlots>;

	// setCameraManipulator() takes a second `resetPosition` argument that plain attribute
	// assignment can't supply directly (`obj.attr = value` only ever passes one value) -
	// matching the (eye, center, up) tuple convention `CameraManipulator.homePosition`
	// already uses (pyosgGA.cpp), accept either a bare manipulator (resetPosition=True) or a
	// (manip, resetPosition) pair:
	//
	// view.cameraManipulator = manip
	// view.cameraManipulator = (manip, False)
	auto view_camera_manipulator_setter() {
		return [](osgViewer::View& self, py::object obj) {
			py::object manip_obj = obj;
			bool resetPosition = true;

			if(auto vals = pyx::try_unpack_sequence<py::object, bool>(obj)) {
				manip_obj = std::get<0>(*vals);
				resetPosition = std::get<1>(*vals);
			}

			else if(!obj.is_none() && !py::isinstance<osgGA::CameraManipulator>(obj)) throw py::type_error(
				"Expected CameraManipulator, None, or (manip, resetPosition) pair"
			);

			auto* manip = manip_obj.is_none() ? nullptr : manip_obj.cast<osgGA::CameraManipulator*>();

			self.setCameraManipulator(manip, resetPosition);

			auto& slots = ViewStorage::get(self)->template proxy<ViewSlots>();

			slots.set(CameraManipulatorSlot, manip_obj, manip);
		};
	}

	constexpr size_t RealizeOperationSlot = 0;

	using ViewerBaseSlots = pyx::PropertySlots<osgViewer::ViewerBase, 1>;
	using ViewerBaseStorage = pyx::ProxyStorageOSG<osgViewer::ViewerBase, ViewerBaseSlots>;
}

void bind(py::module_& m) {
	py::class_<osgViewer::Scene, osg::Referenced, osg::ref_ptr<osgViewer::Scene>>(m, "Scene")
		// NOT a straightforward PropertySlot conversion like the ones just done for
		// osgViewer::View: pyx::ProxyStorageOSG needs getOrCreateUserDataContainer(), an
		// osg::Object method, but osgViewer::Scene derives from osg::Referenced only. Needs a
		// new ref_ptr-backed ProxyStorage variant first (ProxyStorageShared exists but is
		// shared_ptr-based, doesn't fit). No keep_alive here currently either, so this is an
		// identity-stability gap, not a lifetime leak: Scene holds its own ref_ptr<Node>
		// internally, so the C++ side already keeps sceneData alive independent of Python.
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
	>(m, "GraphicsWindow")
		// setWindowName's base implementation is a no-op (just an OSG_NOTICE) on backends that
		// don't have a native window at all (GraphicsWindowEmbedded, offscreen pbuffers); real
		// windowed backends (X11 confirmed) override it to actually retitle the OS window.
		.def_property(
			"windowName",
			&osgViewer::GraphicsWindow::getWindowName,
			&osgViewer::GraphicsWindow::setWindowName
		)
	;

	py::class_<
		osgViewer::GraphicsWindowEmbedded,
		osgViewer::GraphicsWindow,
		osg::ref_ptr<osgViewer::GraphicsWindowEmbedded>
	>(m, "GraphicsWindowEmbedded");

	// osgGA::GUIActionAdapter is deliberately LEFT OUT of the base classes here! It doesn't use
	// a `ref_ptr` as a "holder", and pybind can't "mix" them!
	auto view = py::class_<osgViewer::View, osg::View, osg::ref_ptr<osgViewer::View>>(m, "View");

	pyx::bind_proxy_property<detail::EventHandlersProxy, osgViewer::View, detail::ViewStorage>(
		view, "_EventHandlers", "eventHandlers"
	);

	view
		.def(py::init<>())

		// No addEventHandler() method binding - use `.eventHandlers.append(handler)` above
		// instead (same removal as Geometry.addPrimitiveSet -> `.primitiveSets.append(...)`).
		// Also a strict capability upgrade, not just a rename: EventHandlersProxy's from_python
		// already accepts a plain Python callable (wrapping it in CallableGUIEventHandler), which
		// this method's raw `.cast<GUIEventHandler*>()` never did.
		.def_property_readonly(
			"scene",
			py::overload_cast<>(&osgViewer::View::getScene),
			py::return_value_policy::reference_internal
		)

		.def_property(
			"sceneData",
			detail::ViewSlots::getter<detail::SceneDataSlot>(
				static_cast<osg::Node*(osgViewer::View::*)()>(&osgViewer::View::getSceneData)
			),
			detail::ViewSlots::setter<detail::SceneDataSlot, osg::Node*>(
				static_cast<void(osgViewer::View::*)(osg::Node*)>(&osgViewer::View::setSceneData)
			)
		)

		.def_property(
			"cameraManipulator",
			detail::ViewSlots::getter<detail::CameraManipulatorSlot>(
				static_cast<osgGA::CameraManipulator*(osgViewer::View::*)()>(
					&osgViewer::View::getCameraManipulator
				)
			),
			detail::view_camera_manipulator_setter()
		)

		.def_property(
			"eventQueue",
			detail::ViewSlots::getter<detail::EventQueueSlot>(
				static_cast<osgGA::EventQueue*(osgViewer::View::*)()>(&osgViewer::View::getEventQueue)
			),
			detail::ViewSlots::setter<detail::EventQueueSlot, osgGA::EventQueue*>(
				static_cast<void(osgViewer::View::*)(osgGA::EventQueue*)>(
					&osgViewer::View::setEventQueue
				)
			)
		)
	;

	auto vb = py::class_<
		osgViewer::ViewerBase,
		detail::ViewerBase,
		osg::Object,
		osg::ref_ptr<osgViewer::ViewerBase>
	>(m, "ViewerBase")
		// .def(py::init_alias<>())
		.def("frame", [](osgViewer::ViewerBase& self) {
			// Only release the GIL for genuinely multi-threaded models (real OSG cull/draw
			// threads that would otherwise contend with Python for no reason). Under
			// SingleThreaded (this project's standing default - see CLAUDE.md/examples),
			// there is no concurrency benefit to releasing it, only a hazard: OSG defers
			// actual GL-object teardown (dropping the last ref_ptr on an old Program/Uniform/
			// etc.) to a flush pass that can run *inside* this call, and if that drop is the
			// last reference to a pybind11-tracked object, its destructor needs the GIL to
			// deregister the Python wrapper - which isn't held, aborting the process
			// (confirmed via a minimal repro: attach a scene with a Program+Uniform, replace
			// it with a second one, keep calling frame()-- reliably crashes without this).
			if(self.getThreadingModel() == osgViewer::ViewerBase::SingleThreaded) {
				self.frame();
			}

			else {
				py::gil_scoped_release release;

				self.frame();
			}
		})

		.def_property(
			"realizeOperation",
			detail::ViewerBaseSlots::getter<detail::RealizeOperationSlot>(
				&osgViewer::ViewerBase::getRealizeOperation
			),
			detail::ViewerBaseSlots::setter<detail::RealizeOperationSlot, osg::Operation*>(
				&osgViewer::ViewerBase::setRealizeOperation
			)
		)
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
		// .def(py::init<osg::ArgumentParser&>())
		.def(py::init([](pyosg::detail::ArgumentParser& args) {
			return new osgViewer::Viewer(args.parser);
		}))

		.def(
			"setUpViewerAsEmbeddedInWindow",
			&osgViewer::Viewer::setUpViewerAsEmbeddedInWindow,
			py::return_value_policy::reference_internal
		)
		.def(
			"setUpViewInWindow",
			&osgViewer::Viewer::setUpViewInWindow,
			"x"_a,
			"y"_a,
			"width"_a,
			"height"_a,
			"screenNum"_a=0
		)

		// TODO: This is where I put stuff I NEED to call, but haven't wrapped (YET)!
		.def("TODO", [](osgViewer::Viewer& self, bool glModern) {
			// self.setThreadingModel(osgViewer::Viewer::SingleThreaded);
			// self.setCameraManipulator(new osgGA::TrackballManipulator());
			self.addEventHandler(new osgViewer::StatsHandler());

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
