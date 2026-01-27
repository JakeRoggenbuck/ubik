from __future__ import annotations

from collections import defaultdict
import io
from itertools import cycle

import discord
import matplotlib
import seaborn as sns
from discord.ext import commands

matplotlib.use("Agg")
import matplotlib.pyplot as plt

import kronicler


PLOT_COLORS = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd"]


def create_runtime_plot(log_data: list[list]) -> io.BytesIO:
    """Create a bar chart with error bars showing mean runtime and std deviation."""
    function_times: defaultdict[str, list[float]] = defaultdict(list)

    for entry in log_data:
        _, function_name, _start_time, duration = entry
        runtime_ms = duration / 1_000_000
        function_times[function_name].append(runtime_ms)

    if not function_times:
        return io.BytesIO()

    functions = []
    means = []
    stds = []

    for function_name in sorted(function_times.keys()):
        times = function_times[function_name]
        functions.append(function_name)
        mean_time = sum(times) / len(times)
        means.append(mean_time)
        variance = sum((x - mean_time) ** 2 for x in times) / len(times)
        stds.append(variance**0.5)

    sns.set_theme(
        style="darkgrid",
        font="DejaVu Sans",
        rc={
            "axes.facecolor": "#262626",
            "figure.facecolor": "#1b1b1b",
            "text.color": "#f0f0f0",
            "axes.labelcolor": "#f0f0f0",
            "xtick.color": "#d8d8d8",
            "ytick.color": "#d8d8d8",
            "grid.color": "#3a3a3a",
        },
    )
    fig, ax = plt.subplots(figsize=(10, 4.5))
    color_cycle = cycle(PLOT_COLORS)
    bar_colors = [next(color_cycle) for _ in functions]

    x_pos = range(len(functions))
    bars = ax.bar(
        x_pos,
        means,
        yerr=stds,
        capsize=10,
        alpha=0.75,
        color=bar_colors,
        ecolor="#ffffff",
    )

    ax.set_xlabel("Function Name", fontsize=12, fontweight="bold")
    ax.set_ylabel("Runtime (milliseconds)", fontsize=12, fontweight="bold")
    ax.set_title(
        "Function Runtime Analysis\n(Mean with Standard Deviation)",
        fontsize=14,
        fontweight="bold",
    )
    ax.set_yscale("log")
    ax.set_xticks(list(x_pos))
    ax.set_xticklabels(functions, rotation=45, ha="right")
    ax.grid(axis="y", alpha=0.3, linestyle="--")

    for i, (bar, count) in enumerate(
        zip(bars, [len(function_times[f]) for f in functions])
    ):
        height = bar.get_height()
        ax.text(
            bar.get_x() + bar.get_width() * 0.95,
            height,
            f"{height:.2f}",
            ha="right",
            va="bottom",
            fontsize=8,
        )
        ax.text(
            bar.get_x() + bar.get_width() * 0.05,
            height,
            f"n={count}",
            ha="left",
            va="bottom",
            fontsize=9,
        )

    fig.subplots_adjust(left=0.12, right=0.98, top=0.88, bottom=0.32)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150)
    buf.seek(0)
    plt.close(fig)

    return buf


@kronicler.capture
async def send_runtime_plot(ctx: commands.Context, db: kronicler.Database):
    log_data = db.logs()
    if not log_data:
        await ctx.send("No kronicler data available yet.")
        return

    image_buffer = create_runtime_plot(log_data)
    if image_buffer.getbuffer().nbytes == 0:
        await ctx.send("No kronicler data available yet.")
        return

    await ctx.send(
        file=discord.File(image_buffer, filename="runtime_analysis.png"),
    )
