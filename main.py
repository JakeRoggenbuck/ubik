import discord
from discord import app_commands
from discord.ext import commands
from pathlib import Path
import tomllib
import kronicler
import subprocess
import sys
import hy

import activities
import birthday
import kronicler_report
import bowling
import antispam
import latex
import notifications
import pinger
import hyeval
import audit_log


BOT_CONFIG_PATH = Path("bot.toml")

DB = kronicler.Database(sync_consume=True)

print(antispam.classify_message("a"))

@kronicler.capture
def load_bot_config(path: Path) -> dict:
    return tomllib.loads(path.read_text(encoding="utf-8"))


if not BOT_CONFIG_PATH.exists():
    raise FileNotFoundError(f"The file {BOT_CONFIG_PATH} not found.")

BOT_CONFIG = load_bot_config(BOT_CONFIG_PATH)

CHANNEL_ID = int(BOT_CONFIG["channel_id"])
INVITE_LINK = str(BOT_CONFIG.get("invite_link", "")).strip()
ADMIN_ID = int(BOT_CONFIG.get("admin_id", 0))
RESTART_EXIT_CODE = 42

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
intents.presences = True  # needed to resolve @here (member online status)

bot = commands.Bot(command_prefix=">", intents=intents)


@bot.tree.command(name="ping", description="Ping members using a set-algebra expression")
@app_commands.describe(
    expression="Set expression over roles/users, e.g. @here & Rusty Minecraft",
    message="Message to send with the ping",
)
async def slash_ping(interaction: discord.Interaction, expression: str, message: str):
    await pinger.handle_slash_ping(interaction, expression, message)


@slash_ping.autocomplete("expression")
async def ping_expression_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[str]]:
    return pinger.get_autocomplete_choices(interaction.guild, current)


@bot.event
async def setup_hook():
    await bot.add_cog(bowling.Bowling(bot))
    await bot.tree.sync()

daily_birthday_check = birthday.create_daily_birthday_check(bot, CHANNEL_ID)
daily_notification_check = notifications.create_daily_notification_check(bot)


@bot.event
async def on_message_delete(message: discord.Message):
    await audit_log.on_message_delete(message)


@bot.event
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
    if str(payload.emoji) != "👍":
        return
    url = notifications._PENDING_LINKS.get(payload.message_id)
    if url is None:
        return
    if payload.user_id == bot.user.id:
        return
    try:
        user = await bot.fetch_user(payload.user_id)
        await user.send(url)
    except Exception as exc:
        print(f"Failed to DM link to {payload.user_id}: {exc}")


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    await bot.change_presence(activity=discord.Game("Hey! Use '/ping'"))
    if not daily_birthday_check.is_running():
        daily_birthday_check.start()
    if not daily_notification_check.is_running():
        daily_notification_check.start()


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
async def activity(ctx, limit: int = 1000):
    """See how much activity each person has on a server by message count."""
    await activities.get_activity(ctx, limit)


@bot.command()
async def birthdays(ctx):
    """List everyone's birthday"""
    if ctx.channel.id != CHANNEL_ID:
        await ctx.send("This channel does not have permission for it.")
        return
    birthdays = birthday.load_birthdays(birthday.BIRTHDAYS_PATH)
    await ctx.send(birthday.format_birthdays(birthdays))


@bot.group(name="notify", invoke_without_command=True)
async def notify_group(ctx):
    """Notification stream utilities."""
    await ctx.send(
        "Use `>notify list`, `>notify signup <stream> [dm|channel]`, "
        "`>notify unsubscribe <stream>`, or `>notify run`."
    )


@notify_group.command(name="list")
async def notify_list(ctx):
    """List available notification streams."""
    names = notifications.list_stream_names(notifications.NOTIFICATION_STREAMS_PATH)
    if not names:
        await ctx.send("No notification streams are configured.")
        return

    await ctx.send("\n".join(["Notification streams:", "```", *names, "```"]))


@notify_group.command(name="signup")
async def notify_signup(ctx, stream: str, delivery: str = "dm"):
    """Sign up for a notification stream."""
    channel_id = ctx.channel.id if delivery.strip().lower() == "channel" else None
    ok, message = await notifications.subscribe(
        notifications.NOTIFICATION_STREAMS_PATH,
        stream,
        ctx.author.id,
        delivery,
        channel_id,
    )
    await ctx.send(message)
    if ok and delivery.strip().lower() == "dm":
        await ctx.send("You will receive notifications in DMs.")
    elif ok:
        await ctx.send(f"You will receive notifications in <#{ctx.channel.id}>.")


@notify_group.command(name="unsubscribe")
async def notify_unsubscribe(ctx, stream: str):
    """Remove your notification stream subscription."""
    _, message = await notifications.unsubscribe(
        notifications.NOTIFICATION_STREAMS_PATH,
        stream,
        ctx.author.id,
    )
    await ctx.send(message)


@notify_group.command(name="post")
async def notify_post(ctx, stream: str, url: str):
    """Send a URL as a manual event to a stream. Admin only."""
    if ADMIN_ID == 0 or ctx.author.id != ADMIN_ID:
        await ctx.send("You are not authorized to run this command.")
        return

    await ctx.send(f"Fetching `{url}` and sending to `{stream}`...")
    found, err, sent = await notifications.send_url_to_stream(
        bot, notifications.NOTIFICATION_STREAMS_PATH, stream, url
    )
    if not found:
        await ctx.send(err)
    elif sent == 0:
        await ctx.send("No subscribers on that stream.")
    else:
        await ctx.send(f"Sent to {sent} subscriber(s).")


@notify_group.command(name="run")
async def notify_run(ctx):
    """Manually run all notification streams once."""
    sent = await notifications.dispatch_notifications(
        bot, notifications.NOTIFICATION_STREAMS_PATH
    )
    if not sent:
        await ctx.send("No streams were processed.")
        return

    lines = ["Notification run complete:", "```"]
    for stream, count in sorted(sent.items()):
        lines.append(f"{stream}: {count} sent")
    lines.append("```")
    await ctx.send("\n".join(lines))


@bot.group(name="birthday", invoke_without_command=True)
async def birthday_group(ctx):
    """Birthday utilities."""
    await ctx.send("Use `>birthday channel check` to verify the announcements channel.")


@birthday_group.group(name="channel", invoke_without_command=True)
async def birthday_channel(ctx):
    """Birthday channel utilities."""
    await ctx.send("Use `>birthday channel check` to verify the announcements channel.")


@birthday_channel.command(name="check")
async def birthday_channel_check(ctx):
    """Send a test message to the birthday announcements channel."""
    if not await birthday.send_birthday_channel_check(bot, CHANNEL_ID):
        await ctx.send("Unable to find the birthday announcements channel.")


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


@bot.command(name="latex")
async def latex_command(ctx, *, expression: str = ""):
    """Render a LaTeX expression as an image. Usage: >latex e^{i\\pi} + 1 = 0"""
    await latex.send_latex(ctx, expression)


@bot.command()
async def update(ctx):
    """Pull the latest code and restart the bot. Admin only."""
    if ADMIN_ID == 0 or ctx.author.id != ADMIN_ID:
        await ctx.send("You are not authorized to run this command.")
        return

    try:
        result = subprocess.run(
            ["git", "pull"],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        await ctx.send(f"git pull failed:\n```\n{exc.stderr.strip() or exc.stdout.strip()}\n```")
        return

    await ctx.send(f"```\n{result.stdout.strip()}\n```\nRestarting...")
    await bot.close()
    sys.exit(RESTART_EXIT_CODE)


@bot.command(name="eval")
async def eval_command(ctx, *, source: str = ""):
    """Evaluate Hy (Lisp) code and reply with the result. Admin only."""
    await hyeval.handle_eval(ctx, ADMIN_ID, source)


@bot.command(name="auditlog", hidden=True)
async def auditlog_command(ctx, *, keyword: str = ""):
    """View the audit log. Admin only. Optionally filter by keyword."""
    if ADMIN_ID == 0 or ctx.author.id != ADMIN_ID:
        await ctx.send("You are not authorized to run this command.")
        return
    await ctx.send(audit_log.read_audit_log(keyword.strip() or None))


@bot.command()
async def source(ctx):
    """Show the GitHub repository link."""
    await ctx.send("https://github.com/JakeRoggenbuck/ubik")


@bot.command()
async def link(ctx):
    """Share the bot invite link."""
    if not INVITE_LINK:
        await ctx.send("Invite link is not configured.")
        return

    await ctx.send("Invite Ubik to a server using the link: " + INVITE_LINK)


bot.run(TOKEN)
