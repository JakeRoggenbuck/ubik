import discord
from discord.ext import commands
from datetime import datetime, timezone
from collections import defaultdict


class MyClient(discord.Client):
    async def on_ready(self):
        print("Logged on as", self.user)

    async def on_message(self, message):
        print(message)

        if message.author == self.user:
            return

        if message.content == "ping":
            await message.channel.send("pong")


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


intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guild_messages = True

bot = commands.Bot(command_prefix=">", intents=intents)


@bot.command()
async def ping(ctx):
    await ctx.send("pong")


@bot.command()
async def activity(ctx, limit: int = 1000):
    """
    DM the requesting user a list of all users, their last message time, and total messages.
    limit: how many messages per channel to scan (default 1000)
    """
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
                if message.author.id not in last_messages or message.created_at > last_messages[message.author.id]:
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
            time_since_last = discord.utils.format_dt(last_msg_time, style='R')  # Relative time
        else:
            time_since_last = "No messages found"
        report_lines.append(f"{member.name}#{member.discriminator}: Last message {time_since_last}, Total messages: {total_msgs}")

    # Split into chunks if too long
    chunk_size = 2000
    report_text = "\n".join(report_lines)
    chunks = [report_text[i:i+chunk_size] for i in range(0, len(report_text), chunk_size)]

    # Send DM to user
    try:
        for chunk in chunks:
            await ctx.author.send(chunk)
        await ctx.send("✅ Check your DMs for the activity report!")
    except discord.Forbidden:
        await ctx.send("❌ I couldn't DM you. Do you have DMs disabled?")


with open("token.secret") as file:
    TOKEN = file.read().rstrip()

# client = MyClient(intents=intents)
# client.run(TOKEN)

bot.run(TOKEN)
