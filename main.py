import discord
from discord.ext import commands
from datetime import datetime, timezone


class MyClient(discord.Client):
    async def on_ready(self):
        print('Logged on as', self.user)

    async def on_message(self, message):
        print(message)

        if message.author == self.user:
            return

        if message.content == 'ping':
            await message.channel.send('pong')


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

bot = commands.Bot(command_prefix='>', intents=intents)


@bot.command()
async def ping(ctx):
    await ctx.send('pong')


@bot.command()
async def activity(ctx):
    await ctx.send("Scanning message history. This may take a moment...")

    last_message = {}   # user_id -> datetime
    message_count = {}  # user_id -> int

    for channel in ctx.guild.text_channels:
        try:
            async for msg in channel.history(limit=None, oldest_first=False):
                if msg.author.bot:
                    continue

                uid = msg.author.id
                ts = msg.created_at

                # update last message time
                if uid not in last_message or ts > last_message[uid]:
                    last_message[uid] = ts

                # increment message count
                message_count[uid] = message_count.get(uid, 0) + 1

        except discord.Forbidden:
            # bot can't read this channel
            continue

    # Build output for all members
    rows = []
    now = datetime.now(timezone.utc)

    for member in ctx.guild.members:
        if member.bot:
            continue

        last = last_message.get(member.id)
        count = message_count.get(member.id, 0)

        if last:
            ago = now - last
            ago_str = format_timedelta(ago)
        else:
            ago_str = "No messages found"

        rows.append((member.display_name, ago_str, count, last or datetime.fromtimestamp(0, tz=timezone.utc)))

    # Sort by last activity (most recent first)
    rows.sort(key=lambda x: x[3], reverse=True)

    # Build readable output
    result_lines = [
        f"{name}: Last message {ago}, Total messages {count}"
        for name, ago, count, _ in rows
    ]

    # Discord messages have a 2000-character limit — chunk it
    chunk = ""
    for line in result_lines:
        if len(chunk) + len(line) + 1 > 1990:
            await ctx.send(f"```{chunk}```")
            chunk = ""
        chunk += line + "\n"

    if chunk:
        await ctx.send(f"```{chunk}```")


with open("token.secret") as file:
    TOKEN = file.read().rstrip()

client = MyClient(intents=intents)
client.run(TOKEN)
