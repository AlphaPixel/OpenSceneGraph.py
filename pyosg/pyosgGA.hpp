#pragma once

#include "pyosg.hpp"
#include "osg/callable.hpp"

OSGX_DISABLE_WARNINGS

#include <osgGA/GUIEventHandler>
#include <osgGA/EventVisitor>
#include <osgGA/EventQueue>
#include <osgGA/TrackballManipulator>

OSGX_ENABLE_WARNINGS

#include "pybind11x.hpp"

namespace pyx = pybind11x;

namespace pyosgGA {

void bind(py::module_& m);

namespace detail {
	class GUIActionAdapter: public osgGA::GUIActionAdapter {
	public:
		void requestRedraw() override {
			PYBIND11_OVERRIDE_PURE(void, osgGA::GUIActionAdapter, requestRedraw);
		}

		void requestContinuousUpdate(bool needed=true) override {
			PYBIND11_OVERRIDE_PURE(
				void,
				osgGA::GUIActionAdapter,
				requestContinuousUpdate,
				needed
			);
		}

		void requestWarpPointer(float x, float y) override {
			PYBIND11_OVERRIDE_PURE(void, osgGA::GUIActionAdapter, requestWarpPointer, x, y);
		}
	};

	constexpr size_t NodeSlot = 0;

	using CameraManipulatorSlots = pyx::PropertySlots<osgGA::CameraManipulator, 1>;
	using CameraManipulatorStorage = pyx::ProxyStorageOSG<
		osgGA::CameraManipulator,
		CameraManipulatorSlots
	>;

	class GUIEventHandler: public osgGA::GUIEventHandler {
	public:
		using osgGA::GUIEventHandler::GUIEventHandler;

		bool handle(
			const osgGA::GUIEventAdapter& ea,
			osgGA::GUIActionAdapter& aa,
			osg::Object* obj,
			osg::NodeVisitor* nv
		) override {
			py::gil_scoped_acquire gil;

			auto r = pyosg::detail::call_override<bool>("handle", this, &ea, &aa);

			if(r.has_value()) return *r;

			return osgGA::GUIEventHandler::handle(ea, aa, obj, nv);
		}
	};

#if 0
	class GUIEventHandler: public osgGA::GUIEventHandler {
	public:
		using osgGA::GUIEventHandler::GUIEventHandler;

		bool handle(
			const osgGA::GUIEventAdapter& ea,
			osgGA::GUIActionAdapter& aa
		) override {
			auto r = pyosg::detail::call_override<bool>(
				"handle",
				this,
				&ea,
				&aa
			);

			if(r.has_value()) {
				return *r;
			}

			return osgGA::GUIEventHandler::handle(ea, aa);
		}

		bool handle(
			const osgGA::GUIEventAdapter& ea,
			osgGA::GUIActionAdapter& aa,
			osg::Object* obj,
			osg::NodeVisitor* nv
		) override {
			auto r = pyosg::detail::call_override<bool>(
				"handle",
				this,
				&ea,
				&aa
			);

			if(r.has_value()) {
				return *r;
			}

			return osgGA::GUIEventHandler::handle(ea, aa, obj, nv);
		}
	};
#endif

	class PYOSG_INTERNAL CallableGUIEventHandler: public osgGA::GUIEventHandler {
	public:
		explicit CallableGUIEventHandler(py::object fn): _fn(std::move(fn)) {}

		bool handle(
			const osgGA::GUIEventAdapter& ea,
			osgGA::GUIActionAdapter& aa,
			osg::Object* obj,
			osg::NodeVisitor* nv
		) override {
			py::gil_scoped_acquire gil;

			/* py::object result = _fn(
				py::cast(&ea, py::return_value_policy::reference),
				py::cast(&aa, py::return_value_policy::reference)
			);

			// Match the trampoline semantics above...
			if(!result.is_none() && result.cast<bool>()) {
				return true;
			}

			return osgGA::GUIEventHandler::handle(ea, aa, obj, nv); */

			py::object result = _fn(&ea, &aa);

			if(result.is_none()) return false;

			return result.cast<bool>();
		}

	private:
		py::object _fn;
	};

	class CameraManipulator: public osgGA::CameraManipulator {
	public:
		using osgGA::CameraManipulator::CameraManipulator;

		~CameraManipulator() override {}

		osg::Node* getNode() override {
			PYBIND11_OVERRIDE(osg::Node*, osgGA::CameraManipulator, getNode);
		}

		void setNode(osg::Node* node) override {
			PYBIND11_OVERRIDE(void, osgGA::CameraManipulator, setNode, node);
		}

		void home(const osgGA::GUIEventAdapter& ea, osgGA::GUIActionAdapter& aa) override {
			// PYBIND11_OVERRIDE tries to copy `ea` when marshaling it to a Python override, and
			// GUIEventAdapter (derived from osg::Referenced) isn't copyable -- crashes the instant
			// a Python subclass defines home() and View.setCameraManipulator() calls this (it's the
			// only overload that call site uses). call_override passes by reference instead; see
			// detail::GUIEventHandler::handle above, which takes this exact same (ea, aa) pair.
			if(pyosg::detail::call_override<void>("home", this, &ea, &aa)) return;

			osgGA::CameraManipulator::home(ea, aa);
		}

		void home(double t) override {
			PYBIND11_OVERRIDE(void, osgGA::CameraManipulator, home, t);
		}

		bool handle(const osgGA::GUIEventAdapter& ea, osgGA::GUIActionAdapter& aa) override {
			// BINDING GAP FIX (2026-08-02): like updateCamera() below, this was entirely
			// missing from the trampoline, so REAL C++-side event dispatch never called a
			// Python handle() override at all. osgViewer::Viewer's eventTraversal() reaches
			// this via GUIEventHandler::handle(Event*,Object*,NodeVisitor*) -> the 4-arg
			// handle(ea,aa,obj,nv) -> its default body calling this 2-arg form -- every step
			// along that chain is an unoverridden C++ default until here, and
			// osgGA::CameraManipulator::handle(ea,aa)'s own real implementation
			// (CameraManipulator.cpp) is a literal `return false;`.
			//
			// Confirmed empirically, not just by reading source: a DIRECT Python-side call
			// (`manip.handle(ea, aa)`) looked like it worked and called the Python override
			// -- but that's ordinary Python attribute lookup finding the subclass's method
			// directly on the Python object, completely unrelated to whether a real C++-side
			// virtual call (through this trampoline's vtable) reaches it. That false positive
			// masked this gap. The real test is driving it through an actual `viewer.frame()`
			// with an injected event -- see test/osgGA_CameraManipulator.py.
			//
			// Same non-copyable-argument hazard as home(ea, aa) above -- call_override, not
			// PYBIND11_OVERRIDE.
			if(auto r = pyosg::detail::call_override<bool>("handle", this, &ea, &aa)) return *r;

			return osgGA::CameraManipulator::handle(ea, aa);
		}

		void setAutoComputeHomePosition(bool flag) override {
			PYBIND11_OVERRIDE(void, osgGA::CameraManipulator, setAutoComputeHomePosition, flag);
		}

		void getHomePosition(osg::Vec3d& eye, osg::Vec3d& center, osg::Vec3d& up) const override {
			PYBIND11_OVERRIDE(
				void,
				osgGA::CameraManipulator,
				getHomePosition,
				eye,
				center,
				up
			);
		}

		void setHomePosition(
			const osg::Vec3d& eye,
			const osg::Vec3d& center,
			const osg::Vec3d& up,
			bool autoComputeHomePosition=false
		) override {
			PYBIND11_OVERRIDE(
				void,
				osgGA::CameraManipulator,
				setHomePosition,
				eye,
				center,
				up,
				autoComputeHomePosition
			);
		}

		osg::Matrixd getMatrix() const override {
			// std::cerr << "detail::CameraManipulator::getMatrix" << std::endl;

			PYBIND11_OVERRIDE_PURE(
				osg::Matrixd,
				osgGA::CameraManipulator,
				getMatrix
			);
		}

		osg::Matrixd getInverseMatrix() const override {
			// std::cerr << "detail::CameraManipulator::getInverseMatrix" << std::endl;

			PYBIND11_OVERRIDE_PURE(
				osg::Matrixd,
				osgGA::CameraManipulator,
				getInverseMatrix
			);
		}

		void setByMatrix(const osg::Matrixd& mat) override {
			// std::cerr << "detail::CameraManipulator::setByMatrix" << std::endl;

			PYBIND11_OVERRIDE_PURE(
				void,
				osgGA::CameraManipulator,
				setByMatrix,
				mat
			);
		}

		void setByInverseMatrix(const osg::Matrixd& mat) override {
			// std::cerr << "detail::CameraManipulator::setByInverseMatrix" << std::endl;

			PYBIND11_OVERRIDE_PURE(
				void,
				osgGA::CameraManipulator,
				setByInverseMatrix,
				mat
			);
		}

		void updateCamera(osg::Camera& camera) override {
			// BINDING GAP FIX: this was entirely missing from the trampoline, so a Python
			// override of updateCamera() was silently never called -- osgViewer::Viewer::
			// updateTraversal() always ran the C++ default (camera.setViewMatrix(getInverse
			// Matrix())) instead, no matter what a subclass defined. Same shape as the
			// setNode()/getNode()/home() gaps documented in aipython/05-camera-manipulator.md.
			//
			// Same non-copyable-argument hazard as home(ea, aa) above -- osg::Camera (derived
			// from osg::Referenced) can't be copied, so PYBIND11_OVERRIDE's implicit copy-for-
			// marshaling would crash the instant a Python subclass overrides this. call_override
			// passes by reference instead.
			if(pyosg::detail::call_override<void>("updateCamera", this, &camera)) return;

			osgGA::CameraManipulator::updateCamera(camera);
		}

		void computeHomePosition(const osg::Camera* camera=nullptr, bool useBoundingBox=false) override {
			// BINDING GAP FIX (2026-08-02): this was entirely missing from the trampoline (the
			// one commented-out attempt here had copy-pasted setAutoComputeHomePosition's macro
			// args instead of its own -- dead, wrong code, never actually compiled). Not pure
			// virtual, so PYBIND11_OVERRIDE (not call_override) is correct here -- falls through
			// to the real OSG default (computes eye/center/up from the node's bounding sphere/
			// box) when no Python override exists. `camera` is a pointer, not a by-value/
			// reference non-copyable type, so this doesn't hit the same copy-marshaling hazard
			// home()/updateCamera() did -- same shape as setNode(osg::Node*) just above, which
			// already safely uses plain PYBIND11_OVERRIDE with a pointer argument.
			PYBIND11_OVERRIDE(
				void,
				osgGA::CameraManipulator,
				computeHomePosition,
				camera,
				useBoundingBox
			);
		}
	};
}

}
