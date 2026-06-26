#pragma once

// One-line summaries of what you'll find in this file:
//
// SlotCache -> "Don't recreate Python objects unless the underlying pointer changed."
// ProxyStorage -> "Attach all Python views to the lifetime of the C++ object."
// PropertySlots -> "Make fields behave like stable Python attributes."
// SequenceProxy -> "Turn arbitrary C++ containers into Python lists."
// MappingProxy -> "Turn arbitrary C++ containers into Python dicts."
// Traits -> "Define behavior once, reuse everywhere."
// build_info -> Injects "common" Python compiler information, merged with a user-defined dict

#include "pybind11/pybind11.h"
#include "pybind11/stl.h"
#include "pybind11/stl_bind.h"
#include "pybind11/operators.h"
#include "pybind11/embed.h"

#include <algorithm>

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
		if (++counter % 64 == 0) {
			for (auto it = reg.begin(); it != reg.end(); ) {
				if (it->second.weak.expired()) it = reg.erase(it);
				else ++it;
			}
		}

		auto it = reg.find(key);

		if (it != reg.end()) {
			if (it->second.weak.lock()) return it->second.storage.get();
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

			base_type::set(i, py_obj, ptr);
		}
	}

	void del(py::ssize_t index) {
		if constexpr(!SequenceDeletable<T, Tag>) throw py::type_error(
			"Sequence does not support deletion"
		);

		else {
			auto i = n_index(size(), index);

			traits_type::del(obj, i);

			for (auto j = i; j < size(); j++) base_type::erase(j);
		}
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

	bool contains(py::object py_obj) {
		if(py_obj.is_none()) return false;

		auto* ptr = py_obj.cast<element_type*>();

		for(size_t i = 0; i < size(); i++) {
			if(traits_type::get(obj, i) == ptr) {
				return true;
			}
		}

		return false;
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

	void del(key_type key) {
		if constexpr(!MappingDeletable<T, Tag>) throw py::type_error(
			"Mapping does not support deletion"
		);

		else {
			traits_type::del(obj, key);

			base_type::erase(key);
		}
	}

	bool contains(key_type key) {
		if constexpr(!MappingContains<T, Tag>) return traits_type::get(obj, key) != nullptr;

		else return traits_type::contains(obj, key);
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
			.def("__getitem__", &MappingProxy<T, Tag>::get)
			.def("__setitem__", &MappingProxy<T, Tag>::set)
			.def("__delitem__", &MappingProxy<T, Tag>::del)
			.def("__contains__", &MappingProxy<T, Tag>::contains)
			.def("__iter__", &MappingProxy<T, Tag>::iter)
			.def("__len__", &MappingProxy<T, Tag>::size)
			.def("keys", &MappingProxy<T, Tag>::keys)
			.def("values", &MappingProxy<T, Tag>::values)
			.def("items", &MappingProxy<T, Tag>::items)
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

	void set(key_type key, py::object py_obj) {
		if constexpr(!ValueMappingSettable<T, Tag>) throw py::type_error(
			"Mapping does not support assignment"
		);

		else {
			auto value = traits_type::from_python(py_obj);

			traits_type::set(obj, key, value);
		}
	}

	void del(key_type key) {
		if constexpr(!ValueMappingDeletable<T, Tag>) throw py::type_error(
			"Mapping does not support deletion"
		);

		else traits_type::del(obj, key);
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
			.def("__getitem__", &ValueMappingProxy<T, Tag>::get)
			.def("__setitem__", &ValueMappingProxy<T, Tag>::set)
			.def("__delitem__", &ValueMappingProxy<T, Tag>::del)
			.def("__contains__", &ValueMappingProxy<T, Tag>::contains)
			.def("__iter__", &ValueMappingProxy<T, Tag>::iter)
			.def("__len__", &ValueMappingProxy<T, Tag>::size)
			.def("keys", &ValueMappingProxy<T, Tag>::keys)
			.def("values", &ValueMappingProxy<T, Tag>::values)
			.def("items", &ValueMappingProxy<T, Tag>::items)
		;

		return mp;
	}
};

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

}
