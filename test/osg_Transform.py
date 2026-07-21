#vimrun! pytest -sv ../test/osg_Transform.py

from .conftest import refcmp

from OpenSceneGraph.osg import (
	Matrix,
	MatrixTransform,
	PositionAttitudeTransform,
	Transform,
	Vec3d
)

def test_transform_construction_kwargs():
	t = Transform()

	assert t.referenceFrame == Transform.ReferenceFrame.RELATIVE_RF

	t = Transform(referenceFrame=Transform.ReferenceFrame.ABSOLUTE_RF)

	assert t.referenceFrame == Transform.ReferenceFrame.ABSOLUTE_RF
	assert refcmp(t, 1, 1)

def test_matrixtransform_construction():
	m = Matrix.translate(1, 2, 3)

	mt = MatrixTransform(m)

	assert mt.matrix == m

	# `kwargs_ctor<osg::MatrixTransform, const osg::Matrix&>()` -- the leading positional Matrix
	# arg AND kwargs (here, the Object-level `name`) working together in one constructor call.
	mt = MatrixTransform(m, name="mt")

	assert mt.name == "mt"
	assert mt.matrix == m

	mt = MatrixTransform(matrix=m, name="mt2")

	assert mt.name == "mt2"
	assert mt.matrix == m
	assert refcmp(mt, 1, 1)

def test_positionattitudetransform_construction_kwargs():
	pat = PositionAttitudeTransform(
		position=Vec3d(1, 2, 3),
		scale=Vec3d(2, 2, 2),
		pivotPoint=Vec3d(0, 1, 0),
		name="pat"
	)

	assert pat.name == "pat"
	assert pat.position == Vec3d(1, 2, 3)
	assert pat.scale == Vec3d(2, 2, 2)
	assert pat.pivotPoint == Vec3d(0, 1, 0)
	assert refcmp(pat, 1, 1)
