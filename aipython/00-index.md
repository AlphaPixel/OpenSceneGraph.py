# aipython + OpenSceneGraph.py — Index

This directory is OpenSceneGraph.py's own accumulated knowledge for driving a
live OSG viewer through the `aipython` MCP bridge (tmux or Jupyter-kernel
backed IPython). It exists because this project's REPL setup has a handful of
sharp, non-obvious edges that get rediscovered by trial and error unless
written down -- several of them cost real debugging sessions before being
pinned down.

**Always read [`01-core.md`](01-core.md) first**, in any session that's about
to drive `viewer.frame()` live via `aipython`, before writing any callback or
running any multi-line block through a tmux-backed session. Everything in it
has been hit for real, more than once, across different sessions.

Read the others situationally:

| File | Read when... |
|---|---|
| [`01-core.md`](01-core.md) | Always, first. Session bootstrap, callback safety, tmux/IPython mechanics. |
| [`02-inspect.md`](02-inspect.md) | Handed a live viewer or loaded scene you didn't build and don't have context on -- get a real read on its structure/shaders/uniforms instead of guessing. |
| [`03-headless-frames.md`](03-headless-frames.md) | Testing callbacks, events, visitors, or Python/C++ trampolines without behavior that genuinely needs a Viewer, graphics context, cull, or draw traversal. |
| [`05-camera-manipulator.md`](05-camera-manipulator.md) | Building/customizing an `osgGA.CameraManipulator` subclass, or doing camera-relative work (e.g. "light the subject from the camera's upper-right"). |
| [`06-camera-effects.md`](06-camera-effects.md) | Layering a TEMPORARY camera effect (shake, kick, scripted move) on top of the user's live manipulator without taking control away -- an update callback on the camera cannot do this, read why before trying. |
| [`07-lighting.md`](07-lighting.md) | Getting PBR/IBL lighting going quickly via `osgx`'s `#pragma osgx::*` shader-library system -- fastest path to a lit glTF model with zero IBL assets, plus the full IBL pipeline when one is worth loading. |
| [`10-rtt.md`](10-rtt.md) | Building a render-to-texture / multi-camera scene graph live (RTT cameras, `osg.Camera()` construction quirks, `Group.children` limitations). |
| [`15-shader-hotswap.md`](15-shader-hotswap.md) | Debugging shader-side logic live by patching GLSL and hot-swapping a `Program`, or when a live variable reassignment "has no effect." |
| [`17-particles.md`](17-particles.md) | Building a one-shot, GPU-only instanced particle/burst effect (fire, explosions, debris) driven purely by `osg_SimulationTime` + a `triggerTime` uniform, or wiring an `osgx.imgui` live-tuning panel on top of one. |
| [`18-deterministic-captures.md`](18-deterministic-captures.md) | Capturing a precise, repeatable animation state by freezing an effect-local elapsed-time uniform instead of racing the realtime frame loop. |
| [`20-object-lifetime.md`](20-object-lifetime.md) | Investigating a leak, a "removed but still alive" object, or verifying true C++ destruction vs. just scene-graph detachment. |
| [`30-pbribl.md`](30-pbribl.md) | Applying `osgx.gltf.pbribl`'s full reflective PBR/IBL renderer to ordinary OSG geometry such as `ShapeDrawable`. |

## Why this exists as `aipython/*.md` and not a Claude Code skill

This is deliberately a plain, agent-agnostic directory of markdown files at
the repo root, not `.claude/skills/`. Multiple "agentic scaffolding" tools
(Claude Code, Codex, others) use this project via the `aipython` MCP server;
putting this knowledge in a Claude-Code-specific location would hide it from
everyone else. The intent is for `aipython` itself to grow a small discovery
feature (scan `<repo>/aipython/*.md`, surface the index) so any connected
agent finds this automatically -- until then, an agent working in this repo
should proactively `ls`/`Read` this directory before starting REPL work here,
the same way it would check `CLAUDE.md`.
