import logging
from pathlib import Path
import discord

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
