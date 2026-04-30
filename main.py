import discord

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

CHANNEL_NAME = "poles🤔"  # Nom de ton salon

@client.event
async def on_ready():
    print(f"Bot connecté : {client.user}")

@client.event
async def on_message(message):
    # Ignore les messages du bot lui-même
    if message.author == client.user:
        return

    # Vérifie que c'est dans le bon salon
    if message.channel.name != CHANNEL_NAME:
        return

    # Vérifie que c'est un sondage natif Discord
    if message.poll:
        # Crée un thread sous le sondage
        thread = await message.create_thread(name="Discussion du sondage")
        # Écrit @poles dans le thread
        role = discord.utils.get(message.guild.roles, name="poles")
        if role:
            await thread.send(role.mention)
        else:
            await thread.send("@poles")  # Fallback si le rôle n'existe pas

client.run("MTQ5OTIwMTgyNTY3OTg3MjA5Mg.G0jHZ0.wdhrfSf_sNCMqmxogQwlfNuBvIaNUrOMmgTVrQ")  # Remplace par ton token
