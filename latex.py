from __future__ import annotations

import io

import discord
import matplotlib
from discord.ext import commands

matplotlib.use("Agg")
import matplotlib.pyplot as plt


MAX_INPUT_LENGTH = 1000


def _wrap_math(expression: str) -> list[str]:
    lines = expression.splitlines() or [expression]
    wrapped = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if "$" in stripped:
            wrapped.append(stripped)
        else:
            wrapped.append(f"${stripped}$")
    return wrapped


def render_latex(expression: str) -> io.BytesIO:
    lines = _wrap_math(expression)
    text = "\n".join(lines)

    fig = plt.figure(figsize=(0.01, 0.01), facecolor="white")
    fig.text(
        0.5,
        0.5,
        text,
        ha="center",
        va="center",
        fontsize=22,
        color="black",
    )

    buf = io.BytesIO()
    fig.savefig(
        buf,
        format="png",
        dpi=200,
        bbox_inches="tight",
        pad_inches=0.25,
        facecolor="white",
    )
    buf.seek(0)
    plt.close(fig)
    return buf


async def send_latex(ctx: commands.Context, expression: str) -> None:
    expression = expression.strip()
    if not expression:
        await ctx.send("Usage: `>latex <expression>` (e.g. `>latex e^{i\\pi} + 1 = 0`)")
        return
    if len(expression) > MAX_INPUT_LENGTH:
        await ctx.send(f"Expression too long (max {MAX_INPUT_LENGTH} characters).")
        return

    try:
        image_buffer = render_latex(expression)
    except (ValueError, RuntimeError) as exc:
        await ctx.send(f"Could not render LaTeX: {exc}")
        return

    await ctx.send(file=discord.File(image_buffer, filename="latex.png"))
