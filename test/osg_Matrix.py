import math

import pytest

from OpenSceneGraph.osg import Matrix, Matrixd, Matrixf, Vec3d


def assert_matrix_close(actual, expected, abs=1e-6):
	for row in range(4):
		for column in range(4):
			assert actual[row, column] == pytest.approx(expected[row, column], abs=abs)


def test_construction_and_copy_are_independent():
	identity = Matrix()

	assert identity.isIdentity()
	assert identity.valid()
	assert not identity.isNaN()
	assert repr(identity).startswith("Matrix")

	translation = Matrix.translate(1, 2, 3)
	copy = Matrix(translation)
	converted_float = Matrixf(translation)
	converted_double = Matrixd(converted_float)

	translation[3, 0] = 9

	assert copy[3, 0] == 1
	assert converted_float[3, 1] == pytest.approx(2.0)
	assert converted_double[3, 2] == pytest.approx(3.0)


def test_indexing_and_call_access_are_row_major():
	matrix = Matrix(range(16))

	assert matrix[0, 0] == 0
	assert matrix[2, 3] == 11
	assert matrix[-1, -1] == 15
	assert matrix(1, 2) == 6

	matrix[-1, -2] = 123

	assert matrix[3, 2] == 123

	with pytest.raises(IndexError):
		matrix[4, 0]

	with pytest.raises(IndexError):
		matrix[0, -5]


def test_static_and_mutating_factories_match():
	from_static = Matrix.translate(1.5, -2.0, 3.25)
	from_mutating = Matrix()

	from_mutating.makeTranslate(1.5, -2.0, 3.25)

	assert from_static == from_mutating
	assert from_static[3, 0] == pytest.approx(1.5)
	assert from_static[3, 1] == pytest.approx(-2.0)
	assert from_static[3, 2] == pytest.approx(3.25)

	from_static = Matrix.scale(Vec3d(2.0, 3.0, 4.0))
	from_mutating.makeScale(2.0, 3.0, 4.0)

	assert from_static == from_mutating
	assert from_static[0, 0] == pytest.approx(2.0)
	assert from_static[1, 1] == pytest.approx(3.0)
	assert from_static[2, 2] == pytest.approx(4.0)


def test_multiplication_and_in_place_multiplication():
	translation = Matrix.translate(1.0, 2.0, 3.0)
	scale = Matrix.scale(2.0, 3.0, 4.0)
	composed = translation * scale
	in_place = Matrix(translation)

	result = in_place.__imul__(scale)

	assert result is in_place
	assert composed == in_place
	assert translation[3, 0] == pytest.approx(1.0)
	assert composed[3, 0] == pytest.approx(2.0)
	assert composed[3, 1] == pytest.approx(6.0)
	assert composed[3, 2] == pytest.approx(12.0)

	inverse = Matrix.inverse(composed)

	assert_matrix_close(composed * inverse, Matrix.identity())


def test_rotation_decomposition_and_transpose():
	rotation = Matrix.rotate(math.pi / 2.0, Vec3d(0.0, 0.0, 1.0))
	translation = Matrix.translate(4.0, 5.0, 6.0)
	matrix = rotation * translation
	position, orientation, scale, scale_orientation = matrix.decompose()

	assert position == Vec3d(4.0, 5.0, 6.0)
	assert scale == Vec3d(1.0, 1.0, 1.0)
	assert orientation.length() == pytest.approx(1.0)
	assert scale_orientation.length() == pytest.approx(1.0)

	transposed = Matrix()

	assert transposed.transpose(matrix)

	assert transposed[0, 1] == pytest.approx(matrix[1, 0])
	assert transposed[3, 0] == pytest.approx(matrix[0, 3])


def test_projection_and_view_round_trips():
	perspective = Matrix.perspective(60.0, 16.0 / 9.0, 0.1, 100.0)
	fovy, aspect, near, far = perspective.getPerspective()

	assert fovy == pytest.approx(60.0)
	assert aspect == pytest.approx(16.0 / 9.0)
	assert near == pytest.approx(0.1)
	assert far == pytest.approx(100.0)

	eye = Vec3d(1.0, 2.0, 3.0)
	center = Vec3d(1.0, 3.0, 3.0)
	up = Vec3d(0.0, 0.0, 1.0)
	view = Matrix.lookAt(eye, center, up)
	returned_eye, returned_center, returned_up = view.getLookAt()

	assert returned_eye == eye
	assert returned_center == center
	assert returned_up.normalized() == up
