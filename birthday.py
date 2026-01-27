import random
from datetime import time, timezone, timedelta, datetime
from pathlib import Path

import discord
from discord.ext import tasks
import kronicler
import tomllib


BIRTHDAYS_PATH = Path("birthdays.toml")

PARTY = "🎉"
CAKE = "🎂"

BIRTHDAY_MESSAGE = [
    f"Make sure to bring some cake! {CAKE}",
    f"Whoooh!! {PARTY}",
]

MY_TIMEZONE = timezone(timedelta(hours=-8))


@kronicler.capture
def load_birthdays(path: Path) -> dict[tuple[int, int], tuple[int, str]]:
    data = tomllib.loads(path.read_text(encoding="utf-8"))

    birthdays: dict[tuple[int, int], tuple[int, str]] = {}

    for entry in data.get("birthdays", []):
        month = int(entry["month"])
        day = int(entry["day"])
        user_id = int(entry["user_id"])
        name = str(entry["name"])
        birthdays[(month, day)] = (user_id, name)

    return birthdays


if not BIRTHDAYS_PATH.exists():
    raise FileNotFoundError(f"The file {BIRTHDAYS_PATH} not found.")

BIRTHDAYS = load_birthdays(BIRTHDAYS_PATH)


@kronicler.capture
def format_birthdays(birthdays: dict[tuple[int, int], tuple[int, str]]) -> str:
    if not birthdays:
        return "No birthdays configured."

    lines = []
    for (month, day), (_, name) in sorted(birthdays.items()):
        lines.append(f"{month:02d}/{day:02d}  {name}")

    header = f"Birthdays ({len(lines)}):"
    return "\n".join([header, "```", *lines, "```"])


@kronicler.capture
async def get_daily_birthday_check(bot: discord.Client, channel_id: int):
    now = datetime.now()

    if (bday := (now.month, now.day)) in BIRTHDAYS:
        user = BIRTHDAYS[bday]

        channel = bot.get_channel(channel_id)
        if channel:
            await channel.send(f"Happy Birthday {user[1]}!! <@{user[0]}>")
            await channel.send(random.choice(BIRTHDAY_MESSAGE))
            await channel.send(file=discord.File("./images/birthday ubik.jpg"))
        else:
            print(f"Could not find channel with ID {channel_id}")


def create_daily_birthday_check(bot: discord.Client, channel_id: int):
    @tasks.loop(time=time(hour=12, minute=0, tzinfo=MY_TIMEZONE))
    async def daily_birthday_check():
        await get_daily_birthday_check(bot, channel_id)

    return daily_birthday_check


@kronicler.capture
async def send_birthday_channel_check(bot: discord.Client, channel_id: int) -> bool:
    channel = bot.get_channel(channel_id)
    if channel:
        await channel.send("We will send birthday announcements here.")
        return True

    print(f"Could not find channel with ID {channel_id}")
    return False
