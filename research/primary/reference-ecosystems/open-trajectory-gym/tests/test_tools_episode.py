"""Tests for episode state management in training/tool_wrappers.py.

Validates thread-local episode isolation:
- mark_step_begin() resets episode state
- is_episode_done() returns False initially
- flag_found success sets episode done for that generation
- Other threads have independent episode state
- _step() returns "[EPISODE COMPLETE]" when done
"""

import threading

import pytest
from trajgym.training.tool_wrappers import (
    _get_episode_done,
    _set_episode_done,
    _step,
    close_env,
    flag_found,
    init_env,
    is_episode_done,
    mark_step_begin,
    shell_command,
)


@pytest.fixture(autouse=True)
def setup_env():
    """Initialize and tear down ToolExecutor for each test."""
    init_env(target="http://localhost:9999", ground_truth="FLAG{test}", max_steps=30)
    mark_step_begin(ground_truth="FLAG{test}")
    yield
    close_env()


class TestMarkStepBegin:
    def test_resets_episode_done(self):
        _set_episode_done(True)
        assert _get_episode_done() is True
        mark_step_begin(ground_truth="FLAG{test}")
        assert _get_episode_done() is False

    def test_resets_step_count(self):
        shell_command("echo hello")
        shell_command("echo world")
        mark_step_begin(ground_truth="FLAG{test}")
        assert is_episode_done() is False


class TestIsEpisodeDone:
    def test_false_initially(self):
        assert is_episode_done() is False

    def test_true_after_correct_flag(self):
        result = flag_found("FLAG{test}")
        assert "Correct" in result
        assert is_episode_done() is True

    def test_not_done_after_incorrect_flag_submission(self):
        """Incorrect flag submissions allow the agent to retry.

        ToolExecutor returns done=False for incorrect submissions when
        step_count < max_steps, so the episode continues.
        """
        mark_step_begin(ground_truth="FLAG{real_flag}")
        result = flag_found("FLAG{wrong}")
        assert "Incorrect" in result
        assert is_episode_done() is False


class TestStepEarlyExit:
    def test_returns_episode_complete_when_done(self):
        _set_episode_done(True)
        result = _step("shell_command", {"command": "echo should not run"})
        assert "[EPISODE COMPLETE]" in result

    def test_normal_execution_when_not_done(self):
        result = _step("shell_command", {"command": "echo hello"})
        assert "[EPISODE COMPLETE]" not in result
        assert "hello" in result


class TestThreadIsolation:
    def test_independent_episode_state(self):
        """Episode done in one thread should not affect another thread."""
        results = {}
        barrier = threading.Barrier(2)

        def thread_a():
            mark_step_begin(ground_truth="FLAG{test}")
            barrier.wait(timeout=5)
            flag_found("FLAG{test}")
            results["a_done"] = is_episode_done()

        def thread_b():
            mark_step_begin(ground_truth="FLAG{test}")
            barrier.wait(timeout=5)
            # Don't submit flag -- just check state
            results["b_done_before"] = is_episode_done()
            # Small delay to let thread_a finish
            import time

            time.sleep(0.1)
            results["b_done_after"] = is_episode_done()

        t_a = threading.Thread(target=thread_a)
        t_b = threading.Thread(target=thread_b)
        t_a.start()
        t_b.start()
        t_a.join(timeout=10)
        t_b.join(timeout=10)

        assert results["a_done"] is True
        assert results["b_done_before"] is False
        # Thread B's state should still be False (thread-local)
        assert results["b_done_after"] is False

    def test_step_short_circuits_only_in_done_thread(self):
        """_step should only short-circuit in the thread that set done.

        Both threads must sync to the same batch_gen before one sets done,
        otherwise mark_step_begin advancing batch_gen causes a reset.
        """
        results = {}
        setup_barrier = threading.Barrier(2)
        action_barrier = threading.Barrier(2)

        def thread_done():
            # Sync batch_gen (call _get_episode_done to sync thread state)
            _get_episode_done()
            setup_barrier.wait(timeout=5)
            _set_episode_done(True)
            action_barrier.wait(timeout=5)
            results["done_result"] = _step("shell_command", {"command": "echo x"})

        def thread_active():
            _get_episode_done()
            setup_barrier.wait(timeout=5)
            # Don't set done
            action_barrier.wait(timeout=5)
            results["active_result"] = _step("shell_command", {"command": "echo y"})

        t1 = threading.Thread(target=thread_done)
        t2 = threading.Thread(target=thread_active)
        t1.start()
        t2.start()
        t1.join(timeout=10)
        t2.join(timeout=10)

        assert "[EPISODE COMPLETE]" in results["done_result"]
        assert "[EPISODE COMPLETE]" not in results["active_result"]
