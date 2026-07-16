#vimrun! pytest -sv ../test/osgGA_CameraManipulator.py

from .conftest import refcmp

from OpenSceneGraph.osg import Geode, Matrix, Matrixd
from OpenSceneGraph.osgGA import CameraManipulator
from OpenSceneGraph.osgViewer import Viewer

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

def test_home_dispatches_without_crashing():
	"""Regression test for a second, separate pybind11 trampoline bug in the same
	class: home(const GUIEventAdapter&, GUIActionAdapter&) used raw PYBIND11_OVERRIDE,
	which tries to COPY `ea` when marshaling it to a Python override. GUIEventAdapter
	derives from osg::Referenced and isn't copyable, so this crashed with
	`RuntimeError: return_value_policy = copy, but type osgGA::GUIEventAdapter is
	non-copyable!` the instant a Python subclass defined home() -- triggered by
	View.setCameraManipulator(..., resetPosition=True), which is exactly what
	`viewer.cameraManipulator = manip` runs, and always calls this two-argument
	overload. No window/realize() needed to reproduce -- just constructing a bare
	Viewer and assigning sceneData + cameraManipulator is enough.

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

	v = Viewer()
	v.sceneData = Geode()

	v.cameraManipulator = HomeManip()

	assert len(calls) == 1
