"""Admin-only Hy (Lisp) eval.

`>eval (+ 1 2)` runs arbitrary Hy code and replies with the value of the last
form. This is full code execution, so it is restricted to the configured
`admin_id`. Output (both the return value and anything printed to stdout) is
captured and sent back in a code block.
"""

import contextlib
import io
import traceback

import hy
import kronicler


def run_hy(source: str):
    """Eval Hy ``source`` and return ``(result, printed_output)``.

    Every top-level form is evaluated in a shared namespace; the value of the
    last form is returned. Raises on read or eval errors.
    """
    namespace = {}
    stdout = io.StringIO()
    result = None
    with contextlib.redirect_stdout(stdout):
        for form in hy.read_many(source):
            result = hy.eval(form, namespace)
    return result, stdout.getvalue()


def format_response(result, printed: str) -> str:
    """Build the Discord reply for an eval result, capped at 2000 chars."""
    parts = []
    if printed:
        parts.append(printed.rstrip("\n"))
    if result is not None:
        parts.append(repr(result))
    body = "\n".join(parts) if parts else "(no output)"

    fenced = f"```\n{body}\n```"
    if len(fenced) <= 2000:
        return fenced

    # Trim the body so the fenced block fits Discord's 2000-char limit.
    budget = 2000 - len("```\n\n```") - len("\n... (truncated)")
    return f"```\n{body[:budget]}\n... (truncated)\n```"


@kronicler.capture
async def handle_eval(ctx, admin_id: int, source: str):
    """Run admin-only Hy eval and reply with the result."""
    if admin_id == 0 or ctx.author.id != admin_id:
        await ctx.send("You are not authorized to run this command.")
        return

    if not source.strip():
        await ctx.send("Usage: `>eval (+ 1 2)`")
        return

    try:
        result, printed = run_hy(source)
    except Exception:  # noqa: BLE001 - surface any eval error to the admin
        tb = traceback.format_exc()
        await ctx.send(f"```\n{tb[-1900:]}\n```")
        return

    await ctx.send(format_response(result, printed))
