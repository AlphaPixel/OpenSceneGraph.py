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

	assert mapping.get(second) == 1
	assert mapping.get("nonexistent") is None
	assert mapping.get("nonexistent", -1) == -1

	assert mapping.pop(second) == 1
	assert len(mapping) == 0

	with pytest.raises(KeyError):
		mapping.pop(second)

	assert mapping.pop(second, -1) == -1

	mapping[first] = 0
	mapping[second] = 1

	mapping.clear()

	assert len(mapping) == 0

	mapping[first] = 5

	# already present -- returns the existing value, unchanged
	assert mapping.setdefault(first, 999) == 5

	# absent -- sets it, then returns the (now-existing) value
	assert mapping.setdefault(second, 7) == 7
	assert mapping[second] == 7

	mapping.clear()


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


def test_shaders_insert():
	# Program has no native insert-at-position primitive either (only addShader/removeShader),
	# so this is the same emulation fallback as Geode.drawables.
	program = Program()
	s0 = Shader(Shader.VERTEX)
	s1 = Shader(Shader.FRAGMENT)
	s2 = Shader(Shader.GEOMETRY)

	program.shaders.extend((s0, s2))
	program.shaders.insert(1, s1)

	assert list(program.shaders) == [s0, s1, s2]
	assert program.shaders[0] is s0
	assert program.shaders[2] is s2

def test_shaders_pop_and_clear():
	program = Program()
	s0 = Shader(Shader.VERTEX)
	s1 = Shader(Shader.FRAGMENT)

	program.shaders.extend((s0, s1))

	assert program.shaders.pop() is s1
	assert len(program.shaders) == 1

	program.shaders.append(s1)

	assert program.shaders.pop(0) is s0
	assert len(program.shaders) == 1
	assert program.shaders[0] is s1

	program.shaders.clear()

	assert len(program.shaders) == 0


def test_program_storage_keeps_shaders_and_binding_maps_together():
	program = Program()
	shader = Shader(Shader.VERTEX)

	program.shaders.append(shader)
	program.bindAttribLocation["position"] = 0

	assert program.shaders[0] is shader
	assert program.bindAttribLocation["position"] == 0
	assert program.shaders is program.shaders
	assert program.bindAttribLocation is program.bindAttribLocation
