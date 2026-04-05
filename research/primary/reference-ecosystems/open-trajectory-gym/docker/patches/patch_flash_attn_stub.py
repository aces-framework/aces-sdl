#!/usr/bin/env python3
"""Create flash_attn stub package when real flash_attn is not available.

Real flash_attn requires CUDA compilation for the specific GPU arch (e.g. sm_121a
for GB10). When it's not available, SkyRL FSDP worker and vLLM V1 engine fail
at import time. This stub provides:

- flash_attn.bert_padding: pad_input, unpad_input (PyTorch fallback)
- flash_attn.ops.triton.rotary: apply_rotary (PyTorch fallback)
"""
import pathlib
import sysconfig

_site_packages = pathlib.Path(sysconfig.get_path("purelib"))
SITE = _site_packages / "flash_attn"


def main():
    # Check if real flash_attn is already installed and working
    try:
        import flash_attn

        if flash_attn.__version__ != "0.0.0+stub":
            print(
                f"   Patch (flash_attn stub): SKIP (real flash_attn {flash_attn.__version__} installed)"
            )
            return
        else:
            print("   Patch (flash_attn stub): already exists")
            return
    except ImportError:
        pass

    SITE.mkdir(parents=True, exist_ok=True)
    (SITE / "ops").mkdir(exist_ok=True)
    (SITE / "ops" / "triton").mkdir(exist_ok=True)

    # Main __init__.py
    (SITE / "__init__.py").write_text(
        '"""flash_attn stub -- real flash_attn not available on this platform."""\n'
        '__version__ = "0.0.0+stub"\n'
    )

    # bert_padding module (needed by SkyRL FSDP worker)
    (SITE / "bert_padding.py").write_text(
        '"""Stub for flash_attn.bert_padding -- provides PyTorch fallback."""\n'
        "import torch\n"
        "\n"
        "\n"
        "def pad_input(hidden_states, indices, batch, seqlen):\n"
        "    output = torch.zeros(\n"
        "        batch, seqlen, hidden_states.shape[-1],\n"
        "        dtype=hidden_states.dtype, device=hidden_states.device,\n"
        "    )\n"
        "    output.view(-1, hidden_states.shape[-1])[indices] = hidden_states\n"
        "    return output\n"
        "\n"
        "\n"
        "def unpad_input(hidden_states, attention_mask):\n"
        "    seqlens_in_batch = attention_mask.sum(dim=-1, dtype=torch.int32)\n"
        "    indices = torch.nonzero(attention_mask.flatten(), as_tuple=False).flatten()\n"
        "    max_seqlen_in_batch = seqlens_in_batch.max().item()\n"
        "    cu_seqlens = torch.nn.functional.pad(\n"
        "        torch.cumsum(seqlens_in_batch, dim=0, dtype=torch.int32), (1, 0)\n"
        "    )\n"
        "    return (\n"
        "        hidden_states.view(-1, hidden_states.shape[-1])[indices],\n"
        "        indices,\n"
        "        cu_seqlens,\n"
        "        max_seqlen_in_batch,\n"
        "    )\n"
    )

    # ops/__init__.py
    (SITE / "ops" / "__init__.py").write_text("")

    # ops/triton/__init__.py
    (SITE / "ops" / "triton" / "__init__.py").write_text("")

    # ops/triton/rotary.py (needed by vLLM V1)
    (SITE / "ops" / "triton" / "rotary.py").write_text(
        '"""Stub for flash_attn rotary -- PyTorch fallback."""\n'
        "import torch\n"
        "\n"
        "\n"
        "def apply_rotary(x, cos, sin, interleaved=False, inplace=False, conjugate=False):\n"
        "    if interleaved:\n"
        "        x1 = x[..., 0::2]\n"
        "        x2 = x[..., 1::2]\n"
        "    else:\n"
        "        d = x.shape[-1] // 2\n"
        "        x1, x2 = x[..., :d], x[..., d:]\n"
        "    if conjugate:\n"
        "        sin = -sin\n"
        "    o1 = x1 * cos - x2 * sin\n"
        "    o2 = x1 * sin + x2 * cos\n"
        "    if interleaved:\n"
        "        return torch.stack((o1, o2), dim=-1).flatten(-2)\n"
        "    else:\n"
        "        return torch.cat((o1, o2), dim=-1)\n"
    )

    print("   Patch (flash_attn stub): CREATED")


if __name__ == "__main__":
    main()
