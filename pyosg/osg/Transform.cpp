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

	template<>
	void kwargs_init_own(osg::AutoTransform& self, const py::kwargs& kwargs) {
		// Same Vec3d-explicit reasoning as PositionAttitudeTransform above: position/scale/
		// pivotPoint all getter/setter as Vec3d, not the Vec3f-aliased osg::Vec3.
		if(kwargs.contains("position")) self.setPosition(kwargs["position"].cast<osg::Vec3d>());
		if(kwargs.contains("scale")) self.setScale(kwargs["scale"].cast<osg::Vec3d>());
		if(kwargs.contains("pivotPoint")) self.setPivotPoint(kwargs["pivotPoint"].cast<osg::Vec3d>());
		if(kwargs.contains("autoRotateMode")) self.setAutoRotateMode(
			kwargs["autoRotateMode"].cast<osg::AutoTransform::AutoRotateMode>()
		);
		if(kwargs.contains("autoScaleToScreen")) self.setAutoScaleToScreen(
			kwargs["autoScaleToScreen"].cast<bool>()
		);
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
		.def(
			"asAutoTransform",
			py::overload_cast<>(&osg::Transform::asAutoTransform),
			py::return_value_policy::reference_internal,
			"Return this Transform as an AutoTransform if it is one, else None."
		)
	;

	auto autoTransform = py::class_<
		osg::AutoTransform,
		osg::Transform,
		osg::ref_ptr<osg::AutoTransform>
	>(m, "AutoTransform",
		"A Transform that automatically scales and/or rotates each frame to keep its children "
		"aligned with screen coordinates -- e.g. billboards, or text/HUD geometry that should "
		"stay a constant pixel size regardless of camera distance."
	)
		.def(py::init<>(), "Create an AutoTransform at the identity, with auto-scale/rotate off.")
		.def(py::init<const osg::AutoTransform&>(), "Create a shallow copy of another AutoTransform.")
		.def(py::init(pyx::kwargs_ctor<osg::AutoTransform>()),
			"Create an AutoTransform, optionally setting position/scale/pivotPoint/"
			"autoRotateMode/autoScaleToScreen via keyword arguments."
		)
		.def_property(
			"position",
			&osg::AutoTransform::getPosition,
			&osg::AutoTransform::setPosition,
			"World-space (or parent-relative, under RELATIVE_RF) translation, as a Vec3d."
		)
		// TODO: Implement `osg::Quat` wrapper! (see PositionAttitudeTransform.attitude's same TODO)
		/* .def_property(
			"rotation",
			&osg::AutoTransform::getRotation,
			&osg::AutoTransform::setRotation
		) */
		.def_property(
			"scale",
			&osg::AutoTransform::getScale,
			py::overload_cast<const osg::Vec3d&>(&osg::AutoTransform::setScale),
			"Per-axis scale factor applied about pivotPoint, as a Vec3d. Recomputed automatically "
			"each frame while autoScaleToScreen is True."
		)
		.def_property(
			"minimumScale",
			&osg::AutoTransform::getMinimumScale,
			&osg::AutoTransform::setMinimumScale,
			"Lower clamp on the auto-computed scale."
		)
		.def_property(
			"maximumScale",
			&osg::AutoTransform::getMaximumScale,
			&osg::AutoTransform::setMaximumScale,
			"Upper clamp on the auto-computed scale."
		)
		.def_property(
			"pivotPoint",
			&osg::AutoTransform::getPivotPoint,
			&osg::AutoTransform::setPivotPoint,
			"Point (in the node's own local space) that scale and rotation are applied about, "
			"as a Vec3d."
		)
		.def_property(
			"autoUpdateEyeMovementTolerance",
			&osg::AutoTransform::getAutoUpdateEyeMovementTolerance,
			&osg::AutoTransform::setAutoUpdateEyeMovementTolerance,
			"Eye-movement threshold below which the cached transform is reused instead of "
			"recomputed; 0 recomputes every frame."
		)
		.def_property(
			"autoRotateMode",
			&osg::AutoTransform::getAutoRotateMode,
			&osg::AutoTransform::setAutoRotateMode,
			"Whether/how this node rotates to face the screen, camera, or a fixed axis."
		)
		.def_property(
			"axis",
			&osg::AutoTransform::getAxis,
			&osg::AutoTransform::setAxis,
			"Rotation axis used when autoRotateMode == ROTATE_TO_AXIS."
		)
		.def_property(
			"normal",
			&osg::AutoTransform::getNormal,
			&osg::AutoTransform::setNormal,
			"Front-face direction of the child nodes when unrotated."
		)
		.def_property(
			"autoScaleToScreen",
			&osg::AutoTransform::getAutoScaleToScreen,
			&osg::AutoTransform::setAutoScaleToScreen,
			"When True, scale is recomputed each frame to keep children a constant pixel size."
		)
		.def_property(
			"autoScaleTransitionWidthRatio",
			&osg::AutoTransform::getAutoScaleTransitionWidthRatio,
			&osg::AutoTransform::setAutoScaleTransitionWidthRatio,
			"Width (as a ratio of the minimum/maximum scale transition) over which scale clamping "
			"is smoothed rather than hard-clamped."
		)
	;

	py::enum_<osg::AutoTransform::AutoRotateMode>(autoTransform, "AutoRotateMode",
		"Selects how an AutoTransform rotates its children to face the viewer."
	)
		.value("NO_ROTATION", osg::AutoTransform::NO_ROTATION)
		.value("ROTATE_TO_SCREEN", osg::AutoTransform::ROTATE_TO_SCREEN)
		.value("ROTATE_TO_CAMERA", osg::AutoTransform::ROTATE_TO_CAMERA)
		.value("ROTATE_TO_AXIS", osg::AutoTransform::ROTATE_TO_AXIS)
		.export_values()
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
