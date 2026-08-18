#!/usr/bin/env python3
#vimrun! ../examples/pyosg-match4.py

"""Match-4 demo, per the plan in ~/dev/osgx/CLAUDE.md ("Planned/next steps for
picking", item 5). Two layers in this one file:

  - Board: pure-Python game state, no OSG/osgx dependency -- grid, match
    detection, swap/resolve, constructive deal. Reusable/importable standalone.
  - __main__: the OSG scene + osgx.picking interaction on top of it -- one
    sphere per cell, full-window SYNC click picking (same wiring as
    pyosg-picking.py). First cut, proof-of-concept only: click a piece, click
    an adjacent piece, and it swaps if that creates a match (reverts silently
    if not) -- no hover preview yet (see pyosg-hover.py for that mechanism,
    not yet wired in here).

Design decisions (confirmed 2026-08-07):
  - Match shape: MatchMode.CONNECTED (default) -- any 4-connected (orthogonal)
    same-color blob, covering straight lines AND L/T-shapes in one flood fill,
    no separate detectors needed. MatchMode.LINE -- straight horizontal/vertical
    runs of >=4 only, the more classic "4-in-a-row" rule -- added after
    CONNECTED's blob matches (e.g. "RBR / BBB", a T-shape) turned out to read as
    surprising in practice even though it was the originally-requested behavior.
    MatchMode.LINE_CONNECTED -- LINE's straight-run rule gates whether a match
    exists, then floods outward from a qualifying run to sweep up any other
    touching same-color cells (other runs, blobs, loose singles) into it.
    --match-mode on the command line selects between the three.
  - Match length: 4 or more (not exactly-4).
  - Board size: configurable (width/height/num_colors are constructor args).
  - Interaction: simplest possible first proof -- two-click select-then-swap,
    no legality preview on hover, no adjacency hint. "Swap these two I clicked."

Board.find_legal_moves()/has_legal_move() is the swap-scanner shared between
initial-deal validation and in-game "no moves left -> reshuffle" detection, per
the same osgx notes. Initial deal is CONSTRUCTIVE, not generate-and-retry:
_fill() places each cell under a "no color completes a run of 4" constraint,
then _plant_legal_move() deliberately constructs one guaranteed swap if the
constrained fill didn't happen to leave one -- retrying whole-board generation
would be unreliable here, since landing a 4-in-a-row opportunity by chance is
much rarer than a 3-in-a-row one.
"""

import argparse
import enum
import random

EMPTY = -1

class MatchMode(enum.Enum):
	# Any 4-connected same-color blob (straight lines, L/T-shapes, blobs) -- one flood
	# fill covers all of those shapes at once. Default -- see module docstring.
	CONNECTED = "connected"
	# Straight horizontal/vertical runs of >=4 only, scanned independently -- the more
	# classic "4-in-a-row" match-3/4 rule. A cell can be part of both a horizontal and
	# a vertical run at once (both clear); runs never merge into one blob the way
	# CONNECTED's flood fill does.
	LINE = "line"
	# LINE's straight-run-of->=4 rule decides whether a match exists at all, but once
	# a run qualifies, flood-fill outward from it (reusing CONNECTED's _flood()) sweeps
	# up any other same-color cells touching it -- other runs, blobs, loose singles --
	# into the same match. A pure blob with no straight run of >=4 still doesn't match.
	LINE_CONNECTED = "line_connected"

class ResetMode(enum.Enum):
	# Regenerate the whole board from scratch when no legal moves remain -- same
	# constructive, region-spread deal as the initial one (Board.reset() just calls
	# _fill() again). Default and only mode for now; a future mode that reshuffles the
	# tiles already on the board in place (no new colors introduced, retried until a
	# legal move exists) is planned but not yet implemented.
	FULL = "full"

class Board:
	def __init__(
		self, width=8, height=16, num_colors=6, rng=None, match_mode=MatchMode.CONNECTED,
		min_initial_moves=3
	):
		self.width = width
		self.height = height
		self.num_colors = num_colors
		self.rng = rng or random.Random()
		self.match_mode = match_mode
		self.min_initial_moves = min_initial_moves
		self._cells = [[EMPTY] * height for _ in range(width)]

		self._fill()

	# --- grid access ---

	def in_bounds(self, x, y):
		return 0 <= x < self.width and 0 <= y < self.height

	def get(self, x, y):
		return self._cells[x][y]

	def set(self, x, y, color):
		self._cells[x][y] = color

	def __getitem__(self, pos):
		x, y = pos

		return self._cells[x][y]

	def __setitem__(self, pos, color):
		x, y = pos

		self._cells[x][y] = color

	def neighbors(self, x, y):
		for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
			nx, ny = x + dx, y + dy

			if self.in_bounds(nx, ny):
				yield nx, ny

	# --- match detection ---

	def find_matches(self):
		"""All matches on the board right now, per self.match_mode."""
		if self.match_mode == MatchMode.LINE:
			return self._find_matches_line()

		if self.match_mode == MatchMode.LINE_CONNECTED:
			return self._find_matches_line_connected()

		return self._find_matches_connected()

	def _find_matches_connected(self):
		"""All >=4-cell 4-connected same-color groups (lines, L/T-shapes, blobs)."""
		seen = set()
		matches = []

		for x in range(self.width):
			for y in range(self.height):
				if (x, y) in seen:
					continue

				color = self._cells[x][y]

				if color == EMPTY:
					continue

				group = self._flood(x, y, color, seen)

				if len(group) >= 4:
					matches.append(frozenset(group))

		return matches

	def _find_matches_line(self):
		"""Straight horizontal/vertical runs of >=4 only -- no L/T/blob merging."""
		matches = []

		for x in range(self.width):
			self._scan_run(matches, [(x, y) for y in range(self.height)])

		for y in range(self.height):
			self._scan_run(matches, [(x, y) for x in range(self.width)])

		return matches

	def _scan_run(self, matches, positions):
		run = []
		prev_color = EMPTY

		for pos in positions:
			color = self._cells[pos[0]][pos[1]]

			if color != EMPTY and color == prev_color:
				run.append(pos)
			else:
				if len(run) >= 4:
					matches.append(frozenset(run))

				run = [pos] if color != EMPTY else []

			prev_color = color

		if len(run) >= 4:
			matches.append(frozenset(run))

	def _find_matches_line_connected(self):
		"""LINE's runs gate whether a match exists; each qualifying run then floods
		outward to absorb any other same-color cells touching it. `seen` is shared
		across runs -- a run whose seed cell is already swept up by an earlier flood
		(e.g. the other arm of a plus shape) is skipped, since flood-filling from a
		same-color run necessarily already reached it.
		"""
		seen = set()
		matches = []

		for run in self._find_matches_line():
			x, y = next(iter(run))

			if (x, y) in seen:
				continue

			color = self._cells[x][y]

			matches.append(frozenset(self._flood(x, y, color, seen)))

		return matches

	def _flood(self, x, y, color, seen):
		stack = [(x, y)]
		group = set()

		while stack:
			cx, cy = stack.pop()

			if (cx, cy) in seen:
				continue

			seen.add((cx, cy))
			group.add((cx, cy))

			for nx, ny in self.neighbors(cx, cy):
				if (nx, ny) not in seen and self._cells[nx][ny] == color:
					stack.append((nx, ny))

		return group

	# --- swapping ---

	def swap(self, pos0, pos1):
		x0, y0 = pos0
		x1, y1 = pos1

		self._cells[x0][y0], self._cells[x1][y1] = self._cells[x1][y1], self._cells[x0][y0]

	def try_swap(self, pos0, pos1):
		"""Swap two cells; if no match results, swap back and report failure."""
		self.swap(pos0, pos1)

		if self.find_matches():
			return True

		self.swap(pos0, pos1)

		return False

	def _creates_match_if_swapped(self, pos0, pos1):
		self.swap(pos0, pos1)

		matched = bool(self.find_matches())

		self.swap(pos0, pos1)

		return matched

	def find_legal_moves(self):
		"""Every adjacent swap that would create >=1 match, without mutating the board."""
		moves = []

		for x in range(self.width):
			for y in range(self.height):
				for pos1 in ((x + 1, y), (x, y + 1)):
					if self.in_bounds(*pos1) and self._creates_match_if_swapped((x, y), pos1):
						moves.append(((x, y), pos1))

		return moves

	def has_legal_move(self):
		for x in range(self.width):
			for y in range(self.height):
				for pos1 in ((x + 1, y), (x, y + 1)):
					if self.in_bounds(*pos1) and self._creates_match_if_swapped((x, y), pos1):
						return True

		return False

	# --- clear / gravity / refill ---

	def resolve(self, max_passes=64):
		"""Clear matches, drop survivors, refill from the top, repeat until stable.

		Returns the list of match-sets cleared per cascade pass (scoring/animation
		hooks can key off this later). Capped at max_passes: with too few colors
		for the board size, random refill can make a fresh accidental match on
		nearly every pass, so cascades aren't guaranteed to stabilize quickly --
		bail out rather than spin (and grow `passes`) unboundedly.
		"""
		passes = []

		while len(passes) < max_passes:
			result = self.resolve_one_pass()

			if result is None:
				break

			matched, _, _ = result

			passes.append(matched)

		return passes

	def resolve_one_pass(self):
		"""One pass of what resolve()'s loop does internally -- clear the matches
		currently on the board, drop survivors, refill from the top -- but returns
		the per-cell movement/fill detail resolve() itself throws away, for an
		animated gravity collapse instead of an instant snap. Returns None if
		there's nothing to resolve this pass.

		Returns (matched, moves, filled):
		  matched -- match-groups just cleared (same shape as find_matches())
		  moves   -- (x, old_y, new_y) triples, one per surviving cell that shifted
		             down within its column (color unchanged, only position moves)
		  filled  -- (x, y, color) triples, one per newly refilled cell
		"""
		matched = self.find_matches()

		if not matched:
			return None

		for group in matched:
			for x, y in group:
				self._cells[x][y] = EMPTY

		moves = self._drop()
		filled = self._refill()

		return matched, moves, filled

	def _drop(self):
		"""Compact each column, dropping survivors to the bottom. Returns
		(x, old_y, new_y) triples for every surviving cell that actually shifted --
		see resolve_one_pass(). resolve()'s own loop ignores the return value.
		"""
		moves = []

		for x in range(self.width):
			survivors = [(y, c) for y, c in enumerate(self._cells[x]) if c != EMPTY]
			pad = self.height - len(survivors)

			for i, (old_y, color) in enumerate(survivors):
				new_y = pad + i

				if new_y != old_y:
					moves.append((x, old_y, new_y))

			self._cells[x] = [EMPTY] * pad + [c for _, c in survivors]

		return moves

	def _refill(self):
		"""Fill every remaining EMPTY cell with a random color. Returns
		(x, y, color) triples for each newly filled cell -- see resolve_one_pass().
		resolve()'s own loop ignores the return value.
		"""
		filled = []

		for x in range(self.width):
			for y in range(self.height):
				if self._cells[x][y] == EMPTY:
					color = self.rng.randrange(self.num_colors)

					self._cells[x][y] = color

					filled.append((x, y, color))

		return filled

	# --- constructive initial deal ---

	def _fill(self):
		for x in range(self.width):
			for y in range(self.height):
				self._cells[x][y] = self._pick_safe_color(x, y)

		self._ensure_spread_legal_moves(self.min_initial_moves)

	def _pick_safe_color(self, x, y):
		"""A color for (x, y) that doesn't complete a >=4 group with already-placed
		neighbors (cells not yet visited in fill order are still EMPTY, so the flood
		naturally can't spread through them).
		"""
		colors = list(range(self.num_colors))

		self.rng.shuffle(colors)

		for color in colors:
			self._cells[x][y] = color

			if len(self._flood(x, y, color, set())) < 4:
				return color

		# Every color would complete a match -- only possible with very few colors
		# on a tiny board. Fall back to whichever creates the smallest group.
		return min(colors, key=lambda c: self._preview_group_size(x, y, c))

	def _preview_group_size(self, x, y, color):
		self._cells[x][y] = color

		return len(self._flood(x, y, color, set()))

	def _plant_legal_move(self, max_attempts=200, x_range=None, y_range=None, orientation=None):
		"""Construct a 'C C C D' run with a same-colored donor one swap away from D,
		so swapping D<->donor completes a 4-run. Verified via a real find_matches()
		before committing (never introduces an accidental pre-swap match) and
		retried locally on collision -- not a whole-board regeneration.

		`x_range`/`y_range` (default: the whole board) confine where the run is
		planted -- used by `_ensure_spread_legal_moves()` to target a specific
		region. `orientation` ("horizontal"/"vertical", default: whichever fits,
		coin-flipping if both do) forces the run's axis; a region split narrow
		along one axis still has the *other* axis at full board length, so it
		always has a valid orientation as long as the board itself does.
		"""
		x_lo, x_hi = x_range if x_range is not None else (0, self.width)
		y_lo, y_hi = y_range if y_range is not None else (0, self.height)
		can_horizontal = x_hi - x_lo >= 4
		can_vertical = y_hi - y_lo >= 4

		if not can_horizontal and not can_vertical:
			what = "board" if x_range is None and y_range is None else "region"

			raise RuntimeError(f"{what} too small to guarantee a legal move")

		for _ in range(max_attempts):
			color = self.rng.randrange(self.num_colors)
			horizontal = orientation == "horizontal" or (
				orientation is None and can_horizontal and (not can_vertical or self.rng.choice((True, False)))
			)

			if horizontal:
				x = self.rng.randrange(x_lo, x_hi - 3)
				y = self.rng.randrange(y_lo, y_hi)
				run = [(x, y), (x + 1, y), (x + 2, y)]
				slot = (x + 3, y)
				donor = (x + 3, y + 1) if y + 1 < self.height else (x + 3, y - 1)
			else:
				x = self.rng.randrange(x_lo, x_hi)
				y = self.rng.randrange(y_lo, y_hi - 3)
				run = [(x, y), (x, y + 1), (x, y + 2)]
				slot = (x, y + 3)
				donor = (x + 1, y + 3) if x + 1 < self.width else (x - 1, y + 3)

			touched = run + [slot, donor]
			saved = {pos: self._cells[pos[0]][pos[1]] for pos in touched}

			for pos in run:
				self._cells[pos[0]][pos[1]] = color

			self._cells[donor[0]][donor[1]] = color

			if not self.find_matches():
				return slot, donor

			for pos, value in saved.items():
				self._cells[pos[0]][pos[1]] = value

		raise RuntimeError("could not plant a guaranteed legal move")

	def _region_bands(self, count):
		"""Partition the board into up to `count` bands along whichever axis is
		longer, each spanning the FULL extent of the other axis -- every band is
		plantable (>=4 cells) along that unsplit axis as long as the board itself
		is, regardless of how narrow the split makes the band. Returns
		(x_range, y_range, orientation) triples for `_plant_legal_move()`.
		"""
		if self.width >= self.height:
			edges = sorted({round(i * self.width / count) for i in range(count + 1)})

			return [
				((edges[i], edges[i + 1]), (0, self.height), "vertical")
				for i in range(len(edges) - 1)
			]

		edges = sorted({round(i * self.height / count) for i in range(count + 1)})

		return [
			((0, self.width), (edges[i], edges[i + 1]), "horizontal")
			for i in range(len(edges) - 1)
		]

	def _region_move_count(self, moves, x_range, y_range):
		x_lo, x_hi = x_range
		y_lo, y_hi = y_range

		def inside(pos):
			return x_lo <= pos[0] < x_hi and y_lo <= pos[1] < y_hi

		return sum(1 for pos0, pos1 in moves if inside(pos0) or inside(pos1))

	def _ensure_spread_legal_moves(self, min_moves, max_attempts=None):
		"""If the constructive deal's natural legal-move count is already
		>=min_moves, leave the board alone. Otherwise repeatedly plant a
		guaranteed move into whichever board region (region count == min_moves)
		currently has the fewest, re-checking the real move count fresh every
		iteration -- not a single one-pass-per-region walk, since a plant's
		donor cell can straddle into a neighboring region (making it look
		already-covered when it isn't) or, rarely, incidentally invalidate an
		earlier move elsewhere on the board (match footprints can extend past
		the swapped cells themselves, e.g. under LINE_CONNECTED). Recomputing
		from scratch each time is self-correcting against both. The goal is
		spreading activity across the board instead of it all clustering
		wherever a single fallback plant happened to go -- which left
		everywhere else frozen from the match-avoiding deal for the rest of the
		game, since resolve() only re-rolls columns that actually matched.
		"""
		max_attempts = max_attempts if max_attempts is not None else min_moves * 8
		bands = self._region_bands(min_moves)

		for _ in range(max_attempts):
			moves = self.find_legal_moves()

			if len(moves) >= min_moves:
				return

			x_range, y_range, orientation = min(
				bands, key=lambda band: self._region_move_count(moves, band[0], band[1])
			)

			self._plant_legal_move(x_range=x_range, y_range=y_range, orientation=orientation)

		if len(self.find_legal_moves()) < min_moves:
			raise RuntimeError(f"could not reach {min_moves} legal moves after {max_attempts} plants")

	# --- reset ---

	def reset(self, mode=ResetMode.FULL):
		"""Regenerate the board when no legal moves remain, per `mode`. Continues
		drawing from self.rng rather than reseeding, so a --seed run stays fully
		reproducible through any number of resets.
		"""
		if mode != ResetMode.FULL:
			raise ValueError(f"unsupported reset mode: {mode}")

		self._fill()

# ================================================================================================
# OSG scene + osgx.picking interaction -- everything above this line is pure Python and
# importable without OSG; everything below requires it.
# ================================================================================================

import os
import time

os.environ.setdefault("OSG_WINDOW", "50 50 800 600")
os.environ.setdefault("OSG_THREADING", "SingleThreaded")
os.environ.setdefault("OSG_GL_CONTEXT_PROFILE_MASK", "1")
os.environ.setdefault("OSG_GL_VERSION", "4.6")
os.environ.setdefault("OSG_GL_CONTEXT_VERSION", "4.6")

from OpenSceneGraph import *
from OpenSceneGraph.GL import *

import osgx

W, H = 800, 600
CELL_SPACING = 2.2

# Same core-profile-safe minimal Lambertian shader as pyosg-picking.py/pyosg-hover.py.
SCENE_VERTEX_SHADER = """
#version 330 core

in vec4 osg_Vertex;
in vec3 osg_Normal;
in vec4 osg_Color;

uniform mat4 osg_ModelViewProjectionMatrix;
uniform mat3 osg_NormalMatrix;

out vec3 vNormal;
out vec4 vColor;

void main() {
	vNormal = normalize(osg_NormalMatrix * osg_Normal);
	vColor = osg_Color;

	gl_Position = osg_ModelViewProjectionMatrix * osg_Vertex;
}
"""

SCENE_FRAGMENT_SHADER = """
#version 330 core

in vec3 vNormal;
in vec4 vColor;

out vec4 fragColor;

void main() {
	const vec3 L = vec3(0.4, 0.6, 0.7);

	float diffuse = max(dot(normalize(vNormal), normalize(L)), 0.0);
	float light = 0.35 + 0.65 * diffuse;

	fragColor = vec4(vColor.rgb * light, vColor.a);
}
"""

PALETTE = (
	osg.Vec4(1.0, 0.2, 0.2, 1.0),
	osg.Vec4(0.2, 1.0, 0.2, 1.0),
	osg.Vec4(0.2, 0.2, 1.0, 1.0),
	osg.Vec4(1.0, 1.0, 0.2, 1.0),
	osg.Vec4(1.0, 0.2, 1.0, 1.0),
	osg.Vec4(0.2, 1.0, 1.0, 1.0),
)

def cell_pos(x, y, board):
	"""World position for (x, y), grid centered on the origin. Board's y=0 is the
	top row, so it maps to high Z (near the viewer's default trackball orientation).
	"""
	return osg.Vec3(
		(x - (board.width - 1) / 2.0) * CELL_SPACING,
		0.0,
		((board.height - 1) / 2.0 - y) * CELL_SPACING,
	)

def pick_id(x, y, board):
	return y * board.width + x + 1

def id_to_cell(pid, board):
	idx = pid - 1

	return idx % board.width, idx // board.width

def adjacent(pos0, pos1):
	x0, y0 = pos0
	x1, y1 = pos1

	return abs(x0 - x1) + abs(y0 - y1) == 1

def report_board_state(board):
	"""Console ground-truth, not a visual hint yet: prints every legal move so you
	don't have to spot one by eye (also doubles as a leftover-match sanity check --
	find_matches() should always be empty right after a rebuild, since resolve()
	only stops once it is; a nonzero warning here would mean a real Board bug).
	"""
	leftover = board.find_matches()

	if leftover:
		osg.notice(
			f"[pyosg-match4] WARNING: {len(leftover)} unresolved match(es) still on "
			f"the board (shouldn't happen): {leftover}"
		)

	moves = board.find_legal_moves()

	osg.notice(f"[pyosg-match4] {len(moves)} legal move(s): {moves}")

def make_piece(board, x, y):
	"""One sphere piece for cell (x, y): a MatrixTransform (positioned via
	cell_pos(), full scale) -> Geode -> ShapeDrawable, with a pickID uniform for
	this cell's current pid. Shared by rebuild_scene() and the animated
	match-resolution sequence's "a new piece appears" cases (see start_fall()
	in __main__).
	"""
	base = osg.Matrix.translate(cell_pos(x, y, board))
	mt = osg.MatrixTransform(base)
	geode = osg.Geode()
	drawable = osg.ShapeDrawable(osg.Sphere(osg.Vec3(), 0.9))

	drawable.color = PALETTE[board.get(x, y) % len(PALETTE)]

	pid = pick_id(x, y, board)
	uid = osg.Uniform(osg.Uniform.Type.UNSIGNED_INT, "pickID")

	uid.value = pid

	geode.stateSet.uniforms.extend((uid,))
	geode.drawables.append(drawable)
	mt.children.append(geode)

	return mt, base

def rebuild_scene(scene, board, pieces):
	"""Destroy and repopulate: clears every child and rebuilds one sphere per cell
	from current Board state. No per-cell diffing -- called at startup and again
	once a full match-resolution animation sequence (shrink -> fall -> any
	cascades) finishes, to snap `pieces` back to a clean, correctly pid-keyed
	state for hover/selection to rely on.

	`pieces` (pid -> (MatrixTransform, base_matrix)) is cleared and refilled too --
	every node's identity is new after a rebuild, so hover/selection code always
	needs the current node, not whatever it cached from before.
	"""
	scene.children.clear()
	pieces.clear()

	for x in range(board.width):
		for y in range(board.height):
			mt, base = make_piece(board, x, y)

			scene.children.append(mt)
			pieces[pick_id(x, y, board)] = (mt, base)

class ShrinkCallback:
	"""Animates one piece's MatrixTransform scale from 1.0 down to `target_scale`
	over `duration` seconds (wall-clock via time.time(), same pattern as
	LiveUpdateCallback in pyosg-dynamic-verts.py), then marks itself done by
	discarding `key` from the shared `pending` set -- the main loop watches that
	set to know when every matched piece has finished shrinking. No need to
	detach the callback on completion: the whole node is destroyed by the next
	rebuild_scene() call regardless, so a finished callback just goes stale/inert
	until then. `key` is whatever the caller uses to track this piece in `pending`
	(board position, in start_shrink() below) -- opaque to the callback itself.
	"""

	def __init__(self, mt, base, pending, key, duration, target_scale):
		self.mt = mt
		self.base = base
		self.pending = pending
		self.key = key
		self.duration = duration
		self.target_scale = target_scale
		self.t0 = time.time()
		self.done = False

	def __call__(self, node, nv):
		if not self.done:
			t = (time.time() - self.t0) / self.duration

			if t >= 1.0:
				t = 1.0
				self.done = True

				self.pending.discard(self.key)

			scale = 1.0 + (self.target_scale - 1.0) * t

			self.mt.matrix = osg.Matrix.scale(scale, scale, scale) * self.base

		return True

class FallCallback:
	"""Animates one piece's MatrixTransform from `from_pos` to `to_pos`
	(world-space osg.Vec3, linearly interpolated) over `duration` seconds --
	same wall-clock-timer/no-self-detach/shared-`pending`-set pattern as
	ShrinkCallback, covering both a survivor dropping into a gap (gravity) and a
	newly refilled piece falling in from above the board (see start_fall()).
	"""

	def __init__(self, mt, from_pos, to_pos, pending, key, duration):
		self.mt = mt
		self.from_pos = from_pos
		self.to_pos = to_pos
		self.pending = pending
		self.key = key
		self.duration = duration
		self.t0 = time.time()
		self.done = False

	def __call__(self, node, nv):
		if not self.done:
			t = (time.time() - self.t0) / self.duration

			if t >= 1.0:
				t = 1.0
				self.done = True

				self.pending.discard(self.key)

			pos = self.from_pos + (self.to_pos - self.from_pos) * t

			self.mt.matrix = osg.Matrix.translate(pos)

		return True

if __name__ == "__main__":
	parser = argparse.ArgumentParser(description="Match-4 board demo")

	parser.add_argument(
		"--seed", type=int, default=None,
		help="RNG seed for reproducible board generation (default: random, printed at startup)"
	)
	parser.add_argument(
		"--match-mode", choices=[m.value for m in MatchMode], default=MatchMode.CONNECTED.value,
		help="connected: any 4-connected blob (lines/L/T-shapes); "
		"line: straight horizontal/vertical runs of >=4 only; "
		"line_connected: a line run gates the match, then floods outward to absorb "
		"any touching same-color cells (default: %(default)s)"
	)
	parser.add_argument(
		"--reset-mode", choices=[m.value for m in ResetMode], default=ResetMode.FULL.value,
		help="what to do when a swap leaves no legal moves: "
		"full: regenerate the whole board (default: %(default)s)"
	)

	args = parser.parse_args()

	osg.setNotifyLevel(osg.NotifySeverity.NOTICE)

	# Always run through an explicit seed, even when the caller didn't pass one --
	# an unseeded random.Random() is just as reproducible, but only if you print the
	# seed it landed on so a later run can pass it back in via --seed.
	seed = args.seed if args.seed is not None else random.SystemRandom().randrange(2**31)
	match_mode = MatchMode(args.match_mode)
	reset_mode = ResetMode(args.reset_mode)

	osg.notice(f"[pyosg-match4] seed = {seed} (pass --seed {seed} to reproduce this board)")
	osg.notice(f"[pyosg-match4] match mode = {match_mode.value}")
	osg.notice(f"[pyosg-match4] reset mode = {reset_mode.value}")

	viewer = osgViewer.Viewer()
	viewer.cameraManipulator = osgGA.TrackballManipulator()

	board = Board(width=8, height=8, num_colors=5, rng=random.Random(seed), match_mode=match_mode)

	scene = osg.Group(name="scene")

	prog = osg.Program(name="pyosg-match4-scene", shaders=(
		osg.Shader(osg.Shader.VERTEX, SCENE_VERTEX_SHADER),
		osg.Shader(osg.Shader.FRAGMENT, SCENE_FRAGMENT_SHADER),
	))

	scene.stateSet.attributes.append(prog)

	# pid -> (MatrixTransform, base_matrix); rebuilt in place by rebuild_scene() every
	# time the board changes, since destroy-and-repopulate means every node's identity
	# is new. Hover/selection scaling always looks the current node up here.
	pieces = {}

	rebuild_scene(scene, board, pieces)
	report_board_state(board)

	HOVER_SCALE = 1.15
	SELECT_SCALE = 1.35
	SHRINK_DURATION = 0.3
	SHRINK_TARGET_SCALE = 0.1
	FALL_DURATION = 0.3

	def set_piece_scale(pid, scale):
		mt, base = pieces[pid]

		mt.matrix = osg.Matrix.scale(scale, scale, scale) * base

	# Match-resolution is a small frame-driven state machine, not a single instant
	# snap: a successful swap kicks off shrink -> fall (survivors drop into gaps,
	# new pieces fall in from above their column) -> repeat from shrink if that
	# fall revealed a cascade, else finish. Nothing here blocks/sleeps -- `phase`
	# and the two `pending_*` sets are advanced from the main loop after each
	# viewer.frame(), since that's what actually ticks ShrinkCallback/FallCallback
	# (attached as each piece's updateCallback, same mechanism as LiveUpdateCallback
	# in pyosg-dynamic-verts.py) via OSG's own update traversal.
	#
	# `live_nodes` is a (x, y) -> MatrixTransform map of what's really on screen
	# *during* a sequence -- `pieces` (pid-keyed) goes stale the instant pieces
	# start moving and is only trustworthy again once rebuild_scene() restores it
	# at the very end. Input (on_pick/on_enter/on_leave) is locked out for the
	# whole sequence via `animating`, so that staleness never leaks into picking.
	animating = [False]
	phase = ["idle"]
	pending_shrink = set()
	pending_fall = set()
	live_nodes = {}

	# 1x1 FBO + continuous sub-frustum, same mechanism as pyosg-hover.py -- lets us layer
	# real-time onEnter/onLeave hover feedback on top of the click-to-select-then-swap loop
	# from the first pass (that version used full-window CLICK-only picking).
	pick_image = osg.Image()

	pick_image.allocateImage(1, 1, 1, GL_RGBA, GL_UNSIGNED_BYTE)

	pick_cam = osgx.picking.makePickCamera(1, 1, pick_image)

	pick_cam.children.append(scene)

	rb = osgx.picking.PickReadbackSync(
		1, pick_image, W, H,
		rule=osgx.picking.PickRule.SPIRAL,
		mode=osgx.picking.PickReadbackSync.Mode.CONTINUOUS,
	)

	# Two-click select-then-swap, same game logic as the first pass, now layered with
	# visual feedback: a persistent SELECT_SCALE indicator on the first-clicked piece,
	# and a lighter HOVER_SCALE indicator that follows the cursor over every OTHER piece
	# (skipped on the selected piece itself -- its own indicator already covers that,
	# and stacking both would just be confusing) -- "hover indicator applies to the 2nd one."
	selected = [None]

	def selected_pid():
		return pick_id(selected[0][0], selected[0][1], board) if selected[0] else None

	def clear_selection():
		if selected[0] is not None:
			set_piece_scale(selected_pid(), 1.0)

		selected[0] = None

	def on_enter(pid):
		if not animating[0] and pid != selected_pid():
			set_piece_scale(pid, HOVER_SCALE)

	def on_leave(pid):
		if not animating[0] and pid != selected_pid():
			set_piece_scale(pid, 1.0)

	def start_shrink(matched_positions):
		"""Phase 1 of a match-resolution sequence: shrink every piece at a
		matched (x, y) via ShrinkCallback. `matched_positions` must be looked up
		against `live_nodes`, not `pieces` -- on a cascade (called again from
		advance_after_fall()) the pieces at these positions may be ones that just
		fell into place, which only `live_nodes` knows about.
		"""
		animating[0] = True
		phase[0] = "shrink"
		pending_shrink.clear()

		for x, y in matched_positions:
			mt = live_nodes[(x, y)]
			base = osg.Matrix.translate(cell_pos(x, y, board))
			key = (x, y)

			pending_shrink.add(key)
			mt.updateCallback = ShrinkCallback(mt, base, pending_shrink, key, SHRINK_DURATION, SHRINK_TARGET_SCALE)

	def start_fall():
		"""Phase 2: run exactly one Board.resolve_one_pass() (clearing the pieces
		that just finished shrinking), remove their now-empty nodes, animate
		surviving pieces dropping into the resulting gaps, and drop new pieces in
		from above their column (stacked so simultaneous refills in one column
		queue up instead of overlapping) instead of just warping them in.
		"""
		matched, moves, filled = board.resolve_one_pass()

		for x, y in set().union(*matched):
			scene.children.remove(live_nodes.pop((x, y)))

		phase[0] = "fall"
		pending_fall.clear()

		# Read every mover out of live_nodes BEFORE writing any new keys back in --
		# a column can shift more than one survivor at once (e.g. old_y 0->1 and
		# old_y 1->2 in the same pass), and interleaving reads/writes would let an
		# earlier move's new key clobber a later move's old key it still needs to
		# read, silently losing that piece's fall animation.
		movers = [(x, new_y, live_nodes.pop((x, old_y)), cell_pos(x, old_y, board)) for x, old_y, new_y in moves]

		for x, new_y, mt, from_pos in movers:
			to_pos = cell_pos(x, new_y, board)
			key = (x, new_y)

			live_nodes[key] = mt
			pending_fall.add(key)
			mt.updateCallback = FallCallback(mt, from_pos, to_pos, pending_fall, key, FALL_DURATION)

		filled_per_column = {}

		for x, y, color in filled:
			filled_per_column.setdefault(x, []).append(y)

		for x, y, color in filled:
			mt, _ = make_piece(board, x, y)
			pad = len(filled_per_column[x])
			from_pos = cell_pos(x, y - pad, board)
			to_pos = cell_pos(x, y, board)
			key = (x, y)

			mt.matrix = osg.Matrix.translate(from_pos)

			scene.children.append(mt)
			live_nodes[key] = mt
			pending_fall.add(key)
			mt.updateCallback = FallCallback(mt, from_pos, to_pos, pending_fall, key, FALL_DURATION)

	def advance_after_fall():
		"""Phase 3: the fall settled -- either it revealed a new cascade (back to
		shrink) or the board is stable (finish the whole sequence)."""
		matches = board.find_matches()

		if matches:
			start_shrink(set().union(*matches))
		else:
			finish_sequence()

	def finish_sequence():
		if not board.has_legal_move():
			osg.notice(f"[pyosg-match4] no legal moves left -- auto-reset ({reset_mode.value})")
			board.reset(reset_mode)

		rebuild_scene(scene, board, pieces)
		report_board_state(board)

		phase[0] = "idle"
		animating[0] = False
		live_nodes.clear()

	def on_pick(pid, action):
		# PickReadbackSync fires onPick(id, HOVER) on every hover transition too (not just
		# reportClick() -> CLICK) -- ignore those, or hovering alone drives the whole
		# select/swap state machine instead of requiring a real click.
		if action != osgx.picking.ActionType.CLICK:
			return

		if animating[0]:
			return

		if not pid:
			clear_selection()

			return

		pos = id_to_cell(pid, board)

		if selected[0] is None:
			selected[0] = pos

			set_piece_scale(pid, SELECT_SCALE)
			osg.notice(f"[pyosg-match4] selected {pos}")

			return

		if selected[0] == pos:
			osg.notice(f"[pyosg-match4] deselected {pos}")

			clear_selection()

			return

		if not adjacent(selected[0], pos):
			osg.notice(f"[pyosg-match4] {pos} not adjacent to {selected[0]}, reselecting")

			clear_selection()
			selected[0] = pos
			set_piece_scale(pid, SELECT_SCALE)

			return

		prev = selected[0]

		clear_selection()

		if board.try_swap(prev, pos):
			# Rebuild now so the swap itself is visible immediately, before the matched
			# pieces start shrinking -- find_matches() on this same (post-swap,
			# pre-clear) board state is exactly the first pass resolve_one_pass() would
			# compute, so the animated set and the set it actually clears agree.
			rebuild_scene(scene, board, pieces)

			live_nodes.clear()
			live_nodes.update({
				(x, y): pieces[pick_id(x, y, board)][0]
				for x in range(board.width) for y in range(board.height)
			})

			matched = set().union(*board.find_matches())

			osg.notice(f"[pyosg-match4] swap {prev} <-> {pos} -- match! shrinking {len(matched)} piece(s)")

			start_shrink(matched)
		else:
			osg.notice(f"[pyosg-match4] swap {prev} <-> {pos} -- no match, reverted")

	rb.onPick = on_pick
	rb.onEnter = on_enter
	rb.onLeave = on_leave

	sync = osgx.picking.PickCameraSync(viewer.camera, True, W, H, rb)
	hover = osgx.picking.PickHoverCallback(rb)

	# Order matters: sync (aim sub-frustum) -> hover (fire onEnter/onLeave from last
	# frame's lastID()) -> rb (sample this frame's 1x1 readback). See pyosg-hover.py.
	pick_cam.updateCallback = osgx.NodeCallbacksGroup([sync, hover, rb])

	root = osg.Group(name="root")

	root.children.append(pick_cam)
	root.children.append(scene)

	viewer.sceneData = root
	viewer.eventHandlers.append(osgx.picking.PickHandler(rb, True))

	while not viewer.done:
		viewer.frame()

		if phase[0] == "shrink" and not pending_shrink:
			start_fall()
		elif phase[0] == "fall" and not pending_fall:
			advance_after_fall()
