#include "Transform.hpp"
// TODO: We include the following file ONLY BECAUSE we need the `MAKE_OPAQUE` call in the same
// source file where it's actually USED. :/ There are ways around this we can add to pybind11x.hpp
// at some time in the future.
#include "NodeVisitor.hpp"

namespace pybind11x {
	template<>
	void kwargs_init_own(osg::Transform& self, const py::kwargs& kwargs) {
		if(kwargs.contains("referenceFrame")) self.setReferenceFrame(
			kwargs["referenceFrame"].cast<osg::Transform::ReferenceFrame>()
		);
	}

	template<>
	void kwargs_init_own(osg::MatrixTransform& self, const py::kwargs& kwargs) {
		if(kwargs.contains("matrix")) self.setMatrix(kwargs["matrix"].cast<osg::Matrix>());
	}

	template<>
	void kwargs_init_own(osg::PositionAttitudeTransform& self, const py::kwargs& kwargs) {
		// `setPosition`/`setScale`/`setPivotPoint` all take `const osg::Vec3d&` explicitly (not
		// the generic `osg::Vec3` = `Vec3f` alias) -- matching that here, not just what happens
		// to compile, since `.position`/`.scale`/`.pivotPoint` getters return `Vec3d` too and a
		// `Vec3f` cast silently truncates precision instead of matching them.
		if(kwargs.contains("position")) self.setPosition(kwargs["position"].cast<osg::Vec3d>());
		if(kwargs.contains("scale")) self.setScale(kwargs["scale"].cast<osg::Vec3d>());
		if(kwargs.contains("pivotPoint")) self.setPivotPoint(kwargs["pivotPoint"].cast<osg::Vec3d>());
	}
}

namespace pyosg {

void bind_Transform(py::module_& m) {
	auto transform = py::class_<
		osg::Transform,
		osg::Group,
		osg::ref_ptr<osg::Transform>
	>(m, "Transform",
		"Base class for a Group that concatenates a matrix into the model-view transform seen "
		"by its subgraph; see MatrixTransform and PositionAttitudeTransform for the two "
		"concrete forms."
	)
		.def(py::init<>(), "Create a Transform with an identity matrix.")
		.def(py::init(pyx::kwargs_ctor<osg::Transform>()),
			"Create a Transform, optionally setting referenceFrame via keyword arguments."
		)
	;

	py::enum_<osg::Transform::ReferenceFrame>(transform, "ReferenceFrame",
		"Whether a Transform concatenates onto its parent's coordinate frame (RELATIVE_RF, "
		"the default) or resets to the identity/eye-space frame (ABSOLUTE_RF / "
		"ABSOLUTE_RF_INHERIT_VIEWPOINT)."
	)
		.value("RELATIVE_RF", osg::Transform::RELATIVE_RF)
		.value("ABSOLUTE_RF", osg::Transform::ABSOLUTE_RF)
		.value("ABSOLUTE_RF_INHERIT_VIEWPOINT", osg::Transform::ABSOLUTE_RF_INHERIT_VIEWPOINT)
		.export_values()
	;

	py::class_<
		osg::MatrixTransform,
		osg::Transform,
		osg::ref_ptr<osg::MatrixTransform>
	>(m, "MatrixTransform",
		"A Transform whose matrix is a plain osg.Matrix set directly, rather than derived "
		"from position/attitude/scale components."
	)
		.def(py::init<>(), "Create a MatrixTransform with an identity matrix.")
		.def(py::init<const osg::Matrix&>(), "Create a MatrixTransform with the given matrix.")
		.def(py::init<const osg::MatrixTransform&>(), "Create a shallow copy of another MatrixTransform.")
		.def(py::init(pyx::kwargs_ctor<osg::MatrixTransform>()),
			"Create a MatrixTransform, optionally setting matrix via keyword arguments."
		)
		.def(py::init(pyx::kwargs_ctor<osg::MatrixTransform, const osg::Matrix&>()),
			"Create a MatrixTransform from an initial matrix, optionally overriding it (or "
			"other properties) via keyword arguments."
		)
		.def_property(
			"matrix",
			py::cpp_function(
				&osg::MatrixTransform::getMatrix,
				py::return_value_policy::reference_internal
			),
			&osg::MatrixTransform::setMatrix,
			"Live reference to the transform's native matrix. "
			"Use osg.Matrix(transform.matrix) when retaining a value snapshot."
		)
	;

	py::class_<
		osg::PositionAttitudeTransform,
		osg::Transform,
		osg::ref_ptr<osg::PositionAttitudeTransform>
	>(m, "PositionAttitudeTransform",
		"A Transform whose matrix is composed each frame from separate position/attitude/"
		"scale/pivot components; easier to animate piecewise than MatrixTransform's raw matrix."
	)
		.def(py::init<>(), "Create a PositionAttitudeTransform at the identity (origin, no rotation, unit scale).")
		.def(py::init<const osg::PositionAttitudeTransform&>(),
			"Create a shallow copy of another PositionAttitudeTransform."
		)
		.def(py::init(pyx::kwargs_ctor<osg::PositionAttitudeTransform>()),
			"Create a PositionAttitudeTransform, optionally setting position/scale/pivotPoint "
			"via keyword arguments."
		)
		.def_property(
			"position",
			&osg::PositionAttitudeTransform::getPosition,
			&osg::PositionAttitudeTransform::setPosition,
			"World-space (or parent-relative, under RELATIVE_RF) translation, as a Vec3d."
		)
		// TODO: Implement `osg::Quat` wrapper!
		/* .def_property(
			"attitude",
			&osg::PositionAttitudeTransform::getAttitude,
			&osg::PositionAttitudeTransform::setAttitude
		) */
		.def_property(
			"scale",
			&osg::PositionAttitudeTransform::getScale,
			&osg::PositionAttitudeTransform::setScale,
			"Per-axis scale factor applied about pivotPoint, as a Vec3d."
		)
		.def_property(
			"pivotPoint",
			&osg::PositionAttitudeTransform::getPivotPoint,
			&osg::PositionAttitudeTransform::setPivotPoint,
			"Point (in the node's own local space) that scale and attitude are applied about, "
			"as a Vec3d."
		)
	;

	transform
		.def_property(
			"referenceFrame",
			&osg::Transform::getReferenceFrame,
			&osg::Transform::setReferenceFrame,
			"Whether this Transform's matrix is RELATIVE_RF to its parent or resets to "
			"ABSOLUTE_RF / ABSOLUTE_RF_INHERIT_VIEWPOINT."
		)
		.def(
			"asMatrixTransform",
			py::overload_cast<>(&osg::Transform::asMatrixTransform),
			py::return_value_policy::reference_internal,
			"Return this Transform as a MatrixTransform if it is one, else None."
		)
		.def(
			"asPositionAttitudeTransform",
			py::overload_cast<>(&osg::Transform::asPositionAttitudeTransform),
			py::return_value_policy::reference_internal,
			"Return this Transform as a PositionAttitudeTransform if it is one, else None."
		)
	;

	m
		.def("computeLocalToWorld", &osg::computeLocalToWorld,
			"nodePath"_a,
			"ignoreCameras"_a=true,
			"Concatenate every Transform along a NodePath into a single local-to-world matrix."
		)
		.def("computeWorldToLocal", &osg::computeWorldToLocal,
			"nodePath"_a,
			"ignoreCameras"_a=true,
			"Concatenate every Transform along a NodePath into a single world-to-local matrix "
			"(the inverse of computeLocalToWorld)."
		)
		.def("computeLocalToEye", &osg::computeLocalToEye,
			"modelview"_a,
			"nodePath"_a,
			"ignoreCameras"_a=true,
			"Compute the local-to-eye matrix for a NodePath given a starting modelview matrix."
		)
		.def("computeEyeToLocal", &osg::computeEyeToLocal,
			"modelview"_a,
			"nodePath"_a,
			"ignoreCameras"_a=true,
			"Compute the eye-to-local matrix for a NodePath given a starting modelview matrix "
			"(the inverse of computeLocalToEye)."
		)
	;
}

}
