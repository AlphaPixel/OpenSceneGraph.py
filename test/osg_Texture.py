#vimrun! pytest -v ../test/osg_Texture.py

from .conftest import f32, floatif, refcmp

from OpenSceneGraph.osg import Texture, Texture2D

def test_construction():
	t = Texture2D()

	assert t.size == (0, 0)

	t = Texture2D(256, 256)

	assert t.size == (256, 256)

def test_inheritance():
	# TODO: Test pure virtual methods from trampoline!
	class MyTexture(Texture2D):
		pass

	t = MyTexture()

def test_properties():
	t = Texture2D(256, 256)

	assert t.wrap == tuple([Texture.CLAMP] * 3)
	assert t.filter == (Texture.LINEAR_MIPMAP_LINEAR, Texture.LINEAR)
	assert t.internalFormat == 0
	assert t.internalFormatMode == Texture.USE_IMAGE_DATA_FORMAT
	assert t.internalFormatType == Texture.NORMALIZED
	assert t.sourceFormat == 0
	assert t.sourceType == 0
	assert t.anisotropy == 1.0
