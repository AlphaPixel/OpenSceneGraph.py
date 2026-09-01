#!/usr/bin/env python3

"""Regenerates OVERVIEW.md: a checklist of every pybind11 symbol exposed under pyosg/, grouped
by binding source file, with each symbol's documentation status checked LIVE against a built
OpenSceneGraph module -- not by trusting how the C++ source looks, but by importing the real
compiled module and asking whether pybind11 actually attached a docstring beyond its own
auto-generated signature line.

This file's own job is just extraction (find every py::class_/py::enum_/.def*()/.attr() call
and the name it exposes) -- it does not attempt to be a real C++ parser, and it will occasionally
mis-read something unusual. When that happens the affected symbol shows up as "not found at
runtime" in the output rather than silently vanishing, which is the signal to go fix the scanner
or the binding, whichever is wrong.

Usage:
	generate-bindings-overview.py [--source-dir DIR] [--build-dir DIR] [--output FILE] [--module NAME]

--build-dir defaults to the newest BUILD-*/ directory (checked from the repo root) that has an
importable --module package/extension sitting in it.

--module (default "OpenSceneGraph") is the top-level module imported and checked against. A
binding-file heading is normally resolved as an attribute of that module by name (osg/Camera ->
native.osg, osgAnimation -> native.osgAnimation, ...), which is how OpenSceneGraph.py's own
per-submodule pyosg/ layout works. A project whose binding files are instead named
"<module>-topic.cpp" but bind most of "topic" flat onto the module's own top level (osgx et al.)
gets a fallback: if "topic" isn't itself a real submodule, the whole group resolves against
--module directly instead of reporting everything in it as missing.
"""

from __future__ import annotations

import argparse
import importlib
import inspect
import re
import sys

from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_SOURCE_DIR = REPO_ROOT / "pyosg"
DEFAULT_OUTPUT = REPO_ROOT / "OVERVIEW.md"

# pybind11 registration methods that appear chained off a py::class_/py::enum_ (or free-standing
# off a py::module_ variable, for module-level functions/attrs). ".attr(" is handled separately
# below since it's an assignment target, not a call whose return value keeps chaining.
CHAIN_METHODS = (
	"def_static",
	"def_property_readonly",
	"def_property",
	"def_readwrite",
	"def_readonly",
	"def",
	"value",
)

CHILD_KIND_BY_METHOD = {
	"def": "method",
	"def_static": "static_method",
	"def_property": "property",
	"def_property_readonly": "property_readonly",
	"def_readwrite": "field",
	"def_readonly": "field_readonly",
	"value": "enum_value",
}

LABELS = {
	"class": "class",
	"enum": "enum",
	"enum_value": "enum value",
	"method": "method",
	"static_method": "static method",
	"property": "property",
	"property_readonly": "readonly property",
	"field": "field",
	"field_readonly": "readonly field",
	"constructor": "constructor",
	"function": "function",
	"module_property": "module property",
	"attr": "constant",
}

# Symbol kinds whose runtime __doc__ pybind11 auto-populates with a signature line even when no
# real docstring was passed -- these need signature_only() rather than a plain truthiness check.
SIGNATURE_METHOD_KINDS = {"method", "static_method", "constructor", "function"}

# Kinds with no meaningful per-symbol docstring to check at all (an enum value or a raw GL
# constant has nothing pybind11-doc-shaped to attach a real explanation to).
NOT_APPLICABLE_KINDS = {"enum_value", "attr"}

STRING_RE = re.compile(r'"(?:[^"\\]|\\.)*"')
DECL_RE = re.compile(r'(?:auto\s+(\w+)\s*=\s*)?py::(class_|enum_)\s*<')
CHAIN_CALL_RE = re.compile(r'\.(\w+)\s*\(')
# pyx::bind_proxy_property<Proxy, Owner, Storage>(owner_var, "_Internal", "public") -- etc/
# pybind11x.hpp's free-function equivalent of `.def_property_readonly(...)`, used throughout
# pyosg/ for every Sequence/Mapping-proxied member (Geode.drawables, Group.children, ...). It
# never appears as a chained `.method()` call, so it needs its own scan -- see scan_text().
BIND_PROXY_PROPERTY_RE = re.compile(r"pyx::bind_proxy_property\s*<")
# A `template<typename T> auto bind_XXX(py::module_& m, const char* name) { py::class_<T>(m,
# name)...` helper (osg/Matrix.hpp, osg/Vec.hpp, osg/Bound.hpp, osg/Array.hpp,
# pyosgAnimation.cpp's bind_Motion<T>) builds its py::class_/enum_ using a runtime PARAMETER as
# the exposed name, not a string literal -- DECL_RE's first_name_literal() finds nothing there, so
# without this, the whole templated family silently vanishes from the checklist (this is exactly
# what happened to Matrix/Vec/Bound/Array and all 29 osgAnimation ...Motion classes). Resolving it
# takes two regexes: this one finds the helper's OWN signature (to walk its body and capture its
# member list under a placeholder), and TEMPLATE_BINDER_CALL_RE below finds each call site that
# instantiates it with a real type + literal name -- see scan_template_binders().
TEMPLATE_BINDER_SIG_RE = re.compile(
	r"(?:auto|void)\s+(\w+)\s*\(\s*py::module_&\s*\w+\s*,\s*const\s+char\s*\*\s*(\w+)"
)
TEMPLATE_BINDER_CALL_RE = re.compile(r"\b(?:detail::)?(\w+)\s*<[^<>]*>\s*\(")
# Reopened fluent chains normally put the owner and `.def*()` on separate lines, e.g.
# `quat\n\t.def_property(...)`, so whitespace is allowed on both sides of the dot.
MODULE_CALL_RE = re.compile(
	r'\b(\w+)\s*\.\s*(def_static|def_property_readonly|def_property|def_readwrite|def_readonly|def)\s*\('
)
ATTR_ASSIGN_RE = re.compile(r'\b(\w+)\.attr\(\s*"([^"]+)"\s*\)\s*=')
# `auto VAR = OTHER.def_submodule("name", ...)` -- a nested py::module_ a binding file creates for
# itself (osgx-gltf.cpp's `m_gltf_shader`/`m_gltf_pbribl`, off the `m_gltf` parameter). Recorded so
# render_group() can walk VAR back to a real attribute path off the group's own resolved base
# module, instead of only ever recognizing symbols bound directly on that base -- see scan_text()'s
# `submodules` return and resolve_submodule_chain() below.
SUBMODULE_DECL_RE = re.compile(r'(?:auto\s+)?(\w+)\s*=\s*(\w+)\s*\.\s*def_submodule\s*\(\s*"([^"]+)"')

# OpenSceneGraph-python.cpp is the one file that binds directly onto several different
# py::module_ variables in the same source (the root module `m`, plus each submodule it creates)
# -- everywhere else, whatever identifier a chain is built on always means "this file's own
# module", so this map is only consulted for that one heading. See scan_text()'s `owners` return.
ROOT_OWNER_SUBMODULE = {
	"gl": ("GL",),
	"osg": ("osg",),
	"osgAnimation": ("osgAnimation",),
	"osgUtil": ("osgUtil",),
	"osgDB": ("osgDB",),
	"osgGA": ("osgGA",),
	"osgViewer": ("osgViewer",),
}


@dataclass
class Symbol:
	kind: str
	name: str
	children: list["Symbol"] = field(default_factory=list)


# ------------------------------------------------------------------------------------------------
# Bracket-aware text scanning -- deliberately not a real C++ parser. Just enough to walk past
# nested (...)/{...} (lambdas passed to .def_property_readonly(), etc.) and string literals
# without losing track of which top-level ";" actually ends a fluent binding chain.
# ------------------------------------------------------------------------------------------------

def skip_string(text: str, i: int) -> int:
	"""text[i] == '"'; returns the index just past the matching close quote."""

	i += 1

	while i < len(text):
		if text[i] == "\\":
			i += 2
			continue
		if text[i] == '"':
			return i + 1
		i += 1

	return i


def find_matching(text: str, open_index: int, open_ch: str, close_ch: str, skip_strings: bool) -> int:
	"""text[open_index] == open_ch; returns the index just past its matching close_ch."""

	depth = 0
	i = open_index

	while i < len(text):
		c = text[i]

		if skip_strings and c == '"':
			i = skip_string(text, i)
			continue
		if c == open_ch:
			depth += 1
		elif c == close_ch:
			depth -= 1
			if depth == 0:
				return i + 1

		i += 1

	return i


def find_chain_end(text: str, start: int) -> int:
	"""Finds the top-level ';' terminating a py::class_/py::enum_ fluent chain, starting just
	after its constructor call's closing ')'. Tracks (), [], {} depth and skips string literals
	so a ';' inside a lambda body or a docstring can't end the chain early."""

	depth = 0
	i = start

	while i < len(text):
		c = text[i]

		if c == '"':
			i = skip_string(text, i)
			continue
		if c in "([{":
			depth += 1
		elif c in ")]}":
			depth -= 1
		elif c == ";" and depth == 0:
			return i

		i += 1

	return len(text)


def strip_comments(text: str) -> str:
	"""Removes // and /* */ comments (string literals are left alone) so commented-out binding
	code doesn't get scanned as if it were real."""

	out = []
	i = 0
	n = len(text)

	while i < n:
		c = text[i]

		if c == '"':
			j = skip_string(text, i)
			out.append(text[i:j])
			i = j
			continue
		if text[i:i + 2] == "//":
			j = text.find("\n", i)
			i = j if j != -1 else n
			continue
		if text[i:i + 2] == "/*":
			j = text.find("*/", i + 2)
			i = j + 2 if j != -1 else n
			continue

		out.append(c)
		i += 1

	return "".join(out)


def first_name_literal(arg_text: str) -> str | None:
	"""The first quoted string in `arg_text` that isn't a pybind11 keyword-argument literal (one
	immediately followed by `_a`, e.g. "needed"_a=true) -- in every real binding call this
	codebase writes, that's always the symbol's exposed Python name."""

	for m in STRING_RE.finditer(arg_text):
		if arg_text[m.end():m.end() + 2] == "_a":
			continue
		return m.group(0)[1:-1]

	return None


def first_identifier(text: str) -> str | None:
	m = re.match(r"\s*(\w+)", text)
	return m.group(1) if m else None


def second_positional_is_literal(ctor_args: str) -> bool:
	"""True if the argument right after the first top-level comma in a py::class_/enum_ call's
	ctor_args (the exposed-name slot, right after the module/owner argument) is ITSELF a quoted
	string literal -- distinguishes a normal `py::class_<T>(m, "Name", ...)` from a templated
	`py::class_<T>(m, name_param, ...)` whose own docstring (a real literal appearing LATER in the
	same arg list) would otherwise fool a plain "is there any literal in here" check."""

	depth = 0
	i = 0
	n = len(ctor_args)

	while i < n:
		c = ctor_args[i]

		if c == '"':
			i = skip_string(ctor_args, i)
			continue
		if c in "([{<":
			depth += 1
		elif c in ")]}>":
			depth -= 1
		elif c == "," and depth == 0:
			break

		i += 1

	j = i + 1

	while j < n and ctor_args[j].isspace():
		j += 1

	return j < n and ctor_args[j] == '"'


def scan_chain_calls(text: str, start: int, end: int) -> list[tuple[str, str | None, str]]:
	"""Finds each top-level `.method(...)` call within text[start:end] (one binding chain's
	body), returning (method_name, exposed_name_or_None, raw_arg_text). Nested (), lambda {}
	bodies, and string literals inside an argument list are consumed as one unit via
	find_matching(), so they never get misread as chain calls of their own."""

	calls = []
	i = start

	while i < end:
		c = text[i]

		if c == '"':
			i = skip_string(text, i)
			continue
		if c == ".":
			m = CHAIN_CALL_RE.match(text, i, end)

			if m and m.group(1) in CHAIN_METHODS:
				call_open = m.end() - 1
				call_close = find_matching(text, call_open, "(", ")", skip_strings=True)
				arg_text = text[call_open + 1:call_close - 1]
				method = m.group(1)

				if method == "def" and arg_text.lstrip().startswith("py::init"):
					calls.append(("def", "__init__", arg_text))
				else:
					calls.append((method, first_name_literal(arg_text), arg_text))

				i = call_close
				continue

		i += 1

	return calls


def scan_template_binders(text: str) -> dict[str, Symbol]:
	"""Returns {function_name: Symbol} for every `bind_XXX(py::module_& m, const char* name)`
	template helper found in `text` (see TEMPLATE_BINDER_SIG_RE) -- one Symbol per helper, holding
	the member list from that helper's OWN py::class_/py::enum_ declaration (matched against
	`name` used as the exposed-name argument), under a placeholder name since there's no single
	real Python name at the declaration site.

	A helper with no py::class_/enum_ of its own (bind_alias_Vec: it just forwards to bind_Vec and
	aliases the result via m.add_object) is instead aliased onto whichever OTHER already-scanned
	template helper it calls with its own (module, name) parameters forwarded unchanged -- found
	via a second TEMPLATE_BINDER_CALL_RE scan of its body."""

	templates: dict[str, Symbol] = {}
	forwarding: list[tuple[str, str]] = []  # (this helper's name, body text) still unresolved

	for sig in TEMPLATE_BINDER_SIG_RE.finditer(text):
		func_name, name_param = sig.group(1), sig.group(2)
		body_open = text.find("{", sig.end())

		if body_open == -1:
			continue

		body_close = find_matching(text, body_open, "{", "}", skip_strings=True)
		body = text[body_open:body_close]
		found_own_decl = False

		for decl in DECL_RE.finditer(body):
			decl_kind = decl.group(2)
			angle_close = find_matching(body, decl.end() - 1, "<", ">", skip_strings=False)
			paren_open = body.find("(", angle_close)

			if paren_open == -1:
				continue

			paren_close = find_matching(body, paren_open, "(", ")", skip_strings=True)
			ctor_args = body[paren_open + 1:paren_close - 1]
			args = ctor_args.split(",", 2)

			# Only a py::class_/enum_ built directly on THIS helper's own `name` parameter (as its
			# 2nd ctor arg -- the module is always 1st) counts; anything else in the body (e.g. a
			# nested-type declaration built on a different variable) isn't what we're after.
			if len(args) < 2 or args[1].strip() != name_param:
				continue

			var_name = decl.group(1)
			chain_end = find_chain_end(body, paren_close)
			symbol = Symbol("class" if decl_kind == "class_" else "enum", f"<template:{func_name}>")
			children_by_name: dict[str, Symbol] = {}

			for method, cname, _arg in scan_chain_calls(body, paren_close, chain_end):
				if cname is None:
					continue

				kind = "constructor" if cname == "__init__" else CHILD_KIND_BY_METHOD[method]
				children_by_name[cname] = Symbol(kind, cname)

			# Follow reopened chains on the same local variable -- e.g. Matrix.hpp's
			# `if constexpr(...) mat.def(...)` and its later `mat\n\t.def_static(...)...` block, or
			# Vec.hpp's conditional `vec.def_property("z", ...)` sections -- exactly like
			# MODULE_CALL_RE's handling of reopened chains on a module-level var in scan_text()
			# below, just scoped to this helper's own body and its own local var.
			if var_name:
				for m in MODULE_CALL_RE.finditer(body):
					if m.group(1) != var_name:
						continue

					reopen_open = m.end() - 1
					reopen_close = find_matching(body, reopen_open, "(", ")", skip_strings=True)
					reopen_end = find_chain_end(body, reopen_close)

					for method, cname, arg_text in scan_chain_calls(body, m.start(), reopen_end):
						if method == "def" and arg_text.lstrip().startswith("py::init"):
							cname = "__init__"

						if cname is None:
							continue

						kind = "constructor" if cname == "__init__" else CHILD_KIND_BY_METHOD[method]
						children_by_name[cname] = Symbol(kind, cname)

			symbol.children = list(children_by_name.values())
			templates[func_name] = symbol
			found_own_decl = True
			break

		if not found_own_decl:
			forwarding.append((func_name, body))

	for func_name, body in forwarding:
		for call in TEMPLATE_BINDER_CALL_RE.finditer(body):
			target = templates.get(call.group(1))

			if target is not None:
				templates[func_name] = target
				break

	return templates


def scan_text(text: str) -> tuple[list[Symbol], dict[str, str], dict[str, tuple[str, str]]]:
	"""Returns (top_level_symbols, owner_by_name, submodule_by_var). `owner_by_name` records, for
	each top-level symbol, the C++ identifier its binding call was made on -- meaningless for most
	files (every chain there is built on the same module variable), but needed for
	OpenSceneGraph-python.cpp, which binds directly onto several different py::module_ variables in
	one file. `submodule_by_var` records, for each local `auto VAR = OTHER.def_submodule("name",
	...)`, the (OTHER, "name") it was declared with -- see SUBMODULE_DECL_RE."""

	text = strip_comments(text)
	symbols: list[Symbol] = []
	owners: dict[str, str] = {}
	submodules: dict[str, tuple[str, str]] = {}
	var_to_symbol: dict[str, Symbol] = {}
	consumed: list[tuple[int, int]] = []

	for m in SUBMODULE_DECL_RE.finditer(text):
		submodules[m.group(1)] = (m.group(2), m.group(3))

	for decl in DECL_RE.finditer(text):
		var_name, decl_kind = decl.group(1), decl.group(2)
		angle_close = find_matching(text, decl.end() - 1, "<", ">", skip_strings=False)
		paren_open = text.find("(", angle_close)

		if paren_open == -1:
			continue

		# Direct-initialization idiom (osgx's own style): `> varname(m, "Name")`, with no `auto
		# varname =` prefix for DECL_RE to have captured. Whatever sits between the declaration's
		# closing '>' and its constructor call's opening '(' is that variable name, if anything.
		if var_name is None:
			direct_init = re.match(r"\s*(\w+)\s*$", text[angle_close:paren_open])

			if direct_init:
				var_name = direct_init.group(1)

		paren_close = find_matching(text, paren_open, "(", ")", skip_strings=True)
		chain_end = find_chain_end(text, paren_close)

		# Recorded even when this declaration turns out to be unreadable below (e.g. a
		# templated bind_VecT<T>(m, name) where `name` is a runtime const char*, not a string
		# literal) -- otherwise its chained .def*() calls stay unconsumed and leak out as bogus
		# module-level symbols in the free-function pass further down.
		consumed.append((paren_close, chain_end))

		ctor_args = text[paren_open + 1:paren_close - 1]

		if not second_positional_is_literal(ctor_args):
			# A templated bind_XT<T>(m, name) call (see osg/Vec.hpp): `name` is a runtime const
			# char*, so there's no static Python name to report -- even though a LATER argument
			# in this same call might be a real string literal (this helper's own docstring, or
			# py::buffer_protocol()'s neighbors), which is exactly why this checks the exposed-name
			# ARGUMENT POSITION specifically rather than "is there any literal anywhere in
			# ctor_args" (first_name_literal() alone would wrongly grab that docstring as the
			# name). Still register a placeholder under `var_name` so later reopened statements
			# like `vec.def_property("x", ...)` attach to IT instead of leaking out as bogus
			# module-level symbols below -- but never add the placeholder itself to `symbols`, so
			# this whole unnameable family is silently excluded from the checklist rather than
			# shown under a fabricated name.
			if var_name:
				var_to_symbol[var_name] = Symbol("class" if decl_kind == "class_" else "enum", "<templated>")

			continue

		exposed_name = first_name_literal(ctor_args)
		symbol = Symbol("class" if decl_kind == "class_" else "enum", exposed_name)

		children_by_name: dict[str, Symbol] = {}

		for method, name, _arg_text in scan_chain_calls(text, paren_close, chain_end):
			if name is None:
				continue

			kind = "constructor" if name == "__init__" else CHILD_KIND_BY_METHOD[method]

			children_by_name[name] = Symbol(kind, name)

		symbol.children = list(children_by_name.values())

		# A class_/enum_ constructed on a variable that already holds another class (e.g.
		# `py::class_<...>(gc, "Traits")`, where `gc` is GraphicsContext's own class_ variable)
		# is a nested C++ type bound as a nested Python attribute -- not a module-level symbol.
		owner = first_identifier(ctor_args)

		if owner in var_to_symbol:
			var_to_symbol[owner].children.append(symbol)
		else:
			symbols.append(symbol)
			owners[exposed_name] = owner or ""

		if var_name:
			var_to_symbol[var_name] = symbol

	# Only the SECOND string argument (the public name) is a real Python-visible symbol here --
	# the first is `bind_proxy_property`'s internal implementation-detail name, and an optional
	# third string is its docstring.
	for m in BIND_PROXY_PROPERTY_RE.finditer(text):
		angle_close = find_matching(text, m.end() - 1, "<", ">", skip_strings=False)
		paren_open = text.find("(", angle_close)

		if paren_open == -1:
			continue

		paren_close = find_matching(text, paren_open, "(", ")", skip_strings=True)
		call_args = text[paren_open + 1:paren_close - 1]
		names = [
			literal.group(0)[1:-1]
			for literal in STRING_RE.finditer(call_args)
			if call_args[literal.end():literal.end() + 2] != "_a"
		]

		if len(names) < 2:
			continue

		owner = first_identifier(call_args)
		proxy_symbol = Symbol("property_readonly", names[1])

		if owner in var_to_symbol:
			var_to_symbol[owner].children.append(proxy_symbol)
		else:
			symbols.append(proxy_symbol)
			owners[names[1]] = owner or ""

	def is_consumed(pos: int) -> bool:
		return any(s <= pos < e for s, e in consumed)

	for m in MODULE_CALL_RE.finditer(text):
		if is_consumed(m.start()):
			continue

		# A reopened fluent chain has an owner only before its first call:
		# `opts\n\t.def(...)\n\t.def_property(...)`. Walk the complete chain here rather
		# than treating that first call as a standalone registration.
		call_open = m.end() - 1
		call_close = find_matching(text, call_open, "(", ")", skip_strings=True)
		chain_end = find_chain_end(text, call_close)
		owner_var = m.group(1)

		for method, name, arg_text in scan_chain_calls(text, m.start(), chain_end):
			if method == "def" and arg_text.lstrip().startswith("py::init"):
				name = "__init__"

			if name is None:
				continue

			if owner_var in var_to_symbol:
				kind = "constructor" if name == "__init__" else CHILD_KIND_BY_METHOD[method]
				symbol = Symbol(kind, name)
				var_to_symbol[owner_var].children.append(symbol)
			else:
				kind = "function" if method in ("def", "def_static") else "module_property"
				symbol = Symbol(kind, name)
				symbols.append(symbol)
				owners[name] = owner_var

	for m in ATTR_ASSIGN_RE.finditer(text):
		if is_consumed(m.start()):
			continue

		owner_var, name = m.group(1), m.group(2)
		symbol = Symbol("attr", name)

		if owner_var in var_to_symbol:
			var_to_symbol[owner_var].children.append(symbol)
		else:
			symbols.append(symbol)
			owners[name] = owner_var

	# Re-emit each templated bind_XXX(module, name) helper's member list under every call site's
	# real literal name -- see scan_template_binders(). A call passing more than one string literal
	# (bind_alias_Vec<T, N>(m, "Vec2f", "Vec2")) only exposes the FIRST as a distinct Python object;
	# any literal after it is just an `m.add_object(alias, ...)` alias for the SAME object, not a
	# second symbol worth its own checklist entry.
	templates = scan_template_binders(text)

	for call in TEMPLATE_BINDER_CALL_RE.finditer(text):
		template = templates.get(call.group(1))

		if template is None:
			continue

		call_open = call.end() - 1
		call_close = find_matching(text, call_open, "(", ")", skip_strings=True)
		call_args = text[call_open + 1:call_close - 1]
		exposed_name = first_name_literal(call_args)

		if exposed_name is None:
			continue

		symbol = Symbol(template.kind, exposed_name)
		symbol.children = template.children
		symbols.append(symbol)
		owners[exposed_name] = first_identifier(call_args) or ""

	return symbols, owners, submodules


# ------------------------------------------------------------------------------------------------
# File-group discovery -- osg/ is the only per-class-file subdir today (see CLAUDE.md), so it
# gets one heading per file stem ("osg/Object", "osg/Camera", ...); every other flat
# pyosgX.{cpp,hpp} pair collapses to a single "osgX" heading.
# ------------------------------------------------------------------------------------------------

def discover_groups(source_dir: Path) -> dict[str, list[Path]]:
	groups: dict[str, list[Path]] = {}

	for path in sorted((source_dir / "osg").glob("*.[hc]pp")):
		groups.setdefault(f"osg/{path.stem}", []).append(path)

	for path in sorted(source_dir.glob("*.[hc]pp")):
		stem = path.stem

		if stem == "pyosg":
			heading = "osg"
		elif stem.startswith("pyosg"):
			heading = "osg" + stem[len("pyosg"):]
		else:
			heading = stem

		groups.setdefault(heading, []).append(path)

	return groups


# ------------------------------------------------------------------------------------------------
# Runtime doc-status -- the actual point of this script. A missing symbol (AttributeError) means
# either the scanner mis-read the source, or this build has it compiled out (#ifdef-gated); both
# are worth a human looking, so it's reported rather than silently dropped.
# ------------------------------------------------------------------------------------------------

def signature_only(doc: str | None, name: str) -> bool:
	if not doc:
		return True

	pattern = re.compile(rf"^(\d+\.\s*)?{re.escape(name)}\(.*\)(\s*->\s*.*)?$")
	remaining = [
		stripped
		for stripped in (line.strip() for line in doc.splitlines())
		if stripped and stripped != "Overloaded function." and not pattern.match(stripped)
	]

	return len(remaining) == 0


def enum_auto_only(doc: str | None) -> bool:
	"""pybind11 auto-appends a "Members:\\n\\n  NAME\\n\\n  NAME..." listing to every enum's
	__doc__ regardless of whether a real docstring was passed -- a real docstring, when one was
	given, always comes BEFORE that marker, so anything present only at/after it is boilerplate,
	not documentation (mirrors signature_only() below, same auto-generated-content trap)."""

	if not doc:
		return True

	return not doc.split("Members:", 1)[0].strip()


def doc_status(resolved: object, kind: str, name: str) -> str:
	if kind in NOT_APPLICABLE_KINDS:
		return "n/a"

	doc = getattr(resolved, "__doc__", None)

	if kind in SIGNATURE_METHOD_KINDS:
		return "sparse" if signature_only(doc, name) else "documented"
	if kind == "enum":
		return "sparse" if enum_auto_only(doc) else "documented"

	return "documented" if doc and doc.strip() else "sparse"


def render_symbol(
	lines: list[str],
	base: object,
	symbol: Symbol,
	depth: int,
	stats: list[int],
	checklist_only: bool
) -> None:
	# --checklist-only drops kinds that never get a checkbox in the first place (enum VALUES,
	# raw GL-style constants) -- an enum's own TYPE line stays (it has real doc-status), only
	# its NOT_APPLICABLE_KINDS members are skipped. Checked by kind alone, before any runtime
	# lookup, so it applies whether or not the symbol even resolves.
	skip_line = checklist_only and symbol.kind in NOT_APPLICABLE_KINDS

	indent = "  " * depth
	label = LABELS.get(symbol.kind, symbol.kind)

	# base is None once ANY ancestor failed to resolve. Every Python object -- including None
	# itself -- has a real, documented __init__, so getattr(None, "__init__") would silently
	# "succeed" here rather than raising, and a whole missing subtree would misreport its
	# constructors as documented. Short-circuit before that trap instead of relying on
	# AttributeError to catch it.
	if base is None:
		if not skip_line:
			lines.append(f"{indent}- [!] `{symbol.name}` ({label}) -- not found at runtime")

		for child in symbol.children:
			render_symbol(lines, None, child, depth + 1, stats, checklist_only)

		return

	try:
		resolved = getattr(base, "__init__") if symbol.kind == "constructor" else getattr(base, symbol.name)
	except AttributeError:
		if not skip_line:
			lines.append(f"{indent}- [!] `{symbol.name}` ({label}) -- not found at runtime")

		resolved = None
		child_base = None
	else:
		status = doc_status(resolved, symbol.kind, symbol.name)

		if not skip_line:
			if status == "n/a":
				lines.append(f"{indent}- `{symbol.name}` ({label})")
			else:
				stats[0] += 1
				stats[1] += status == "documented"
				lines.append(f"{indent}- [{'x' if status == 'documented' else ' '}] `{symbol.name}` ({label})")

		child_base = base if symbol.kind == "constructor" else resolved

	for child in symbol.children:
		render_symbol(lines, child_base, child, depth + 1, stats, checklist_only)


def resolve_submodule_chain(owner_var: str, submodules: dict[str, tuple[str, str]]) -> list[str]:
	"""Walks `owner_var` back through consecutive local `def_submodule()` declarations (see
	SUBMODULE_DECL_RE) to the first ancestor that ISN'T itself one -- that ancestor is assumed to
	be whatever the caller already resolved as the group's own base module. Returns the chain of
	submodule names to `getattr()` through, in parent-to-child order (usually just one name; a
	multi-level chain isn't exercised by any file today but falls out of the same walk)."""

	names: list[str] = []
	var = owner_var
	seen: set[str] = set()

	while var in submodules and var not in seen:
		seen.add(var)
		parent_var, name = submodules[var]
		names.append(name)
		var = parent_var

	names.reverse()

	return names


def render_group(
	heading: str,
	symbols: list[Symbol],
	owners: dict[str, str],
	submodules: dict[str, tuple[str, str]],
	native,
	module: str,
	checklist_only: bool
) -> tuple[list[str], tuple[int, int]]:
	lines: list[str] = []
	stats = [0, 0]

	for symbol in symbols:
		if heading == "OpenSceneGraph-python":
			submodule_path = ROOT_OWNER_SUBMODULE.get(owners.get(symbol.name, ""), ())
			base = native

			for part in submodule_path:
				base = getattr(base, part, None)
				if base is None:
					break
		else:
			base = getattr(native, heading.split("/", 1)[0], None)

			# "<module>-topic.cpp" naming (osgx et al.) with most groups bound flat onto the
			# module's own top level rather than a real "topic" submodule -- try the stripped
			# topic name as a submodule first, otherwise the group's symbols live on `native`
			# itself. Gated on the "<module>-" prefix so OpenSceneGraph.py's own headings (none
			# of which start with "OpenSceneGraph-") never take this path -- unchanged behavior.
			if base is None and heading.startswith(f"{module}-"):
				candidate = getattr(native, heading[len(module) + 1:], None)

				base = candidate if inspect.ismodule(candidate) else native

			# A symbol bound on a submodule the file created for itself via def_submodule() (e.g.
			# osgx-gltf.cpp's `m_gltf_pbribl`) lives one or more attribute levels deeper than
			# `base` -- walk the chain SUBMODULE_DECL_RE recorded rather than reporting it missing.
			for part in resolve_submodule_chain(owners.get(symbol.name, ""), submodules):
				if base is None:
					break

				base = getattr(base, part, None)

		render_symbol(lines, base, symbol, 0, stats, checklist_only)

	return lines, (stats[0], stats[1])


# ------------------------------------------------------------------------------------------------

def _module_available(build_dir: Path, module: str) -> bool:
	"""True if `module` looks importable from build_dir -- either a real package directory
	(OpenSceneGraph/__init__.py) or a single compiled extension module (osgx.cpython-*.so)."""

	if (build_dir / module / "__init__.py").exists():
		return True

	return any(build_dir.glob(f"{module}.*.so")) or any(build_dir.glob(f"{module}.pyd"))


def find_default_build_dir(module: str) -> Path | None:
	for candidate in sorted(REPO_ROOT.glob("BUILD-*"), reverse=True):
		if _module_available(candidate, module):
			return candidate

	return None


def main() -> None:
	parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)

	parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE_DIR)
	parser.add_argument("--build-dir", type=Path, default=None)
	parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
	parser.add_argument(
		"--module", default="OpenSceneGraph",
		help="Top-level module to import and check docstrings against (default: OpenSceneGraph)."
	)
	parser.add_argument(
		"--checklist-only", action="store_true",
		help="Drop entries that never get a checkbox (enum VALUES, raw constants) -- an enum's "
		"own type entry stays, only its members are dropped."
	)

	args = parser.parse_args()
	build_dir = args.build_dir or find_default_build_dir(args.module)

	if build_dir is None:
		raise SystemExit(
			f"No BUILD-*/{args.module} found under the repo root -- pass --build-dir explicitly."
		)

	sys.path.insert(0, str(build_dir))

	native = importlib.import_module(args.module)  # only importable once sys.path is set up

	groups = discover_groups(args.source_dir)
	rendered: list[tuple[str, list[str], tuple[int, int]]] = []

	for heading, paths in sorted(groups.items()):
		text = "\n".join(path.read_text() for path in paths)
		symbols, owners, submodules = scan_text(text)

		if not symbols:
			continue

		lines, stats = render_group(
			heading, symbols, owners, submodules, native, args.module, args.checklist_only
		)

		rendered.append((heading, lines, stats))

	total_symbols = sum(n for _, _, (n, _) in rendered)
	total_documented = sum(d for _, _, (_, d) in rendered)
	pct = (100.0 * total_documented / total_symbols) if total_symbols else 0.0

	out = [
		"# OVERVIEW.md",
		"",
		"Every pybind11 symbol exposed under `pyosg/`, grouped by binding source file. Each",
		"symbol's checkbox reflects its LIVE documentation status -- checked by importing a built",
		"`OpenSceneGraph` module and asking whether pybind11 attached a real docstring, not just",
		"whether the C++ source looks like it passed one. `[!]` means the scanner found a binding",
		"the running module doesn't have -- either a scanner misread, or this build has it",
		"compiled out; either way it's worth a look.",
		"",
		f"**Regenerated by `etc/scripts/generate-bindings-overview.py` -- do not hand-edit, rerun",
		f"the script instead.** {total_documented}/{total_symbols} symbols documented ({pct:.1f}%).",
		"",
	]

	for heading, lines, (n, documented) in rendered:
		out.append(f"## {heading} ({documented}/{n} documented)")
		out.append("")
		out.extend(lines)
		out.append("")

	args.output.write_text("\n".join(out).rstrip() + "\n")

	print(f"Wrote {args.output} -- {total_documented}/{total_symbols} documented ({pct:.1f}%)")


if __name__ == "__main__":
	main()
