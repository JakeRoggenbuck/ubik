import discord
from discord.ext import commands


class MyClient(discord.Client):
    async def on_ready(self):
        print('Logged on as', self.user)

    async def on_message(self, message):
        print(message)

        if message.author == self.user:
            return

        if message.content == 'ping':
            await message.channel.send('pong')


intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='>', intents=intents)


@bot.command()
async def ping(ctx):
    await ctx.send('pong')


with open("token.secret") as file:
    TOKEN = file.read().rstrip()

client = MyClient(intents=intents)
client.run(TOKEN)
