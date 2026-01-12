import discord
from discord.ext import commands, tasks
from collections import defaultdict
from datetime import time, timezone, timedelta, datetime
from pathlib import Path
import tomllib
import random


CHANNEL_ID = 1416214869090238506

BIRTHDAYS_PATH = Path("birthdays.toml")


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

PARTY = "🎉"
CAKE = "🎂"

BIRTHDAY_MESSAGE = [
    f"Make sure to bring some cake! {CAKE}",
    f"Whoooh!! {PARTY}",
]

MY_TIMEZONE = timezone(timedelta(hours=-8))

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guild_messages = True

bot = commands.Bot(command_prefix=">", intents=intents)


def format_timedelta(td):
    secs = int(td.total_seconds())
    days, secs = divmod(secs, 86400)
    hours, secs = divmod(secs, 3600)
    minutes, secs = divmod(secs, 60)

    if days > 0:
        return f"{days}d {hours}h ago"
    if hours > 0:
        return f"{hours}h {minutes}m ago"
    if minutes > 0:
        return f"{minutes}m {secs}s ago"
    return f"{secs}s ago"


@bot.command()
async def ping(ctx):
    await ctx.send("pong")


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    daily_birthday_check.start()


@bot.command()
async def activity(ctx, limit: int = 1000):
    await ctx.send("Collecting data, this may take a moment...")

    members = {member.id: member for member in ctx.guild.members if not member.bot}
    message_counts = defaultdict(int)
    last_messages = {}

    # Loop through all text channels
    for channel in ctx.guild.text_channels:
        try:
            async for message in channel.history(limit=limit):
                if message.author.bot:
                    continue
                message_counts[message.author.id] += 1
                # Update last message timestamp if this message is newer
                if (
                    message.author.id not in last_messages
                    or message.created_at > last_messages[message.author.id]
                ):
                    last_messages[message.author.id] = message.created_at
        except discord.Forbidden:
            continue  # Skip channels the bot can't read
        except discord.HTTPException:
            continue  # Skip on rate limit or errors

    report_lines = []
    for member_id, member in members.items():
        last_msg_time = last_messages.get(member_id, None)
        total_msgs = message_counts.get(member_id, 0)
        if last_msg_time:
            time_since_last = discord.utils.format_dt(
                last_msg_time, style="R"
            )  # Relative time
        else:
            time_since_last = "No messages found"
        report_lines.append(
            f"{member.name}#{member.discriminator}: Last message {time_since_last}, Total messages: {total_msgs}"
        )

    # Split into chunks if too long
    chunk_size = 2000
    report_text = "\n".join(report_lines)
    chunks = [
        report_text[i : i + chunk_size] for i in range(0, len(report_text), chunk_size)
    ]

    # Send DM to user
    try:
        for chunk in chunks:
            await ctx.author.send(chunk)
        await ctx.send("✅ Check your DMs for the activity report!")
    except discord.Forbidden:
        await ctx.send("❌ I couldn't DM you. Do you have DMs disabled?")


@tasks.loop(time=time(hour=20, minute=25, tzinfo=MY_TIMEZONE))
async def daily_birthday_check():
    now = datetime.now()

    if (bday := (now.month, now.day)) in BIRTHDAYS:
        user = BIRTHDAYS[bday]

        channel = bot.get_channel(CHANNEL_ID)
        if channel:
            await channel.send(f"Happy Birthday {user[1]}!! <@{user[0]}>")
            await channel.send(random.choice(BIRTHDAY_MESSAGE))
        else:
            print(f"Could not find channel with ID {CHANNEL_ID}")


with open("token.secret") as file:
    TOKEN = file.read().rstrip()

bot.run(TOKEN)
