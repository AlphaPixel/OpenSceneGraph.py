#pragma once

// One-line summaries of what you'll find in this file:
//
// try_unpack_sequence -> "Try to unpack a py::object as an exact-length tuple of specific types."
// kwargs_init -> "Chain a type's constructor-kwargs handling through its actual C++ bases."
// kwargs_ctor -> "Build the `py::init([](kwargs){ ... })` lambda for a kwargs_init participant."
// SlotCache -> "Don't recreate Python objects unless the underlying pointer changed."
// ProxyStorage -> "Attach all Python views to the lifetime of the C++ object."
// PropertySlots -> "Make fields behave like stable Python attributes."
// SequenceProxy -> "Turn arbitrary C++ containers into Python lists."
// MappingProxy -> "Turn arbitrary C++ containers into Python dicts."
// Traits -> "Define behavior once, reuse everywhere."
// bind_proxy_property -> "Wire a Sequence/Mapping/ValueMapping proxy onto its owner in one call."
// build_info -> Injects "common" Python compiler information, merged with a user-defined dict
// StopEvent -> "Cooperative cancellation flag shared between a Python task and a C++ background thread."
// put_nowait -> "Thread-safe: push a message onto an asyncio.Queue from any thread via call_soon_threadsafe."

#include "pybind11/pybind11.h"
#include "pybind11/stl.h"
#include "pybind11/stl_bind.h"
#include "pybind11/operators.h"
#include "pybind11/embed.h"

#include <algorithm>
#include <atomic>
#include <optional>
#include <tuple>
#include <type_traits>
#include <utility>

namespace py = pybind11;

using namespace std::string_literals;
using namespace py::literals;

#define PYOBJECT_INTERNAL __attribute__((visibility("hidden")))

namespace pybind11x {

// Used when the user doesn't define their OWN (which they would need to do if they have MULTIPLE
// proxies on one object).
struct DEFAULT_PROXY_TAG {};

// A helper for "normalizing" numeric index values, converting negative numbers to their C++
// equivalent. Any time you ACCEPT an index from Python, this helper will ensure that the returned
// value is safe to use in C++.
template<typename R=size_t>
auto n_index(size_t size, py::ssize_t index) {
	if(index < 0) index += static_cast<py::ssize_t>(size);

	if(index < 0 || static_cast<size_t>(index) >= size) throw py::index_error(
		"Index " + std::to_string(index) +
		" out of range for container of size " + std::to_string(size)
	);

	return static_cast<R>(index);
}

// list.insert()'s index rule is deliberately different from n_index() above: it never raises,
// it clamps -- insert(-100, x) on a 3-element list inserts at 0, insert(100, x) inserts at 3
// (the end). This matches CPython's list.insert() exactly.
template<typename R=size_t>
auto n_insert_index(size_t size, py::ssize_t index) {
	if(index < 0) index += static_cast<py::ssize_t>(size);

	if(index < 0) index = 0;

	else if(static_cast<size_t>(index) > size) index = static_cast<py::ssize_t>(size);

	return static_cast<R>(index);
}

// Chains a type's constructor-kwargs handling through its actual C++ base classes, automatically.
// Each participating type specializes two things (see the manifest in pyosg.hpp, which is what
// makes these specializations visible everywhere the chain below might need them):
//
//   - `kwargs_base<T>::type` -- T's REAL immediate base (left as `void` for the root of a chain,
//     or for any type that doesn't participate at all)
//   - `kwargs_init_own<T>`   -- whatever kwargs T itself understands; no delegation code needed,
//     `kwargs_init<T>` walks `kwargs_base` up the chain for you
//
// A type's binding file therefore never has to know or re-derive what its "next" base is; if that
// base later gains its own kwargs handling, every subclass picks it up for free.
template<typename T>
struct kwargs_base { using type = void; };

template<typename T>
void kwargs_init_own(T&, const py::kwargs&) {}

template<typename T>
void kwargs_init(T& self, const py::kwargs& kwargs) {
	using Base = typename kwargs_base<T>::type;

	if constexpr(!std::is_void_v<Base>) kwargs_init(static_cast<Base&>(self), kwargs);

	kwargs_init_own(self, kwargs);
}

// The common `py::init([](Args... args, py::kwargs kwargs) { auto obj = new T(args...);
// kwargs_init(*obj, kwargs); return obj; })` pattern -- `Args...` are T's REAL leading positional
// constructor parameter types (empty for the plain default-constructible case, e.g.
// `kwargs_ctor<osg::Node>()`; e.g. `kwargs_ctor<osg::MatrixTransform, const osg::Matrix&>()` for
// a type whose real constructor takes a required leading arg, letting `osg.MatrixTransform(m,
// name=...)` work instead of forcing a separate `xform.name = ...` statement afterward). Each
// `Args` parameter is necessarily positional-only from Python's side -- pybind11 has no name to
// match a keyword against an unnamed lambda parameter, so `py::kwargs` is the only way anything
// past it can be passed. Types needing custom/aliased allocation (a Python-subclassing trampoline)
// still write their own lambda and just call `kwargs_init(*obj, kwargs)` directly.
template<typename T, typename... Args>
auto kwargs_ctor() {
	return [](Args... args, py::kwargs kwargs) {
		osg::ref_ptr<T> obj = new T(args...);

		kwargs_init(*obj, kwargs);

		return obj;
	};
}

namespace detail {
	// The actual cast attempt, split out so the index pack (`Is...`) can be built from `Ts...`
	// via `index_sequence_for` -- expanding `seq[Is].cast<Ts>()` directly keeps each index tied
	// to its own compile-time constant, unlike a runtime counter (e.g. `seq[i++]`), which would
	// have unspecified evaluation order across pack elements.
	template<typename... Ts, size_t... Is>
	std::optional<std::tuple<Ts...>> try_unpack_sequence_impl(
		const py::sequence& seq,
		std::index_sequence<Is...>
	) {
		try {
			return std::make_tuple(seq[Is].template cast<Ts>()...);
		}

		catch(const py::cast_error&) {
			return std::nullopt;
		}
	}
}

// Attempts to unpack `obj` as an exact-length sequence of `sizeof...(Ts)` elements, casting
// element `i` to `Ts...[i]`. Returns `std::nullopt` -- never throws -- if `obj` isn't
// sequence-like, is a `str`/`bytes` (both satisfy `py::isinstance<py::sequence>`, but are never
// what's meant by "a tuple of values" at any of this helper's call sites), doesn't have exactly
// `sizeof...(Ts)` elements, or any element fails to cast to its corresponding type. Folding EVERY
// failure mode into one `nullopt` (rather than letting a mismatched element type raise its own
// raw pybind cast error) means the caller's single fallback `throw` after trying this is reliably
// the error the user sees.
//
// For a setter that accepts a variable number of elements (e.g. 1-3), call this once per exact
// arity, largest first -- there is deliberately no separate variadic/min-max variant.
template<typename... Ts>
std::optional<std::tuple<Ts...>> try_unpack_sequence(const py::object& obj) {
	if(py::isinstance<py::str>(obj) || py::isinstance<py::bytes>(obj)) return std::nullopt;
	if(!py::isinstance<py::sequence>(obj)) return std::nullopt;

	auto seq = obj.cast<py::sequence>();

	if(seq.size() != sizeof...(Ts)) return std::nullopt;

	return detail::try_unpack_sequence_impl<Ts...>(seq, std::index_sequence_for<Ts...>{});
}

// A single cache entry that ties a C++ pointer identity to a stable Python object wrapper. If the
// underlying pointer changes, the Python object is invalidated and rebuilt.
struct PYOBJECT_INTERNAL IdentitySlot {
	py::object py = py::none();

	const void* ptr = nullptr;
};

// Defines the minimal interface for a storage backend (`slot(k), erase(k)`), letting you swap
// vector-based or map-based storage without touching higher layers.
template<typename S>
concept SlotStorageConcept = requires(S s, typename S::key_type k) {
	typename S::key_type;
	typename S::slot_type;

	{ s.slot(k) } -> std::same_as<typename S::slot_type&>;
	{ s.erase(k) };
};

// Index-based storage (like arrays / sequences). Auto-resizes and gives you O(1) slot access by
// index, perfect for `SequenceProxy`.
template<typename Key>
class PYOBJECT_INTERNAL VectorSlotStorage {
public:
	using key_type = Key;
	using slot_type = IdentitySlot;

	slot_type& slot(Key k) {
		if(k >= _slots.size()) _slots.resize(k + 1);

		return _slots[k];
	}

	void erase(Key k) { if(k < _slots.size()) _slots[k] = {}; }

protected:
	std::vector<slot_type> _slots;
};

// Key-based storage (like dicts). Uses `unordered_map`, so slots are created on demand and erased
// cleanly by key.
template<typename Key>
class PYOBJECT_INTERNAL MapSlotStorage {
public:
	using key_type = Key;
	using slot_type = IdentitySlot;

	slot_type& slot(Key k) { return _slots[k]; }

	void erase(Key k) { _slots.erase(k); }

protected:
	std::unordered_map<Key, slot_type> _slots;
};

// The core identity system. Handles:
//
// - Pointer comparison -> detects when the underlying C++ object changed
// - Lazy py::object creation -> only wraps when needed
// - Stable identity -> same pointer -> same Python object
//
// This is the piece that makes everything "feel Pythonic" instead of wrapper-churn hell.
template<SlotStorageConcept Storage>
class PYOBJECT_INTERNAL SlotCache: protected Storage {
public:
	using key_type = typename Storage::key_type;
	using slot_type = typename Storage::slot_type;

	template<typename T>
	py::object get(key_type k, T* ptr) {
		auto& s = Storage::slot(k);
		const void* erased = static_cast<const void*>(ptr);

		if(erased != s.ptr) {
			s.py = py::none();
			s.ptr = nullptr;

			if(ptr) {
				s.py = py::cast(ptr);
				s.ptr = erased;
			}
		}

		return s.py;
	}

	// TODO: Investigate a future optimization similar to get() above -- unlike get(), this always
	// reassigns even when `ptr` is unchanged from the cached slot, relying on pybind11's own
	// registered-instance registry (py::cast() returns the existing wrapper for a known pointer)
	// to avoid allocating a duplicate Python object. That's a hashmap-lookup-plus-refcount cost
	// per set() call that get()'s short-circuit avoids; skip it here unless a real profile shows
	// it matters (see osgSlug's ShapeDrawable.layers proxy for the case that prompted this note).
	template<typename T>
	void set(key_type k, py::object obj, T* ptr) {
		auto& s = Storage::slot(k);

		s.py = std::move(obj);
		s.ptr = static_cast<const void*>(ptr);
	}

	void erase(key_type k) {
		Storage::erase(k);
	}
};

// Convenience aliases binding `SlotCache` to a storage type (`std::vector`).
template<typename Key>
using VectorSlotCache = SlotCache<VectorSlotStorage<Key>>;

// Convenience aliases binding `SlotCache` to a storage type (`std::unordered_map`).
template<typename Key>
using MapSlotCache = SlotCache<MapSlotStorage<Key>>;

// A container for multiple proxy instances tied to a single C++ object. Think: "one per-object
// bundle of all Python-facing views."
template<typename T, typename... Proxies>
struct ProxyStorage {
	std::tuple<Proxies...> proxies;

	ProxyStorage() : proxies(Proxies()...) {}
	explicit ProxyStorage(T* obj) : proxies(Proxies(obj)...) {}

	template<typename Proxy>
	Proxy& proxy() {
		return std::get<Proxy>(proxies);
	}
};

// Attaches `ProxyStorage` directly to an `osg::Object` via `UserDataContainer`. This solves the
// problem of C++ objects being created anywhere (but you still want persistent Python-side state,
// no matter WHO/WHAT created the instance).
//
// A kind of "sidecar" storage attached to the scene graph itself.
template<typename T, typename... Proxies>
struct ProxyStorageOSG: public osg::Object, public ProxyStorage<T, Proxies...> {
	using base_type = ProxyStorage<T, Proxies...>;

	PYOSG_DISABLE_WARNINGS

	META_Object(pyosg, ProxyStorageOSG)

	PYOSG_ENABLE_WARNINGS

	ProxyStorageOSG(): osg::Object(), base_type() {
		setName("pyosg.ProxyStorage");
		// setName(std::string(libraryName()) + "." + className());
	}

	explicit ProxyStorageOSG(T* obj): osg::Object(), base_type(obj) {
		setName("pyosg.ProxyStorage");
	}

	ProxyStorageOSG(
		const ProxyStorageOSG& rhs,
		const osg::CopyOp& copyop=osg::CopyOp::SHALLOW_COPY
	):
	osg::Object(rhs, copyop),
	base_type() {
	}

	static ProxyStorageOSG* get(T& obj) {
		auto* udc = obj.getOrCreateUserDataContainer();

		for(unsigned int i = 0; i < udc->getNumUserObjects(); i++) {
			if(auto* s = dynamic_cast<ProxyStorageOSG*>(udc->getUserObject(i))) return s;
		}

		auto* s = new ProxyStorageOSG(&obj);

		udc->addUserObject(s);

		return s;
	}
};

// Equivalent idea to `ProxyStorageOSG`, designed for `std::shared_ptr`-managed objects. Uses a
// global registry with `std::weak_ptr` cleanup to ensure:
//
// - One storage per live object
// - No leaks after destruction
//
// The non-OSG ownership model counterpart.
template<typename T, typename... Proxies>
struct ProxyStorageShared: public ProxyStorage<T, Proxies...> {
	using ProxyStorage<T, Proxies...>::ProxyStorage;

	struct Entry {
		std::weak_ptr<T> weak;
		std::unique_ptr<ProxyStorageShared> storage;
	};

	static auto& registry() {
		static auto& r = *new std::unordered_map<void*, Entry>();
		return r;
	}

	static ProxyStorageShared* get(const std::shared_ptr<T>& obj) {
		auto& reg = registry();
		void* key = obj.get();

		auto it = reg.find(key);

		if(it != reg.end()) {
			// Weak ptr check: if somehow the key was reused, replace it
			if(it->second.weak.lock()) return it->second.storage.get();

			reg.erase(it);
		}

		auto entry = Entry{obj, std::make_unique<ProxyStorageShared>(obj.get())};
		auto* ptr = entry.storage.get();

		reg.emplace(key, std::move(entry));

		return ptr;
	}

#if 0
	static ProxyStorageShared* get(const std::shared_ptr<T>& obj) {
		auto& reg = registry();
		const void* key = obj.get();

		static size_t counter = 0;
		i (++counter % 64 == 0) {
			for(auto it = reg.begin(); it != reg.end(); ) {
				if(it->second.weak.expired()) it = reg.erase(it);
				else ++it;
			}
		}

		auto it = reg.find(key);

		if(it != reg.end()) {
			if(it->second.weak.lock()) return it->second.storage.get();
			reg.erase(it);
		}

		auto entry = Entry{obj, std::make_unique<ProxyStorageShared>(obj.get())};
		auto* ptr = entry.storage.get();

		reg.emplace(key, std::move(entry));
		return ptr;
	}
#endif
};

// Abstracts how you "get the owner" from self.
//
// - OSG -> just Derived&
// - shared_ptr -> recover shared_ptr<Derived> from Python
//
// This is necessary for `PropertySlots` work identically across both worlds.
template<typename Derived, template<typename, typename...> typename Storage>
struct OwnerAccess;

template<typename Derived>
struct OwnerAccess<Derived, ProxyStorageOSG> {
	using owner_type = Derived&;

	static owner_type from_self(Derived& self) {
		return self;
	}
};

template<typename Derived>
struct OwnerAccess<Derived, ProxyStorageShared> {
	using owner_type = std::shared_ptr<Derived>;

	static owner_type from_self(Derived& self) {
		return py::cast(self).template cast<owner_type>();
	}
};

// A fixed-size slot cache for object properties (like fields or indexed members).
//
// - Each "slot" corresponds to a specific property
// - `Getter` pulls pointer -> returns cached Python object
// - `Setter` updates C++ -> updates cache with correct identity
//
// This gives us:
//
// - Stable identity for properties
// - No accidental wrapper duplication
// - Unified handling for raw pointers and `std::shared_ptr`
//
// The main inspiration for this object were the deficiencies in `py::keep_alive`, which doesn't
// provide any way to programmatically let the "patient" be destroyed without ALSO destroying the
// "nurse." This ends up being a very big deal when you want to support syntax like:
//
// `obj.prop = foo.Bar()` # No need for a foo.Bar() temporary
// `obj.prop = foo.Baz()` # With keep_alive, the PREVIOUS instance is STILL alive
//
// If you want to support the concise syntax AND have predictable destruction, use `PropertySlots`.
template<
	typename Derived,
	size_t N,
	template<typename, typename...> typename Storage = ProxyStorageOSG
>
class PYOBJECT_INTERNAL PropertySlots: public SlotCache<VectorSlotStorage<size_t>> {
public:
	using slot_type = PropertySlots<Derived, N, Storage>;
	using storage_type = Storage<Derived, slot_type>;
	using owner_access_type = OwnerAccess<Derived, Storage>;

	PropertySlots() = default;

	explicit PropertySlots(Derived*) {}

	template<size_t I, typename Getter>
	static auto getter(Getter getter_) {
		return [getter_](Derived& self) -> py::object {
			// auto owner = owner_access_type::from_self(self);
			decltype(auto) owner = owner_access_type::from_self(self);
			auto& slots = storage_type::get(owner)->template proxy<slot_type>();
			auto* current = (self.*getter_)();

			return slots.get(I, current);
		};
	}

	template<size_t I, typename T, typename Setter>
	static auto setter(Setter setter_) {
		return [setter_](Derived& self, py::object obj) {
			// auto owner = owner_access_type::from_self(self);
			decltype(auto) owner = owner_access_type::from_self(self);
			auto& slots = storage_type::get(owner)->template proxy<slot_type>();
			auto val = obj.is_none() ? T{} : obj.cast<T>();

			(self.*setter_)(val);

			auto* ptr = [&]() {
				if constexpr(std::is_pointer_v<T>) return val;

				else return val ? val.get() : nullptr;
			}();

			slots.set(I, obj, ptr);
		};
	}
};

// Defines how a C++ type behaves like a sequence:
//
// - size / get / set / del / append
// - plus conversion from Python
//
// This isolates container semantics from the proxy itself, and is where you'll put your "glue
// code" to resolve Python/C++ interop.
template<typename T, typename Tag=DEFAULT_PROXY_TAG>
struct SequenceTraits;

// Enforces the "contract" used by the `SequenceTraits` instance you define for `SequenceProxy`.
template<typename T, typename Tag=DEFAULT_PROXY_TAG>
concept SequenceTraitsConcept = requires(T* obj, size_t i, py::object py_obj) {
	// What do you GET when you READ?
	typename SequenceTraits<T, Tag>::element_type;

	// What do you ACCEPT when you WRITE?
	typename SequenceTraits<T, Tag>::value_type;

	{
		SequenceTraits<T, Tag>::from_python(py_obj)
	} -> std::same_as<typename SequenceTraits<T, Tag>::value_type>;

	{ SequenceTraits<T, Tag>::size(obj) } -> std::convertible_to<size_t>;
	{
		SequenceTraits<T, Tag>::get(obj, i)
	} -> std::same_as<typename SequenceTraits<T, Tag>::element_type*>;
	// { SequenceTraits<T, Tag>::set(obj, i, SequenceTraits<T, Tag>::from_python(py_obj)) };
	// { SequenceTraits<T, Tag>::del(obj, i) };
	// { SequenceTraits<T, Tag>::append(obj, SequenceTraits<T, Tag>::from_python(py_obj)) };
};

template<typename T, typename Tag=DEFAULT_PROXY_TAG>
concept SequenceSettable = requires(T* obj, size_t i, py::object py_obj) {
	SequenceTraits<T, Tag>::set(obj, i, SequenceTraits<T, Tag>::from_python(py_obj));
};

template<typename T, typename Tag=DEFAULT_PROXY_TAG>
concept SequenceDeletable = requires(T* obj, size_t i) {
	SequenceTraits<T, Tag>::del(obj, i);
};

template<typename T, typename Tag=DEFAULT_PROXY_TAG>
concept SequenceAppendable = requires(T* obj, py::object py_obj) {
	SequenceTraits<T, Tag>::append(obj, SequenceTraits<T, Tag>::from_python(py_obj));
};

// Does this specialization provide a REAL insert-at-position primitive (e.g. Group's
// insertChild, Geometry's insertPrimitiveSet, or View reaching into its own mutable
// std::list)? Not every owner has one -- Geode and Program only expose append/remove.
template<typename T, typename Tag=DEFAULT_PROXY_TAG>
concept SequenceTraitsProvidesInsert = requires(T* obj, size_t i, py::object py_obj) {
	SequenceTraits<T, Tag>::insert(obj, i, SequenceTraits<T, Tag>::from_python(py_obj));
};

// insert() is supported either via a native traits-provided primitive, or -- for owners
// without one -- by emulating it out of append()/del(), both of which are already required
// to be optional-but-present via their own concepts above.
template<typename T, typename Tag=DEFAULT_PROXY_TAG>
concept SequenceInsertable =
	SequenceTraitsProvidesInsert<T, Tag> || (SequenceAppendable<T, Tag> && SequenceDeletable<T, Tag>)
;

// A Python list-like wrapper over arbitrary C++ containers.
//
// - Delegates all logic to SequenceTraits
// - Uses SlotCache to preserve identity per index
// - Supports Python behaviors: indexing, slicing-style negatives, iteration, in, append, extend
//
// Identity is tied to index + pointer; if the container mutates, cache stays consistent because
// pointer mismatch invalidates entries.
template<typename T, typename Tag=DEFAULT_PROXY_TAG>
requires SequenceTraitsConcept<T, Tag>
struct PYOBJECT_INTERNAL SequenceProxy: public SlotCache<VectorSlotStorage<size_t>> {
	using traits_type = SequenceTraits<T, Tag>;
	using element_type = typename traits_type::element_type;

	// The compiler can find `key_type` here from our inheritance above; thus, in this
	// case, the type ends up being `size_t`.
	using base_type = SlotCache<VectorSlotStorage<key_type>>;

	T* obj = nullptr;

	explicit SequenceProxy(): obj(nullptr) {}
	explicit SequenceProxy(T* o) : obj(o) {}

	size_t size() const { return traits_type::size(obj); }

	py::object get(py::ssize_t index) {
		auto i = n_index(size(), index);
		auto* ptr = traits_type::get(obj, i);

		return base_type::get(i, ptr);
	}

	void set(py::ssize_t index, py::object py_obj) {
		if constexpr(!SequenceSettable<T, Tag>) throw py::type_error(
			"Sequence does not support assignment"
		);

		else {
			auto i = n_index(size(), index);
			auto value = traits_type::from_python(py_obj);

			traits_type::set(obj, i, value);

			auto* ptr = traits_type::get(obj, i);

			// Cache the canonical pointer's own wrapper, not the raw input py_obj -- see the
			// "Caching Rules" section of ai/context-pybind11x.md. Only mattered silently before
			// because every prior SequenceTraits had value_type == element_type*, where py_obj
			// already wrapped the same pointer get() would independently return; a value_type
			// distinct from element_type* (e.g. assigning a plain struct that gets copied into
			// C++ state addressed by a separate handle type) exposes the difference.
			base_type::set(i, py::cast(ptr), ptr);
		}
	}

	void del(py::ssize_t index) {
		if constexpr(!SequenceDeletable<T, Tag>) throw py::type_error(
			"Sequence does not support deletion"
		);

		else {
			auto i = n_index(size(), index);
			auto old_size = size();

			traits_type::del(obj, i);

			// Every index AFTER i shifts down by one -- it's still a live, still-present
			// element (just relocated), so its cached slot must SHIFT down with it, not be
			// erased: erasing here can drop the only strong Python reference a trampoline-
			// backed object has (e.g. `viewer.eventHandlers.append(SomeHandler())` with no
			// local variable retaining it), letting it get garbage collected even though
			// OSG's own ref_ptr keeps the C++ object alive -- silently downgrading later
			// access to the nearest bound C++ base type, with no error anywhere. This used
			// to erase every slot from i through the old last index; that was the root cause
			// behind "del viewer.eventHandlers[i] corrupts identity, use [i] = x instead"
			// being a known workaround rather than something that needed one.
			//
			// Copy into a local first, then assign -- `slot(j - 1) = slot(j)` directly hits
			// the same C++17 evaluation-order hazard insert() did: assignment sequences its
			// RIGHT side before its LEFT side, so the right-hand slot(j) reference would be
			// taken before the left-hand slot(j - 1) call's possible resize/reallocation,
			// leaving that already-taken reference dangling before the assignment runs.
			for(auto j = i + 1; j < old_size; j++) {
				auto moved = base_type::slot(j);

				base_type::slot(j - 1) = moved;
			}

			// old_size - 1, not the now-shrunk size() - 1 -- whatever's left there is either
			// the deleted element's own slot (if i was already the last index, so nothing
			// shifted) or a stale duplicate of what the loop above just copied down one slot.
			// Either way it must be cleared, or it leaks a duplicate strong reference.
			base_type::erase(old_size - 1);
		}
	}

	// list.insert(i, x). Prefers a native SequenceTraits::insert() when the specialization
	// provides one (O(1)/native for Group.children, Geometry.primitiveSets, View.eventHandlers
	// -- see the owner traits files for how each reaches its underlying container). Falls back,
	// for owners with only append()/del() (Geode, Program), to rotating the tail out and back
	// in around the new value: capture it via get(), remove it back-to-front (front-to-back
	// would shift indices out from under later del() calls), append the new value, then
	// re-append the tail. Each captured py::object is the SAME wrapper get() already cached, so
	// re-appending it (rather than a fresh lookup) preserves identity through the round trip.
	void insert(py::ssize_t index, py::object py_obj) {
		if constexpr(!SequenceInsertable<T, Tag>) throw py::type_error(
			"Sequence does not support insert"
		);

		else {
			if(py_obj.is_none()) throw py::type_error("cannot insert None");

			auto i = n_insert_index(size(), index);

			if constexpr(SequenceTraitsProvidesInsert<T, Tag>) {
				auto old_size = size();
				auto value = traits_type::from_python(py_obj);

				traits_type::insert(obj, i, value);

				// UNLIKE del()'s "just erase, let it re-derive later" -- erasing here would be
				// wrong, not just less efficient. A trampoline-backed element (e.g. a Python
				// GUIEventHandler subclass passed straight into append()/insert() with no local
				// variable retaining it, as viewer.eventHandlers.append(MyHandler()) commonly
				// is) can have this SlotCache slot as its ONLY strong Python reference; OSG's
				// own ref_ptr keeps the C++ object alive regardless, but erasing the slot here
				// would drop the only thing keeping the PYTHON wrapper (and its subclass
				// identity/handle() override) alive, silently downgrading later access to it to
				// the nearest bound C++ base type once GC collects it. So: shift each surviving
				// slot to follow its element to its new (+1) index, back-to-front so a not-yet-
				// moved entry is never clobbered, then cache the newly-inserted element the same
				// way append()/set() do (also as a strong reference, not left to be discovered
				// later, for the identical reason).
				//
				// Copy into a local first, THEN assign -- do not write `slot(j) = slot(j - 1)`
				// directly. Since C++17, assignment sequences its right side before its left
				// side, so slot(j - 1) (a reference) is taken FIRST while the backing vector is
				// still short, and slot(j) evaluated second is exactly what may grow/reallocate
				// that vector -- invalidating the reference slot(j - 1) already handed back
				// before the assignment it's part of ever runs. Segfaulted inside
				// IdentitySlot::operator=, Py_INCREF on a dangling pointer, until fixed this way.
				for(auto j = old_size; j > i; j--) {
					auto moved = base_type::slot(j - 1);

					base_type::slot(j) = moved;
				}

				auto* ptr = traits_type::get(obj, i);

				base_type::set(i, py_obj, ptr);
			}

			else {
				auto old_size = size();
				std::vector<py::object> tail;

				tail.reserve(old_size - i);

				for(auto j = i; j < old_size; j++) tail.push_back(get(static_cast<py::ssize_t>(j)));

				for(auto j = old_size; j > i; j--) del(static_cast<py::ssize_t>(j - 1));

				append(py_obj);

				for(auto& t : tail) append(t);
			}
		}
	}

	// list.pop(index=-1): remove-and-return. Deliberately implemented as get() (before
	// mutation) followed by del() (which already does the correct from-i cache invalidation),
	// rather than duplicating that invalidation logic here.
	py::object pop(py::ssize_t index) {
		if constexpr(!SequenceDeletable<T, Tag>) throw py::type_error(
			"Sequence does not support deletion"
		);

		else {
			auto result = get(index);

			del(index);

			return result;
		}
	}

	py::object pop() { return pop(static_cast<py::ssize_t>(-1)); }

	void clear() {
		if constexpr(!SequenceDeletable<T, Tag>) throw py::type_error(
			"Sequence does not support deletion"
		);

		// Remove from the back so each del() only ever invalidates the single slot being
		// removed (see the comment on del() above), instead of the O(n) re-invalidation a
		// front-to-back clear would trigger on every iteration.
		else while(size() > 0) del(static_cast<py::ssize_t>(size() - 1));
	}

	void append(py::object py_obj) {
		if constexpr(!SequenceAppendable<T, Tag>) throw py::type_error(
			"Sequence does not support append"
		);

		else {
			if(py_obj.is_none()) throw py::type_error("cannot append None");

			auto value = traits_type::from_python(py_obj);

			traits_type::append(obj, value);

			auto* ptr = traits_type::get(obj, size() - 1);

			base_type::set(size() - 1, py_obj, ptr);
		}
	}

	void extend(py::object iterable) {
		for(py::handle item : iterable) append(py::reinterpret_borrow<py::object>(item));
	}

	// Shared by contains()/index()/remove() -- first index whose element pointer equals
	// py_obj's, or nullopt if py_obj is None or not found. Identity comparison (pointer
	// equality), same as contains() always used -- not value equality.
	std::optional<size_t> _find_index(py::object py_obj) {
		if(!py_obj.is_none()) {
			auto* ptr = py_obj.cast<element_type*>();

			for(size_t i = 0; i < size(); i++) {
				if(traits_type::get(obj, i) == ptr) return i;
			}
		}

		return std::nullopt;
	}

	bool contains(py::object py_obj) {
		return _find_index(py_obj).has_value();
	}

	// list.index(x): position of the first matching element, ValueError if absent -- same
	// exception CPython's list.index() raises, not IndexError.
	size_t index(py::object py_obj) {
		if(auto i = _find_index(py_obj)) return *i;

		throw py::value_error("value not found in sequence");
	}

	// list.remove(x): remove the first matching element. index() already raises ValueError
	// if absent, matching list.remove()'s own exception; del() already does the correct
	// shift-not-erase SlotCache handling, so there's nothing extra to get right here.
	void remove(py::object py_obj) {
		if constexpr(!SequenceDeletable<T, Tag>) throw py::type_error(
			"Sequence does not support deletion"
		);

		else del(static_cast<py::ssize_t>(index(py_obj)));
	}

	size_t _index(py::ssize_t index) const { return n_index(size(), index); }

	struct Iterator {
		SequenceProxy* proxy = nullptr;
		size_t index = 0;

		py::object next() {
			if(!proxy || index >= proxy->size()) throw py::stop_iteration();

			return proxy->get(static_cast<py::ssize_t>(index++));
		}
	};

	Iterator iter() {
		return Iterator{this, 0};
	}

	static auto bind(py::handle parent, const char* name) {
		using iterator_type = typename SequenceProxy<T, Tag>::Iterator;

		auto sp = py::class_<SequenceProxy<T, Tag>>(parent, name);

		py::class_<iterator_type>(sp, "Iterator")
			.def("__iter__", [](iterator_type& self) -> iterator_type& {
				return self;
			}, py::return_value_policy::reference_internal)
			.def("__next__", &iterator_type::next)
		;

		sp
			.def("__len__", &SequenceProxy<T, Tag>::size)
			.def("__getitem__", &SequenceProxy<T, Tag>::get)
			.def("__setitem__", &SequenceProxy<T, Tag>::set)
			.def("__delitem__", &SequenceProxy<T, Tag>::del)
			.def("__iter__", &SequenceProxy<T, Tag>::iter, py::keep_alive<0, 1>())
			.def("__contains__", &SequenceProxy<T, Tag>::contains)
			.def("append", &SequenceProxy<T, Tag>::append)
			.def("extend", &SequenceProxy<T, Tag>::extend)
			.def("insert", &SequenceProxy<T, Tag>::insert)
			.def("pop", py::overload_cast<py::ssize_t>(&SequenceProxy<T, Tag>::pop))
			.def("pop", py::overload_cast<>(&SequenceProxy<T, Tag>::pop))
			.def("clear", &SequenceProxy<T, Tag>::clear)
			.def("index", &SequenceProxy<T, Tag>::index)
			.def("remove", &SequenceProxy<T, Tag>::remove)
		;

		return sp;
	}
};

// Defines how a C++ type behaves like a mapping:
//
// - size / get / set / del / keys / items
// - plus conversion from Python
//
// Essentially, the counterpart to `SequenceTraits` for "map-like" C++ objects.
template<typename T, typename Tag=DEFAULT_PROXY_TAG>
struct MappingTraits;

// Enforces the "contract" used by the `MappingTraits` instance you define for `MappingProxy`.
template<typename T, typename Tag=DEFAULT_PROXY_TAG>
concept MappingTraitsConcept = requires(
	T* obj,
	typename MappingTraits<T, Tag>::key_type key,
	py::handle h
) {
	typename MappingTraits<T, Tag>::element_type;
	typename MappingTraits<T, Tag>::key_type;
	typename MappingTraits<T, Tag>::value_type;

	{
		MappingTraits<T, Tag>::from_python(h)
	} -> std::same_as<typename MappingTraits<T, Tag>::value_type>;

	{ MappingTraits<T, Tag>::size(obj) } -> std::convertible_to<size_t>;
	{
		MappingTraits<T, Tag>::get(obj, key)
	} -> std::same_as<typename MappingTraits<T, Tag>::element_type*>;
	// { MappingTraits<T, Tag>::set(obj, key, MappingTraits<T, Tag>::from_python(h)) };
	// { MappingTraits<T, Tag>::del(obj, key) };
	// { MappingTraits<T, Tag>::keys(obj) };
};

template<typename T, typename Tag=DEFAULT_PROXY_TAG>
concept MappingSettable = (
	requires(T* obj, typename MappingTraits<T, Tag>::key_type key, py::handle h) {
		MappingTraits<T, Tag>::set(obj, key, MappingTraits<T, Tag>::from_python(h));
	}) || (
	requires(T* obj, typename MappingTraits<T, Tag>::key_type key, py::handle h) {
		MappingTraits<T, Tag>::set(obj, key, h);
	})
;

template<typename T, typename Tag=DEFAULT_PROXY_TAG>
concept MappingDeletable = requires(T* obj, typename MappingTraits<T, Tag>::key_type key) {
	MappingTraits<T, Tag>::del(obj, key);
};

template<typename T, typename Tag=DEFAULT_PROXY_TAG>
concept MappingIterable = requires(T* obj) {
	MappingTraits<T, Tag>::keys(obj);
};

template<typename T, typename Tag=DEFAULT_PROXY_TAG>
concept MappingContains = requires(T* obj, typename MappingTraits<T, Tag>::key_type key) {
	{ MappingTraits<T, Tag>::contains(obj, key) } -> std::convertible_to<bool>;
};

// A Python dict-like wrapper (similar to `SequenceProxy`):
//
// - Key-based identity caching via `MapSlotCache`
// - Lazy wrapping of values
// - Supports `keys()`, `values()`, `items()`, iteration, membership
//
// Also, contains() conditionally uses traits-provided implementation if available.
//
// TODO: Important! What happens the `key_type` is another wrapped object!?
template<typename T, typename Tag=DEFAULT_PROXY_TAG>
requires MappingTraitsConcept<T, Tag>
struct PYOBJECT_INTERNAL MappingProxy:
public MapSlotCache<typename MappingTraits<T, Tag>::key_type> {
	using traits_type = MappingTraits<T, Tag>;
	using element_type = typename traits_type::element_type;
	using key_type = typename traits_type::key_type;
	using base_type = SlotCache<MapSlotStorage<key_type>>;

	T* obj = nullptr;

	explicit MappingProxy(): obj(nullptr) {}
	explicit MappingProxy(T* o): obj(o) {}

	size_t size() const { return traits_type::size(obj); }

	py::object get(key_type key) {
		auto* ptr = traits_type::get(obj, key);

		if(!ptr) throw py::key_error("key not found");

		return base_type::get(key, ptr);
	}

	// dict.get(key, default=None) -- a separate method from get() above (which is __getitem__
	// and must raise KeyError) rather than a default argument on it, since the two need
	// different missing-key behavior.
	py::object get(key_type key, py::object default_value) {
		auto* ptr = traits_type::get(obj, key);

		if(!ptr) return default_value;

		return base_type::get(key, ptr);
	}

	/* void set(key_type key, py::object py_obj) {
		if constexpr(!MappingSettable<T, Tag>) throw py::type_error(
			"Mapping does not support assignment"
		);

		else {
			auto value = traits_type::from_python(py_obj);

			traits_type::set(obj, key, value);

			auto* ptr = traits_type::get(obj, key);

			base_type::set(key, py_obj, ptr);
		}
	} */

	void set(key_type key, py::object py_obj) {
		if constexpr(!MappingSettable<T, Tag>) throw py::type_error(
			"Mapping does not support assignment"
		);

		else {
			// The pure Python object/handle function always has a higher priority than the
			// `from_python` native version (although both CAN be inside the same traits).
			if constexpr(requires { traits_type::set(obj, key, py_obj); }) {
				traits_type::set(obj, key, py_obj);
			}

			else {
				auto value = traits_type::from_python(py_obj);

				traits_type::set(obj, key, value);
			}

			auto* ptr = traits_type::get(obj, key);

			// base_type::set(key, py_obj, ptr);
			base_type::set(key, py::cast(ptr), ptr);
		}
	}

	// dict.setdefault(key, default=None): return the existing value if key is present,
	// otherwise set it to default and return that. Unlike get()/pop(), there's no
	// raise-vs-not-raise split to force two overloads -- a plain pybind11 default argument
	// is enough, since setdefault() always treats a missing `default` the same way (as
	// None), never differently depending on whether the caller passed it.
	py::object setdefault(key_type key, py::object default_value) {
		if constexpr(!MappingSettable<T, Tag>) throw py::type_error(
			"Mapping does not support assignment"
		);

		else {
			auto* ptr = traits_type::get(obj, key);

			if(ptr) return base_type::get(key, ptr);

			set(key, default_value);

			return get(key);
		}
	}

	void del(key_type key) {
		if constexpr(!MappingDeletable<T, Tag>) throw py::type_error(
			"Mapping does not support deletion"
		);

		else {
			traits_type::del(obj, key);

			base_type::erase(key);
		}
	}

	// dict.pop(key): remove-and-return, raising KeyError if absent.
	py::object pop(key_type key) {
		if constexpr(!MappingDeletable<T, Tag>) throw py::type_error(
			"Mapping does not support deletion"
		);

		else {
			auto result = get(key);

			del(key);

			return result;
		}
	}

	// dict.pop(key, default): same, but returns default instead of raising when absent. A
	// second overload rather than a default argument on the one above, mirroring get()'s split
	// for the same reason -- the no-default form must raise, the with-default form must not.
	py::object pop(key_type key, py::object default_value) {
		if constexpr(!MappingDeletable<T, Tag>) throw py::type_error(
			"Mapping does not support deletion"
		);

		else {
			if(!traits_type::get(obj, key)) return default_value;

			return pop(key);
		}
	}

	void clear() {
		if constexpr(!MappingDeletable<T, Tag> || !MappingIterable<T, Tag>) throw py::type_error(
			"Mapping does not support deletion or key-based iteration"
		);

		// Snapshot keys() up front -- del() mutates the underlying container, so iterating a
		// live view of it while deleting would be undefined behavior.
		else for(auto k : traits_type::keys(obj)) del(k);
	}

	bool contains(key_type key) {
		if constexpr(!MappingContains<T, Tag>) return traits_type::get(obj, key) != nullptr;

		else return traits_type::contains(obj, key);
	}

	// Match dict.update(): accept one mapping (via keys()), one iterable of
	// key/value pairs, and keyword arguments. Crucially, every assignment goes
	// through set(), so individual MappingTraits retain their conversion,
	// replacement, and proxy-cache behavior.
	void update(py::args args, py::kwargs kwargs) {
		if(args.size() > 1) throw py::type_error(
			"update expected at most 1 positional argument"
		);

		auto apply_pair = [this](py::handle key, py::handle value) {
			set(key.cast<key_type>(), py::reinterpret_borrow<py::object>(value));
		};

		if(args.size() == 1) {
			py::object other = py::reinterpret_borrow<py::object>(args[0]);

			if(py::hasattr(other, "keys")) {
				for(py::handle key : other.attr("keys")()) {
					apply_pair(key, other.attr("__getitem__")(key));
				}
			}

			else {
				for(py::handle item : other) {
					auto pair = py::reinterpret_borrow<py::sequence>(item);

					if(pair.size() != 2) throw py::value_error(
						"update sequence element does not have length 2"
					);

					apply_pair(pair[0], pair[1]);
				}
			}
		}

		for(auto item : kwargs) apply_pair(item.first, item.second);
	}

	py::list keys() {
		if constexpr(!MappingIterable<T, Tag>) throw py::type_error(
			"Mapping does not support key-based iteration"
		);

		else {
			py::list out;

			auto ks = traits_type::keys(obj);

			for(auto k : ks) out.append(k);

			return out;
		}
	}

	// TODO: Guard this (like the rest above)!
	py::list values() {
		py::list out;

		auto ks = traits_type::keys(obj);

		for(auto k : ks) {
			auto* ptr = traits_type::get(obj, k);

			out.append(base_type::get(k, ptr));
		}

		return out;
	}

	// TODO: Guard this (like the rest above)!
	py::list items() {
		py::list out;

		auto ks = traits_type::keys(obj);

		for(auto k : ks) {
			auto* ptr = traits_type::get(obj, k);

			out.append(py::make_tuple(k, base_type::get(k, ptr)));
		}

		return out;
	}

	struct Iterator {
		MappingProxy* proxy = nullptr;
		std::vector<key_type> keys;
		size_t index = 0;

		key_type next() {
			if(index >= keys.size()) throw py::stop_iteration();

			return keys[index++];
		}
	};

	Iterator iter() {
		return Iterator{this, traits_type::keys(obj), 0};
	}

	static auto bind(py::handle parent, const char* name) {
		using iterator_type = typename MappingProxy<T, Tag>::Iterator;

		auto mp = py::class_<MappingProxy<T, Tag>>(parent, name);

		py::class_<iterator_type>(mp, "Iterator")
			.def("__iter__", [](iterator_type& self) -> iterator_type& {
				return self;
			}, py::return_value_policy::reference_internal)
			.def("__next__", &iterator_type::next)
		;

		mp
			.def("__getitem__", py::overload_cast<key_type>(&MappingProxy<T, Tag>::get))
			.def("__setitem__", &MappingProxy<T, Tag>::set)
			.def("__delitem__", &MappingProxy<T, Tag>::del)
			.def("__contains__", &MappingProxy<T, Tag>::contains)
			.def("__iter__", &MappingProxy<T, Tag>::iter)
			.def("__len__", &MappingProxy<T, Tag>::size)
			.def("keys", &MappingProxy<T, Tag>::keys)
			.def("values", &MappingProxy<T, Tag>::values)
			.def("items", &MappingProxy<T, Tag>::items)
			.def("update", &MappingProxy<T, Tag>::update)
			.def(
				"get",
				py::overload_cast<key_type, py::object>(&MappingProxy<T, Tag>::get),
				"key"_a, "default"_a=py::none()
			)
			.def("pop", py::overload_cast<key_type, py::object>(&MappingProxy<T, Tag>::pop))
			.def("pop", py::overload_cast<key_type>(&MappingProxy<T, Tag>::pop))
			.def("clear", &MappingProxy<T, Tag>::clear)
			.def(
				"setdefault",
				&MappingProxy<T, Tag>::setdefault,
				"key"_a, "default"_a=py::none()
			)
		;

		return mp;
	}
};

// Defines how a C++ type behaves like a value mapping:
//
// - size / get / set / del / keys
// - plus conversion from Python
//
// This is the scalar-value counterpart to `MappingTraits`. It intentionally does not require
// `element_type` or pointer-valued `get()`, and `ValueMappingProxy` does not use `SlotCache`.
template<typename T, typename Tag=DEFAULT_PROXY_TAG>
struct ValueMappingTraits;

template<typename T, typename Tag=DEFAULT_PROXY_TAG>
concept ValueMappingTraitsConcept = requires(
	T* obj,
	typename ValueMappingTraits<T, Tag>::key_type key,
	py::handle h
) {
	typename ValueMappingTraits<T, Tag>::key_type;
	typename ValueMappingTraits<T, Tag>::value_type;

	{
		ValueMappingTraits<T, Tag>::from_python(h)
	} -> std::same_as<typename ValueMappingTraits<T, Tag>::value_type>;

	{ ValueMappingTraits<T, Tag>::size(obj) } -> std::convertible_to<size_t>;
	{
		ValueMappingTraits<T, Tag>::get(obj, key)
	} -> std::same_as<typename ValueMappingTraits<T, Tag>::value_type>;
	{ ValueMappingTraits<T, Tag>::keys(obj) };
};

template<typename T, typename Tag=DEFAULT_PROXY_TAG>
concept ValueMappingSettable = requires(
	T* obj,
	typename ValueMappingTraits<T, Tag>::key_type key,
	py::handle h
) {
	ValueMappingTraits<T, Tag>::set(
		obj,
		key,
		ValueMappingTraits<T, Tag>::from_python(h)
	);
};

template<typename T, typename Tag=DEFAULT_PROXY_TAG>
concept ValueMappingDeletable = requires(
	T* obj,
	typename ValueMappingTraits<T, Tag>::key_type key
) {
	ValueMappingTraits<T, Tag>::del(obj, key);
};

template<typename T, typename Tag=DEFAULT_PROXY_TAG>
concept ValueMappingIterable = requires(T* obj) {
	ValueMappingTraits<T, Tag>::keys(obj);
};

template<typename T, typename Tag=DEFAULT_PROXY_TAG>
concept ValueMappingContains = requires(
	T* obj,
	typename ValueMappingTraits<T, Tag>::key_type key
) {
	{ ValueMappingTraits<T, Tag>::contains(obj, key) } -> std::convertible_to<bool>;
};

template<typename T, typename Tag=DEFAULT_PROXY_TAG>
requires ValueMappingTraitsConcept<T, Tag>
struct PYOBJECT_INTERNAL ValueMappingProxy {
	using traits_type = ValueMappingTraits<T, Tag>;
	using key_type = typename traits_type::key_type;
	using value_type = typename traits_type::value_type;

	T* obj = nullptr;

	explicit ValueMappingProxy(): obj(nullptr) {}
	explicit ValueMappingProxy(T* o): obj(o) {}

	size_t size() const { return traits_type::size(obj); }

	value_type get(key_type key) {
		if(!contains(key)) throw py::key_error("key not found");

		return traits_type::get(obj, key);
	}

	// dict.get(key, default=None) -- see MappingProxy::get(key, default) for why this is a
	// separate overload rather than a default argument on get() above.
	py::object get(key_type key, py::object default_value) {
		if(!contains(key)) return default_value;

		return py::cast(traits_type::get(obj, key));
	}

	void set(key_type key, py::object py_obj) {
		if constexpr(!ValueMappingSettable<T, Tag>) throw py::type_error(
			"Mapping does not support assignment"
		);

		else {
			auto value = traits_type::from_python(py_obj);

			traits_type::set(obj, key, value);
		}
	}

	// dict.setdefault(key, default=None) -- see MappingProxy::setdefault for why a single
	// overload with a plain default argument is enough here.
	py::object setdefault(key_type key, py::object default_value) {
		if constexpr(!ValueMappingSettable<T, Tag>) throw py::type_error(
			"Mapping does not support assignment"
		);

		else {
			if(contains(key)) return py::cast(traits_type::get(obj, key));

			set(key, default_value);

			return py::cast(traits_type::get(obj, key));
		}
	}

	void del(key_type key) {
		if constexpr(!ValueMappingDeletable<T, Tag>) throw py::type_error(
			"Mapping does not support deletion"
		);

		else traits_type::del(obj, key);
	}

	// dict.pop(key): remove-and-return, raising KeyError if absent.
	value_type pop(key_type key) {
		if constexpr(!ValueMappingDeletable<T, Tag>) throw py::type_error(
			"Mapping does not support deletion"
		);

		else {
			auto result = get(key);

			del(key);

			return result;
		}
	}

	// dict.pop(key, default): same, but returns default instead of raising when absent. See
	// MappingProxy::pop(key, default) for why this is a second overload.
	py::object pop(key_type key, py::object default_value) {
		if constexpr(!ValueMappingDeletable<T, Tag>) throw py::type_error(
			"Mapping does not support deletion"
		);

		else {
			if(!contains(key)) return default_value;

			return py::cast(pop(key));
		}
	}

	void clear() {
		if constexpr(!ValueMappingDeletable<T, Tag> || !ValueMappingIterable<T, Tag>) {
			throw py::type_error("Mapping does not support deletion or key-based iteration");
		}

		// Snapshot keys() up front, same reasoning as MappingProxy::clear().
		else for(auto k : traits_type::keys(obj)) del(k);
	}

	bool contains(key_type key) {
		if constexpr(!ValueMappingContains<T, Tag>) {
			auto ks = traits_type::keys(obj);

			return std::find(ks.begin(), ks.end(), key) != ks.end();
		}

		else return traits_type::contains(obj, key);
	}

	py::list keys() {
		if constexpr(!ValueMappingIterable<T, Tag>) throw py::type_error(
			"Mapping does not support key-based iteration"
		);

		else {
			py::list out;

			auto ks = traits_type::keys(obj);

			for(auto k : ks) out.append(k);

			return out;
		}
	}

	py::list values() {
		if constexpr(!ValueMappingIterable<T, Tag>) throw py::type_error(
			"Mapping does not support key-based iteration"
		);

		else {
			py::list out;

			auto ks = traits_type::keys(obj);

			for(auto k : ks) out.append(traits_type::get(obj, k));

			return out;
		}
	}

	py::list items() {
		if constexpr(!ValueMappingIterable<T, Tag>) throw py::type_error(
			"Mapping does not support key-based iteration"
		);

		else {
			py::list out;

			auto ks = traits_type::keys(obj);

			for(auto k : ks) out.append(py::make_tuple(k, traits_type::get(obj, k)));

			return out;
		}
	}

	struct Iterator {
		ValueMappingProxy* proxy = nullptr;
		std::vector<key_type> keys;
		size_t index = 0;

		key_type next() {
			if(index >= keys.size()) throw py::stop_iteration();

			return keys[index++];
		}
	};

	Iterator iter() {
		return Iterator{this, traits_type::keys(obj), 0};
	}

	static auto bind(py::handle parent, const char* name) {
		using iterator_type = typename ValueMappingProxy<T, Tag>::Iterator;

		auto mp = py::class_<ValueMappingProxy<T, Tag>>(parent, name);

		py::class_<iterator_type>(mp, "Iterator")
			.def("__iter__", [](iterator_type& self) -> iterator_type& {
				return self;
			}, py::return_value_policy::reference_internal)
			.def("__next__", &iterator_type::next)
		;

		mp
			.def("__getitem__", py::overload_cast<key_type>(&ValueMappingProxy<T, Tag>::get))
			.def("__setitem__", &ValueMappingProxy<T, Tag>::set)
			.def("__delitem__", &ValueMappingProxy<T, Tag>::del)
			.def("__contains__", &ValueMappingProxy<T, Tag>::contains)
			.def("__iter__", &ValueMappingProxy<T, Tag>::iter)
			.def("__len__", &ValueMappingProxy<T, Tag>::size)
			.def("keys", &ValueMappingProxy<T, Tag>::keys)
			.def("values", &ValueMappingProxy<T, Tag>::values)
			.def("items", &ValueMappingProxy<T, Tag>::items)
			.def(
				"get",
				py::overload_cast<key_type, py::object>(&ValueMappingProxy<T, Tag>::get),
				"key"_a, "default"_a=py::none()
			)
			.def("pop", py::overload_cast<key_type, py::object>(&ValueMappingProxy<T, Tag>::pop))
			.def("pop", py::overload_cast<key_type>(&ValueMappingProxy<T, Tag>::pop))
			.def("clear", &ValueMappingProxy<T, Tag>::clear)
			.def(
				"setdefault",
				&ValueMappingProxy<T, Tag>::setdefault,
				"key"_a, "default"_a=py::none()
			)
		;

		return mp;
	}
};

// Wires a Sequence/Mapping/ValueMapping-style proxy onto its owning class in one call: binds the
// proxy's own (internal, `_`-prefixed by convention) Python type via `Proxy::bind()`, then exposes
// it as a read-only property that returns the per-object proxy instance out of `Storage`. This is
// the exact `Proxy::bind(cls, "_Name"); cls.def_property_readonly("name", [](Owner& self) -> Proxy&
// { return Storage::get(self)->template proxy<Proxy>(); }, py::return_value_policy::reference_
// internal);` pair that was previously hand-written at every proxy call site (Program.shaders/
// .bindAttribLocation/.bindFragDataLocation/.bindUniformBlock, StateSet.uniforms/.textureAttributes)
// -- `Proxy` can be any of `SequenceProxy`/`MappingProxy`/`ValueMappingProxy`, they all expose the
// same `::bind(py::handle, const char*)` static method this relies on.
template<typename Proxy, typename Owner, typename Storage, typename PyClass>
PyClass& bind_proxy_property(PyClass& cls, const char* internal_name, const char* property_name) {
	Proxy::bind(cls, internal_name);

	cls.def_property_readonly(property_name, [](Owner& self) -> Proxy& {
		return Storage::get(self)->template proxy<Proxy>();
	}, py::return_value_policy::reference_internal);

	return cls;
}

inline void build_info(py::module_ m, py::dict info) {
	m.def("build_info", [info]() {
		info["pybind"] = py::str("{}.{}.{}").format(
			PYBIND11_VERSION_MAJOR,
			PYBIND11_VERSION_MINOR,
			PYBIND11_VERSION_MICRO
		);

		info["date"] = __DATE__ " " __TIME__;

		info["compiler"] =
#ifdef __clang__
		"Clang " __clang_version__
#elif defined(__GNUC__)
		"GCC " __VERSION__
#elif defined(_MSC_VER)
		std::string("MSVC ") + std::to_string(_MSC_VER)
#else
		"Unknown compiler"
#endif
		;

		return info;
	});

	// return info;
}

// A cooperative cancellation flag: Python creates one, hands it to a C++ function running on a
// background thread (see put_nowait below), and can call stop() from the event-loop thread at any
// time. The C++ side must check stop.load() itself between units of work -- this cannot preemptively
// interrupt anything already in flight (e.g. a single blocking third-party library call).
//
// The py::class_ binding for this type must be registered in exactly ONE module's PYBIND11_MODULE
// block (currently OpenSceneGraph-python.cpp) -- pybind11 doesn't allow the same C++ type to be
// registered as a Python class twice across different extension modules loaded into one interpreter.
// Other modules (e.g. osgGLTF's) can still accept `StopEvent*`/`StopEvent&` as a parameter type in
// their own bound functions; pybind11 resolves it via that single existing registration at runtime.
struct StopEvent {
	std::atomic<bool> stop{false};
};

// Thread-safe bridge: schedules `queue.put_nowait((args...))` onto `loop` from whatever thread calls
// this (typically a C++ background thread with the GIL released). Re-acquires the GIL to touch the
// Python objects at all; `loop`/`queue` are a plain asyncio.AbstractEventLoop/asyncio.Queue handed in
// from Python -- call_soon_threadsafe is what makes this safe to call from a non-Python thread.
template<typename... Args>
inline void put_nowait(const py::object& loop, const py::object& queue, Args&&... args) {
	py::gil_scoped_acquire gil;

	loop.attr("call_soon_threadsafe")(
		queue.attr("put_nowait"),
		py::make_tuple(std::forward<Args>(args)...)
	);
}

}
