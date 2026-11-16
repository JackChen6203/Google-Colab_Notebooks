# Experimental ComfyUI PyTorch/XLA patch

This patch adds single-device TPU selection and basic XLA-aware ComfyUI memory/attention handling to one pinned upstream ComfyUI revision. It is experimental integration work, not proof that a Krea 2 workflow completes.

## Pinned source and runtime

Apply only to ComfyUI commit `e9afbccc2669677076feb08e52658f129cd8c12b`:

```bash
git checkout e9afbccc2669677076feb08e52658f129cd8c12b
git apply --check /path/to/comfyui_xla_29.patch
git apply /path/to/comfyui_xla_29.patch
```

The only runtime tuple confirmed in the preceding Colab matrix smoke test is:

- Python `3.13.18`
- PyTorch `2.9.0+cpu`
- PyTorch/XLA `2.9.0`
- `libtpu==0.0.21.1`

The preceding Colab run used the existing `/content/comfy-tpu-venv`; there is no verified fresh-install command for this tuple. Do not reinstall or downgrade packages as part of this patch. Check the active environment first with `python -m pip show torch torch_xla libtpu`. A Kaggle runtime must be measured separately. This patch fails during startup if XLA is missing or the active PJRT backend is not TPU; it does not fall back to CPU silently.

## Run

Set `PJRT_DEVICE=TPU` in the runtime before starting ComfyUI, then launch with `--xla`. For example:

```bash
PJRT_DEVICE=TPU python main.py --xla --cpu-vae --listen 127.0.0.1 --port 8188
```

`--xla` selects one local TPU device. This patch does not add SPMD or model sharding. It routes attention through PyTorch SDPA, disables CUDA-only attention kernels and async copy streams, prefers BF16 for TPU text/VAE work, uses XLA memory reports for ComfyUI's partial model loading, and flushes each KSampler step for PyTorch/XLA's lazy graph mode.

Use the Krea 2 Turbo model and the official ComfyUI Krea 2 workflow/settings. Prefer FP8-scaled checkpoints for a single v5e core; BF16 checkpoints and text encoders require much more device memory. `--cpu-vae` leaves extra TPU memory for the diffusion model. NVFP4 is not enabled by this patch and must not be treated as TPU-compatible.

## Validation boundary

The included tests use a mocked XLA runtime to verify device checks, memory-report parsing, synchronization, and the missing-runtime failure path. They do not import ComfyUI's full runtime or prove support for Krea 2 attention/FP8 shapes.

No full ComfyUI launch, Krea 2 model load, denoising step, VAE decode, or saved image was verified on TPU while building this patch. In particular, a matrix multiply smoke test is not end-to-end workflow evidence. The patch should remain marked experimental until the target Colab run records a successful queue, 8 denoising steps, decoded image, and output file.

PyTorch/XLA is now deprecated in favor of TorchTPU; this patch targets the already-verified PyTorch/XLA 2.9 environment only. A TorchTPU backend would need a separate port and validation.

## Unit test

After applying the patch to the pinned checkout:

```bash
python -m unittest tests-unit.comfy_test.test_xla_support -v
```
