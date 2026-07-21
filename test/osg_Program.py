import pytest

from OpenSceneGraph.osg import Program, Shader


def assert_binding_mapping(mapping, first, second):
	mapping[first] = 0
	mapping[second] = 1

	assert mapping[first] == 0
	assert mapping[second] == 1
	assert first in mapping
	assert "missing" not in mapping
	assert len(mapping) == 2

	expected_items = sorted([(first, 0), (second, 1)])

	assert mapping.keys() == [key for key, _ in expected_items]
	assert mapping.values() == [value for _, value in expected_items]
	assert mapping.items() == expected_items
	assert list(mapping) == [key for key, _ in expected_items]

	del mapping[first]

	assert first not in mapping
	assert mapping.keys() == [second]

	with pytest.raises(KeyError):
		mapping[first]


def test_construction_kwargs():
	shader = Shader(Shader.VERTEX)

	program = Program(shaders=(shader,))

	assert len(program.shaders) == 1
	assert program.shaders[0] is shader

def test_program_binding_location_mappings():
	program = Program()

	assert not hasattr(program, "addBindAttribLocation")

	assert_binding_mapping(program.bindAttribLocation, "position", "normal")
	assert_binding_mapping(program.bindFragDataLocation, "fragColor", "brightColor")
	assert_binding_mapping(program.bindUniformBlock, "Camera", "Lights")


def test_program_storage_keeps_shaders_and_binding_maps_together():
	program = Program()
	shader = Shader(Shader.VERTEX)

	program.shaders.append(shader)
	program.bindAttribLocation["position"] = 0

	assert program.shaders[0] is shader
	assert program.bindAttribLocation["position"] == 0
	assert program.shaders is program.shaders
	assert program.bindAttribLocation is program.bindAttribLocation
