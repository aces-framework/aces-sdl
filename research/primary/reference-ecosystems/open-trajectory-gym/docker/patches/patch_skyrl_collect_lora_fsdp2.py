#!/usr/bin/env python3
"""Fix collect_lora_params to handle FSDP2 (no summon_full_params).

Problem: collect_lora_params() in fsdp_utils.py calls FSDP.summon_full_params()
(an FSDP1-only API) when fsdp_version > 0. With FSDP2 (composable API),
summon_full_params doesn't exist and blocks forever, causing sync_weights to hang.

Fix: Check fsdp_version == 2 separately and access params directly (FSDP2
auto-unshards via full_tensor()). Only use summon_full_params for FSDP1.
"""
import sys

filepath = (
    "/usr/local/lib/python3.12/dist-packages/skyrl_train/distributed/fsdp_utils.py"
)

try:
    with open(filepath) as f:
        content = f.read()
except FileNotFoundError:
    print(f"SKIP: {filepath} not found")
    sys.exit(0)

# Check if already patched (handles both variable styles: _fv == 2 or fsdp_version(module) == 2)
if (
    "_fv == 2" in content or "fsdp_version(module) == 2" in content
) and "FSDP2" in content:
    print("patch_skyrl_collect_lora_fsdp2: already applied")
    sys.exit(0)

old = '''def collect_lora_params(module: FSDP) -> OrderedDict:
    """
    collect lora params or full params if base model is not ready in vllm
    requires `module._fsdp_wrapped_module` to be a `PeftModel`
    """
    lora_params = OrderedDict()
    peft_model = getattr(module, "_fsdp_wrapped_module", module)
    if fsdp_version(module) > 0:
        with FSDP.summon_full_params(module, writeback=False):
            # If base model is synced, we can get the full state dict from peft model
            lora_params = get_peft_model_state_dict(peft_model)
            lora_params = {
                name: param.full_tensor().detach().cpu() if hasattr(param, "full_tensor") else param.detach().cpu()
                for name, param in lora_params.items()
            }
        torch.cuda.empty_cache()
    else:
        lora_params = get_peft_model_state_dict(peft_model)
    return lora_params'''

new = '''def collect_lora_params(module: FSDP) -> OrderedDict:
    """
    collect lora params or full params if base model is not ready in vllm
    requires `module._fsdp_wrapped_module` to be a `PeftModel`
    """
    lora_params = OrderedDict()
    peft_model = getattr(module, "_fsdp_wrapped_module", module)
    _fv = fsdp_version(module)
    if _fv == 2:
        # FSDP2: no summon_full_params (FSDP1-only API). Access params directly.
        lora_params = get_peft_model_state_dict(peft_model)
        lora_params = {
            name: param.full_tensor().detach().cpu() if hasattr(param, "full_tensor") else param.detach().cpu()
            for name, param in lora_params.items()
        }
        torch.cuda.empty_cache()
    elif _fv == 1:
        with FSDP.summon_full_params(module, writeback=False):
            # If base model is synced, we can get the full state dict from peft model
            lora_params = get_peft_model_state_dict(peft_model)
            lora_params = {
                name: param.full_tensor().detach().cpu() if hasattr(param, "full_tensor") else param.detach().cpu()
                for name, param in lora_params.items()
            }
        torch.cuda.empty_cache()
    else:
        lora_params = get_peft_model_state_dict(peft_model)
    return lora_params'''

if old not in content:
    print("ERROR: Could not find collect_lora_params function to patch")
    sys.exit(1)

content = content.replace(old, new)
with open(filepath, "w") as f:
    f.write(content)

print("patch_skyrl_collect_lora_fsdp2: applied (FSDP2 path avoids summon_full_params)")
