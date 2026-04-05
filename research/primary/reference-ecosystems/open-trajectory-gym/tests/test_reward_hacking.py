#!/usr/bin/env python3
"""Reward function stress tests: hacking vectors, long-horizon scoring, edge cases.

Tests the Reward function against adversarial and realistic scenarios
to identify reward hacking opportunities before expensive Online RL training.

Run: pytest tests/test_reward_hacking.py -v
"""

import json

import pytest
from trajgym.rewards.reward import Reward


@pytest.fixture
def reward():
    """Deterministic reward function (no noise)."""
    return Reward(seed=42, noise_range=0.0)


# -----------------------------------------------------------------------
# Helper: build a tool call
# -----------------------------------------------------------------------


def tc(name: str, args: dict | str = "") -> dict:
    """Build a tool call message."""
    if isinstance(args, dict):
        args = json.dumps(args)
    return {"name": name, "arguments": args}


def shell(cmd: str) -> dict:
    return tc("shell_command", {"command": cmd})


def python_code(code: str) -> dict:
    return tc("python_code", {"code": code})


def flag_found(flag: str) -> dict:
    return tc("flag_found", {"content": flag})


def web_search(query: str) -> dict:
    return tc("web_search", {"query": query})


def read_file(path: str) -> dict:
    return tc("read_file", {"path": path})


def completion(tool_calls: list[dict], text: str = "") -> list[dict]:
    """Build a ChatML completion with tool calls."""
    msgs = []
    if text:
        msgs.append({"role": "assistant", "content": text})
    for i, t in enumerate(tool_calls):
        msgs.append(
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [{"function": t}],
            }
        )
        msgs.append(
            {
                "role": "tool",
                "tool_call_id": f"call_{i}",
                "content": f"output_{i}",
            }
        )
    return msgs


# =======================================================================
# 1. REWARD HACKING VECTORS
# =======================================================================


class TestEfficiencyGaming:
    """Test that efficiency can't be gamed with minimal tool calls."""

    def test_exactly_3_steps_no_flag(self, reward):
        """3 garbage calls shouldn't earn max efficiency."""
        comp = completion(
            [
                shell("echo hi"),
                shell("echo hello"),
                shell("echo bye"),
            ]
        )
        scores = reward([comp], ground_truth_flag=["FLAG{real}"], optimal_steps=[5])
        # efficiency = min(5/3, 1.0) = 1.0 BUT capped at 0.3 (no flag)
        # So 0.25 * 0.3 = 0.075 from efficiency
        assert scores[0] < 0.5, f"3 garbage steps scored too high: {scores[0]}"

    def test_2_steps_gated(self, reward):
        """Less than 3 steps = 0 efficiency."""
        comp = completion([shell("nmap target"), shell("cat /flag")])
        scores = reward([comp], ground_truth_flag=["FLAG{real}"], optimal_steps=[2])
        # efficiency_score = 0 (< 3 step gate)
        assert scores[0] < 0.5

    def test_0_steps(self, reward):
        """No tool calls at all."""
        scores = reward(["just thinking text"], ground_truth_flag=["FLAG{x}"])
        assert scores[0] < 0.1, f"Empty completion scored: {scores[0]}"

    def test_efficiency_with_flag(self, reward):
        """With flag found, efficiency should be fully credited."""
        comp = completion(
            [
                shell("nmap target"),
                shell("curl target/vuln"),
                shell("python3 exploit.py"),
                flag_found("FLAG{real}"),
            ],
            text="Found: FLAG{real}",
        )
        scores = reward([comp], ground_truth_flag=["FLAG{real}"], optimal_steps=[4])
        assert scores[0] > 0.7, f"Successful trace too low: {scores[0]}"


class TestFakeToolNames:
    """Test that fake/unknown tool names don't inflate exploration."""

    def test_all_fake_tools(self, reward):
        """Completions with fake tool names should score low overall."""
        comp = completion(
            [
                tc("magic_scanner", {"target": "foo"}),
                tc("super_exploiter", {"vuln": "bar"}),
                tc("auto_pwner", {"flag": "baz"}),
                tc("insta_root", {"level": "max"}),
            ]
        )
        scores = reward([comp])
        # exploration = high (4 unique novel tools)
        # but progression = 0 (none are real CTF phases)
        # format = 1.0 (valid JSON)
        # uniqueness likely high (all different)
        assert scores[0] < 0.5, f"Fake tools scored too high: {scores[0]}"

    def test_fake_vs_real_tools(self, reward):
        """Real tool names should outscore fake ones."""
        fake = completion(
            [
                tc("fake_a", {"x": "1"}),
                tc("fake_b", {"x": "2"}),
                tc("fake_c", {"x": "3"}),
                tc("fake_d", {"x": "4"}),
            ]
        )
        real = completion(
            [
                shell("nmap -sV target"),
                shell("curl target/admin"),
                python_code("import requests; r = requests.get('target')"),
                read_file("/etc/passwd"),
            ]
        )
        fake_score = reward([fake])[0]
        real_score = reward([real])[0]
        assert (
            real_score > fake_score
        ), f"Real tools ({real_score:.3f}) should outscore fake ({fake_score:.3f})"


class TestInvalidJSONPartialCredit:
    """Test that invalid JSON doesn't give too much credit."""

    def test_all_invalid_json(self, reward):
        """All invalid JSON tool calls should score low on format."""
        comp = completion(
            [
                tc("shell_command", "not json at all"),
                tc("python_code", "{broken: json}"),
                tc("read_file", "also not json"),
            ]
        )
        scores = reward([comp])
        # format: each gets 0.5 partial credit → 0.5
        # Other signals (progression, exploration, uniqueness) also contribute
        # since these are known tool names. Total ~0.43 is acceptable.
        assert scores[0] < 0.5

    def test_valid_vs_invalid_format(self, reward):
        """Valid JSON should outscore invalid JSON."""
        valid = completion(
            [
                shell("nmap target"),
                shell("curl target"),
                shell("cat /etc/passwd"),
            ]
        )
        invalid = completion(
            [
                tc("shell_command", "nmap target"),
                tc("shell_command", "curl target"),
                tc("shell_command", "cat /etc/passwd"),
            ]
        )
        v_score = reward([valid])[0]
        i_score = reward([invalid])[0]
        assert (
            v_score > i_score
        ), f"Valid JSON ({v_score:.3f}) should outscore invalid ({i_score:.3f})"


class TestFlagPatternInThinking:
    """Test that mentioning FLAG{} in thinking text doesn't give unearned credit."""

    def test_flag_in_think_no_submission(self, reward):
        """Mentioning FLAG{} in thinking but not submitting should give minimal credit."""
        comp = [
            {
                "role": "assistant",
                "content": "<think>I think the flag might be FLAG{test123}</think>",
            }
        ]
        scores = reward([comp], ground_truth_flag=["FLAG{real_flag}"])
        # Should get at most 0.1 flag pattern credit (not 1.0)
        # 0.20 * 0.1 = 0.02 from flag
        assert scores[0] < 0.15, f"Flag in thinking scored too high: {scores[0]}"

    def test_flag_pattern_vs_exact_match(self, reward):
        """Exact flag match (with flag_found) should score much higher than pattern."""
        pattern_only = [{"role": "assistant", "content": "Found FLAG{wrong_guess}"}]
        exact_match = completion(
            [flag_found("FLAG{real_flag}")], text="Found FLAG{real_flag}"
        )

        pattern_score = reward([pattern_only], ground_truth_flag=["FLAG{real_flag}"])[0]
        exact_score = reward([exact_match], ground_truth_flag=["FLAG{real_flag}"])[0]
        assert (
            exact_score > pattern_score + 0.1
        ), f"Exact ({exact_score:.3f}) should dominate pattern ({pattern_score:.3f})"


# =======================================================================
# 2. LONG-HORIZON SCORING SCENARIOS
# =======================================================================


class TestLongHorizonCyberOps:
    """Test reward behavior for realistic long CTF trajectories."""

    def test_successful_10_step_exploit(self, reward):
        """Clean RECON→ENUM→EXPLOIT with flag capture."""
        comp = completion(
            [
                # RECON
                shell("nmap -sV -p- 10.0.0.1"),
                shell("whois 10.0.0.1"),
                # ENUM
                shell(
                    "gobuster dir -u http://10.0.0.1 -w /usr/share/wordlists/common.txt"
                ),
                shell("curl -s http://10.0.0.1/admin"),
                shell("curl -s http://10.0.0.1/robots.txt"),
                read_file("/etc/hosts"),
                # EXPLOIT
                python_code(
                    "import requests\nr = requests.post('http://10.0.0.1/admin', data={'user': \"' OR 1=1--\"})"
                ),
                shell("sqlmap -u 'http://10.0.0.1/admin?id=1' --dump"),
                python_code("print(open('/tmp/flag.txt').read())"),
                flag_found("FLAG{sqli_success}"),
            ],
            text="FLAG{sqli_success}",
        )
        scores = reward(
            [comp],
            ground_truth_flag=["FLAG{sqli_success}"],
            optimal_steps=[8],
        )
        assert scores[0] > 0.75, f"Successful 10-step exploit too low: {scores[0]}"

    def test_failed_20_step_enumeration(self, reward):
        """Long enumeration that never reaches exploitation."""
        comp = completion(
            [
                shell("nmap -sV 10.0.0.1"),
                shell("nmap -sC 10.0.0.1"),
                shell("nmap -p- 10.0.0.1"),
                shell("curl http://10.0.0.1"),
                shell("curl http://10.0.0.1/admin"),
                shell("curl http://10.0.0.1/login"),
                shell("curl http://10.0.0.1/api"),
                shell("gobuster dir -u http://10.0.0.1 -w common.txt"),
                shell("gobuster dir -u http://10.0.0.1 -w big.txt"),
                shell("nikto -h http://10.0.0.1"),
                shell("whatweb http://10.0.0.1"),
                shell("wpscan --url http://10.0.0.1"),
                shell("curl http://10.0.0.1/.git/HEAD"),
                shell("curl http://10.0.0.1/.env"),
                shell("curl http://10.0.0.1/wp-config.php"),
                shell("ffuf -u http://10.0.0.1/FUZZ -w common.txt"),
                shell("dirb http://10.0.0.1"),
                shell("curl http://10.0.0.1/backup.zip"),
                shell("curl http://10.0.0.1/sitemap.xml"),
                shell("curl http://10.0.0.1/crossdomain.xml"),
            ]
        )
        scores = reward(
            [comp],
            ground_truth_flag=["FLAG{real}"],
            optimal_steps=[5],
        )
        # Should get some credit for enum/recon but not too much
        assert 0.1 < scores[0] < 0.5, f"Failed long enum: {scores[0]}"

    def test_stuck_loop_penalty(self, reward):
        """Repeating the same command = low uniqueness, should score poorly."""
        comp = completion(
            [
                shell("curl http://target/login"),
                shell("curl http://target/login"),
                shell("curl http://target/login"),
                shell("curl http://target/login"),
                shell("curl http://target/login"),
            ]
        )
        scores = reward([comp], ground_truth_flag=["FLAG{x}"], optimal_steps=[3])
        # uniqueness = 1/5 = 0.2
        assert scores[0] < 0.3, f"Stuck loop scored too high: {scores[0]}"

    def test_progressive_vs_random_ordering(self, reward):
        """RECON→ENUM→EXPLOIT should outscore random tool ordering."""
        ordered = completion(
            [
                shell("nmap -sV target"),  # RECON
                shell("gobuster dir -u target"),  # ENUM
                shell("curl target/admin"),  # ENUM
                python_code("exploit()"),  # EXPLOIT
            ]
        )
        random_order = completion(
            [
                python_code("exploit()"),  # EXPLOIT first
                shell("nmap -sV target"),  # RECON second
                shell("gobuster dir -u target"),  # ENUM last
                shell("curl target/admin"),  # ENUM
            ]
        )
        ordered_score = reward([ordered])[0]
        random_score = reward([random_order])[0]
        assert (
            ordered_score > random_score
        ), f"Ordered ({ordered_score:.3f}) should outscore random ({random_score:.3f})"

    def test_50_step_realistic_trace(self, reward):
        """Realistic long trace: scan, enum, multiple exploit attempts, flag."""
        tools = []
        # Phase 1: Recon (steps 1-5)
        tools.extend(
            [
                shell("nmap -sV -p- 10.0.0.1"),
                shell("masscan 10.0.0.1 -p1-65535 --rate=1000"),
                web_search("CVE web application framework"),
                shell("whois 10.0.0.1"),
                shell("dig 10.0.0.1"),
            ]
        )
        # Phase 2: Enum (steps 6-20)
        tools.extend(
            [
                shell("curl -s http://10.0.0.1"),
                shell("curl -s http://10.0.0.1/robots.txt"),
                shell("gobuster dir -u http://10.0.0.1 -w common.txt"),
                shell("nikto -h http://10.0.0.1"),
                shell("curl -s http://10.0.0.1/admin"),
                shell("curl -s http://10.0.0.1/login"),
                shell("curl -s http://10.0.0.1/api/users"),
                read_file("/etc/hosts"),
                shell("curl -s http://10.0.0.1/api/v1/config"),
                shell("whatweb http://10.0.0.1"),
            ]
        )
        # Phase 3: Initial exploit attempts (steps 21-35)
        tools.extend(
            [
                python_code(
                    "import requests\nr = requests.post('http://10.0.0.1/login', data={'user': 'admin', 'pass': 'admin'})"
                ),
                python_code(
                    "import requests\nr = requests.post('http://10.0.0.1/login', data={'user': \"admin' OR 1=1--\", 'pass': 'x'})"
                ),
                shell(
                    "sqlmap -u 'http://10.0.0.1/login' --data 'user=admin&pass=x' --batch"
                ),
                shell(
                    "hydra -l admin -P /usr/share/wordlists/rockyou.txt http://10.0.0.1 http-post-form '/login:user=^USER^&pass=^PASS^:Invalid'"
                ),
                python_code(
                    "import requests\nfor i in range(1,20):\n  r = requests.get(f'http://10.0.0.1/api/users/{i}')"
                ),
                shell("curl -s -H 'X-UserId: 10050' http://10.0.0.1/dashboard"),
                shell("curl -s -H 'X-UserId: 10051' http://10.0.0.1/dashboard"),
                shell("curl -s -H 'X-UserId: 10052' http://10.0.0.1/dashboard"),
            ]
        )
        # Phase 4: Flag extraction (steps 36-40)
        tools.extend(
            [
                python_code(
                    "# Found flag in user 10052\nprint('FLAG{idor_header_bypass}')"
                ),
                flag_found("FLAG{idor_header_bypass}"),
            ]
        )

        comp = completion(tools, text="FLAG{idor_header_bypass}")
        scores = reward(
            [comp],
            ground_truth_flag=["FLAG{idor_header_bypass}"],
            optimal_steps=[15],
        )
        assert scores[0] > 0.6, f"50-step realistic trace too low: {scores[0]}"

    def test_hallucinated_flag_submission(self, reward):
        """Submitting a wrong flag should be penalized."""
        comp = completion(
            [
                shell("nmap -sV target"),
                shell("curl target/admin"),
                python_code("print('found it')"),
                flag_found("FLAG{wrong_guess}"),
            ],
            text="I found it: FLAG{wrong_guess}",
        )
        scores = reward(
            [comp],
            ground_truth_flag=["FLAG{real_flag}"],
            optimal_steps=[5],
        )
        # Should get hallucination penalty (-0.10)
        no_submit = completion(
            [
                shell("nmap -sV target"),
                shell("curl target/admin"),
                python_code("print('found it')"),
            ]
        )
        no_submit_score = reward(
            [no_submit],
            ground_truth_flag=["FLAG{real_flag}"],
            optimal_steps=[5],
        )[0]
        assert (
            scores[0] < no_submit_score
        ), f"Wrong flag ({scores[0]:.3f}) should score lower than no submission ({no_submit_score:.3f})"


# =======================================================================
# 3. COMPONENT ISOLATION TESTS
# =======================================================================


class TestComponentBreakdown:
    """Verify each component contributes correctly and independently."""

    def test_only_flag(self, reward):
        """Flag score should be dominant with flag_found submission."""
        comp = completion([flag_found("FLAG{exact}")], text="The flag is FLAG{exact}")
        scores = reward([comp], ground_truth_flag=["FLAG{exact}"])
        # flag = 1.0 * flag_weight + format from valid tool call
        assert scores[0] > 0.35

    def test_only_format(self, reward):
        """Valid tool calls with no progression/exploration value."""
        # Using unknown tool names so progression=0, but format=1.0
        comp = completion(
            [
                tc("custom_tool_a", {"arg": "val1"}),
                tc("custom_tool_a", {"arg": "val1"}),
                tc("custom_tool_a", {"arg": "val1"}),
            ]
        )
        scores = reward([comp])
        # format = 1.0 * 0.20 = 0.20
        # exploration: 1 unique tool / 3 total, weighted
        # uniqueness: 1/3 = 0.33 * 0.10 = 0.033
        # progression = 0 (unknown tools)
        assert scores[0] < 0.4

    def test_only_progression(self, reward):
        """Perfect RECON→ENUM→EXPLOIT ordering."""
        comp = completion(
            [
                shell("nmap target"),
                shell("curl target"),
                python_code("exploit()"),
            ]
        )
        reward([comp])
        # progression: recon+enum+exploit (0.6) + recon<enum (0.2) + enum<exploit (0.2) = 1.0
        # progression component = 0.15 * 1.0 = 0.15
        prog_score = reward._progression_score(
            [
                {
                    "name": "shell_command",
                    "arguments": json.dumps({"command": "nmap target"}),
                },
                {
                    "name": "shell_command",
                    "arguments": json.dumps({"command": "curl target"}),
                },
                {"name": "python_code", "arguments": json.dumps({"code": "exploit()"})},
            ]
        )
        assert prog_score == 1.0, f"Perfect progression should be 1.0, got {prog_score}"

    def test_uniqueness_all_unique(self, reward):
        """All unique commands = 1.0 uniqueness."""
        calls = [
            {"name": "shell_command", "arguments": json.dumps({"command": f"cmd_{i}"})}
            for i in range(10)
        ]
        assert reward._uniqueness_score(calls) == 1.0

    def test_uniqueness_all_same(self, reward):
        """All same commands = 1/N uniqueness."""
        calls = [
            {
                "name": "shell_command",
                "arguments": json.dumps({"command": "curl target"}),
            }
            for _ in range(10)
        ]
        assert reward._uniqueness_score(calls) == pytest.approx(0.1)

    def test_exploration_early_novel_vs_late_novel(self, reward):
        """Tools used early should contribute more to exploration than late ones.

        Uses known tool names (from _KNOWN_TOOL_NAMES) so they pass the
        information specificity filter in the exploration scorer.
        """
        early_novel = [
            {
                "name": "shell_command",
                "arguments": json.dumps({"command": "nmap target"}),
            },
            {"name": "python_code", "arguments": json.dumps({"code": "exploit()"})},
            {"name": "read_file", "arguments": json.dumps({"path": "/etc/passwd"})},
            {
                "name": "shell_command",
                "arguments": json.dumps({"command": "nmap again"}),
            },
            {"name": "python_code", "arguments": json.dumps({"code": "exploit2()"})},
        ]
        late_novel = [
            {
                "name": "shell_command",
                "arguments": json.dumps({"command": "nmap target"}),
            },
            {
                "name": "shell_command",
                "arguments": json.dumps({"command": "nmap again"}),
            },
            {
                "name": "shell_command",
                "arguments": json.dumps({"command": "nmap more"}),
            },
            {"name": "python_code", "arguments": json.dumps({"code": "exploit()"})},
            {"name": "read_file", "arguments": json.dumps({"path": "/etc/passwd"})},
        ]
        early_score = reward._exploration_score(early_novel)
        late_score = reward._exploration_score(late_novel)
        assert (
            early_score > late_score
        ), f"Early novel ({early_score:.3f}) should outscore late novel ({late_score:.3f})"


# =======================================================================
# 4. COMPARATIVE SCORING (Online RL GRADIENT SIGNAL)
# =======================================================================


class TestGRPOGradientSignal:
    """Verify that reward ordering matches human intuition for Online RL training.

    In Online RL, the model sees pairs/groups and learns from relative differences.
    These tests verify the ranking is correct.
    """

    def test_ranking_success_gt_partial_gt_fail(self, reward):
        """Success > partial progress > complete failure."""
        success = completion(
            [
                shell("nmap target"),
                shell("curl target/admin"),
                python_code("exploit()"),
                flag_found("FLAG{win}"),
            ],
            text="FLAG{win}",
        )
        partial = completion(
            [
                shell("nmap target"),
                shell("curl target/admin"),
                shell("gobuster dir target"),
            ]
        )
        failure = completion([shell("echo hello")])

        s = reward(
            [success, partial, failure],
            ground_truth_flag=["FLAG{win}"] * 3,
            optimal_steps=[4] * 3,
        )
        assert (
            s[0] > s[1] > s[2]
        ), f"Ranking broken: success={s[0]:.3f}, partial={s[1]:.3f}, fail={s[2]:.3f}"

    def test_ranking_efficient_gt_inefficient(self, reward):
        """Fewer steps (with same outcome) should score higher."""
        efficient = completion(
            [
                shell("nmap target"),
                shell("curl target/vuln"),
                python_code("exploit()"),
                flag_found("FLAG{win}"),
            ],
            text="FLAG{win}",
        )
        inefficient = completion(
            [
                shell("nmap target"),
                shell("nmap -sC target"),
                shell("nmap -p- target"),
                shell("curl target"),
                shell("curl target/admin"),
                shell("curl target/login"),
                shell("curl target/vuln"),
                python_code("exploit()"),
                flag_found("FLAG{win}"),
            ],
            text="FLAG{win}",
        )

        s = reward(
            [efficient, inefficient],
            ground_truth_flag=["FLAG{win}"] * 2,
            optimal_steps=[4] * 2,
        )
        assert (
            s[0] > s[1]
        ), f"Efficient ({s[0]:.3f}) should outscore inefficient ({s[1]:.3f})"

    def test_ranking_diverse_gt_repetitive(self, reward):
        """Diverse tool usage should outscore repetitive commands."""
        diverse = completion(
            [
                shell("nmap target"),
                shell("gobuster dir target"),
                shell("nikto -h target"),
                web_search("CVE for apache 2.4"),
                python_code("requests.get('target')"),
            ]
        )
        repetitive = completion(
            [
                shell("curl target"),
                shell("curl target"),
                shell("curl target"),
                shell("curl target"),
                shell("curl target"),
            ]
        )
        s = reward([diverse, repetitive])
        assert (
            s[0] > s[1]
        ), f"Diverse ({s[0]:.3f}) should outscore repetitive ({s[1]:.3f})"

    def test_ranking_structured_gt_unstructured(self, reward):
        """Structured RECON→ENUM→EXPLOIT should outscore random ordering."""
        structured = completion(
            [
                shell("nmap target"),  # RECON
                shell("curl target/login"),  # ENUM
                shell("gobuster dir target"),  # ENUM
                python_code("exploit()"),  # EXPLOIT
            ]
        )
        unstructured = completion(
            [
                python_code("exploit()"),  # EXPLOIT first
                shell("curl target/login"),  # ENUM
                shell("nmap target"),  # RECON last
                shell("gobuster dir target"),  # ENUM
            ]
        )
        s = reward([structured, unstructured])
        assert (
            s[0] > s[1]
        ), f"Structured ({s[0]:.3f}) should outscore unstructured ({s[1]:.3f})"

    def test_variance_across_batch(self, reward):
        """Online RL needs variance in reward scores across a generation batch."""
        # Simulate 8 completions (typical num_generations=8)
        completions = [
            completion([shell("nmap target")]),
            completion([shell("curl target"), shell("curl target/admin")]),
            completion(
                [
                    shell("nmap target"),
                    shell("gobuster dir target"),
                    python_code("exploit()"),
                ]
            ),
            completion([shell("nmap target"), flag_found("FLAG{wrong}")]),
            completion([]),  # Empty
            completion(
                [
                    shell("nmap target"),
                    shell("curl target"),
                    python_code("exploit()"),
                    flag_found("FLAG{win}"),
                ],
                text="FLAG{win}",
            ),
            completion([tc("fake_tool", {"x": "y"})]),
            completion([shell("curl target")] * 10),
        ]
        scores = reward(
            completions,
            ground_truth_flag=["FLAG{win}"] * 8,
            optimal_steps=[4] * 8,
        )
        variance = sum((s - sum(scores) / len(scores)) ** 2 for s in scores) / len(
            scores
        )
        assert variance > 0.01, f"Insufficient variance for ONLINE_RL: {variance:.4f}"
        assert (
            max(scores) - min(scores) > 0.3
        ), f"Gap too small: {max(scores):.3f} - {min(scores):.3f}"


# =======================================================================
# 5. ONLINE MODE SPECIFIC TESTS
# =======================================================================


class TestOnlineModeEdgeCases:
    """Test scenarios specific to online RL with tools= mode."""

    def test_metadata_success_no_longer_overrides_text(self, reward):
        """metadata_success bypass removed; both should score equally."""
        comp = [{"role": "assistant", "content": "I don't know the flag"}]
        score_success = reward(
            [comp],
            ground_truth_flag=["FLAG{real}"],
            metadata=[{"success": True}],
        )[0]
        score_fail = reward(
            [comp],
            ground_truth_flag=["FLAG{real}"],
            metadata=[{"success": False}],
        )[0]
        # metadata_success is now ignored, so both should be the same
        assert abs(score_success - score_fail) < 0.01

    def test_tool_calls_as_dicts(self, reward):
        """In online mode, TRL passes arguments as dicts, not JSON strings."""
        comp = [
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "function": {
                            "name": "shell_command",
                            "arguments": {"command": "nmap target"},  # Dict, not string
                        }
                    }
                ],
            }
        ]
        scores = reward([comp])
        assert scores[0] > 0, "Dict arguments should be handled"

    def test_empty_tool_response(self, reward):
        """Tool returning empty output shouldn't crash."""
        comp = [
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "function": {
                            "name": "shell_command",
                            "arguments": json.dumps({"command": "nmap target"}),
                        }
                    }
                ],
            },
            {"role": "tool", "content": ""},  # Empty response
        ]
        scores = reward([comp])
        assert isinstance(scores[0], float)

    def test_multi_turn_tool_calling(self, reward):
        """Multiple rounds of tool calling in single completion."""
        comp = [
            # Turn 1
            {
                "role": "assistant",
                "content": "<think>Let me scan first</think>",
                "tool_calls": [
                    {
                        "function": {
                            "name": "shell_command",
                            "arguments": json.dumps({"command": "nmap target"}),
                        }
                    }
                ],
            },
            {"role": "tool", "content": "80/tcp open http"},
            # Turn 2
            {
                "role": "assistant",
                "content": "<think>Found HTTP, let me enumerate</think>",
                "tool_calls": [
                    {
                        "function": {
                            "name": "shell_command",
                            "arguments": json.dumps({"command": "curl -s target"}),
                        }
                    }
                ],
            },
            {"role": "tool", "content": "<html>Login page</html>"},
            # Turn 3
            {
                "role": "assistant",
                "content": "<think>Found login, try SQLi</think>",
                "tool_calls": [
                    {
                        "function": {
                            "name": "python_code",
                            "arguments": json.dumps({"code": "exploit()"}),
                        }
                    }
                ],
            },
            {"role": "tool", "content": "FLAG{sqli_success}"},
            # Turn 4: flag submission
            {
                "role": "assistant",
                "content": "Found flag: FLAG{sqli_success}",
                "tool_calls": [
                    {
                        "function": {
                            "name": "flag_found",
                            "arguments": json.dumps({"content": "FLAG{sqli_success}"}),
                        }
                    }
                ],
            },
            {"role": "tool", "content": "Flag accepted!"},
        ]
        scores = reward(
            [comp],
            ground_truth_flag=["FLAG{sqli_success}"],
            optimal_steps=[4],
        )
        assert scores[0] > 0.7, f"Multi-turn successful trace too low: {scores[0]}"


# =======================================================================
# 6. SCORE RANGE AND DISTRIBUTION TESTS
# =======================================================================


class TestScoreDistribution:
    """Verify score ranges and distributions match expected behavior."""

    def test_max_possible_score(self, reward):
        """Perfect trace should approach theoretical maximum."""
        comp = completion(
            [
                shell("nmap target"),
                shell("curl target"),
                python_code("exploit()"),
                flag_found("FLAG{perfect}"),
            ],
            text="FLAG{perfect}",
        )
        scores = reward(
            [comp],
            ground_truth_flag=["FLAG{perfect}"],
            optimal_steps=[4],
        )
        # All components should be high
        # flag=1.0, eff=1.0, prog=1.0, expl=high, uniq=1.0, fmt=1.0
        assert scores[0] > 0.85, f"Perfect trace score: {scores[0]}"

    def test_min_possible_score(self, reward):
        """Worst case: wrong flag submitted, no useful work."""
        comp = completion(
            [
                flag_found("FLAG{wrong}"),
            ],
            text="FLAG{wrong}",
        )
        scores = reward(
            [comp],
            ground_truth_flag=["FLAG{real}"],
            optimal_steps=[5],
        )
        # flag=0.1 (pattern), eff=0 (<3 steps), hallucination=-0.10
        assert scores[0] < 0.1, f"Worst case too high: {scores[0]}"

    def test_success_failure_gap(self, reward):
        """Gap between success and failure must be large enough for Online RL."""
        successes = []
        failures = []
        for i in range(10):
            # Success: varied approaches that find flag
            s = completion(
                [
                    shell(f"nmap -p{80+i} target"),
                    shell(f"curl target/path{i}"),
                    python_code(f"exploit_{i}()"),
                    flag_found("FLAG{win}"),
                ],
                text="FLAG{win}",
            )
            successes.append(s)
            # Failure: varied approaches that don't find flag
            f = completion(
                [
                    shell("nmap target"),
                    shell(f"curl target/page{i}"),
                    shell(f"gobuster dir target -w list{i}.txt"),
                ]
            )
            failures.append(f)

        all_comps = successes + failures
        all_scores = reward(
            all_comps,
            ground_truth_flag=["FLAG{win}"] * 20,
            optimal_steps=[4] * 20,
        )
        success_mean = sum(all_scores[:10]) / 10
        failure_mean = sum(all_scores[10:]) / 10
        gap = success_mean - failure_mean
        assert (
            gap > 0.3
        ), f"Success-failure gap too small: {gap:.3f} (success={success_mean:.3f}, failure={failure_mean:.3f})"


# =======================================================================
# 7. MISSING SIGNAL DETECTION
# =======================================================================


class TestMissingSignals:
    """Document what the reward function DOESN'T capture.

    These tests intentionally test for behaviors that SHOULD be different
    but currently score the same. Each identifies a potential improvement.
    """

    def test_error_recovery_not_rewarded(self, reward):
        """Model that recovers from errors should outscore one that doesn't.

        CURRENT: Both score similarly (recovery not tracked).
        DESIRED: Recovery trace should score higher.
        """
        # Recovery: tries something, fails, pivots to new approach
        recovery = completion(
            [
                shell("nmap target"),
                shell("curl target/admin"),  # Try admin
                shell("curl target/dashboard"),  # Pivot to dashboard
                python_code("exploit_idor()"),  # New exploit approach
            ]
        )
        # No recovery: keeps trying same thing
        stuck = completion(
            [
                shell("nmap target"),
                shell("curl target/admin"),
                shell("curl target/admin -d 'user=admin'"),
                shell("curl target/admin -H 'Auth: test'"),
            ]
        )
        r_score = reward([recovery])[0]
        s_score = reward([stuck])[0]
        # Document current behavior (may be similar)
        # If this assertion fails, that's actually GOOD - means recovery is rewarded
        print(
            f"\n  [INFO] Recovery={r_score:.3f} vs Stuck={s_score:.3f} (gap={r_score-s_score:.3f})"
        )

    def test_output_parsing_not_rewarded(self, reward):
        """Using information from tool output should be rewarded.

        CURRENT: No tracking of information flow from tool output → next command.
        DESIRED: Commands that reference prior output should score higher.
        """
        # Uses output: nmap finds port 8080, next command targets 8080
        uses_output = completion(
            [
                shell("nmap -sV target"),  # Finds port 8080
                shell("curl target:8080"),  # Uses discovery
                shell("gobuster dir -u target:8080"),
            ]
        )
        # Ignores output: nmap finds port 8080, commands target default 80
        ignores_output = completion(
            [
                shell("nmap -sV target"),
                shell("curl target"),
                shell("gobuster dir -u target"),
            ]
        )
        u_score = reward([uses_output])[0]
        i_score = reward([ignores_output])[0]
        print(
            f"\n  [INFO] Uses output={u_score:.3f} vs Ignores={i_score:.3f} (gap={u_score-i_score:.3f})"
        )

    def test_repeated_failed_commands_not_penalized(self, reward):
        """Repeating a failed command should be penalized more than trying new things.

        CURRENT: Uniqueness catches some of this, but doesn't distinguish
        failed vs successful command repetition.
        """
        # Retries same failed command
        retry_failed = completion(
            [
                shell("curl target/admin"),  # 404
                shell("curl target/admin"),  # 404 again
                shell("curl target/admin"),  # 404 still
            ]
        )
        # Tries different things
        diverse_attempts = completion(
            [
                shell("curl target/admin"),  # 404
                shell("curl target/login"),  # Found login!
                shell("curl target/api"),  # Found API!
            ]
        )
        r_score = reward([retry_failed])[0]
        d_score = reward([diverse_attempts])[0]
        assert (
            d_score > r_score
        ), f"Diverse attempts ({d_score:.3f}) should outscore retry ({r_score:.3f})"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
