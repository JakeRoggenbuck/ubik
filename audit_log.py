import logging
from pathlib import Path
import discord

MAX_LINES = 20
MAX_CHARS = 1900  # leave room for code block markers

AUDIT_LOG_PATH = Path("audit.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
    handlers=[
        logging.FileHandler(AUDIT_LOG_PATH, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)

audit_logger = logging.getLogger("audit")


async def on_message_delete(message: discord.Message):
    if message.author.bot:
        return

    guild = message.guild.name if message.guild else "DM"
    channel = f"#{message.channel.name}" if hasattr(message.channel, "name") else "DM"
    author = f"{message.author} ({message.author.id})"
    content = message.content or "<no text content>"

    audit_logger.info(
        "[DELETED] guild=%r channel=%s author=%s message_id=%s content=%r",
        guild,
        channel,
        author,
        message.id,
        content,
    )


def read_audit_log(keyword: str | None = None) -> str:
    if not AUDIT_LOG_PATH.exists():
        return "Audit log is empty."

    lines = AUDIT_LOG_PATH.read_text(encoding="utf-8").splitlines()

    if keyword:
        lines = [l for l in lines if keyword.lower() in l.lower()]

    if not lines:
        return f"No entries matching {keyword!r}."

    # Return the most recent MAX_LINES lines, truncated to fit a Discord message
    recent = lines[-MAX_LINES:]
    block = "\n".join(recent)
    if len(block) > MAX_CHARS:
        block = block[-MAX_CHARS:]
        block = block[block.index("\n") + 1:]  # trim partial first line

    header = f"Last {len(recent)} entries" + (f" matching {keyword!r}" if keyword else "")
    return f"{header}:\n```\n{block}\n```"
