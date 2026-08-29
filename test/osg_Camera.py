from .conftest import refcmp

from OpenSceneGraph.osg import Camera, Matrixd, Transform, Vec4, Viewport
from OpenSceneGraph.GL import GL_COLOR_BUFFER_BIT

def test_construction_defaults():
	c = Camera()

	assert c.allowEventFocus == True
	assert c.nearFarRatio == 0.0005
	assert c.renderOrder == Camera.RenderOrder.POST_RENDER
	assert c.referenceFrame == Transform.ReferenceFrame.RELATIVE_RF
	assert refcmp(c, 1, 1)

def test_construction_kwargs():
	# One instance exercising every plain (non-callback) `kwargs_init_own<osg::Camera>()`
	# argument at once -- `viewport`/`renderOrder`/`renderTargetImplementation` share the exact
	# setter functors used by the identically-named properties below, so this also confirms that
	# wiring, not just the parsing logic in isolation.
	c = Camera(
		name="cam",
		clearColor=Vec4(0.1, 0.2, 0.3, 1.0),
		clearMask=GL_COLOR_BUFFER_BIT,
		allowEventFocus=False,
		computeNearFarMode=Camera.ComputeNearFarMode.DO_NOT_COMPUTE_NEAR_FAR,
		nearFarRatio=0.001,
		viewport=(0, 0, 800, 600),
		renderOrder=(Camera.RenderOrder.PRE_RENDER, 3),
		renderTargetImplementation=Camera.RenderTargetImplementation.PIXEL_BUFFER,
		referenceFrame=Transform.ReferenceFrame.ABSOLUTE_RF
	)

	assert c.name == "cam"
	assert c.clearColor == Vec4(0.1, 0.2, 0.3, 1.0)
	assert c.clearMask == GL_COLOR_BUFFER_BIT
	assert c.allowEventFocus == False
	assert c.computeNearFarMode == Camera.ComputeNearFarMode.DO_NOT_COMPUTE_NEAR_FAR
	assert c.nearFarRatio == 0.001
	assert (c.viewport.x, c.viewport.y, c.viewport.width, c.viewport.height) == (0, 0, 800, 600)
	assert c.renderOrder == Camera.RenderOrder.PRE_RENDER
	assert c.renderTargetImplementation[0] == Camera.RenderTargetImplementation.PIXEL_BUFFER
	assert c.referenceFrame == Transform.ReferenceFrame.ABSOLUTE_RF

def test_viewport_property_both_forms():
	c = Camera()

	c.viewport = Viewport(1, 2, 3, 4)

	assert (c.viewport.x, c.viewport.y, c.viewport.width, c.viewport.height) == (1, 2, 3, 4)

	c.viewport = (5, 6, 7, 8)

	assert (c.viewport.x, c.viewport.y, c.viewport.width, c.viewport.height) == (5, 6, 7, 8)

def test_renderorder_property_both_forms():
	c = Camera()

	c.renderOrder = Camera.RenderOrder.PRE_RENDER

	assert c.renderOrder == Camera.RenderOrder.PRE_RENDER

	c.renderOrder = (Camera.RenderOrder.NESTED_RENDER, 1)

	assert c.renderOrder == Camera.RenderOrder.NESTED_RENDER

def test_rendertargetimplementation_property_both_forms():
	c = Camera()

	c.renderTargetImplementation = Camera.RenderTargetImplementation.PIXEL_BUFFER_RTT

	# The single-value form calls OSG's own one-arg `setRenderTargetImplementation(impl)`
	# overload, which picks its own fallback -- only the primary target is ours to assert on.
	assert c.renderTargetImplementation[0] == Camera.RenderTargetImplementation.PIXEL_BUFFER_RTT

	c.renderTargetImplementation = (
		Camera.RenderTargetImplementation.FRAME_BUFFER_OBJECT,
		Camera.RenderTargetImplementation.PIXEL_BUFFER
	)

	assert c.renderTargetImplementation == (
		Camera.RenderTargetImplementation.FRAME_BUFFER_OBJECT,
		Camera.RenderTargetImplementation.PIXEL_BUFFER
	)

def test_projection_and_view_matrix_properties():
	c = Camera()
	m = Matrixd.identity()

	c.projectionMatrix = m

	assert c.projectionMatrix == m

	c.viewMatrix = m

	assert c.viewMatrix == m

def test_draw_callbacks_construction_and_property():
	calls = []

	c = Camera(
		initialDrawCallback=lambda ri: calls.append("initial"),
		preDrawCallback=lambda ri: calls.append("pre"),
		postDrawCallback=lambda ri: calls.append("post"),
		finalDrawCallback=lambda ri: calls.append("final")
	)

	assert c.initialDrawCallback is not None
	assert c.preDrawCallback is not None
	assert c.postDrawCallback is not None
	assert c.finalDrawCallback is not None

	c.preDrawCallback = None

	assert c.preDrawCallback is None

def test_destruction():
	deleted = []

	c = Camera(name="CAM", debug=lambda addr, cls, name: deleted.append(addr))
	addr = c.addr

	assert refcmp(c, 1, 1)

	del c

	assert deleted[-1] == addr
