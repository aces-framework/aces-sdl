"""Tests for SDL parser — YAML loading, key normalization, shorthands."""

import re
from pathlib import Path

import pytest

from aces.core.sdl import instantiate_scenario
from aces.core.sdl._errors import SDLParseError
from aces.core.sdl.nodes import NodeType
from aces.core.sdl.parser import parse_sdl, parse_sdl_file


class TestKeyNormalization:
    def test_lowercase_keys(self):
        s = parse_sdl("name: test\nnodes:\n  sw:\n    type: switch")
        assert "sw" in s.nodes

    def test_uppercase_keys(self):
        """Pydantic field keys are normalized but user-defined names are preserved."""
        s = parse_sdl("Name: test\nNodes:\n  SW:\n    Type: Switch")
        assert "SW" in s.nodes  # user-defined name preserved as-is
        assert s.nodes["SW"].type == NodeType.SWITCH  # enum value normalized

    def test_hyphenated_keys(self):
        sdl = """
name: test
nodes:
  vm-1:
    type: vm
    resources:
      ram: 1 gib
      cpu: 1
infrastructure:
  vm-1:
    count: 1
"""
        s = parse_sdl(sdl)
        assert "vm-1" in s.nodes

    def test_integer_keys_in_user_defined_mapping_are_rejected(self):
        # YAML lets authors write a bare ``1:`` as a key, which yaml.safe_load
        # parses as an integer. User-defined hashmap keys (node names, role
        # names, etc.) bypass the field-key normalization pass so the
        # integer survives until Pydantic. Closed-world ``SDLModel`` rejects
        # non-string keys; this test pins that contract so a future loosening
        # of the dict-key types (or a silent coerce-to-string) surfaces as a
        # test failure rather than a downstream cross-reference bug.
        sdl = """
name: test
nodes:
  vm:
    type: vm
    resources: {ram: 1 gib, cpu: 1}
    roles:
      1: admin
"""
        with pytest.raises(SDLParseError) as excinfo:
            parse_sdl(sdl)
        assert "string" in str(excinfo.value).lower() or "type=string_type" in str(excinfo.value)

    def test_non_string_top_level_keys_are_rejected_cleanly(self):
        with pytest.raises(SDLParseError, match="top-level mapping keys must be strings"):
            parse_sdl("?")

    @pytest.mark.parametrize(
        ("sdl", "key_path"),
        [
            (
                """
name: test
variables:
  node_name:
    type: string
    default: sw
nodes:
  ${node_name}:
    type: switch
""",
                "nodes.${node_name}",
            ),
            (
                """
name: test
nodes:
  vm:
    type: vm
    resources: {ram: 1 gib, cpu: 1}
    roles:
      ${role_name}: root
""",
                "nodes.vm.roles.${role_name}",
            ),
            (
                """
name: test
nodes:
  net:
    type: switch
  vm:
    type: vm
    resources: {ram: 1 gib, cpu: 1}
infrastructure:
  net:
    count: 1
    properties: {cidr: 10.0.0.0/24, gateway: 10.0.0.1}
  vm:
    count: 1
    links: [net]
    properties:
      - ${link_name}: 10.0.0.10
""",
                "infrastructure.vm.properties[0].${link_name}",
            ),
            (
                """
name: test
objectives:
  ${objective_name}:
    agent: red-agent
    success:
      goals: [pass-exercise]
""",
                "objectives.${objective_name}",
            ),
        ],
    )
    def test_variable_placeholders_rejected_in_mapping_keys(self, sdl, key_path):
        with pytest.raises(
            SDLParseError,
            match=re.escape(f"user-defined mapping keys: '{key_path}'"),
        ):
            parse_sdl(sdl)


class TestShorthandExpansion:
    def test_objectives_section_parses(self):
        sdl = """
name: test
entities:
  red-team:
    role: Red
agents:
  red-agent:
    entity: red-team
    actions: [Scan, Exploit]
goals:
  pass-exercise:
    tlos: [web-defense]
tlos:
  web-defense:
    evaluation: overall
evaluations:
  overall:
    metrics: [service-uptime]
    min-score: 75
metrics:
  service-uptime:
    type: manual
    max-score: 100
objectives:
  initial-access:
    agent: red-agent
    actions: [Scan]
    targets: [red-agent]
    success:
      goals: [pass-exercise]
"""
        s = parse_sdl(sdl, skip_semantic_validation=True)
        assert s.objectives["initial-access"].agent == "red-agent"
        assert s.objectives["initial-access"].success.goals == ["pass-exercise"]
        assert s.advisories == []

    def test_workflows_section_parses(self):
        sdl = """
name: test
entities:
  blue-team:
    role: Blue
metrics:
  release-check:
    type: manual
    max-score: 100
evaluations:
  eval-1:
    metrics: [release-check]
    min-score: 75
tlos:
  tlo-1:
    evaluation: eval-1
goals:
  pass-exercise:
    tlos: [tlo-1]
objectives:
  validate-release:
    entity: blue-team
    success:
      goals: [pass-exercise]
workflows:
  release-response:
    start: validate
    steps:
      validate:
        type: objective
        objective: validate-release
        on-success: finish
      finish:
        type: end
"""
        s = parse_sdl(sdl, skip_semantic_validation=True)
        assert s.workflows["release-response"].start == "validate"
        assert "validate" in s.workflows["release-response"].steps

    def test_vm_without_resources_generates_advisory(self):
        sdl = """
name: test
nodes:
  vm:
    type: VM
"""
        s = parse_sdl(sdl)
        assert any("without 'resources'" in advisory for advisory in s.advisories)

    def test_runtime_configuration_parses_without_overloading_other_sections(self):
        sdl = """
name: shuffle-runtime-inventory
nodes:
  shuffle-backend:
    type: vm
    os: linux
    runtime:
      mounts:
        - target: /shuffle-database
          source: aptl_shuffle_data
          source-kind: volume
          filesystem-type: ext4
          read-only: false
          options: [rw, nosuid]
          propagation: rprivate
          stability: volume-backed
          backend-generated: true
      filesystem-inventory:
        - path: /app/app.py
          entry-type: file
          owner-user: root
          owner-group: root
          uid: "0"
          gid: "0"
          mode: "0644"
          size: "4096"
          content-digest: 4f8c2d
          digest-algorithm: sha256
          source-path: src/webapp/app.py
          provenance: python-package
          stability: stable
          sensitivity: plain
        - path: /var/log/gunicorn/access.log
          entry-type: file
          mode: "0600"
          stability: log
          sensitivity: operator-secret
      local-control-interfaces:
        - path: /run/docker.sock
          kind: unix-socket
          protocol: docker
          bind-source: /var/run/docker.sock
          access: read-write
      process:
        pid: 1
        command: ./shufflebackend
        user: root
        working-directory: /app
      processes:
        - name: supervisord
          pid: 1
          command: supervisord -n
          role: supervisor
        - name: gunicorn
          parent-pid: 1
          command: [gunicorn, app:app]
          role: worker
      environment:
        - name: TECHVAULT_ADMIN_PASSWORD
          value-classification: redacted
          provenance: operator
        - name: SCENARIO_FIXTURE_TOKEN
          value: fixture-token
          value-classification: secret-fixture
          provenance: compose
      linux-capabilities:
        required: [CAP_NET_ADMIN]
        effective: CAP_NET_ADMIN
      operational-policy:
        restart: unless-stopped
        resource-limits:
          memory: 512 MiB
          cpu: 0.5
          pids: 128
      container:
        entrypoint: [/entrypoint.sh]
        command: [gunicorn, app:app]
        log-driver: json-file
        log-options:
          max-size: 10m
          max-file: "3"
        namespaces:
          cgroup: private
          ipc: private
          pid: private
          userns: host
          uts: private
        privileged: false
        read-only-rootfs: false
        publish-all-ports: false
        autoremove: false
        shm-size: 64 MiB
        masked-paths: [/proc/acpi, /proc/kcore]
        read-only-paths: /proc/sys
        cgroup-parent: /docker
        runtime-name: runc
        devices:
          - host-path: /dev/null
            container-path: /dev/null
            permissions: rwm
        device-cgroup-rules: c 1:3 rwm
        extra-hosts:
          - hostname: wazuh-manager
            address: 172.20.0.10
        dns: [8.8.8.8]
        dns-options: ndots:0
        dns-search: [techvault.local]
        group-add: [adm, "101"]
      health:
        status: healthy
        failing-streak: "0"
        log:
          - start: "2026-05-20T12:00:00Z"
            end: "2026-05-20T12:00:01Z"
            exit-code: "0"
            output: ok
      packages:
        - manager: apk
          name: musl
          version: 1.2.4-r2
      dependency-manifests:
        - ecosystem: go
          path: /app/go.mod
          format: go-module
      package-vulnerabilities:
        - id: CVE-2026-12345
          package-name: musl
          installed-version: 1.2.4-r2
          fixed-version: 1.2.5-r0
          severity: high
          scanner: trivy
          image-digest: sha256:abc123
          scan-time: "2026-05-20T12:00:00Z"
"""
        scenario = parse_sdl(sdl)
        node = scenario.nodes["shuffle-backend"]

        assert node.services == []
        assert scenario.vulnerabilities == {}
        assert node.runtime is not None
        assert node.runtime.mounts[0].target == "/shuffle-database"
        assert node.runtime.mounts[0].filesystem_type == "ext4"
        assert node.runtime.mounts[0].propagation == "rprivate"
        assert node.runtime.mounts[0].stability == "volume_backed"
        assert node.runtime.mounts[0].backend_generated is True
        assert node.runtime.filesystem_inventory[0].path == "/app/app.py"
        assert node.runtime.filesystem_inventory[0].entry_type == "file"
        assert node.runtime.filesystem_inventory[0].uid == 0
        assert node.runtime.filesystem_inventory[0].gid == 0
        assert node.runtime.filesystem_inventory[0].mode == "0644"
        assert node.runtime.filesystem_inventory[0].size == 4096
        assert node.runtime.filesystem_inventory[0].digest_algorithm == "sha256"
        assert node.runtime.filesystem_inventory[0].content_digest == "4f8c2d"
        assert node.runtime.filesystem_inventory[0].source_path == "src/webapp/app.py"
        assert node.runtime.filesystem_inventory[0].stability == "stable"
        assert node.runtime.filesystem_inventory[1].stability == "log"
        assert node.runtime.filesystem_inventory[1].sensitivity == "operator_secret"
        assert node.runtime.local_control_interfaces[0].path == "/run/docker.sock"
        assert node.runtime.process is not None
        assert node.runtime.process.command == ["./shufflebackend"]
        assert node.runtime.processes[0].name == "supervisord"
        assert node.runtime.processes[1].parent_pid == 1
        assert node.runtime.environment[0].name == "TECHVAULT_ADMIN_PASSWORD"
        assert node.runtime.environment[0].value_classification == "redacted"
        assert node.runtime.environment[1].value_classification == "secret_fixture"
        assert node.runtime.linux_capabilities.required == ["CAP_NET_ADMIN"]
        assert node.runtime.linux_capabilities.effective == ["CAP_NET_ADMIN"]
        assert node.runtime.operational_policy.restart == "unless_stopped"
        assert node.runtime.operational_policy.resource_limits.memory == 512 * 1048576
        assert node.runtime.operational_policy.resource_limits.cpu == 0.5
        assert node.runtime.operational_policy.resource_limits.pids == 128
        assert node.runtime.container is not None
        assert node.runtime.container.entrypoint == ["/entrypoint.sh"]
        assert node.runtime.container.command == ["gunicorn", "app:app"]
        assert node.runtime.container.log_driver == "json-file"
        assert node.runtime.container.log_options == {"max-size": "10m", "max-file": "3"}
        assert node.runtime.container.namespaces.userns == "host"
        assert node.runtime.container.shm_size == 64 * 1048576
        assert node.runtime.container.masked_paths == ["/proc/acpi", "/proc/kcore"]
        assert node.runtime.container.read_only_paths == ["/proc/sys"]
        assert node.runtime.container.devices[0].container_path == "/dev/null"
        assert node.runtime.container.device_cgroup_rules == ["c 1:3 rwm"]
        assert node.runtime.container.extra_hosts[0].hostname == "wazuh-manager"
        assert node.runtime.container.dns_options == ["ndots:0"]
        assert node.runtime.container.group_add == ["adm", "101"]
        assert node.runtime.health is not None
        assert node.runtime.health.status == "healthy"
        assert node.runtime.health.failing_streak == 0
        assert node.runtime.health.log[0].exit_code == 0
        assert node.runtime.packages[0].manager == "apk"
        assert node.runtime.packages[0].name == "musl"
        assert node.runtime.packages[0].version == "1.2.4-r2"
        assert node.runtime.dependency_manifests[0].ecosystem == "go"
        assert node.runtime.dependency_manifests[0].path == "/app/go.mod"
        assert node.runtime.dependency_manifests[0].format == "go-module"
        assert node.runtime.package_vulnerabilities[0].id == "CVE-2026-12345"
        assert node.runtime.package_vulnerabilities[0].package_name == "musl"
        assert node.runtime.package_vulnerabilities[0].installed_version == "1.2.4-r2"
        assert node.runtime.package_vulnerabilities[0].fixed_version == "1.2.5-r0"
        assert node.runtime.package_vulnerabilities[0].severity == "high"
        assert node.runtime.package_vulnerabilities[0].scanner == "trivy"
        assert node.runtime.package_vulnerabilities[0].image_digest == "sha256:abc123"
        assert node.runtime.package_vulnerabilities[0].scan_time == "2026-05-20T12:00:00Z"

    def test_runtime_local_identity_inventory_parses_with_kebab_keys(self):
        sdl = """
name: techvault-identity-inventory
nodes:
  techvault-webapp:
    type: vm
    os: linux
    runtime:
      local-identity:
        description: getent passwd/group capture
        users:
          - username: root
            uid: 0
            primary-gid: 0
            primary-group: root
            gecos: root
            home: /root
            shell: /bin/bash
            provenance: image
            stability: stable
          - username: www-data
            uid: 33
            primary-gid: 33
            primary-group: www-data
            home: /var/www
            shell: /usr/sbin/nologin
            supplemental-groups: [wazuh]
            no-login: true
            provenance: package
        groups:
          - name: root
            gid: 0
            members: [root]
          - name: wazuh
            gid: 101
            members: [www-data]
        sudo-rules:
          - principal: operator
            principal-kind: user
            run-as-users: [root]
            commands: ["/usr/bin/systemctl restart gunicorn"]
            nopasswd: true
"""
        scenario = parse_sdl(sdl)
        identity = scenario.nodes["techvault-webapp"].runtime.local_identity
        assert identity is not None
        assert identity.description == "getent passwd/group capture"
        assert identity.users[0].username == "root"
        assert identity.users[0].primary_gid == 0
        assert identity.users[0].provenance == "image"
        assert identity.users[1].username == "www-data"
        assert identity.users[1].no_login is True
        assert identity.users[1].supplemental_groups == ["wazuh"]
        assert identity.users[1].provenance == "package"
        assert identity.groups[1].name == "wazuh"
        assert identity.groups[1].gid == 101
        assert identity.sudo_rules[0].principal == "operator"
        assert identity.sudo_rules[0].run_as_users == ["root"]
        assert identity.sudo_rules[0].commands == ["/usr/bin/systemctl restart gunicorn"]
        assert identity.sudo_rules[0].nopasswd is True

    def test_runtime_local_identity_uid_variable_substitutes_on_instantiation(self):
        sdl = """
name: techvault-identity-variable
variables:
  svc_uid:
    type: integer
    required: true
nodes:
  techvault-webapp:
    type: vm
    os: linux
    runtime:
      local-identity:
        users:
          - username: wazuh
            uid: ${svc_uid}
            home: /var/ossec
            shell: /usr/sbin/nologin
            no-login: true
"""
        raw = parse_sdl(sdl)
        assert raw.nodes["techvault-webapp"].runtime.local_identity.users[0].uid == "${svc_uid}"
        instantiated = instantiate_scenario(raw, parameters={"svc_uid": 999})
        user = instantiated.nodes["techvault-webapp"].runtime.local_identity.users[0]
        assert user.uid == 999
        assert user.no_login is True

    def test_source_build_provenance_parses_with_kebab_keys(self):
        sdl = """
name: techvault-build-provenance
nodes:
  techvault-webapp:
    type: vm
    os: linux
    source:
      name: techvault-webapp
      version: local
      build:
        base-image: python:3.12-slim
        base-image-digest: sha256:deadbeef
        dockerfile-path: containers/webapp/Dockerfile
        instructions:
          - instruction: from
            arguments: [python:3.12-slim]
          - instruction: copy
            arguments: [webapp/app.py, /app/app.py]
        layers:
          - digest: sha256:layer1
            created-by: FROM python:3.12-slim
            size: "31000000"
          - created-by: ENV APP_HOME=/app
            empty: true
        build-args:
          - name: APP_VERSION
            value: 1.4.2
            value-classification: plain
          - name: PIP_INDEX_TOKEN
            value-classification: redacted
        copied-sources:
          - source-path: webapp/app.py
            destination-path: /app/app.py
        config:
          entrypoint: [/entrypoint.sh]
          command: [gunicorn, app:app]
          working-directory: /app
          exposed-ports: [8080/tcp]
          labels:
            org.opencontainers.image.source: https://example.test/techvault
            com.Example.Tier: webapp
          default-environment:
            - name: APP_HOME
              value: /app
        source-inputs:
          - identifier: webapp-app
            source-path: webapp/app.py
            destination-path: /app/app.py
            checksum: 4f8c2d
            checksum-algorithm: sha256
        attestation:
          status: absent
          verification: not-applicable
          attestation-type: in-toto
"""
        s = parse_sdl(sdl, skip_semantic_validation=True)
        build = s.nodes["techvault-webapp"].source.build

        assert build is not None
        assert build.base_image == "python:3.12-slim"
        assert build.dockerfile_path == "containers/webapp/Dockerfile"
        assert build.instructions[1].instruction.value == "copy"
        assert build.instructions[1].arguments == ["webapp/app.py", "/app/app.py"]
        assert build.layers[0].size == 31000000
        assert build.layers[1].empty is True
        assert build.build_args[1].value_classification.value == "redacted"
        assert build.copied_sources[0].destination_path == "/app/app.py"
        assert build.config.working_directory == "/app"
        assert build.config.exposed_ports == ["8080/tcp"]
        # Native, case-sensitive image label keys are preserved verbatim.
        assert build.config.labels == {
            "org.opencontainers.image.source": "https://example.test/techvault",
            "com.Example.Tier": "webapp",
        }
        assert build.config.default_environment[0].name == "APP_HOME"
        assert build.source_inputs[0].checksum_algorithm == "sha256"
        assert build.attestation.verification.value == "not_applicable"
        assert build.attestation.attestation_type.value == "in_toto"

    def test_source_shorthand(self):
        sdl = """
name: test
features:
  svc:
    type: service
    source: my-package
"""
        s = parse_sdl(sdl, skip_semantic_validation=True)
        assert s.features["svc"].source.name == "my-package"
        assert s.features["svc"].source.version == "*"

    def test_source_longhand(self):
        sdl = """
name: test
features:
  svc:
    type: service
    source:
      name: my-package
      version: 2.0.0
"""
        s = parse_sdl(sdl, skip_semantic_validation=True)
        assert s.features["svc"].source.version == "2.0.0"

    def test_infrastructure_count_shorthand(self):
        sdl = """
name: test
nodes:
  sw:
    type: switch
infrastructure:
  sw: 1
"""
        s = parse_sdl(sdl)
        assert s.infrastructure["sw"].count == 1

    def test_infrastructure_count_placeholder_shorthand(self):
        sdl = """
name: test
variables:
  switch_count:
    type: integer
    default: 1
nodes:
  sw:
    type: switch
infrastructure:
  sw: ${switch_count}
"""
        s = parse_sdl(sdl)
        assert s.infrastructure["sw"].count == "${switch_count}"

    def test_role_shorthand(self):
        sdl = """
name: test
nodes:
  vm:
    type: vm
    resources:
      ram: 1 gib
      cpu: 1
    roles:
      admin: "admin-user"
"""
        s = parse_sdl(sdl)
        assert s.nodes["vm"].roles["admin"].username == "admin-user"

    def test_min_score_shorthand(self):
        sdl = """
name: test
conditions:
  c1:
    command: /check
    interval: 10
metrics:
  m1:
    type: conditional
    max-score: 10
    condition: c1
evaluations:
  e1:
    metrics:
      - m1
    min-score: 75
"""
        s = parse_sdl(sdl, skip_semantic_validation=True)
        assert s.evaluations["e1"].min_score.percentage == 75

    def test_min_score_placeholder_shorthand(self):
        sdl = """
name: test
variables:
  pass_pct:
    type: integer
    default: 75
conditions:
  c1:
    command: /check
    interval: 10
metrics:
  m1:
    type: conditional
    max-score: 10
    condition: c1
evaluations:
  e1:
    metrics:
      - m1
    min-score: ${pass_pct}
"""
        s = parse_sdl(sdl)
        assert s.evaluations["e1"].min_score.percentage == "${pass_pct}"

    def test_entity_facts_keys_preserved(self):
        sdl = """
name: test
entities:
  blue-team:
    name: Blue Team
    facts:
      Department-Name: SOC
      Shift: nights
"""
        s = parse_sdl(sdl, skip_semantic_validation=True)
        assert s.entities["blue-team"].facts == {
            "Department-Name": "SOC",
            "Shift": "nights",
        }

    def test_feature_key_named_source_is_not_treated_as_source_field(self):
        sdl = """
name: test
nodes:
  web:
    type: vm
    resources: {ram: 1 gib, cpu: 1}
    roles: {admin: root}
    features:
      source: admin
features:
  source:
    type: service
    source: busybox
infrastructure:
  web: {count: 1}
"""
        s = parse_sdl(sdl, skip_semantic_validation=True)
        assert s.nodes["web"].features == {"source": "admin"}
        assert s.features["source"].source.name == "busybox"

    def test_entity_fact_key_named_source_is_not_treated_as_source_field(self):
        sdl = """
name: test
entities:
  blue-team:
    facts:
      source: internal-doc
"""
        s = parse_sdl(sdl, skip_semantic_validation=True)
        assert s.entities["blue-team"].facts == {"source": "internal-doc"}

    def test_ocr_duration_units_parse(self):
        sdl = """
name: test
events:
  phase-1: {}
scripts:
  main:
    start-time: 1 us
    end-time: 1 mon
    speed: 1
    events:
      phase-1: 1 ms
stories:
  exercise:
    scripts: [main]
"""
        s = parse_sdl(sdl)
        assert s.scripts["main"].start_time == 1
        assert s.scripts["main"].end_time == 2_592_000
        assert s.scripts["main"].events["phase-1"] == 1

    def test_leaf_enum_placeholders_parse(self):
        sdl = """
name: test
variables:
  account_strength:
    type: string
    default: strong
  host_os:
    type: string
    default: linux
  acl_action:
    type: string
    default: allow
  success_mode:
    type: string
    default: any_of
  team_role:
    type: string
    default: blue
nodes:
  net:
    type: switch
  vm:
    type: vm
    os: ${host_os}
    resources: {ram: 1 gib, cpu: 1}
infrastructure:
  net:
    count: 1
    properties: {cidr: 10.0.0.0/24, gateway: 10.0.0.1}
    acls:
      - {name: allow-admin, direction: in, from_net: net, action: "${acl_action}"}
  vm:
    count: 1
    links: [net]
entities:
  blue-team:
    role: ${team_role}
accounts:
  admin:
    username: admin
    node: vm
    password_strength: ${account_strength}
goals:
  pass-exercise:
    tlos: [tlo-1]
tlos:
  tlo-1:
    evaluation: eval-1
evaluations:
  eval-1:
    metrics: [release-check]
    min-score: 75
metrics:
  release-check:
    type: manual
    max-score: 100
objectives:
  review:
    entity: blue-team
    success:
      mode: ${success_mode}
      goals: [pass-exercise]
"""
        s = parse_sdl(sdl)
        assert s.nodes["vm"].os == "${host_os}"
        assert s.infrastructure["net"].acls[0].action == "${acl_action}"
        assert s.entities["blue-team"].role == "${team_role}"
        assert s.accounts["admin"].password_strength == "${account_strength}"
        assert s.objectives["review"].success.mode == "${success_mode}"

    def test_negative_numeric_duration_rejected(self):
        sdl = """
name: test
events:
  phase-1: {}
scripts:
  main:
    start-time: -5
    end-time: 10
    speed: 1
    events:
      phase-1: 1
stories:
  exercise:
    scripts: [main]
"""
        with pytest.raises(SDLParseError, match="Invalid duration"):
            parse_sdl(sdl)


class TestFormat:
    def test_ocr_format(self):
        s = parse_sdl("name: test\nnodes:\n  sw:\n    type: switch")
        assert s.name == "test"

    def test_switch_rejects_vm_only_fields(self):
        sdl = """
name: test
nodes:
  sw:
    type: switch
    os: linux
    services:
      - port: 80
        name: http
"""
        with pytest.raises(SDLParseError, match="Switch nodes cannot have VM-only fields"):
            parse_sdl(sdl)

    @pytest.mark.parametrize(
        "field_name",
        [
            "nodes.vm.type",
            "features.svc.type",
            "content.seed.type",
            "metrics.m1.type",
            "relationships.r1.type",
            "variables.v1.type",
        ],
    )
    def test_discriminant_enums_reject_placeholders(self, field_name):
        sdl_by_field = {
            "nodes.vm.type": """
name: test
nodes:
  vm:
    type: ${node_type}
""",
            "features.svc.type": """
name: test
features:
  svc:
    type: ${feature_type}
""",
            "content.seed.type": """
name: test
nodes:
  vm:
    type: vm
    resources: {ram: 1 gib, cpu: 1}
content:
  seed:
    type: ${content_type}
    target: vm
""",
            "metrics.m1.type": """
name: test
metrics:
  m1:
    type: ${metric_type}
    max-score: 100
""",
            "relationships.r1.type": """
name: test
nodes:
  vm:
    type: vm
    resources: {ram: 1 gib, cpu: 1}
relationships:
  r1:
    type: ${relationship_type}
    source: vm
    target: vm
""",
            "variables.v1.type": """
name: test
variables:
  v1:
    type: ${variable_type}
    default: hello
""",
        }
        with pytest.raises(SDLParseError, match=rf"{field_name}[\s\S]*Input should be"):
            parse_sdl(sdl_by_field[field_name], skip_semantic_validation=True)

    @pytest.mark.parametrize(
        ("sdl", "message"),
        [
            (
                """
name: test
content:
  c1:
    type: file
""",
                "Content requires 'target'",
            ),
            (
                """
name: test
accounts:
  a1:
    username: admin
""",
                "Account requires 'node'",
            ),
            (
                """
name: test
agents:
  red-agent:
    actions: [Scan]
""",
                "Agent requires 'entity'",
            ),
        ],
    )
    def test_extension_sections_reject_missing_anchor_fields(self, sdl, message):
        with pytest.raises(SDLParseError, match=message):
            parse_sdl(sdl)


class TestErrorHandling:
    def test_empty_content(self):
        with pytest.raises(SDLParseError, match="empty"):
            parse_sdl("")

    def test_invalid_yaml(self):
        with pytest.raises(SDLParseError, match="YAML"):
            parse_sdl(":::invalid")

    def test_non_mapping(self):
        with pytest.raises(SDLParseError, match="mapping"):
            parse_sdl("- just\n- a\n- list")

    def test_no_identity(self):
        with pytest.raises(SDLParseError, match="name"):
            parse_sdl("description: no name or metadata")


class TestSkipSemanticValidation:
    def test_structural_only(self):
        """skip_semantic_validation=True skips cross-reference checks."""
        s = parse_sdl(
            "name: test\ngoals:\n  g1:\n    tlos:\n      - missing-tlo",
            skip_semantic_validation=True,
        )
        assert "g1" in s.goals


class TestModuleImports:
    def test_parse_sdl_rejects_imports_without_file_context(self):
        with pytest.raises(SDLParseError, match="parse_sdl_file"):
            parse_sdl(
                """
                name: root
                imports:
                  - path: common.yaml
                """
            )

    def test_parse_sdl_file_expands_namespaced_imports(self, tmp_path: Path):
        imported = tmp_path / "common.yaml"
        imported.write_text(
            """
name: common
version: 1.2.0
nodes:
  vm:
    type: vm
    os: linux
    resources: {ram: 1 gib, cpu: 1}
    conditions: {health: ops}
    roles:
      ops:
        username: operator
conditions:
  health:
    command: /bin/true
    interval: 15
entities:
  blue:
    role: blue
objectives:
  validate:
    entity: blue
    success:
      conditions: [health]
workflows:
  response:
    start: run
    steps:
      run:
        type: objective
        objective: validate
        on-success: finish
      finish:
        type: end
""",
            encoding="utf-8",
        )
        root = tmp_path / "root.yaml"
        root.write_text(
            """
name: root
imports:
  - path: common.yaml
    namespace: shared
    version: 1.2.0
""",
            encoding="utf-8",
        )

        scenario = parse_sdl_file(root)

        assert "shared.vm" in scenario.nodes
        assert "shared.health" in scenario.conditions
        assert "shared.validate" in scenario.objectives
        assert "shared.response" in scenario.workflows

    def test_parse_sdl_file_namespaces_named_qualified_refs(self, tmp_path: Path):
        # Composition must rewrite section-qualified named refs
        # (e.g. ``nodes.vm``, ``content.docs.items.playbook``) the same way
        # it rewrites bare names; the named-ref index added in #70 covers
        # both forms. The pre-existing relationship and objective rewrite
        # paths benefit from this fix too. Without it, importing a module
        # whose author uses a qualified ref leaves the ref pointing at a
        # nonexistent (or accidentally root-scoped) element after
        # namespacing.
        imported = tmp_path / "common.yaml"
        imported.write_text(
            """
name: common
version: 1.2.0
nodes:
  vm:
    type: vm
    os: linux
    resources: {ram: 1 gib, cpu: 1}
    services:
      - name: ssh
        port: 22
    roles:
      ops:
        username: operator
  net:
    type: switch
infrastructure:
  net:
    count: 1
    properties:
      cidr: 10.0.0.0/24
      gateway: 10.0.0.1
  vm:
    count: 1
    links: [net]
entities:
  blue:
    role: blue
conditions:
  health:
    command: /bin/true
    interval: 15
content:
  docs:
    type: dataset
    target: vm
    items:
      - name: playbook
relationships:
  blue-controls-vm:
    type: manages
    source: entities.blue
    target: nodes.vm
agents:
  blue-agent:
    entity: blue
    starting_conditions: [conditions.health, health]
    authority_anchors: [entities.blue, content.docs.items.playbook]
    allowed_subnets: [net]
    operating_scope: [nodes.vm, infrastructure.net, nodes.vm.services.ssh]
""",
            encoding="utf-8",
        )
        root = tmp_path / "root.yaml"
        root.write_text(
            """
name: root
imports:
  - path: common.yaml
    namespace: shared
    version: 1.2.0
""",
            encoding="utf-8",
        )

        scenario = parse_sdl_file(root)

        agent = scenario.agents["shared.blue-agent"]
        # ADR-020 §6 accepts both bare (`health`) and qualified
        # (`conditions.health`) references in starting_conditions; both
        # must survive composition with the namespace baked in.
        assert agent.starting_conditions == ["conditions.shared.health", "shared.health"]
        assert agent.authority_anchors == ["entities.shared.blue", "content.shared.docs.items.playbook"]
        assert agent.operating_scope == [
            "nodes.shared.vm",
            "infrastructure.shared.net",
            "nodes.shared.vm.services.ssh",
        ]
        rel = scenario.relationships["shared.blue-controls-vm"]
        assert rel.source == "entities.shared.blue"
        assert rel.target == "nodes.shared.vm"

    def test_parse_sdl_file_namespaces_agent_participant_framing_fields(self, tmp_path: Path):
        # ACT-601 / ADR-020: Agent.starting_conditions, .authority_anchors, and
        # .operating_scope are semantic references and must be rewritten by the
        # module composition pass when their imported targets are namespaced;
        # otherwise an `agent.starting_conditions: [health]` from a root
        # scenario silently breaks (or, worse, accidentally binds to a same-
        # named root element) once the imported `conditions: health` becomes
        # `shared.health`.
        imported = tmp_path / "common.yaml"
        imported.write_text(
            """
name: common
version: 1.2.0
nodes:
  vm:
    type: vm
    os: linux
    resources: {ram: 1 gib, cpu: 1}
    roles:
      ops:
        username: operator
  net:
    type: switch
infrastructure:
  net:
    count: 1
    properties:
      cidr: 10.0.0.0/24
      gateway: 10.0.0.1
  vm:
    count: 1
    links: [net]
entities:
  blue:
    role: blue
conditions:
  health:
    command: /bin/true
    interval: 15
relationships:
  blue-controls-vm:
    type: manages
    source: blue
    target: vm
agents:
  blue-agent:
    entity: blue
    starting_conditions: [health]
    authority_anchors: [blue, blue-controls-vm]
    allowed_subnets: [net]
    operating_scope: [vm, net]
""",
            encoding="utf-8",
        )
        root = tmp_path / "root.yaml"
        root.write_text(
            """
name: root
imports:
  - path: common.yaml
    namespace: shared
    version: 1.2.0
""",
            encoding="utf-8",
        )

        scenario = parse_sdl_file(root)

        agent = scenario.agents["shared.blue-agent"]
        assert agent.starting_conditions == ["shared.health"]
        assert agent.authority_anchors == ["shared.blue", "shared.blue-controls-vm"]
        assert agent.operating_scope == ["shared.vm", "shared.net"]
        # Semantic validation has already run as part of parse_sdl_file; if the
        # rewrite path were missing, validator would have raised on the
        # now-bare names that no longer exist after namespacing.

    def test_parse_sdl_file_rejects_version_mismatch(self, tmp_path: Path):
        imported = tmp_path / "common.yaml"
        imported.write_text(
            """
name: common
version: 2.0.0
nodes:
  sw:
    type: switch
""",
            encoding="utf-8",
        )
        root = tmp_path / "root.yaml"
        root.write_text(
            """
name: root
imports:
  - path: common.yaml
    version: 1.0.0
""",
            encoding="utf-8",
        )

        with pytest.raises(SDLParseError, match="requested version"):
            parse_sdl_file(root)

    def test_parse_sdl_file_rejects_namespace_collisions(self, tmp_path: Path):
        first = tmp_path / "first.yaml"
        first.write_text(
            """
name: shared
nodes:
  vm:
    type: vm
    os: linux
    resources: {ram: 1 gib, cpu: 1}
""",
            encoding="utf-8",
        )
        second = tmp_path / "second.yaml"
        second.write_text(
            """
name: shared
nodes:
  vm:
    type: vm
    os: linux
    resources: {ram: 1 gib, cpu: 1}
""",
            encoding="utf-8",
        )
        root = tmp_path / "root.yaml"
        root.write_text(
            """
name: root
imports:
  - path: first.yaml
    namespace: shared
  - path: second.yaml
    namespace: shared
""",
            encoding="utf-8",
        )

        with pytest.raises(SDLParseError, match="collides"):
            parse_sdl_file(root)


class TestLoadRealScenarios:
    """ACES legacy scenario YAMLs use the metadata format which is no
    longer part of the SDL. These are expected to fail until the
    scenario YAMLs are migrated to SDL format."""

    @pytest.fixture
    def scenarios_dir(self):
        from pathlib import Path

        d = Path("scenarios")
        if not d.exists():
            pytest.skip("scenarios/ directory not found")
        return d

    @pytest.mark.xfail(reason="Legacy ACES scenario format not supported after SDL cleanup")
    def test_all_scenarios_parse(self, scenarios_dir):
        from aces.core.sdl.parser import parse_sdl_file

        for path in sorted(scenarios_dir.glob("*.yaml")):
            scenario = parse_sdl_file(path)
            assert scenario.name
