from OpenSceneGraph.osg import BindImageTexture, BlendEquation, StateAttribute, Texture2D
from OpenSceneGraph.GL import GL_R8, GL_RGBA8

def test_bindimagetexture_defaults():
	b = BindImageTexture()

	assert isinstance(b, StateAttribute)
	assert b.imageUnit == 0
	assert b.texture is None
	assert b.access == BindImageTexture.READ_ONLY
	assert b.format == GL_RGBA8
	assert b.level == 0
	assert b.layered == False
	assert b.layer == 0

def test_bindimagetexture_properties():
	t = Texture2D(16, 16)
	b = BindImageTexture(3, t, BindImageTexture.WRITE_ONLY, GL_R8, level=1)

	assert b.imageUnit == 3
	assert b.texture is t
	assert b.access == BindImageTexture.Access.WRITE_ONLY
	assert b.format == GL_R8
	assert b.level == 1

	b.access = BindImageTexture.READ_WRITE
	b.layered = True
	b.layer = 2
	b.texture = None

	assert b.access == BindImageTexture.READ_WRITE
	assert b.layered == True
	assert b.layer == 2
	assert b.texture is None

def test_blendequation_defaults():
	b = BlendEquation()

	assert isinstance(b, StateAttribute)
	assert b.equationRGB == BlendEquation.FUNC_ADD
	assert b.equationAlpha == BlendEquation.FUNC_ADD

def test_blendequation_properties():
	b = BlendEquation(BlendEquation.RGBA_MIN)

	assert b.equation == BlendEquation.Equation.RGBA_MIN
	assert b.equationAlpha == BlendEquation.RGBA_MIN

	b = BlendEquation(BlendEquation.RGBA_MAX, BlendEquation.FUNC_ADD)

	assert b.equationRGB == BlendEquation.RGBA_MAX
	assert b.equationAlpha == BlendEquation.FUNC_ADD

	b.equation = BlendEquation.FUNC_SUBTRACT

	assert b.equationRGB == BlendEquation.FUNC_SUBTRACT
	assert b.equationAlpha == BlendEquation.FUNC_SUBTRACT

	b.equationAlpha = BlendEquation.RGBA_MIN

	assert b.equationRGB == BlendEquation.FUNC_SUBTRACT
	assert b.equationAlpha == BlendEquation.RGBA_MIN
