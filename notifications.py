from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from datetime import time, timedelta, timezone
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType
from typing import Any

import aiohttp
import discord
from discord.ext import tasks
import kronicler
import tomllib


NOTIFICATION_STREAMS_PATH = Path("notification_streams.toml")
MY_TIMEZONE = timezone(timedelta(hours=-8))

# Maps sent message IDs to their hidden URLs so reactions can trigger DM delivery.
_PENDING_LINKS: dict[int, str] = {}


@dataclass(slots=True)
class Subscriber:
    user_id: int
    delivery: str
    channel_id: int | None = None


@dataclass(slots=True)
class StreamConfig:
    name: str
    script: Path
    subscribers: list[Subscriber]


_write_lock = asyncio.Lock()


def _toml_quote(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


@kronicler.capture
def _dump_streams(streams: list[StreamConfig]) -> str:
    lines = [
        "# Notification stream definitions.",
        "# Each stream script must define get_new_events() and return a list of events.",
        "",
    ]

    for index, stream in enumerate(streams):
        if index > 0:
            lines.append("")

        lines.append("[[streams]]")
        lines.append(f"name = {_toml_quote(stream.name)}")
        lines.append(f"script = {_toml_quote(stream.script.as_posix())}")

        for sub in stream.subscribers:
            lines.append("[[streams.subscribers]]")
            lines.append(f"user_id = {sub.user_id}")
            lines.append(f"delivery = {_toml_quote(sub.delivery)}")
            if sub.channel_id is not None:
                lines.append(f"channel_id = {sub.channel_id}")

    lines.append("")
    return "\n".join(lines)


@kronicler.capture
def _ensure_config_file(path: Path):
    if path.exists():
        return

    path.write_text(
        "# Notification stream definitions.\n\n",
        encoding="utf-8",
    )


@kronicler.capture
def load_streams(path: Path) -> list[StreamConfig]:
    _ensure_config_file(path)

    data = tomllib.loads(path.read_text(encoding="utf-8"))

    streams: list[StreamConfig] = []
    for raw_stream in data.get("streams", []):
        name = str(raw_stream["name"]).strip()
        script = Path(str(raw_stream["script"]).strip())

        if not name:
            continue

        raw_subscribers = raw_stream.get("subscribers", [])
        subscribers: list[Subscriber] = []
        for raw_subscriber in raw_subscribers:
            try:
                user_id = int(raw_subscriber["user_id"])
            except (TypeError, ValueError, KeyError):
                continue

            delivery = str(raw_subscriber.get("delivery", "dm")).strip().lower()
            if delivery not in {"dm", "channel"}:
                delivery = "dm"

            channel_id_raw = raw_subscriber.get("channel_id")
            channel_id: int | None
            if channel_id_raw is None:
                channel_id = None
            else:
                try:
                    channel_id = int(channel_id_raw)
                except (TypeError, ValueError):
                    channel_id = None

            subscribers.append(
                Subscriber(user_id=user_id, delivery=delivery, channel_id=channel_id)
            )

        streams.append(StreamConfig(name=name, script=script, subscribers=subscribers))

    return streams


@kronicler.capture
def write_streams(path: Path, streams: list[StreamConfig]):
    path.write_text(_dump_streams(streams), encoding="utf-8")


@kronicler.capture
def list_stream_names(path: Path) -> list[str]:
    return sorted(stream.name for stream in load_streams(path))


@kronicler.capture
def _find_stream(streams: list[StreamConfig], stream_name: str) -> StreamConfig | None:
    lowered = stream_name.strip().lower()
    for stream in streams:
        if stream.name.lower() == lowered:
            return stream
    return None


@kronicler.capture
async def subscribe(
    path: Path,
    stream_name: str,
    user_id: int,
    delivery: str,
    channel_id: int | None,
) -> tuple[bool, str]:
    delivery_mode = delivery.strip().lower()
    if delivery_mode not in {"dm", "channel"}:
        return False, "Delivery must be `dm` or `channel`."

    if delivery_mode == "channel" and channel_id is None:
        return False, "Channel delivery requires a channel ID."

    async with _write_lock:
        streams = load_streams(path)
        stream = _find_stream(streams, stream_name)
        if stream is None:
            return False, f"Unknown stream `{stream_name}`."

        existing = next((s for s in stream.subscribers if s.user_id == user_id), None)
        if existing is None:
            stream.subscribers.append(
                Subscriber(user_id=user_id, delivery=delivery_mode, channel_id=channel_id)
            )
        else:
            existing.delivery = delivery_mode
            existing.channel_id = channel_id

        write_streams(path, streams)

    return True, f"Subscribed to `{stream.name}` via `{delivery_mode}`."


@kronicler.capture
async def unsubscribe(path: Path, stream_name: str, user_id: int) -> tuple[bool, str]:
    async with _write_lock:
        streams = load_streams(path)
        stream = _find_stream(streams, stream_name)
        if stream is None:
            return False, f"Unknown stream `{stream_name}`."

        before = len(stream.subscribers)
        stream.subscribers = [s for s in stream.subscribers if s.user_id != user_id]
        if len(stream.subscribers) == before:
            return False, f"You are not subscribed to `{stream.name}`."

        write_streams(path, streams)

    return True, f"Unsubscribed from `{stream.name}`."


@kronicler.capture
def load_stream_module(path: Path) -> ModuleType:
    module_name = f"notification_stream_{path.stem}_{abs(hash(path.resolve()))}"
    spec = spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load stream script: {path}")

    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@kronicler.capture
def _event_to_content(stream_name: str, event: Any) -> tuple[str, str | None]:
    """Return (display_text, url_or_None). URL is always stripped from display text."""
    prefix = f"[{stream_name}]"
    if isinstance(event, str):
        return f"{prefix} {event}", None

    if isinstance(event, dict):
        title = str(event.get("message") or event.get("title") or "New event")
        details = str(event.get("details") or event.get("body") or "").strip()
        url = str(event.get("url") or "").strip() or None

        lines = [f"{prefix} {title}"]
        if details:
            lines.append(details)
        return "\n".join(lines), url

    return f"{prefix} {event}", None


async def _fetch_og_data(url: str) -> dict[str, str | None]:
    """Return og:title and og:image scraped from url, or None for each if missing."""
    def _og_match(html: str, prop: str) -> str | None:
        m = re.search(
            rf'<meta[^>]+property=["\']og:{prop}["\'][^>]+content=["\']([^"\']+)["\']'
            rf'|<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:{prop}["\']',
            html,
        )
        return (m.group(1) or m.group(2)) if m else None

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    return {"title": None, "image": None}
                html = await resp.text()
        return {"title": _og_match(html, "title"), "image": _og_match(html, "image")}
    except Exception:
        return {"title": None, "image": None}


@kronicler.capture
async def _send_to_subscriber(
    bot: discord.Client,
    sub: Subscriber,
    content: str,
    embed: discord.Embed | None = None,
    url: str | None = None,
):
    if sub.delivery == "dm":
        user = await bot.fetch_user(sub.user_id)
        dm_content = f"{content}\n{url}" if url else content
        await user.send(dm_content)
        return

    if sub.channel_id is None:
        raise RuntimeError(
            f"Subscriber {sub.user_id} requested channel delivery but has no channel_id"
        )

    channel = bot.get_channel(sub.channel_id)
    if channel is None:
        channel = await bot.fetch_channel(sub.channel_id)

    if not isinstance(channel, discord.abc.Messageable):
        raise RuntimeError(f"Channel {sub.channel_id} is not messageable")

    msg = await channel.send(
        f"<@{sub.user_id}> {content}",
        embed=embed,
    )
    if url:
        _PENDING_LINKS[msg.id] = url
        await msg.add_reaction("👍")


@kronicler.capture
async def send_url_to_stream(
    bot: discord.Client,
    path: Path,
    stream_name: str,
    url: str,
) -> tuple[bool, str, int]:
    """Manually send a URL as an event to all subscribers of a stream.

    Returns (found, error_message, sent_count).
    """
    streams = load_streams(path)
    stream = _find_stream(streams, stream_name)
    if stream is None:
        return False, f"Unknown stream `{stream_name}`.", 0

    og = await _fetch_og_data(url)
    title = og["title"] or url
    content = f"[{stream.name}] {title}"

    embed = discord.Embed()
    if og["image"]:
        embed.set_image(url=og["image"])
    embed.set_footer(text="React with 👍 to receive the link via DM")

    sent = 0
    for sub in stream.subscribers:
        try:
            await _send_to_subscriber(bot, sub, content, embed=embed, url=url)
            sent += 1
        except Exception as exc:
            print(f"Failed to send manual notification to {sub.user_id}: {exc}")

    return True, "", sent


@kronicler.capture
async def dispatch_notifications(
    bot: discord.Client, path: Path = NOTIFICATION_STREAMS_PATH
) -> dict[str, int]:
    streams = load_streams(path)
    sent: dict[str, int] = {}

    for stream in streams:
        script_path = stream.script
        if not script_path.is_absolute():
            script_path = (path.parent / script_path).resolve()

        if not script_path.exists():
            print(f"Notification stream script not found for {stream.name}: {script_path}")
            continue

        try:
            module = load_stream_module(script_path)
        except Exception as exc:
            print(f"Failed to load stream script {script_path}: {exc}")
            continue

        pull = getattr(module, "get_new_events", None)
        if pull is None:
            print(f"Stream script {script_path} does not define get_new_events()")
            continue

        try:
            events = pull()
        except Exception as exc:
            print(f"Error calling get_new_events() for stream {stream.name}: {exc}")
            continue

        if not events:
            sent[stream.name] = 0
            continue

        sent_count = 0
        for event in events:
            content, url = _event_to_content(stream.name, event)

            embed: discord.Embed | None = None
            if url:
                og = await _fetch_og_data(url)
                embed = discord.Embed()
                if og["image"]:
                    embed.set_image(url=og["image"])
                embed.set_footer(text="React with 👍 to receive the link via DM")

            for sub in stream.subscribers:
                try:
                    await _send_to_subscriber(bot, sub, content, embed=embed, url=url)
                    sent_count += 1
                except Exception as exc:
                    print(
                        f"Failed to send stream {stream.name} notification to {sub.user_id}: {exc}"
                    )

        sent[stream.name] = sent_count

    return sent


def create_daily_notification_check(
    bot: discord.Client, path: Path = NOTIFICATION_STREAMS_PATH
):
    @tasks.loop(time=time(hour=12, minute=5, tzinfo=MY_TIMEZONE))
    async def daily_notification_check():
        await dispatch_notifications(bot, path)

    return daily_notification_check
