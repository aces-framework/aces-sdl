package main

import rego.v1


test_legacy_root_is_blocked if {
  failures := deny with input as {
    "changed": ["schemas/backend-manifest.json"],
    "check_set": "file-local",
    "policy": {
      "legacy_top_level_roots": ["schemas"],
      "generated_contracts": {"generated_roots": [], "driver_paths": []},
      "concept_authority": {"reserved_path_tokens": [], "allowed_paths": []},
      "source_roots": [],
      "changelog_path": "CHANGELOG.md",
    },
  }
  count(failures) == 1
  some failure in failures
  failure.rule_id == "legacy-top-level-root"
}


test_generated_schema_edits_require_driver_changes if {
  failures := deny with input as {
    "changed": ["contracts/schemas/backend-manifest/backend-manifest-v2.json"],
    "check_set": "file-local",
    "policy": {
      "legacy_top_level_roots": [],
      "generated_contracts": {
        "generated_roots": ["contracts/schemas"],
        "driver_paths": ["tools/generate_contract_schemas.py"],
      },
      "concept_authority": {"reserved_path_tokens": [], "allowed_paths": []},
      "source_roots": [],
      "changelog_path": "CHANGELOG.md",
    },
  }
  count(failures) == 1
  some failure in failures
  failure.rule_id == "generated-schema-direct-edit"
}


test_generated_schema_edits_pass_with_driver_change if {
  failures := deny with input as {
    "changed": [
      "contracts/schemas/backend-manifest/backend-manifest-v2.json",
      "tools/generate_contract_schemas.py",
    ],
    "check_set": "file-local",
    "policy": {
      "legacy_top_level_roots": [],
      "generated_contracts": {
        "generated_roots": ["contracts/schemas"],
        "driver_paths": ["tools/generate_contract_schemas.py"],
      },
      "concept_authority": {"reserved_path_tokens": [], "allowed_paths": []},
      "source_roots": [],
      "changelog_path": "CHANGELOG.md",
    },
  }
  count(failures) == 0
}


test_reserved_concept_authority_paths_are_enforced if {
  failures := deny with input as {
    "changed": ["docs/drafts/concept-authority-notes.md"],
    "check_set": "file-local",
    "policy": {
      "legacy_top_level_roots": [],
      "generated_contracts": {"generated_roots": [], "driver_paths": []},
      "concept_authority": {
        "reserved_path_tokens": ["concept-authority"],
        "allowed_paths": ["docs/explain/reference/shared-concept-model.md"],
      },
      "source_roots": [],
      "changelog_path": "CHANGELOG.md",
    },
  }
  count(failures) == 1
  some failure in failures
  failure.rule_id == "concept-authority-reserved-path"
}


test_changelog_is_required_for_source_changes if {
  failures := deny with input as {
    "changed": ["implementations/python/packages/aces_processor/runtime.py"],
    "check_set": "full",
    "policy": {
      "legacy_top_level_roots": [],
      "generated_contracts": {"generated_roots": [], "driver_paths": []},
      "concept_authority": {"reserved_path_tokens": [], "allowed_paths": []},
      "source_roots": ["implementations/python/packages"],
      "changelog_path": "CHANGELOG.md",
    },
  }
  count(failures) == 1
  some failure in failures
  failure.rule_id == "changelog-required"
}


test_file_local_mode_skips_changelog if {
  failures := deny with input as {
    "changed": ["implementations/python/packages/aces_processor/runtime.py"],
    "check_set": "file-local",
    "policy": {
      "legacy_top_level_roots": [],
      "generated_contracts": {"generated_roots": [], "driver_paths": []},
      "concept_authority": {"reserved_path_tokens": [], "allowed_paths": []},
      "source_roots": ["implementations/python/packages"],
      "changelog_path": "CHANGELOG.md",
    },
  }
  count(failures) == 0
}
