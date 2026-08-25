# aipython + OpenSceneGraph.py — Index

This directory is OpenSceneGraph.py's accumulated knowledge for driving a
live OSG viewer through the `aipython` MCP bridge (tmux or Jupyter-kernel
backed IPython). It exists because this project's REPL setup has sharp,
non-obvious edges that get rediscovered by trial and error unless written
down.

**Always read [`01-core.md`](01-core.md) first**, in any session that's
about to drive `viewer.frame()` live via `aipython`, before writing any
callback or running any multi-line block through a tmux-backed session.

Read the others situationally:

| File | Read when... |
|---|---|
| [`01-core.md`](01-core.md) | Always, first. Session bootstrap, callback safety, tmux/IPython mechanics, and the Pythonic-vs-raw-OSG binding surface. |
| [`02-inspect.md`](02-inspect.md) | Handed a live viewer or loaded scene you didn't build — get a real read on its structure/shaders/uniforms instead of guessing. |
| [`03-headless-frames.md`](03-headless-frames.md) | Testing callbacks, events, visitors, or Python/C++ trampolines without behavior that genuinely needs a Viewer, graphics context, cull, or draw traversal. |
| [`05-camera-manipulator.md`](05-camera-manipulator.md) | Building/customizing an `osgGA.CameraManipulator` subclass, or doing camera-relative work (e.g. "light the subject from the camera's upper-right"). |
| [`06-camera-effects.md`](06-camera-effects.md) | Layering a TEMPORARY camera effect (shake, kick, scripted move) on top of the user's live manipulator without taking control away. |
| [`07-camera-manual.md`](07-camera-manual.md) | Driving `viewer.camera` directly with NO manipulator (a fixed/orthographic camera) — `realize()`-before-matrices ordering, near/far, and viewport-confinement gotchas. |
| [`08-lighting.md`](08-lighting.md) | Getting PBR/IBL lighting going via `osgx`'s `#pragma osgx::*` shader-library system — fastest path to a lit glTF model, plus the full IBL pipeline. |
| [`09-picking.md`](09-picking.md) | Wiring `osgx` (hover/click) into a scene that ALSO has an `osgx.imgui.Widget` panel — three independent guards needed to block picking near/under ImGui. |
| [`10-rtt.md`](10-rtt.md) | Building a render-to-texture / multi-camera scene graph live. **Read before debugging any fullscreen pass that outputs one flat color** — fullscreen quads must disable `GL_DEPTH_TEST` or they break silently once re-targeted to an FBO. |
| [`15-shader-hotswap.md`](15-shader-hotswap.md) | Debugging shader-side logic live by patching GLSL and hot-swapping a `Program`, or when a live variable reassignment "has no effect." |
| [`17-particles.md`](17-particles.md) | Building a one-shot, GPU-only instanced particle/burst effect (fire, explosions, debris) driven by `osg_SimulationTime` + a `triggerTime` uniform, or wiring an `osgx.imgui` live-tuning panel on top of one. |
| [`18-deterministic-captures.md`](18-deterministic-captures.md) | Capturing a precise, repeatable animation state by freezing an effect-local elapsed-time uniform instead of racing the realtime frame loop. |
| [`20-object-lifetime.md`](20-object-lifetime.md) | Investigating a leak, a "removed but still alive" object, or verifying true C++ destruction vs. just scene-graph detachment. |
| [`25-async-osgpy.md`](25-async-osgpy.md) | Any background OSG.py operation (not just glTF loading): push vs. poll, why a naive async loader can be *slower* than sync (GIL contention between the render pump and a push-based progress mechanism), making `viewer.frame()` an ordinary `asyncio` task, and where the ceiling is (GIL, non-preemptible `frame()`, cooperative cancellation). Read before assuming async is "free" overlap with rendering. |
| [`29-material.md`](29-material.md) | Setting a PBR material (base color/roughness/metallic/maps) on any Drawable via `osgx.Material` — a real `osg.StateAttribute`. Read before `30-pbribl.md` if you just need factors on a shape, no full IBL renderer. |
| [`30-pbribl.md`](30-pbribl.md) | Applying `osgx.gltf.pbribl`'s full reflective PBR/IBL renderer to ordinary OSG geometry such as `ShapeDrawable`. |
| [`40-typed-lights-gizmos.md`](40-typed-lights-gizmos.md) | Adding typed direct/punctual lights (`osgx.LightSet` — Point/Directional/Spot/Sphere) and their debug gizmos (`osgx.LightGizmos`/`osgx.LightMarkers`) to a live scene; also documents the `osgx_DirectLighting()` hook contract every direct-lit shader should call into. |

## Why this exists as `aipython/*.md` and not a Claude Code skill

Deliberately a plain, agent-agnostic directory of markdown files at the repo
root, not `.claude/skills/`. Multiple agentic tools (Claude Code, Codex,
others) use this project via the `aipython` MCP server; a Claude-Code-specific
location would hide this from the rest. An agent working in this repo should
proactively `ls`/`Read` this directory before starting REPL work here, the
same way it would check `CLAUDE.md`.
