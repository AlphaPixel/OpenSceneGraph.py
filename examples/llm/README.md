# LLM CUDA/GL examples

This is a sequential series. Each lesson keeps the LLM activations in VRAM and has a CUDA kernel
write directly into the GL vertex buffer that OpenSceneGraph renders. No activation payload is
copied through the CPU.

Run a lesson directly, for example:

```sh
python examples/llm/00-qwen-activation-carpet.py --model /path/to/Qwen "Explain rainbows"
```

The development-tree runner accepts the same scoped name:

```sh
./pyosg-cli llm/00-qwen-activation-carpet -- --model /path/to/Qwen "Explain rainbows"
```

Pass `--step` to advance the model manually: release `N` once for each generated token.
The decoded response is also shown as a deliberately non-billboarded 3-D `PixelText` label beside
the visualization. It retains the most recent ten decoded token fragments; unsupported font
characters are shown as `?` in the scene, while the terminal keeps the exact text.

`00` shows the raw hidden-state coordinates. They do not normally have individual human meanings;
the later examples transform the same GPU data into increasingly legible relative-change views.

1. `00-qwen-activation-carpet.py` - raw per-layer, per-channel coordinates.
2. `01-qwen-activation-delta.py` - change in every coordinate since the preceding token.
3. `02-qwen-layer-change.py` - one relative RMS-change value per layer.
4. `03-qwen-layer-change-history.py` - that per-layer measure accumulated over generated tokens.

`llm_common.py` contains only Qwen stepping and CUDA/GL interop setup. Each numbered file keeps
its own kernel and shaders so the extra idea taught by that step remains visible.
