"""Figures for the pooled-gamble experiment, drawn from the run folders (raw data stays git-ignored).

    uv run --with matplotlib experiments/pooled-gamble/plots.py                  # all grid runs under results/
    uv run --with matplotlib experiments/pooled-gamble/plots.py --results <dir> --out <dir>

Only COMPLETED episodes are plotted, and each panel says how many episodes finished per cell. Pilot,
mock and multiplier-variant folders are excluded. Runs are read through records.py, so partial and
interrupted runs load without error and their unfinished episodes are counted, never silently dropped.

Palette: the two-series categorical pair (blue, orange) from dataviz/references/palette.md, validated
in both modes with scripts/validate_palette.js. Blue/orange mean board/no-board in panels A-C and
DeepSeek/GLM in panel D; each panel names its series.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from records import iter_calls, load_run, select_episodes

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

MODELS = {"deepseek_deepseek-v4.1-flash-1017": "DeepSeek V4.1 Flash 1017",
          "z-ai_glm-5.3-flash": "Z.ai GLM 5.3 Flash"}
CONDS = {"board": "Board + transfers", "noboard": "No board + transfers"}
BLUE, ORANGE = "#2a78d6", "#eb6834"  # categorical slots 1 and 2 (validated pair)
COND_COLOR = {"board": BLUE, "noboard": ORANGE}
MODEL_COLOR = {"deepseek_deepseek-v4.1-flash-1017": BLUE, "z-ai_glm-5.3-flash": ORANGE}
INK, INK2, MUTED = "#0b0b0b", "#52514e", "#898781"  # text tokens; never series colours
GRID, BASE, SURFACE = "#e1e0d9", "#c3c2b7", "#fcfcfb"  # hairline grid, baseline, chart surface
NS = (2, 4, 8)
CAP_USD = 0.10  # the per-episode dollar cap, as enforced in llm.Budget


def _import_pyplot():
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.lines import Line2D
    except ImportError:
        sys.exit("matplotlib is needed: run with  uv run --with matplotlib experiments/pooled-gamble/plots.py")
    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["Helvetica Neue", "Arial", "DejaVu Sans"],
        "font.size": 10, "axes.titlesize": 11, "axes.titleweight": "bold", "axes.titlecolor": INK,
        "axes.labelcolor": INK2, "axes.edgecolor": BASE, "axes.linewidth": 1, "xtick.color": MUTED,
        "ytick.color": MUTED, "xtick.labelcolor": INK2, "ytick.labelcolor": INK2,
        "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
        "text.color": INK, "legend.frameon": False, "legend.fontsize": 9,
        "axes.spines.top": False, "axes.spines.right": False,
    })
    return plt, Line2D


def _style(ax) -> None:
    ax.yaxis.grid(True, color=GRID, linewidth=0.8, linestyle="-")  # hairline, solid, recessive
    ax.set_axisbelow(True)
    ax.tick_params(length=0)


def _load(results: Path):
    if (results / "config.json").is_file():
        runs = [load_run(results)]
    else:
        runs = [load_run(d) for d in sorted(results.iterdir()) if d.is_dir()] if results.exists() else []
    grid = [r for r in runs if r["kind"] == "grid"]
    chosen, _ = select_episodes(grid)
    done = [e for e in chosen if e["status"] == "completed"]
    caps = {r["name"]: (r["config"] or {}).get("config", {}).get("max_tokens") for r in grid}
    return chosen, done, caps, results


def _jitter(k: int, count: int, width: float = 0.10) -> float:
    return 0.0 if count <= 1 else (k / (count - 1) - 0.5) * width * 2


def fig_totals(plt, Line2D, chosen, done, out: Path) -> Path:
    fig, axes = plt.subplots(1, 2, figsize=(9.6, 4.9), sharey=True)
    for ax, model in zip(axes, MODELS):
        for i, n in enumerate(NS):
            ax.plot([i - 0.42, i + 0.42], [n, n], color=MUTED, linewidth=1, zorder=1)  # start total N x 1
            for cond, dx in (("board", -0.16), ("noboard", 0.16)):
                vals = [e["total_final"] for e in done if e["key"][0] == model and e["key"][1] == cond and e["n"] == n]
                planned = sum(1 for e in chosen if e["key"][0] == model and e["key"][1] == cond and e["key"][2] == n)
                for k, v in enumerate(vals):
                    ax.scatter(i + dx + _jitter(k, len(vals), 0.06), v, s=46, color=COND_COLOR[cond],
                               edgecolors=SURFACE, linewidths=1.5, zorder=3)
                if vals:
                    m = sum(vals) / len(vals)
                    ax.plot([i + dx - 0.10, i + dx + 0.10], [m, m], color=COND_COLOR[cond], linewidth=2.2, zorder=4)
                    ax.annotate(f"{m:.1f}", (i + dx + 0.12, m), va="center", fontsize=8.5, color=INK2)
        ax.set_xticks(range(len(NS)))
        ax.set_xticklabels([f"N = {n}" for n in NS])
        ax.set_xlim(-0.6, len(NS) - 0.4)
        ax.set_title(MODELS[model])
        _style(ax)
    axes[0].set_ylabel("Final group total (points)")
    handles = [Line2D([], [], marker="o", linestyle="", color=COND_COLOR[c], markersize=7,
                      label=CONDS[c]) for c in ("board", "noboard")]
    handles.append(Line2D([], [], color=MUTED, linewidth=1, label="Start total (N × 1)"))
    fig.legend(handles=handles, loc="lower center", ncol=3, bbox_to_anchor=(0.5, -0.01))
    fig.suptitle("Final group total by condition", x=0.02, y=0.985, ha="left", fontsize=13, fontweight="bold")
    lines = []
    for m in MODELS:
        cells = ", ".join(f"N={n}: {sum(1 for e in done if e['key'][0] == m and e['n'] == n)}/"
                          f"{sum(1 for e in chosen if e['key'][0] == m and e['n'] == n)}" for n in NS)
        lines.append(f"{MODELS[m]} completed/planned: {cells}")
    fig.text(0.02, 0.93, "One dot per completed episode; bar = mean.\n" + "\n".join(lines),
             fontsize=8.5, color=INK2, ha="left", va="top")
    fig.tight_layout(rect=(0, 0.07, 1, 0.84))
    path = out / "01_total_by_condition.png"
    fig.savefig(path, dpi=200)
    plt.close(fig)
    return path


def fig_paired(plt, Line2D, done, out: Path) -> Path:
    fig, axes = plt.subplots(1, 2, figsize=(9.6, 4.4), sharey=True)
    for ax, model in zip(axes, MODELS):
        for i, n in enumerate(NS):
            reps = sorted({e["key"][3] for e in done if e["key"][0] == model and e["n"] == n})
            diffs = []
            for rep in reps:
                pair = {e["key"][1]: e["total_final"] for e in done
                        if e["key"][0] == model and e["n"] == n and e["key"][3] == rep}
                if "board" in pair and "noboard" in pair:
                    diffs.append(pair["board"] - pair["noboard"])
            for k, d in enumerate(diffs):
                ax.scatter(i + _jitter(k, len(diffs), 0.12), d, s=46, color=BLUE, edgecolors=SURFACE,
                           linewidths=1.5, zorder=3)
            if diffs:
                m = sum(diffs) / len(diffs)
                ax.plot([i - 0.14, i + 0.14], [m, m], color=BLUE, linewidth=2.2, zorder=4)
                ax.annotate(f"{m:+.1f}", (i + 0.16, m), va="center", fontsize=8.5, color=INK2)
        ax.axhline(0, color=MUTED, linewidth=1, zorder=1)
        ax.set_xticks(range(len(NS)))
        ax.set_xticklabels([f"N = {n}" for n in NS])
        ax.set_xlim(-0.6, len(NS) - 0.4)
        ax.set_title(MODELS[model])
        _style(ax)
    axes[0].set_ylabel("Board minus no-board total (points)")
    fig.suptitle("Paired difference: board minus no-board, same seed", x=0.02, ha="left", fontsize=13,
                 fontweight="bold")
    fig.text(0.02, 0.93, "One dot per replicate with both conditions completed (paired on turn order and game draws). "
             "Bar = mean. Zero = no difference.", fontsize=8.5, color=INK2, ha="left")
    fig.tight_layout(rect=(0, 0, 1, 0.9))
    path = out / "02_paired_difference.png"
    fig.savefig(path, dpi=200)
    plt.close(fig)
    return path


def fig_behaviour(plt, Line2D, done, out: Path) -> Path:
    metrics = [("plays", "Games played per episode", False), ("transfers", "Transfers per episode", False),
               ("posts", "Board posts per episode (board only)", True)]
    fig, axes = plt.subplots(len(MODELS), len(metrics), figsize=(10.4, 6.2), sharey="col")
    for r, model in enumerate(MODELS):
        for c, (key, label, board_only) in enumerate(metrics):
            ax = axes[r][c]
            for i, n in enumerate(NS):
                for cond, dx in (("board", -0.16), ("noboard", 0.16)):
                    if board_only and cond == "noboard":
                        continue
                    vals = [e[key] for e in done if e["key"][0] == model and e["key"][1] == cond and e["n"] == n]
                    for k, v in enumerate(vals):
                        ax.scatter(i + dx + _jitter(k, len(vals), 0.07), v, s=30, color=COND_COLOR[cond],
                                   edgecolors=SURFACE, linewidths=1.2, zorder=3)
                    if vals:
                        m = sum(vals) / len(vals)
                        ax.plot([i + dx - 0.09, i + dx + 0.09], [m, m], color=COND_COLOR[cond], linewidth=2, zorder=4)
            ax.set_xticks(range(len(NS)))
            ax.set_xticklabels([f"N = {n}" for n in NS])
            ax.set_xlim(-0.6, len(NS) - 0.4)
            ax.set_ylim(bottom=-0.3)
            if r == 0:
                ax.set_title(label, fontsize=10)
            if c == 0:
                ax.set_ylabel(MODELS[model], fontsize=10)
            _style(ax)
    handles = [Line2D([], [], marker="o", linestyle="", color=COND_COLOR[c], markersize=6,
                      label=CONDS[c]) for c in ("board", "noboard")]
    fig.legend(handles=handles, loc="lower center", ncol=2, bbox_to_anchor=(0.5, -0.01))
    fig.suptitle("What agents did: play, transfer, post", x=0.02, ha="left", fontsize=13, fontweight="bold")
    fig.text(0.02, 0.945, "One dot per completed episode; bar = mean.", fontsize=8.5, color=INK2, ha="left")
    fig.tight_layout(rect=(0, 0.04, 1, 0.92))
    path = out / "03_behaviour.png"
    fig.savefig(path, dpi=200)
    plt.close(fig)
    return path


def fig_tokens_cost(plt, Line2D, results: Path, chosen, done, caps, out: Path) -> Path:
    # Panel data: per-call completion tokens from the transcripts of chosen (completed) episodes, using only
    # runs at the largest per-call cap present, so a histogram never mixes two different output limits.
    cap = max((c for c in caps.values() if c), default=None)
    calls = {m: [] for m in MODELS}
    excluded = 0
    for e in done:
        if caps.get(e["run"]) != cap:
            excluded += 1
            continue
        for row in iter_calls(results / e["run"], e["dir"]):
            calls[e["key"][0]].append(row.get("completion_tokens") or 0)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10.2, 4.6), gridspec_kw={"width_ratios": [1.45, 1]})
    bins = [i * 1024 for i in range(0, 18)]
    for model in MODELS:
        if calls[model]:
            ax1.hist(calls[model], bins=bins, histtype="step", linewidth=2, color=MODEL_COLOR[model],
                     label=f"{MODELS[model]} (n = {len(calls[model])} calls)")
    if cap:
        ax1.axvline(cap, color=INK2, linewidth=1)
        ax1.text(cap - 250, ax1.get_ylim()[1] * 0.92 if ax1.get_ylim()[1] else 1, f"max_tokens = {cap:,}",
                 ha="right", va="top", fontsize=8.5, color=INK2)
    ax1.set_xlabel("Completion tokens per call (reasoning + reply)")
    ax1.set_ylabel("Calls")
    ax1.set_title("Output length per call")
    _style(ax1)
    if calls and any(calls.values()):
        ax1.legend(loc="upper right", bbox_to_anchor=(1, 0.86))
    for i, model in enumerate(MODELS):
        costs = [e["cost_usd"] for e in done if e["key"][0] == model]
        ax2.scatter([i + _jitter(k, len(costs), 0.12) for k in range(len(costs))], costs, s=46,
                    color=MODEL_COLOR[model], edgecolors=SURFACE, linewidths=1.5, zorder=3)
        if costs:
            m = sum(costs) / len(costs)
            ax2.plot([i - 0.14, i + 0.14], [m, m], color=MODEL_COLOR[model], linewidth=2.2, zorder=4)
            ax2.annotate(f"mean ${m:.4f}", (i + 0.16, m), va="center", fontsize=8.5, color=INK2)
    ax2.axhline(CAP_USD, color=INK2, linewidth=1)
    ax2.text(-0.45, CAP_USD, "per-episode cap $0.10", va="bottom", fontsize=8.5, color=INK2)
    ax2.set_xticks(range(len(MODELS)))
    ax2.set_xticklabels([MODELS[m].split()[0] + " " + MODELS[m].split()[1] for m in MODELS])
    ax2.set_xlim(-0.6, len(MODELS) - 0.4)
    ax2.set_ylim(bottom=-0.002)
    ax2.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"${v:.2f}"))
    ax2.set_ylabel("Cost per completed episode (USD)")
    ax2.set_title("Spend against the cap")
    _style(ax2)
    fig.suptitle("Output tokens and spend", x=0.02, y=0.985, ha="left", fontsize=13, fontweight="bold")
    note = (f"Runs at max_tokens = {cap:,}" if cap else "No run config found") + \
           (f"; {excluded} completed episode(s) from runs with other caps left out of the histogram" if excluded else "")
    fig.text(0.02, 0.93, note + ". Panel right: colours denote models here.", fontsize=8.5, color=INK2, ha="left", va="top")
    fig.tight_layout(rect=(0, 0, 1, 0.86))
    path = out / "04_tokens_and_cost.png"
    fig.savefig(path, dpi=200)
    plt.close(fig)
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--results", type=Path, default=HERE / "results")
    parser.add_argument("--out", type=Path, default=HERE / "figures")
    args = parser.parse_args()
    plt, Line2D = _import_pyplot()
    chosen, done, caps, results = _load(args.results.resolve())
    if not done:
        sys.exit("no completed grid episodes found; nothing to plot")
    args.out.mkdir(parents=True, exist_ok=True)
    written = [fig_totals(plt, Line2D, chosen, done, args.out),
               fig_paired(plt, Line2D, done, args.out),
               fig_behaviour(plt, Line2D, done, args.out),
               fig_tokens_cost(plt, Line2D, results, chosen, done, caps, args.out)]
    for p in written:
        print(f"wrote {p}")
    print(f"{len(done)} completed episodes of {len(chosen)} episode keys; unfinished keys are listed in summarize.py output")


if __name__ == "__main__":
    main()
