#vimrun! pytest -sv ../test/osgGA_CameraManipulator.py

from .conftest import refcmp

from OpenSceneGraph.osg import Camera, Geode, Matrix, Matrixd
from OpenSceneGraph.osgGA import CameraManipulator

class BareManipulator(CameraManipulator):
	"""Minimal concrete CameraManipulator: only the four required pure-virtual
	overrides, nothing else. Used as the base for the node-storage tests below,
	which deliberately add nothing but setNode()/getNode()."""

	def __init__(self):
		super().__init__()

		self._matrix = Matrixd()

	def getMatrix(self):
		return self._matrix

	def setByMatrix(self, m):
		self._matrix = m

	def getInverseMatrix(self):
		return Matrix.inverse(self._matrix)

	def setByInverseMatrix(self, m):
		self._matrix = Matrix.inverse(m)

def test_construction():
	m = BareManipulator()

	assert refcmp(m, 1, 1)

def test_matrix_roundtrip():
	m = BareManipulator()
	mat = Matrixd()

	mat.makeTranslate(1, 2, 3)

	m.matrix = mat

	assert m.matrix == mat
	assert m.inverseMatrix == Matrix.inverse(mat)

def test_node_default_without_override():
	"""A subclass that does NOT override setNode()/getNode() gets no free node
	storage -- it falls through to CameraManipulator's own defaults (setNode()
	does nothing, getNode() always returns None), exactly like a plain C++
	subclass that doesn't add its own storage would behave. This is expected
	scoping, not a bug: node storage is opt-in per subclass."""

	m = BareManipulator()

	m.node = Geode(name="ignored")

	assert m.node is None

class TrackingManipulator(BareManipulator):
	"""BareManipulator + real node storage, tracking every setNode()/getNode() call."""

	def __init__(self):
		super().__init__()

		self._node = None
		self.calls = []

	def setNode(self, node):
		self.calls.append(("set", node.addr if node is not None else None))

		self._node = node

	def getNode(self):
		self.calls.append(("get", self._node.addr if self._node is not None else None))

		return self._node

def test_node_override_dispatches_through_property():
	"""Regression test for a real pybind11 trampoline bug: CameraManipulator's
	trampoline (pyosg/pyosgGA.hpp) previously didn't intercept setNode()/getNode()
	at all, so a Python-level override of either method was silently never
	called via the bound `.node` property (or via View.setCameraManipulator(),
	which calls setNode() on assignment) -- both fell straight through to the
	OSG base class's no-op defaults without ever reaching Python code. Confirmed
	via a standalone reproduction (no viewer/window involved) before the fix:
	assigning `.node` left the Python override's internal storage untouched.
	"""

	m = TrackingManipulator()
	geode = Geode(name="test-geode")

	assert m.node is None

	m.node = geode

	assert ("set", geode.addr) in m.calls
	assert m.node.addr == geode.addr
	assert ("get", geode.addr) in m.calls

def test_node_property_slot_does_not_accumulate():
	"""Regression test for the `.node` property itself: it used to be bound with
	`py::keep_alive<1, 2>()`, which has no way to release a PREVIOUS "patient" --
	every node ever assigned stayed pinned alive for the manipulator's entire
	lifetime. 10 reassignments (not an unusual thing if manipulators are swapped
	on user request) would leak 9 unreachable nodes. It's now a `pyx::PropertySlot`
	(single cached slot, replaced -- not appended -- on every set), matching
	`osg.BufferData.bufferObject`'s existing pattern.

	Verified via `debug=`, this project's true-destruction probe (see
	feedback_dumps.md): a node is only PROVEN dead once its C++ destructor
	actually runs, not merely once it becomes Python-unreachable.
	"""

	m = TrackingManipulator()
	destroyed = []

	def make_node(i):
		return Geode(
			name=f"node-{i}",
			debug=lambda addr, cls, name, i=i: destroyed.append(i),
		)

	for i in range(10):
		# No local Python variable retains this node -- the manipulator's
		# TrackingManipulator._node attribute and the PropertySlot cache are
		# the only things that could keep it alive.
		m.node = make_node(i)

	# Every node except the last should already be truly destroyed, not just
	# unreachable -- proven by the debug= probe firing, not by refcount alone.
	assert destroyed == list(range(9))
	assert m.node.name == "node-9"

def test_home_dispatches_without_crashing(simulate_frame):
	"""Regression test for a second, separate pybind11 trampoline bug in the same
	class: home(const GUIEventAdapter&, GUIActionAdapter&) used raw PYBIND11_OVERRIDE,
	which tries to COPY `ea` when marshaling it to a Python override. GUIEventAdapter
	derives from osg::Referenced and isn't copyable, so this crashed with
	`RuntimeError: return_value_policy = copy, but type osgGA::GUIEventAdapter is
	non-copyable!` the instant a Python subclass defined home() -- triggered by
	View.setCameraManipulator(..., resetPosition=True), which is exactly what
	`viewer.cameraManipulator = manip` runs, and always calls this two-argument
	overload. No window/realize() needed to reproduce -- just constructing a bare
	The same virtual call can now be driven headlessly through the bound base
	method with an EventQueue-created event state and a Python action adapter.

	Fixed by switching to call_override (passes ea/aa by reference instead of
	copying), matching detail::GUIEventHandler::handle's existing use of it for
	this exact same argument pair -- which is what made this bug so sneaky: that
	precedent was adopted for return-value semantics, not argument marshaling, so
	it accidentally avoided the crash it was never known to be a fix for.
	"""

	calls = []

	class HomeManip(BareManipulator):
		def home(self, ea, aa):
			calls.append((ea, aa))

	CameraManipulator.home(
		HomeManip(),
		simulate_frame.events.currentEventState,
		simulate_frame.actions
	)

	assert len(calls) == 1

def test_direct_python_call_is_not_proof_of_real_dispatch(simulate_frame):
	"""Methodology trap, preserved deliberately as its own test: calling a bound
	method directly on a Python object (`manip.handle(ea, aa)`) always finds the
	subclass's own Python-level method via ordinary Python attribute lookup --
	this succeeds regardless of whether the pybind11 TRAMPOLINE actually routes a
	real C++-side virtual call to it. It is not evidence the trampoline works.

	This exact false positive delayed finding the real bug in
	test_handle_dispatches_through_real_event_dispatch below: a direct call
	looked like proof handle() worked, when the trampoline had no handle()
	override at all and real event dispatch never reached Python.
	"""

	calls = []

	class HandleManip(BareManipulator):
		def handle(self, ea, aa):
			calls.append((ea, aa))

			return False

	m = HandleManip()
	ea = simulate_frame.events.currentEventState

	# This call succeeds and calls IS populated -- but it proves nothing about
	# the trampoline. It's plain Python method resolution, not a C++ virtual call.
	m.handle(ea, simulate_frame.actions)

	assert len(calls) == 1

def test_handle_dispatches_through_real_event_dispatch(simulate_frame):
	"""Regression test for a real pybind11 trampoline bug, same shape as
	test_home_dispatches_without_crashing above but for handle() instead of
	home() -- and much easier to miss, because a naive test
	(test_direct_python_call_is_not_proof_of_real_dispatch above) looks like it
	proves this already works when it doesn't.

	CameraManipulator's trampoline (pyosg/pyosgGA.hpp) had NO handle() override
	at all. Real OSG event dispatch (osgViewer::Viewer::eventTraversal(), which
	is what viewer.frame() drives) reaches a manipulator's handle() through a
	chain of C++ defaults: GUIEventHandler::handle(Event*,Object*,NodeVisitor*)
	-> its 4-arg handle(ea,aa,obj,nv) default -> this 2-arg handle(ea,aa) --
	every link in that chain was an unoverridden default, and
	osgGA::CameraManipulator::handle(ea,aa)'s own real implementation
	(CameraManipulator.cpp) is a literal `return false;`. So a Python
	handle() override was silently NEVER called by real interactive use --
	confirmed live in examples/pyosg-fire.py as "mouse orbiting stopped
	responding entirely" once a manipulator wrapping a real inner manipulator
	was installed as viewer.cameraManipulator (see aipython/06-camera-effects.md).

	The test forces that same C++ default chain directly through the bound
	GUIEventHandler base method, avoiding Viewer/window/render lifecycle while
	still bypassing Python's ordinary subclass-method lookup.
	"""

	calls = []

	class HandleManip(BareManipulator):
		def handle(self, ea, aa):
			calls.append((ea, aa))

			return False

	m = HandleManip()
	event = simulate_frame.events.mouseMotion(10, 10)
	simulate_frame.dispatchEvent(m, event)

	assert len(calls) == 1

def test_updateCamera_dispatches_through_real_update_dispatch(simulate_frame):
	"""Regression test for updateCamera(), the third method in this class found
	completely missing from the trampoline (pyosg/pyosgGA.hpp) -- same shape as
	handle() above. osgViewer::Viewer::updateTraversal() calls
	`_cameraManipulator->updateCamera(*_camera)` unconditionally every frame, so
	this is the hook a decorator manipulator needs to compose temporary effects
	(camera shake, etc.) on top of a live interactive manipulator's own output --
	see aipython/06-camera-effects.md. This test forces the same virtual call
	through `CameraManipulator.updateCamera(...)`, avoiding a Viewer while still
	bypassing direct Python subclass-method lookup.
	"""

	calls = []

	class UpdateCameraManip(BareManipulator):
		def updateCamera(self, camera):
			calls.append(camera.addr)

	CameraManipulator.updateCamera(UpdateCameraManip(), Camera())

	assert len(calls) == 1

def test_computeHomePosition_dispatches_via_explicit_base_call():
	"""Regression test for the fourth trampoline gap found in this audit: the
	sole existing attempt at overriding computeHomePosition() was dead,
	uncompiled, commented-out code that had copy-pasted setAutoComputeHomePosition's
	macro arguments instead of its own.

	Unlike handle()/updateCamera() above, nothing in this project's OSG-internal
	call sites invokes computeHomePosition() automatically for a bare
	CameraManipulator, so there's no real event/frame to drive through. Instead
	this uses a DIFFERENT technique for forcing genuine C++ dispatch (proven
	necessary by the false-positive trap documented above): calling the method
	through the BASE class explicitly -- `CameraManipulator.computeHomePosition(m,
	...)` instead of `m.computeHomePosition(...)` -- bypasses Python's own
	subclass-method-shadowing lookup, forcing pybind11's bound wrapper (`self`
	typed as the real C++ base) to run, which makes a genuine virtual call
	through the vtable rather than plain Python attribute resolution.

	NOTE: this same technique does NOT work for handle()/home() -- confirmed
	live, `CameraManipulator.handle(m, ea, viewer)` hits the identical
	GUIActionAdapter TypeError forwarding does, because it's still calling a
	bound method that needs a real GUIActionAdapter argument. It only works
	here because computeHomePosition()'s arguments (a Camera pointer and a
	bool) have no such restriction.
	"""

	calls = []

	class ComputeHomeManip(BareManipulator):
		def computeHomePosition(self, camera, useBoundingBox=False):
			calls.append((camera, useBoundingBox))

	m = ComputeHomeManip()

	CameraManipulator.computeHomePosition(m, None, True)

	assert calls == [(None, True)]
