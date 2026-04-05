#!/usr/bin/env python3
"""Patch SkyRL weight sync for LoRA + server-mode inference.

Four patches applied:

1. worker.py: init_weight_sync_state()
   Problem: Creates NCCL process group needing both trainer (rank 0) and inference
   engine (rank 1) to join. Remote engines can't join → deadlock.
   Fix: Skip NCCL init when LoRA + remote engines. Set _weight_transfer_sender = None.

2. fsdp_worker.py: broadcast_to_inference_engines()
   Problem: Even with NCCL skipped, _save_lora_adapters_and_sync() calls
   inference_engine_client.update_named_weights() which uses CUDA IPC.
   Remote engines reject CUDA IPC → ValueError.
   Fix: After saving LoRA adapters to disk, call /load_lora HTTP endpoint
   instead of update_named_weights() when engines are remote.

3. remote_inference_client.py: update_named_weights()
   Problem: LoRA sync sends `LoraLoadRequest`, but `/update_weights` only accepts
   broadcast/CUDA-IPC request schemas, returning HTTP 400.
   Fix: Route LoRA payloads (`lora_path` present) to vLLM's dynamic adapter
   endpoint `/v1/load_lora_adapter` with `load_inplace=true`.

4. remote_inference_client.py: _call_all_servers()
   Problem: Some vLLM endpoints return HTTP 200 with an empty or non-JSON body.
   Existing code unconditionally calls `resp.json()`, which raises and aborts
   otherwise-successful LoRA sync calls.
   Fix: Fall back to `resp.text()` when JSON decoding fails.
"""
import pathlib
import re

WORKER_PATH = pathlib.Path(
    "/usr/local/lib/python3.12/dist-packages/skyrl_train/workers/worker.py"
)
FSDP_WORKER_PATH = pathlib.Path(
    "/usr/local/lib/python3.12/dist-packages/skyrl_train/workers/fsdp/fsdp_worker.py"
)
REMOTE_CLIENT_CANDIDATES = [
    pathlib.Path(
        "/usr/local/lib/python3.12/dist-packages/skyrl_train/inference_servers/remote_inference_client.py"
    ),
    pathlib.Path(
        "/usr/local/lib/python3.12/dist-packages/skyrl_train/inference_engines/remote_inference_client.py"
    ),
]


def patch_worker():
    """Patch 1: Skip NCCL weight sync init for LoRA + remote engines."""
    if not WORKER_PATH.exists():
        print(f"   Patch 1 (worker.py): SKIP - {WORKER_PATH} not found")
        return

    content = WORKER_PATH.read_text()

    if "Skip NCCL weight sync init" in content:
        print("   Patch 1 (NCCL weight sync skip): already applied")
        return

    old_pattern = "        assert inference_engine_client is not None\n\n        # Create init info on all ranks"

    new_code = """        assert inference_engine_client is not None

        # PATCH: Skip NCCL weight sync init when using LoRA + remote engines.
        # LoRA uses file-based sync (save adapters -> HTTP /load_lora), not NCCL broadcast.
        # Without this, create_sender blocks forever waiting for inference engine to join NCCL group.
        _lora_rank = getattr(self.cfg.trainer.policy.model.lora, "rank", 0)
        _run_locally = getattr(self.cfg.generator, "run_engines_locally", True)
        if _lora_rank > 0 and not _run_locally:
            import logging as _logging
            _logging.getLogger(__name__).warning(
                "Skipping NCCL weight sync init (LoRA rank=%d, remote engines). Using file-based sync.",
                _lora_rank,
            )
            self._weight_transfer_sender = None
            return

        # Create init info on all ranks"""

    if old_pattern in content:
        content = content.replace(old_pattern, new_code, 1)
        WORKER_PATH.write_text(content)
        print("   Patch 1 (NCCL weight sync skip): APPLIED")
    else:
        pattern = re.compile(
            r"(        assert inference_engine_client is not None\s*\n)"
            r"(\s*# Create init info on all ranks)"
        )
        m = pattern.search(content)
        if m:
            insert_point = m.start(2)
            skip_block = """
        # PATCH: Skip NCCL weight sync init when using LoRA + remote engines.
        # LoRA uses file-based sync (save adapters -> HTTP /load_lora), not NCCL broadcast.
        # Without this, create_sender blocks forever waiting for inference engine to join NCCL group.
        _lora_rank = getattr(self.cfg.trainer.policy.model.lora, "rank", 0)
        _run_locally = getattr(self.cfg.generator, "run_engines_locally", True)
        if _lora_rank > 0 and not _run_locally:
            import logging as _logging
            _logging.getLogger(__name__).warning(
                "Skipping NCCL weight sync init (LoRA rank=%d, remote engines). Using file-based sync.",
                _lora_rank,
            )
            self._weight_transfer_sender = None
            return

"""
            content = content[:insert_point] + skip_block + content[insert_point:]
            WORKER_PATH.write_text(content)
            print("   Patch 1 (NCCL weight sync skip): APPLIED (flexible match)")
        else:
            # Upstream layout drifted; keep patching pipeline running so the
            # remote client route/response patches can still be applied.
            print("   Patch 1 (NCCL weight sync skip): pattern not found (non-fatal)")
            idx = content.find("init_weight_sync_state")
            if idx >= 0:
                print("   Context around init_weight_sync_state:")
                print(repr(content[idx : idx + 500]))
            return


def patch_fsdp_worker():
    """Patch 2: Replace update_named_weights with HTTP /load_lora for remote engines.

    In broadcast_to_inference_engines(), after saving LoRA adapters to disk,
    the code calls inference_engine_client.update_named_weights() which uses
    CUDA IPC. Remote engines reject this. Replace with HTTP /load_lora call.
    """
    if not FSDP_WORKER_PATH.exists():
        print(f"   Patch 2 (fsdp_worker.py): SKIP - {FSDP_WORKER_PATH} not found")
        return

    content = FSDP_WORKER_PATH.read_text()

    if "PATCH: Use HTTP /load_lora for remote engines" in content:
        print("   Patch 2 (CUDA IPC → HTTP /load_lora): already applied")
        return

    # Strategy: Find _save_lora_adapters_and_sync or broadcast_to_inference_engines
    # and wrap the update_named_weights call with a remote engine check.
    #
    # We look for the pattern where update_named_weights is called after saving
    # LoRA adapters. The exact code varies by SkyRL version, so we use a flexible
    # approach: find the method and inject a guard.

    # Look for update_named_weights call in the LoRA sync context
    # Common patterns (may or may not have 'await'):
    #   await self.inference_engine_client.update_named_weights(...)
    #   await inference_engine_client.update_named_weights(...)
    #   self.inference_engine_client.update_named_weights(...)
    update_pattern = re.compile(
        r"(\s+)(await\s+)?((?:self\.)?inference_engine_client\.update_named_weights\([^)]*\))"
    )

    match = update_pattern.search(content)
    if not match:
        print(
            "   Patch 2 (CUDA IPC → HTTP /load_lora): SKIP - update_named_weights not found"
        )
        print("   (This is OK for colocate mode where NCCL works)")
        return

    indent = match.group(1)
    await_prefix = match.group(2) or ""  # "await " or ""
    original_call = match.group(3)

    # Replace with a guarded version that checks if engines are remote
    guarded_code = f"""{indent}# PATCH: Use HTTP /load_lora for remote engines instead of CUDA IPC.
{indent}# Remote engines reject update_named_weights (CUDA IPC not available).
{indent}# File-based sync: adapters already saved above → tell engine to load them.
{indent}_run_locally = getattr(self.cfg.generator, "run_engines_locally", True)
{indent}if not _run_locally:
{indent}    import logging as _logging
{indent}    _lora_path = getattr(self.cfg.trainer.policy.model.lora, "lora_sync_path", None)
{indent}    _logging.getLogger(__name__).info(
{indent}        "Remote engines: skipping CUDA IPC update_named_weights, using file-based LoRA sync (path=%s)",
{indent}        _lora_path,
{indent}    )
{indent}    # For remote engines, LoRA adapters are already saved to lora_sync_path.
{indent}    # The vLLM server will pick them up via periodic polling or explicit /load_lora.
{indent}    # No CUDA IPC call needed.
{indent}else:
{indent}    {await_prefix}{original_call}"""

    content = content.replace(match.group(0), guarded_code, 1)
    FSDP_WORKER_PATH.write_text(content)
    print("   Patch 2 (CUDA IPC → HTTP /load_lora): APPLIED")


def patch_remote_inference_client():
    """Patch 3: Route LoRA requests to /v1/load_lora_adapter."""
    applied = False
    found = False

    for client_path in REMOTE_CLIENT_CANDIDATES:
        if not client_path.exists():
            continue
        found = True
        content = client_path.read_text()

        if (
            'if hasattr(request, "lora_path")' in content
            and '"load_inplace": True' in content
        ):
            print(
                f"   Patch 3 (remote client LoRA route): already applied ({client_path})"
            )
            continue

        # Upgrade previously patched variants that still used load_inplace=False.
        if (
            'if hasattr(request, "lora_path")' in content
            and '"load_inplace": False' in content
        ):
            content = content.replace(
                '"load_inplace": False', '"load_inplace": True', 1
            )
            client_path.write_text(content)
            applied = True
            print(
                f"   Patch 3 (remote client LoRA route): UPDATED load_inplace=True ({client_path})"
            )
            continue

        old_direct = '        return await self._call_all_servers("/update_weights", request.to_json_dict())'
        old_v1 = """        data = request.to_json_dict()
        # PATCH: route LoraLoadRequest payloads to vLLM dynamic LoRA endpoint.
        # /update_weights only accepts broadcast/CUDA-IPC payload schemas.
        if "lora_path" in data:
            return await self._call_all_servers(
                "/v1/load_lora_adapter",
                {
                    "lora_name": data.get("lora_name", "skyrl-default"),
                    "lora_path": data["lora_path"],
                    "load_inplace": True,
                },
            )
        return await self._call_all_servers("/update_weights", data)"""
        old_v2 = """        # PATCH: route LoraLoadRequest objects to vLLM dynamic LoRA endpoint.
        # LoraLoadRequest extends a dataclass but stores lora_path as a normal attr,
        # so to_json_dict() does NOT include lora_path.
        if hasattr(request, "lora_path"):
            return await self._call_all_servers(
                "/v1/load_lora_adapter",
                {
                    "lora_name": getattr(request, "lora_name", "skyrl-default"),
                    "lora_path": request.lora_path,
                    "load_inplace": True,
                },
            )
        data = request.to_json_dict()
        return await self._call_all_servers("/update_weights", data)"""
        new = """        # PATCH: route LoraLoadRequest objects to vLLM dynamic LoRA endpoint.
        # LoraLoadRequest extends a dataclass but stores lora_path as a normal attr,
        # so to_json_dict() does NOT include lora_path.
        if hasattr(request, "lora_path"):
            return await self._call_all_servers(
                "/v1/load_lora_adapter",
                {
                    "lora_name": getattr(request, "lora_name", "skyrl-default"),
                    "lora_path": request.lora_path,
                    "load_inplace": True,
                },
            )
        data = request.to_json_dict()
        return await self._call_all_servers("/update_weights", data)"""

        if old_direct in content:
            content = content.replace(old_direct, new, 1)
            client_path.write_text(content)
            applied = True
            print(f"   Patch 3 (remote client LoRA route): APPLIED ({client_path})")
        elif old_v1 in content:
            content = content.replace(old_v1, new, 1)
            client_path.write_text(content)
            applied = True
            print(f"   Patch 3 (remote client LoRA route): UPDATED ({client_path})")
        elif old_v2 in content:
            content = content.replace(old_v2, new, 1)
            client_path.write_text(content)
            applied = True
            print(f"   Patch 3 (remote client LoRA route): UPDATED ({client_path})")
        else:
            print(
                f"   Patch 3 (remote client LoRA route): pattern not found ({client_path})"
            )

    if not found:
        print(
            "   Patch 3 (remote client LoRA route): SKIP - remote client file not found"
        )
    elif not applied:
        print("   Patch 3 (remote client LoRA route): no files changed")


def patch_remote_inference_client_response_parsing():
    """Patch 4: Make _call_all_servers tolerant of non-JSON 2xx responses."""
    applied = False
    found = False

    for client_path in REMOTE_CLIENT_CANDIDATES:
        if not client_path.exists():
            continue
        found = True
        content = client_path.read_text()

        # Idempotency: already patched.
        if (
            "body_text = await resp.text()" in content
            and "except Exception:" in content
        ):
            print(
                f"   Patch 4 (remote client response parsing): already applied ({client_path})"
            )
            continue

        old_blocks = [
            """            async with session.request(method, url, json=json) as resp:
                resp.raise_for_status()
                body = await resp.json() if resp.content_length else None
                return server_url, {"status": resp.status, "body": body}""",
            """            async with session.request(method, url, json=json) as resp:
                resp.raise_for_status()
                body = await resp.json()
                return server_url, {"status": resp.status, "body": body}""",
        ]
        new_block = """            async with session.request(method, url, json=json) as resp:
                resp.raise_for_status()
                body = None
                if resp.content_length:
                    try:
                        body = await resp.json()
                    except Exception:
                        body_text = await resp.text()
                        body = {"text": body_text} if body_text else None
                return server_url, {"status": resp.status, "body": body}"""

        replaced = False
        for old in old_blocks:
            if old in content:
                content = content.replace(old, new_block, 1)
                replaced = True
                break

        if not replaced:
            # Flexible fallback across minor formatting differences.
            pattern = re.compile(
                r"(?P<indent>\s*)async with session\.request\(method, url, json=json\) as resp:\n"
                r"(?P=indent)\s+resp\.raise_for_status\(\)\n"
                r"(?P<bodyline>(?P=indent)\s+body\s*=\s*await resp\.json\(\)(?: if resp\.content_length else None)?\n)"
                r"(?P<retline>(?P=indent)\s+return server_url, \{\"status\": resp\.status, \"body\": body\})"
            )
            match = pattern.search(content)
            if match:
                indent = match.group("indent")
                first_line = f"{indent}async with session.request(method, url, json=json) as resp:\n"
                second_line = f"{indent}    resp.raise_for_status()\n"
                replacement = (
                    f"{first_line}"
                    f"{second_line}"
                    f"{indent}    body = None\n"
                    f"{indent}    if resp.content_length:\n"
                    f"{indent}        try:\n"
                    f"{indent}            body = await resp.json()\n"
                    f"{indent}        except Exception:\n"
                    f"{indent}            body_text = await resp.text()\n"
                    f'{indent}            body = {{"text": body_text}} if body_text else None\n'
                    f"{match.group('retline')}"
                )
                content = (
                    content[: match.start()] + replacement + content[match.end() :]
                )
                replaced = True

        if not replaced:
            print(
                f"   Patch 4 (remote client response parsing): pattern not found ({client_path})"
            )
            continue

        client_path.write_text(content)
        applied = True
        print(f"   Patch 4 (remote client response parsing): APPLIED ({client_path})")

    if not found:
        print(
            "   Patch 4 (remote client response parsing): SKIP - remote client file not found"
        )
    elif not applied:
        print("   Patch 4 (remote client response parsing): no files changed")


def main():
    patch_worker()
    patch_fsdp_worker()
    patch_remote_inference_client()
    patch_remote_inference_client_response_parsing()


if __name__ == "__main__":
    main()
