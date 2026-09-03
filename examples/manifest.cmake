# Single source of truth for example-module tiers. `examples/` builds as its own
# independent CMake project (see examples/CMakeLists.txt), so this file is `include()`d
# separately by both:
#
# - the root CMakeLists.txt (base `openscenegraph` wheel install + the BUILD-*/ dev-tree
#   overlay used by `python -m OpenSceneGraph.examples.<name>` against a native build); and
# - examples/CMakeLists.txt (the optional `openscenegraph-examples` overlay wheel install).
#
# Each entry is "<source file in examples/>=<installed module filename>".

# A small, curated, asset-free subset of examples/ that implements the
# build_scene()/configure_viewer() contract, promoted into the base package's
# OpenSceneGraph.examples package so `pyosg <name>` works out of the box. Most of
# examples/ is a development sandbox and deliberately not part of this list; add an
# entry here once an example implements the contract and is meant to ship in the base
# wheel.
set(PYOSG_CORE_EXAMPLES
	"pyosg-blur.py=blur.py"
	"pyosg-mrt.py=mrt.py"
	"pyosg-info.py=info.py"
	# Shared source/example bootstrap helpers belong to the base package, so
	# optional example distributions can import them without owning package
	# scaffolding files.
	"pyosg_example.py=pyosg_example.py"
	"pyosg_visitor.py=pyosg_visitor.py"
	"pyosg_repl.py=pyosg_repl.py"
)

# Examples that ship only in the separate openscenegraph-examples overlay wheel,
# typically alongside prepared third-party assets (see assets.toml). Never installed
# by the base package; still mirrored into the BUILD-*/ dev tree so they can be run
# and iterated on without building the overlay wheel.
set(PYOSG_OFFICIAL_EXAMPLES
	"pyosg-khronos-viewer.py=khronos_viewer.py"
	# pyosg-async-gltf.py
	# pyosg-async.py
	"pyosg-cuda-points.py=cuda_points.py"
	"pyosg-dice.py=dice.py"
	"pyosg_dice.py=pyosg_dice.py"
	# pyosg-dynamic.py
	# pyosg-dynamic-verts.py
	"pyosg-explosion.py=explosion.py"
	"pyosg-flame.py=flame.py"
	"pyosg-fragcoordxyz.py=fragcoordxyz.py"
	"pyosg-hatch.py=hatch.py"
	"pyosg-hover.py=hover.py"
	"pyosg-ibl-rotate.py=ibl_rotate.py"
	"pyosg-imgui.py=imgui.py"
	"pyosg-instanced.py=instanced.py"
	"pyosg-instanced-ssbo.py=instanced_ssbo.py"
	# pyosg-linux.py
	"pyosg-match4.py=match4.py"
	"pyosg-material.py=material.py"
	"pyosg-motionbricks.py=motionbricks.py"
	# pyosg-msdf.py
	"pyosg-noise.py=noise.py"
	"pyosg-picking.py=picking.py"
	"pyosg-points.py=points.py"
	"pyosg-polyhaven.py=polyhaven.py"
	"pyosg-rtt.py=rtt.py"
	"pyosg-taa.py=taa.py"
	"pyosg-voronoi-reveal.py=voronoi_reveal.py"
	"pyosg-voxelize2d.py=voxelize2d.py"

	# The lighting tutorial series: a subpackage (dst contains "/"), tutorial-numbered source
	# filenames map to clean package-facing module names -- see
	# ai/context-todo-examplespackage.md's "Lighting Series Naming" section for the reasoning
	# (never make hyphenated/leading-digit names the canonical import API). Canonical
	# invocation: `python -m OpenSceneGraph.examples lighting.lambert`.
	"lighting/__init__.py=lighting/__init__.py"
	"lighting/00-lambert.py=lighting/lambert.py"
	"lighting/01-blinnphong.py=lighting/blinnphong.py"
	"lighting/02-multilights.py=lighting/multilights.py"
	"lighting/03-hemiambient.py=lighting/hemiambient.py"
	"lighting/04-basecolor.py=lighting/basecolor.py"
	"lighting/05-normalmapping.py=lighting/normalmapping.py"
	"lighting/06-pbr.py=lighting/pbr.py"
	"lighting/07-emissive.py=lighting/emissive.py"
	"lighting/08-shadows.py=lighting/shadows.py"
	"lighting/09-ibl.py=lighting/ibl.py"
	"lighting/10-dynamicprobes.py=lighting/dynamicprobes.py"
	"lighting/11-sketchfab.py=lighting/sketchfab.py"

	# LLM activation/attention visualizations -- same subpackage shape as lighting/ above.
	# llm_common.py is this subpackage's own shared helper module (distinct from the base
	# package's pyosg_example.py/pyosg_visitor.py/pyosg_repl.py). Needs a local model
	# checkpoint + GPU at runtime; not part of any prepared asset catalog (see README.md).
	"llm/__init__.py=llm/__init__.py"
	"llm/README.md=llm/README.md"
	"llm/llm_common.py=llm/llm_common.py"
	"llm/00-qwen-activation-carpet.py=llm/qwen_activation_carpet.py"
	"llm/01-qwen-activation-delta.py=llm/qwen_activation_delta.py"
	"llm/02-qwen-layer-change.py=llm/qwen_layer_change.py"
	"llm/03-qwen-layer-change-history.py=llm/qwen_layer_change_history.py"
)
