import pytest

from OpenSceneGraph.osg import Image, Texture, Texture2D
from OpenSceneGraph.GL import GL_RGBA, GL_UNSIGNED_BYTE

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

def test_wrap_property_arity():
	# `wrap` accepts a single WrapMode (applied to S/T/R) or a 1-3 element sequence
	# (S[, T[, R]]) -- same parsing the constructor kwarg below goes through.
	t = Texture2D()

	t.wrap = Texture.REPEAT

	assert t.wrap == (Texture.REPEAT, Texture.REPEAT, Texture.REPEAT)

	t.wrap = (Texture.CLAMP_TO_EDGE, Texture.MIRROR)

	assert t.wrap == (Texture.CLAMP_TO_EDGE, Texture.MIRROR, Texture.REPEAT)

	t.wrap = (Texture.CLAMP,)

	assert t.wrap == (Texture.CLAMP, Texture.MIRROR, Texture.REPEAT)

	with pytest.raises(TypeError):
		t.wrap = "bad"

def test_filter_property_mag_strip():
	# A single FilterMode sets MIN directly, but MAG only accepts LINEAR/NEAREST -- the
	# mipmap component gets stripped off automatically.
	t = Texture2D()

	t.filter = Texture.NEAREST_MIPMAP_LINEAR

	assert t.filter == (Texture.NEAREST_MIPMAP_LINEAR, Texture.NEAREST)

	t.filter = Texture.LINEAR_MIPMAP_NEAREST

	assert t.filter == (Texture.LINEAR_MIPMAP_NEAREST, Texture.LINEAR)

	t.filter = (Texture.NEAREST, Texture.LINEAR)

	assert t.filter == (Texture.NEAREST, Texture.LINEAR)

def test_image_property():
	t = Texture2D()
	img = Image()

	img.allocateImage(4, 4, 1, GL_RGBA, GL_UNSIGNED_BYTE)

	t.image = img

	assert t.image is img

	img2 = Image()

	img2.allocateImage(2, 2, 1, GL_RGBA, GL_UNSIGNED_BYTE)

	t.image = (0, img2)

	assert t.image is img2

def test_construction_kwargs():
	# One instance exercising every `kwargs_init_own<osg::Texture>()`/`<osg::Texture2D>()`
	# argument at once -- `wrap`/`filter`/`image` share the exact setter functors used by the
	# properties above, so this is really testing that wiring, not the parsing logic again.
	img = Image()

	img.allocateImage(4, 4, 1, GL_RGBA, GL_UNSIGNED_BYTE)

	t = Texture2D(
		size=(64, 64),
		wrap=Texture.REPEAT,
		filter=(Texture.NEAREST, Texture.LINEAR),
		internalFormat=GL_RGBA,
		sourceFormat=GL_RGBA,
		sourceType=GL_UNSIGNED_BYTE,
		image=img,
		useHardwareMipMapGeneration=False,
		numMipmapLevels=1
	)

	assert t.size == (64, 64)
	assert t.wrap == (Texture.REPEAT, Texture.REPEAT, Texture.REPEAT)
	assert t.filter == (Texture.NEAREST, Texture.LINEAR)
	assert t.internalFormat == GL_RGBA
	assert t.sourceFormat == GL_RGBA
	assert t.sourceType == GL_UNSIGNED_BYTE
	assert t.image is img
	assert t.useHardwareMipMapGeneration == False
	assert t.numMipmapLevels == 1
