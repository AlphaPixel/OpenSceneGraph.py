import osgx

from OpenSceneGraph import osg, osgDB
from OpenSceneGraph.GL import GL_RGBA, GL_UNSIGNED_BYTE

def glsl_simple_path():
	path = osgx.findDataFile("glsl_simple.osgt")

	assert path

	return str(path)

def test_options_and_registry():
	options = osgDB.Options()

	options.optionString = "test-option"

	assert options.optionString == "test-option"
	assert osgDB.Options.CacheHintOptions.CACHE_ALL is not None
	assert osgDB.Options.PrecisionHint.FLOAT_PRECISION_ALL is not None
	assert osgDB.Options.BuildKdTreesHint.NO_PREFERENCE is not None

	registry = osgDB.Registry.instance()

	assert registry is osgDB.Registry.instance()
	assert registry.getReaderWriterForExtension("osgt")

def test_read_node_and_object_file():
	path = glsl_simple_path()

	node = osgDB.readNodeFile(path)
	obj = osgDB.readObjectFile(path)

	assert isinstance(node, osg.Node)
	assert isinstance(obj, osg.Object)

def test_write_and_read_object_file(tmp_path):
	node = osgDB.readNodeFile(glsl_simple_path())
	path = tmp_path / "scene.osgt"

	assert osgDB.writeObjectFile(node, str(path))
	assert isinstance(osgDB.readNodeFile(str(path)), osg.Node)

def test_write_and_read_image_file(tmp_path):
	image = osg.Image()

	image.allocateImage(2, 2, 1, GL_RGBA, GL_UNSIGNED_BYTE)

	path = tmp_path / "image.png"

	assert osgDB.writeImageFile(image, str(path))

	loaded = osgDB.readImageFile(str(path))

	assert (loaded.s, loaded.t, loaded.r) == (2, 2, 1)
	assert loaded.pixelFormat == GL_RGBA
	assert loaded.dataType == GL_UNSIGNED_BYTE
