#pragma once

#include "pyosg.hpp"
#include "osg/callable.hpp"

PYOSG_DISABLE_WARNINGS

#include <osgGA/GUIEventHandler>
#include <osgGA/EventQueue>
#include <osgGA/TrackballManipulator>

PYOSG_ENABLE_WARNINGS

namespace pyosgGA {

void bind(py::module_& m);

namespace detail {
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

		void home(const osgGA::GUIEventAdapter& ea, osgGA::GUIActionAdapter& aa) override {
			PYBIND11_OVERRIDE(void, osgGA::CameraManipulator, home, ea, aa);
		}

		void home(double t) override {
			PYBIND11_OVERRIDE(void, osgGA::CameraManipulator, home, t);
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
			std::cerr << "detail::CameraManipulator::getMatrix" << std::endl;

			PYBIND11_OVERRIDE_PURE(
				osg::Matrixd,
				osgGA::CameraManipulator,
				getMatrix
			);
		}

		osg::Matrixd getInverseMatrix() const override {
			std::cerr << "detail::CameraManipulator::getInverseMatrix" << std::endl;

			PYBIND11_OVERRIDE_PURE(
				osg::Matrixd,
				osgGA::CameraManipulator,
				getInverseMatrix
			);
		}

		void setByMatrix(const osg::Matrixd& mat) override {
			std::cerr << "detail::CameraManipulator::setByMatrix" << std::endl;

			PYBIND11_OVERRIDE_PURE(
				void,
				osgGA::CameraManipulator,
				setByMatrix,
				mat
			);
		}

		void setByInverseMatrix(const osg::Matrixd& mat) override {
			std::cerr << "detail::CameraManipulator::setByInverseMatrix" << std::endl;

			PYBIND11_OVERRIDE_PURE(
				void,
				osgGA::CameraManipulator,
				setByInverseMatrix,
				mat
			);
		}

		/* void computeHomePosition(const osg::Camera* camera=nullptr, bool useBoundingBox=false) {
			PYBIND11_OVERRIDE(void, osgGA::CameraManipulator, setAutoComputeHomePosition, flag);
		} */
	};
}

}
