"""Trajectory browser — generates a self-contained HTML report from online RL logs.

Reads ``{output_dir}/trajectories/`` JSONL files produced by TrajectoryLogger
and renders a browsable HTML page with:
  - Training curve (reward over steps)
  - Challenge scoreboard (solve rate, avg reward)
  - Per-step drill-down (tool calls, model output, reward breakdown)

Usage::

    trajgym-trajectories /path/to/online_rl/output
    trajgym-trajectories /path/to/online_rl/output --port 8765  # live server
"""

import argparse
import contextlib
import http.server
import json
import logging
import os
import sys
import webbrowser
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _load_step_summaries(trajectories_dir: str) -> list[dict[str, Any]]:
    """Load step_summaries.jsonl into a list of dicts."""
    path = os.path.join(trajectories_dir, "step_summaries.jsonl")
    if not os.path.exists(path):
        return []
    entries_by_step: dict[int, dict[str, Any]] = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                entry = json.loads(line)
                step = int(entry.get("global_step", 0))
                # Keep the latest snapshot for each step.
                entries_by_step[step] = entry
    return [entries_by_step[k] for k in sorted(entries_by_step)]


def _load_step_generations(trajectories_dir: str, step: int) -> list[dict[str, Any]]:
    """Load all generations for a given step."""
    path = os.path.join(trajectories_dir, f"step_{step}.jsonl")
    if not os.path.exists(path):
        return []
    entries = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    return entries


def _load_scoreboard(output_dir: str) -> dict[str, Any]:
    """Load challenge_scoreboard.json."""
    path = os.path.join(output_dir, "challenge_scoreboard.json")
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        return json.load(f)


def _escape_html(text: str) -> str:
    """Minimal HTML escaping."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def generate_html(output_dir: str) -> str:
    """Generate self-contained HTML report from trajectory data."""
    trajectories_dir = os.path.join(output_dir, "trajectories")
    summaries = _load_step_summaries(trajectories_dir)
    scoreboard = _load_scoreboard(output_dir)

    # Collect all step files for drill-down
    step_files = sorted(Path(trajectories_dir).glob("step_*.jsonl"))
    step_numbers = []
    for sf in step_files:
        with contextlib.suppress(ValueError, IndexError):
            step_numbers.append(int(sf.stem.split("_")[1]))

    # Prepare chart data
    steps_json = json.dumps([s.get("global_step", 0) for s in summaries])
    rewards_json = json.dumps([round(s.get("avg_reward", 0), 4) for s in summaries])
    flag_rates_json = json.dumps(
        [round(s.get("flag_found_rate", 0), 4) for s in summaries]
    )
    tool_calls_json = json.dumps(
        [round(s.get("avg_tool_calls", 0), 1) for s in summaries]
    )

    # Build scoreboard rows
    scoreboard_rows = ""
    for cid, data in sorted(scoreboard.items()):
        solve_pct = round(data.get("solve_rate", 0) * 100, 1)
        avg_r = round(data.get("avg_reward", 0), 3)
        best_r = round(data.get("best_reward", 0), 3)
        cat = data.get("category", "?")
        diff = data.get("difficulty", "?")
        attempts = data.get("attempts", 0)
        solves = data.get("solves", 0)
        bar_color = (
            "var(--green)"
            if solve_pct > 50
            else "var(--yellow)" if solve_pct > 0 else "var(--red)"
        )
        scoreboard_rows += f"""
        <tr>
          <td class="mono">{_escape_html(cid)}</td>
          <td>{cat}</td><td>{diff}</td>
          <td>{attempts}</td><td>{solves}</td>
          <td><div class="bar" style="width:{min(solve_pct, 100)}%;background:{bar_color}">{solve_pct}%</div></td>
          <td>{avg_r}</td><td>{best_r}</td>
        </tr>"""

    # Build step-level generation data (embedded as JSON for JS drill-down)
    all_generations: dict[int, list[dict[str, Any]]] = {}
    for step_num in step_numbers[:200]:  # Cap at 200 steps to keep HTML reasonable
        gens = _load_step_generations(trajectories_dir, step_num)
        # Slim down for embedding: truncate model_output, drop prompt_messages
        slim_gens = []
        for g in gens:
            slim = {
                "generation_idx": g.get("generation_idx", 0),
                "challenge_id": g.get("challenge_id", ""),
                "reward_total": round(g.get("reward_total", 0), 4),
                "reward_breakdown": g.get("reward_breakdown"),
                "flag_found": g.get("flag_found", False),
                "num_tool_calls": g.get("num_tool_calls", 0),
                "response_length": g.get("response_length", 0),
                "model_output": (g.get("model_output") or "")[:5000],
                "tool_calls": (g.get("tool_calls") or [])[:20],
            }
            slim_gens.append(slim)
        all_generations[step_num] = slim_gens

    generations_json = json.dumps(all_generations, default=str)

    total_steps = len(summaries)
    total_gens = sum(s.get("total_generations", 0) for s in summaries)
    total_flags = sum(s.get("flag_found_count", 0) for s in summaries)
    overall_flag_rate = (
        round(total_flags / total_gens * 100, 1) if total_gens > 0 else 0
    )
    final_reward = round(summaries[-1].get("avg_reward", 0), 4) if summaries else 0

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>trajgym Trajectory Browser</title>
<style>
:root {{
  --bg: #0d1117; --fg: #c9d1d9; --card: #161b22; --border: #30363d;
  --green: #3fb950; --yellow: #d29922; --red: #f85149; --blue: #58a6ff;
  --mono: 'SF Mono', 'Fira Code', monospace;
}}
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family: -apple-system, sans-serif; background:var(--bg); color:var(--fg); padding:20px; }}
h1 {{ color:var(--blue); margin-bottom:4px; font-size:1.5em; }}
h2 {{ color:var(--fg); margin:20px 0 10px; font-size:1.2em; border-bottom:1px solid var(--border); padding-bottom:6px; }}
.subtitle {{ color:#8b949e; font-size:0.85em; margin-bottom:20px; }}
.stats {{ display:grid; grid-template-columns:repeat(auto-fit, minmax(160px,1fr)); gap:12px; margin-bottom:20px; }}
.stat {{ background:var(--card); border:1px solid var(--border); border-radius:8px; padding:12px; }}
.stat-val {{ font-size:1.6em; font-weight:700; color:var(--blue); }}
.stat-label {{ font-size:0.8em; color:#8b949e; margin-top:2px; }}
.chart-container {{ background:var(--card); border:1px solid var(--border); border-radius:8px; padding:16px; margin-bottom:20px; }}
canvas {{ width:100%!important; height:250px!important; }}
table {{ width:100%; border-collapse:collapse; font-size:0.85em; }}
th {{ background:var(--card); position:sticky; top:0; text-align:left; padding:8px; border-bottom:2px solid var(--border); }}
td {{ padding:6px 8px; border-bottom:1px solid var(--border); }}
tr:hover {{ background:#1c2128; }}
.mono {{ font-family:var(--mono); font-size:0.85em; }}
.bar {{ height:18px; border-radius:3px; color:#000; font-size:0.75em; text-align:center; line-height:18px; min-width:32px; }}
.panel {{ background:var(--card); border:1px solid var(--border); border-radius:8px; padding:16px; margin-bottom:12px; }}
.gen-card {{ background:#1c2128; border:1px solid var(--border); border-radius:6px; padding:10px; margin:8px 0; }}
.gen-header {{ display:flex; justify-content:space-between; margin-bottom:6px; }}
.flag-yes {{ color:var(--green); font-weight:700; }}
.flag-no {{ color:#8b949e; }}
.tool-call {{ background:var(--bg); border-radius:4px; padding:6px 8px; margin:4px 0; font-family:var(--mono); font-size:0.8em; }}
.tool-name {{ color:var(--yellow); }}
.tool-output {{ color:#8b949e; white-space:pre-wrap; max-height:100px; overflow-y:auto; }}
pre {{ font-family:var(--mono); font-size:0.8em; white-space:pre-wrap; word-break:break-word; max-height:200px; overflow-y:auto; background:var(--bg); padding:8px; border-radius:4px; }}
.step-select {{ background:var(--card); color:var(--fg); border:1px solid var(--border); padding:6px 10px; border-radius:4px; font-size:0.9em; }}
.reward-breakdown {{ display:grid; grid-template-columns:repeat(auto-fit, minmax(120px,1fr)); gap:6px; margin:6px 0; }}
.rb-item {{ font-size:0.8em; }}
.rb-key {{ color:#8b949e; }}
.rb-val {{ color:var(--blue); font-weight:600; }}
</style>
</head>
<body>

<h1>trajgym Trajectory Browser</h1>
<p class="subtitle">{_escape_html(output_dir)}</p>

<div class="stats">
  <div class="stat"><div class="stat-val">{total_steps}</div><div class="stat-label">Training Steps</div></div>
  <div class="stat"><div class="stat-val">{total_gens}</div><div class="stat-label">Total Generations</div></div>
  <div class="stat"><div class="stat-val">{total_flags}</div><div class="stat-label">Flags Found</div></div>
  <div class="stat"><div class="stat-val">{overall_flag_rate}%</div><div class="stat-label">Overall Flag Rate</div></div>
  <div class="stat"><div class="stat-val">{final_reward}</div><div class="stat-label">Final Avg Reward</div></div>
  <div class="stat"><div class="stat-val">{len(scoreboard)}</div><div class="stat-label">Unique Challenges</div></div>
</div>

<h2>Training Curves</h2>
<div class="chart-container"><canvas id="rewardChart"></canvas></div>
<div class="chart-container"><canvas id="flagChart"></canvas></div>

<h2>Challenge Scoreboard</h2>
<div style="overflow-x:auto;">
<table>
<thead><tr><th>Challenge</th><th>Category</th><th>Difficulty</th><th>Attempts</th><th>Solves</th><th>Solve Rate</th><th>Avg Reward</th><th>Best</th></tr></thead>
<tbody>{scoreboard_rows if scoreboard_rows else '<tr><td colspan="8" style="text-align:center;color:#8b949e;">No scoreboard data yet</td></tr>'}</tbody>
</table>
</div>

<h2>Step Drill-Down</h2>
<div class="panel">
  <label>Step: <select id="stepSelect" class="step-select" onchange="showStep(this.value)">
    <option value="">-- select --</option>
    {"".join(f'<option value="{s}">{s}</option>' for s in step_numbers[:200])}
  </select></label>
  <div id="stepDetail"></div>
</div>

<script>
const STEPS = {steps_json};
const REWARDS = {rewards_json};
const FLAG_RATES = {flag_rates_json};
const TOOL_CALLS = {tool_calls_json};
const GENERATIONS = {generations_json};

// Minimal chart rendering (no Chart.js dependency)
function drawChart(canvasId, labels, datasets) {{
  const canvas = document.getElementById(canvasId);
  const ctx = canvas.getContext('2d');
  const dpr = window.devicePixelRatio || 1;
  const rect = canvas.getBoundingClientRect();
  canvas.width = rect.width * dpr;
  canvas.height = rect.height * dpr;
  ctx.scale(dpr, dpr);
  const W = rect.width, H = rect.height;
  const pad = {{l:50, r:20, t:30, b:30}};
  const pW = W - pad.l - pad.r, pH = H - pad.t - pad.b;

  if (labels.length === 0) {{
    ctx.fillStyle = '#8b949e';
    ctx.font = '14px sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText('No data yet', W/2, H/2);
    return;
  }}

  datasets.forEach(ds => {{
    const vals = ds.data;
    const minV = Math.min(0, ...vals);
    const maxV = Math.max(0.1, ...vals);
    const range = maxV - minV || 1;

    // Axes
    ctx.strokeStyle = '#30363d'; ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(pad.l, pad.t); ctx.lineTo(pad.l, pad.t+pH); ctx.lineTo(pad.l+pW, pad.t+pH); ctx.stroke();

    // Y labels
    ctx.fillStyle = '#8b949e'; ctx.font = '11px sans-serif'; ctx.textAlign = 'right';
    for (let i = 0; i <= 4; i++) {{
      const y = pad.t + pH - (i/4)*pH;
      const v = minV + (i/4)*range;
      ctx.fillText(v.toFixed(2), pad.l-6, y+4);
      ctx.strokeStyle = '#21262d'; ctx.beginPath(); ctx.moveTo(pad.l, y); ctx.lineTo(pad.l+pW, y); ctx.stroke();
    }}

    // Title
    ctx.fillStyle = ds.color; ctx.font = 'bold 12px sans-serif'; ctx.textAlign = 'left';
    ctx.fillText(ds.label, pad.l+4, pad.t-8);

    // Line
    ctx.strokeStyle = ds.color; ctx.lineWidth = 2; ctx.beginPath();
    vals.forEach((v, i) => {{
      const x = pad.l + (i / Math.max(1, vals.length-1)) * pW;
      const y = pad.t + pH - ((v - minV) / range) * pH;
      i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    }});
    ctx.stroke();

    // Points
    ctx.fillStyle = ds.color;
    vals.forEach((v, i) => {{
      const x = pad.l + (i / Math.max(1, vals.length-1)) * pW;
      const y = pad.t + pH - ((v - minV) / range) * pH;
      ctx.beginPath(); ctx.arc(x, y, 3, 0, Math.PI*2); ctx.fill();
    }});
  }});

  // X labels
  ctx.fillStyle = '#8b949e'; ctx.font = '10px sans-serif'; ctx.textAlign = 'center';
  const skip = Math.max(1, Math.floor(labels.length / 10));
  labels.forEach((l, i) => {{
    if (i % skip === 0) {{
      const x = pad.l + (i / Math.max(1, labels.length-1)) * pW;
      ctx.fillText(l, x, pad.t + pH + 18);
    }}
  }});
}}

drawChart('rewardChart', STEPS, [{{label:'Avg Reward', data:REWARDS, color:'#58a6ff'}}]);
drawChart('flagChart', STEPS, [{{label:'Flag Found Rate', data:FLAG_RATES, color:'#3fb950'}}]);

function esc(s) {{ return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }}

function showStep(step) {{
  const el = document.getElementById('stepDetail');
  if (!step || !GENERATIONS[step]) {{ el.innerHTML = '<p style="color:#8b949e;margin-top:10px;">Select a step to see generations.</p>'; return; }}
  const gens = GENERATIONS[step];
  let html = '<div style="margin-top:12px;">';
  gens.forEach((g, i) => {{
    const flagCls = g.flag_found ? 'flag-yes' : 'flag-no';
    const flagTxt = g.flag_found ? 'FLAG FOUND' : 'no flag';
    html += `<div class="gen-card">
      <div class="gen-header">
        <span><b>Gen ${{g.generation_idx}}</b> &mdash; ${{esc(g.challenge_id || '?')}}</span>
        <span class="${{flagCls}}">${{flagTxt}}</span>
        <span>reward: <b>${{g.reward_total}}</b> &bull; tools: ${{g.num_tool_calls}} &bull; len: ${{g.response_length}}</span>
      </div>`;

    // Reward breakdown
    if (g.reward_breakdown) {{
      html += '<div class="reward-breakdown">';
      for (const [k, v] of Object.entries(g.reward_breakdown)) {{
        html += `<div class="rb-item"><span class="rb-key">${{k}}:</span> <span class="rb-val">${{typeof v === 'number' ? v.toFixed(3) : v}}</span></div>`;
      }}
      html += '</div>';
    }}

    // Tool calls
    if (g.tool_calls && g.tool_calls.length > 0) {{
      html += '<details><summary style="cursor:pointer;color:var(--yellow);font-size:0.85em;">Tool calls (' + g.tool_calls.length + ')</summary>';
      g.tool_calls.forEach(tc => {{
        const name = tc.name || tc.tool || '?';
        const args = tc.args ? JSON.stringify(tc.args) : '';
        const out = tc.output || tc.result || '';
        html += `<div class="tool-call"><span class="tool-name">${{esc(name)}}</span> ${{esc(args.substring(0,200))}}<div class="tool-output">${{esc(String(out).substring(0,500))}}</div></div>`;
      }});
      html += '</details>';
    }}

    // Model output (truncated)
    if (g.model_output) {{
      html += '<details><summary style="cursor:pointer;color:var(--blue);font-size:0.85em;">Model output (' + g.model_output.length + ' chars)</summary><pre>' + esc(g.model_output.substring(0, 3000)) + '</pre></details>';
    }}

    html += '</div>';
  }});
  html += '</div>';
  el.innerHTML = html;
}}

// Auto-select last step
if (STEPS.length > 0) {{
  const sel = document.getElementById('stepSelect');
  const lastOpt = sel.options[sel.options.length - 1];
  if (lastOpt) {{ sel.value = lastOpt.value; showStep(lastOpt.value); }}
}}
</script>
</body>
</html>"""
    return html


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Browse online RL training trajectories",
        prog="trajgym-trajectories",
    )
    parser.add_argument(
        "output_dir",
        help="Online RL output directory (contains trajectories/ and challenge_scoreboard.json)",
    )
    parser.add_argument(
        "-o",
        "--html-output",
        help="Write HTML to file instead of serving (default: serve)",
    )
    parser.add_argument(
        "-p",
        "--port",
        type=int,
        default=0,
        help="Serve on this port (0 = write to file, default)",
    )
    args = parser.parse_args()

    if not os.path.isdir(args.output_dir):
        print(f"Error: {args.output_dir} is not a directory", file=sys.stderr)
        sys.exit(1)

    trajectories_dir = os.path.join(args.output_dir, "trajectories")
    if not os.path.isdir(trajectories_dir):
        print(
            f"Error: {trajectories_dir} not found. "
            "Run online RL training with enable_trajectory_logging: true first.",
            file=sys.stderr,
        )
        sys.exit(1)

    html = generate_html(args.output_dir)

    if args.port > 0:
        # Live server mode
        html_path = os.path.join(args.output_dir, "_trajectories.html")
        with open(html_path, "w") as f:
            f.write(html)

        os.chdir(args.output_dir)

        handler = http.server.SimpleHTTPRequestHandler
        server = http.server.HTTPServer(("", args.port), handler)
        url = f"http://localhost:{args.port}/_trajectories.html"
        print(f"Serving trajectory browser at {url}")
        webbrowser.open(url)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down.")
            server.shutdown()
    else:
        # Write to file
        out_path = args.html_output or os.path.join(
            args.output_dir, "trajectories_report.html"
        )
        with open(out_path, "w") as f:
            f.write(html)
        print(f"Trajectory report written to: {out_path}")


if __name__ == "__main__":
    main()
