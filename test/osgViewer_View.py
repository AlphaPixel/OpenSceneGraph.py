from OpenSceneGraph.osgGA import GUIEventHandler
from OpenSceneGraph.osgViewer import View


class Handler(GUIEventHandler):
	pass


class TaggedHandler(GUIEventHandler):
	def __init__(self, tag):
		super().__init__()

		self.tag = tag


def test_event_handlers_insert_preserves_identity_without_local_ref():
	# Regression test for a real bug hit live: SequenceProxy.insert()'s native-path cache
	# invalidation originally ERASED shifted slots instead of shifting them. A trampoline-
	# backed handler appended with no local variable retaining it -- exactly how
	# `viewer.eventHandlers.append(SomeHandler())` is commonly written, e.g.
	# pyosg-praxis.py's `v.eventHandlers.append(PraxisKeyHandler(v.sceneData, v))` -- can have
	# that SlotCache slot as its ONLY strong Python reference; erasing it let the wrapper get
	# garbage collected even though OSG's own ref_ptr kept the underlying C++ object alive,
	# silently downgrading later access to the nearest bound C++ base (GUIEventHandler),
	# losing the subclass identity and handle() override with no error raised anywhere. Fixed
	# by shifting cached slots instead of erasing them. (A second, different bug in that same
	# fix -- an evaluation-order hazard where `slot(j) = slot(j - 1)` read a reference that the
	# SAME assignment's own vector resize had just invalidated -- segfaulted outright before
	# this got to the point of passing or failing on identity.)
	v = View()

	v.eventHandlers.append(TaggedHandler("praxis"))  # no local var -- matches the real bug

	v.eventHandlers.insert(0, TaggedHandler("lock"))

	h0, h1 = v.eventHandlers[0], v.eventHandlers[1]

	assert isinstance(h0, TaggedHandler) and h0.tag == "lock"
	assert isinstance(h1, TaggedHandler) and h1.tag == "praxis"

def test_event_handlers_del_preserves_identity_of_shifted_elements():
	# Companion regression test to the insert() one above, for del(). Same root cause, same
	# fix shape: deleting index i shifts every LATER element down by one -- those are still
	# live, still-present elements, just relocated, so del()'s cache invalidation must shift
	# their slots down with them rather than erasing them. This is very likely the actual
	# root cause the feedback_eventhandlers_delitem_bug memory documented as a symptom+
	# workaround ("del viewer.eventHandlers[i] corrupts identity; use [i] = x") without ever
	# root-causing it -- that workaround should no longer be necessary after this fix.
	v = View()

	v.eventHandlers.append(TaggedHandler("a"))  # no local vars -- matches the real bug
	v.eventHandlers.append(TaggedHandler("b"))
	v.eventHandlers.append(TaggedHandler("c"))

	del v.eventHandlers[0]  # "a" deleted; "b", "c" shift down to 0, 1

	result = [(type(h), h.tag) for h in v.eventHandlers]

	assert result == [(TaggedHandler, "b"), (TaggedHandler, "c")]

def test_event_handlers_del_last_index():
	v = View()

	v.eventHandlers.append(TaggedHandler("a"))
	v.eventHandlers.append(TaggedHandler("b"))

	del v.eventHandlers[1]  # no later elements to shift -- straight erase

	result = [(type(h), h.tag) for h in v.eventHandlers]

	assert result == [(TaggedHandler, "a")]

def test_event_handlers_del_multi_shift():
	v = View()

	for tag in ("a", "b", "c", "d", "e"):
		v.eventHandlers.append(TaggedHandler(tag))

	del v.eventHandlers[1]  # "b" deleted; c, d, e all shift down

	result = [(type(h), h.tag) for h in v.eventHandlers]

	assert result == [
		(TaggedHandler, "a"), (TaggedHandler, "c"), (TaggedHandler, "d"), (TaggedHandler, "e")
	]

def test_event_handlers_insert():
	# The motivating case for SequenceProxy.insert(): View has no addEventHandler-with-index,
	# only append-only addEventHandler(), so this exercises the NATIVE traits insert() (reaching
	# into the mutable std::list via getEventHandlers()), not the append()/del() emulation
	# Geode/Program fall back to.
	v = View()
	h0 = Handler()
	h1 = Handler()
	h2 = Handler()

	v.eventHandlers.append(h0)
	v.eventHandlers.append(h2)
	v.eventHandlers.insert(1, h1)

	assert list(v.eventHandlers) == [h0, h1, h2]

	front = Handler()

	v.eventHandlers.insert(0, front)

	assert list(v.eventHandlers) == [front, h0, h1, h2]

def test_event_handlers_pop_and_clear():
	v = View()
	h0 = Handler()
	h1 = Handler()

	v.eventHandlers.extend((h0, h1))

	assert v.eventHandlers.pop(0) is h0
	assert len(v.eventHandlers) == 1

	v.eventHandlers.clear()

	assert len(v.eventHandlers) == 0
