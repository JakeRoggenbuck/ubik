import discord
from discord.ext import commands
from pathlib import Path
import tomllib
import kronicler
import activity
import birthday
import kronicler_report
import subprocess


BOT_CONFIG_PATH = Path("bot.toml")

DB = kronicler.Database(sync_consume=True)


@kronicler.capture
def load_bot_config(path: Path) -> dict:
    return tomllib.loads(path.read_text(encoding="utf-8"))


if not BOT_CONFIG_PATH.exists():
    raise FileNotFoundError(f"The file {BOT_CONFIG_PATH} not found.")

BOT_CONFIG = load_bot_config(BOT_CONFIG_PATH)

CHANNEL_ID = int(BOT_CONFIG["channel_id"])

if "token" in BOT_CONFIG:
    TOKEN = str(BOT_CONFIG["token"]).strip()
elif "token_secret" in BOT_CONFIG:
    token_path = Path(str(BOT_CONFIG["token_secret"]))
    TOKEN = token_path.read_text(encoding="utf-8").rstrip()
else:
    raise KeyError(
        "Missing token configuration; set 'token' or 'token_secret' in bot.toml."
    )


intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guild_messages = True

bot = commands.Bot(command_prefix=">", intents=intents)

daily_birthday_check = birthday.create_daily_birthday_check(bot, CHANNEL_ID)


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    daily_birthday_check.start()


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
    """Use the >ping command to see if Ubik is working..."""
    await ctx.send("pong")


@bot.command()
async def activity(ctx, limit: int = 1000):
    """See how much activity each person has on a server by message count."""
    await activity.get_activity(ctx, limit)


@bot.command()
async def birthdays(ctx):
    """List everyone's birthday"""
    birthdays = birthday.load_birthdays(birthday.BIRTHDAYS_PATH)
    await ctx.send(birthday.format_birthdays(birthdays))


@bot.command()
async def kronicler(ctx):
    """Show the kronicler data"""
    await kronicler_report.send_runtime_plot(ctx, DB)


@bot.command()
async def commit(ctx):
    """Show the latest commit hash and commit date."""
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%h %cd", "--date=short"],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError:
        await ctx.send("Unable to read the latest commit hash.")
        return

    await ctx.send(result.stdout.strip())


bot.run(TOKEN)
