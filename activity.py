from collections import defaultdict

import discord
import kronicler


@kronicler.capture
async def get_activity(ctx, limit: int):
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
