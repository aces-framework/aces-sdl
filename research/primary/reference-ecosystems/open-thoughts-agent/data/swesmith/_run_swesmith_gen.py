"""Standalone runner for swesmith full task generation.

Avoids importing data.commons (heavy transitive deps) by calling
create_sandboxed_tasks directly and writing to a user-specified output dir.
"""
import json
import sys
from pathlib import Path

from datasets import load_dataset
from swesmith.profiles import registry


# --- Inline the imports we need from data.swesmith without data.commons ---
from data.swesmith.task_templates import (
    TASK_TOML,
    render_instruction_md,
    render_repo_dockerfile,
    render_test_sh,
    render_solution_script,
    render_test_state_py,
)
from data.swesmith.utils import get_image_names


id_to_docker_image: dict[str, str] = {}


def create_sandboxed_task(datum: dict, out_root: Path, idx: int) -> None:
    rp = registry.get_from_inst(datum)
    test_commands, _ = rp.get_test_cmd(datum)

    d = out_root / f"swesmith-{idx:05d}"
    (d / "environment").mkdir(parents=True, exist_ok=True)
    (d / "solution").mkdir(parents=True, exist_ok=True)
    (d / "tests").mkdir(parents=True, exist_ok=True)

    (d / "task.toml").write_text(TASK_TOML, encoding="utf-8")
    instruction = render_instruction_md(datum["problem_statement"])
    (d / "instruction.md").write_text(instruction, encoding="utf-8")

    dockerfile_content = render_repo_dockerfile(
        docker_image=id_to_docker_image[datum["instance_id"]],
        instance_id=datum["instance_id"],
    )
    (d / "environment" / "Dockerfile").write_text(dockerfile_content, encoding="utf-8")

    if datum["patch"].strip():
        solve_script = render_solution_script(datum["patch"])
        (d / "solution" / "solve.sh").write_text(solve_script, encoding="utf-8")

    (d / "tests" / "config.json").write_text(
        json.dumps(datum, indent=2), encoding="utf-8",
    )

    instance_id = datum["instance_id"]
    test_commands, _ = rp.get_test_cmd(datum)
    run_command = f"git checkout {instance_id}; git checkout HEAD~1; {test_commands}"
    test_sh = render_test_sh(run_command)
    (d / "tests" / "test.sh").write_text(test_sh, encoding="utf-8")

    test_state = render_test_state_py(test_output_path="/logs/test_output.log")
    (d / "tests" / "test_state.py").write_text(test_state, encoding="utf-8")


def main():
    global id_to_docker_image

    out_root = Path("/Users/benjaminfeuer/Documents/tasks/swesmith-full")
    out_root.mkdir(parents=True, exist_ok=True)

    print("Loading SWE-bench/SWE-smith dataset (train split)...")
    ds = load_dataset("SWE-bench/SWE-smith", split="train")
    print(f"Dataset has {len(ds)} rows")

    print("Building instance_id -> docker_image mapping...")
    id_to_docker_image = get_image_names(ds)
    print(f"Mapped {len(id_to_docker_image)} images")

    num_produced = 0
    num_skipped = 0

    for i in range(len(ds)):
        row = ds[i]
        if not row.get("problem_statement") or not row.get("patch"):
            num_skipped += 1
            continue
        if not row["problem_statement"].strip() or not row["patch"].strip():
            num_skipped += 1
            continue

        try:
            create_sandboxed_task(row, out_root, num_produced)
        except Exception as e:
            print(f"  WARN: skipping row {i} ({row.get('instance_id', '?')}): {e}", file=sys.stderr)
            num_skipped += 1
            continue

        num_produced += 1
        if num_produced % 1000 == 0:
            print(f"  ... generated {num_produced} tasks")

    print(f"Done: {num_produced} tasks generated, {num_skipped} skipped")
    print(f"Output: {out_root}")


if __name__ == "__main__":
    main()
