from __future__ import annotations

from collections import defaultdict
import csv
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import discord
from discord.ext import commands


BOWLING_DB_PATH = Path("bowling_records.csv")
CSV_FIELDS = ["timestamp", "user_id", "user_name", "record_type", "value", "unit"]


@dataclass(frozen=True)
class BowlingRecord:
    timestamp: str
    user_id: int
    user_name: str
    record_type: str
    value: float
    unit: str


def ensure_bowling_db(path: Path) -> None:
    if path.exists():
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()


def append_bowling_record(record: BowlingRecord, path: Path = BOWLING_DB_PATH) -> None:
    ensure_bowling_db(path)
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writerow(
            {
                "timestamp": record.timestamp,
                "user_id": record.user_id,
                "user_name": record.user_name,
                "record_type": record.record_type,
                "value": record.value,
                "unit": record.unit,
            }
        )


def load_bowling_records(path: Path = BOWLING_DB_PATH) -> list[BowlingRecord]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        records = []
        for row in reader:
            records.append(
                BowlingRecord(
                    timestamp=str(row.get("timestamp", "")),
                    user_id=int(row.get("user_id", 0)),
                    user_name=str(row.get("user_name", "")),
                    record_type=str(row.get("record_type", "")),
                    value=float(row.get("value", 0)),
                    unit=str(row.get("unit", "")),
                )
            )
        return records


def write_bowling_records(
    records: list[BowlingRecord], path: Path = BOWLING_DB_PATH
) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for record in records:
            writer.writerow(
                {
                    "timestamp": record.timestamp,
                    "user_id": record.user_id,
                    "user_name": record.user_name,
                    "record_type": record.record_type,
                    "value": record.value,
                    "unit": record.unit,
                }
            )


def ordinal(num: int) -> str:
    if 11 <= (num % 100) <= 13:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(num % 10, "th")
    return f"{num}{suffix}"


def resolve_user_name(
    guild: Optional[discord.Guild], user_id: int, fallback: str
) -> str:
    if guild:
        member = guild.get_member(user_id)
        if member:
            return member.display_name
    return fallback or f"User {user_id}"


def format_speed(value: float) -> str:
    return f"{value:.2f} mph"


def compute_strike_streak(
    records: list[BowlingRecord],
) -> tuple[int, Optional[int], Optional[str]]:
    records_sorted = sorted(records, key=lambda record: record.timestamp)
    current_streaks: dict[int, int] = defaultdict(int)
    max_streak = 0
    max_user_id: Optional[int] = None
    max_user_name: Optional[str] = None

    for record in records_sorted:
        if record.record_type == "strike":
            current_streaks[record.user_id] += 1
            if current_streaks[record.user_id] > max_streak:
                max_streak = current_streaks[record.user_id]
                max_user_id = record.user_id
                max_user_name = record.user_name
        else:
            current_streaks[record.user_id] = 0

    return max_streak, max_user_id, max_user_name


def parse_add_args(args: tuple[str, ...]) -> tuple[Optional[dict], Optional[str]]:
    if len(args) < 2:
        return None, "Usage: `>bowling add score 170`, `>bowling add speed 22`, or `>bowling add strike speed 22`."

    record_type = args[0].lower()
    if record_type == "score":
        if len(args) != 2:
            return None, "Usage: `>bowling add score 170`."
        try:
            score = int(args[1])
        except ValueError:
            return None, "Score must be a whole number."
        if score <= 0:
            return None, "Score must be greater than zero."
        return {"record_type": "score", "value": float(score), "unit": "points"}, None

    if record_type == "speed":
        if len(args) != 2:
            return None, "Usage: `>bowling add speed 22`."
        try:
            speed = float(args[1])
        except ValueError:
            return None, "Speed must be a number (mph)."
        if speed <= 0:
            return None, "Speed must be greater than zero."
        return {"record_type": "speed", "value": speed, "unit": "mph"}, None

    if record_type == "strike":
        speed_arg: Optional[str] = None
        if len(args) == 2:
            speed_arg = args[1]
        elif len(args) == 3 and args[1].lower() == "speed":
            speed_arg = args[2]
        else:
            return None, "Usage: `>bowling add strike speed 22`."
        try:
            speed = float(speed_arg)
        except ValueError:
            return None, "Strike speed must be a number (mph)."
        if speed <= 0:
            return None, "Strike speed must be greater than zero."
        return {"record_type": "strike", "value": speed, "unit": "mph"}, None

    return None, "Record type must be `score`, `speed`, or `strike`."


def format_bowling_records(records: list[BowlingRecord], guild: Optional[discord.Guild]) -> str:
    lines = ["Bowling Records", "", "Top scores:"]

    scores = sorted(
        (record for record in records if record.record_type == "score"),
        key=lambda record: record.value,
        reverse=True,
    )
    if not scores:
        lines.append("No scores recorded.")
    else:
        medals = ["🥇", "🥈", "🥉"]
        for idx, record in enumerate(scores[:5]):
            name = resolve_user_name(guild, record.user_id, record.user_name)
            label = medals[idx] if idx < len(medals) else ordinal(idx + 1)
            lines.append(f"{label} {int(record.value)} - {name}")

    strike_records = [record for record in records if record.record_type == "strike"]
    speed_records = [record for record in records if record.record_type == "speed"]

    lines.append("")
    if strike_records:
        slowest_strike = min(strike_records, key=lambda record: record.value)
        slowest_name = resolve_user_name(
            guild, slowest_strike.user_id, slowest_strike.user_name
        )
        lines.append(
            f"Slowest Strike: {format_speed(slowest_strike.value)} - {slowest_name}"
        )
    else:
        lines.append("Slowest Strike: n/a")

    if speed_records:
        fastest_bowl = max(speed_records, key=lambda record: record.value)
        fastest_bowl_name = resolve_user_name(
            guild, fastest_bowl.user_id, fastest_bowl.user_name
        )
        lines.append(
            f"Fastest Bowl: {format_speed(fastest_bowl.value)} - {fastest_bowl_name}"
        )
    else:
        lines.append("Fastest Bowl: n/a")

    if strike_records:
        fastest_strike = max(strike_records, key=lambda record: record.value)
        fastest_strike_name = resolve_user_name(
            guild, fastest_strike.user_id, fastest_strike.user_name
        )
        lines.append(
            f"Fastest Strike: {format_speed(fastest_strike.value)} - {fastest_strike_name}"
        )
    else:
        lines.append("Fastest Strike: n/a")

    streak, streak_user_id, streak_user_name = compute_strike_streak(records)
    if streak and streak_user_id is not None:
        streak_name = resolve_user_name(guild, streak_user_id, streak_user_name or "")
        lines.append(f"Most strikes in a row: {streak} - {streak_name}")
    else:
        lines.append("Most strikes in a row: n/a")

    return "\n".join(lines)


class Bowling(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.group(name="bowling", invoke_without_command=True)
    async def bowling_group(self, ctx: commands.Context):
        await ctx.send(
            "Use `>bowling add score 170`, `>bowling add speed 22`, `>bowling add strike speed 22`, or `>bowling stats`."
        )

    @bowling_group.group(name="add", invoke_without_command=True)
    async def bowling_add(self, ctx: commands.Context, *args: str):
        parsed, error = parse_add_args(args)
        if error:
            await ctx.send(error)
            return

        record = BowlingRecord(
            timestamp=datetime.now(timezone.utc).isoformat(),
            user_id=ctx.author.id,
            user_name=ctx.author.display_name,
            record_type=parsed["record_type"],
            value=parsed["value"],
            unit=parsed["unit"],
        )
        append_bowling_record(record)

        if record.record_type == "score":
            await ctx.send(f"Added score {int(record.value)} for {record.user_name}.")
        elif record.record_type == "speed":
            await ctx.send(
                f"Added bowl speed {format_speed(record.value)} for {record.user_name}."
            )
        else:
            await ctx.send(
                f"Added strike speed {format_speed(record.value)} for {record.user_name}."
            )

    @bowling_group.command(name="stats")
    async def bowling_stats(self, ctx: commands.Context):
        records = load_bowling_records()
        if not records:
            await ctx.send("No bowling records yet. Add one with `>bowling add`.")
            return
        await ctx.send(format_bowling_records(records, ctx.guild))

    @bowling_group.group(name="delete", invoke_without_command=True)
    async def bowling_delete(self, ctx: commands.Context):
        await ctx.send("Use `>bowling delete score` to list scores to delete.")

    @bowling_delete.command(name="score")
    async def bowling_delete_score(self, ctx: commands.Context, index: Optional[int] = None):
        records = load_bowling_records()
        score_records = [
            record for record in records if record.record_type == "score"
        ]

        if not score_records:
            await ctx.send("No scores to delete.")
            return

        if index is None:
            lines = ["Scores:"]
            for idx, record in enumerate(score_records, start=1):
                name = resolve_user_name(ctx.guild, record.user_id, record.user_name)
                lines.append(
                    f"{idx}. {int(record.value)} - {name} ({record.timestamp})"
                )
            lines.append("Reply with `>bowling delete score <index>` to delete.")
            await ctx.send("\n".join(lines))
            return

        if index < 1 or index > len(score_records):
            await ctx.send("Index out of range. Run `>bowling delete score` first.")
            return

        target = score_records[index - 1]
        remaining_records = [
            record
            for record in records
            if not (
                record.record_type == "score"
                and record.timestamp == target.timestamp
                and record.user_id == target.user_id
                and record.value == target.value
            )
        ]
        write_bowling_records(remaining_records)
        await ctx.send(
            f"Deleted score {int(target.value)} for {resolve_user_name(ctx.guild, target.user_id, target.user_name)}."
        )
