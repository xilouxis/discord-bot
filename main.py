import discord
import os

intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True
intents.members = True
client = discord.Client(intents=intents)

POLES_CHANNEL = "poles🤔"
ANNONCES_CHANNEL = "annonces📣"
REACTION_EMOJI = "okay"  # Nom de ton emoji custom sans les :

@client.event
async def on_member_join(member):
    role = discord.utils.get(member.guild.roles, name="membre")
    if role:
        await member.add_roles(role)
        print(f"Rôle membre ajouté à {member.name}")

@client.event
async def on_ready():
    print(f"Bot connecté : {client.user}")

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.channel.name != POLES_CHANNEL:
        return

    if message.poll:
        thread = await message.create_thread(name="Discussion du sondage")
        role = discord.utils.get(message.guild.roles, name="poles")
        if role:
            await thread.send(role.mention)
        else:
            await thread.send("@poles")

@client.event
async def on_raw_reaction_add(payload):
    # Vérifie que c'est le bon emoji
    if payload.emoji.name != REACTION_EMOJI:
        return

    guild = client.get_guild(payload.guild_id)
    channel = guild.get_channel(payload.channel_id)

    # Vérifie que c'est dans #annonces
    if channel.name != ANNONCES_CHANNEL:
        return

    # Vérifie que c'est le premier message du channel
    messages = [msg async for msg in channel.history(oldest_first=True, limit=1)]
    if not messages or messages[0].id != payload.message_id:
        return

    # Ajoute le rôle poles
    member = guild.get_member(payload.user_id)
    role = discord.utils.get(guild.roles, name="poles")
    if member and role:
        await member.add_roles(role)
        print(f"Rôle poles ajouté à {member.name}")

@client.event
async def on_raw_reaction_remove(payload):
    # Retire le rôle si la réaction est enlevée
    if payload.emoji.name != REACTION_EMOJI:
        return

    guild = client.get_guild(payload.guild_id)
    channel = guild.get_channel(payload.channel_id)

    if channel.name != ANNONCES_CHANNEL:
        return

    messages = [msg async for msg in channel.history(oldest_first=True, limit=1)]
    if not messages or messages[0].id != payload.message_id:
        return

    member = guild.get_member(payload.user_id)
    role = discord.utils.get(guild.roles, name="poles")
    if member and role:
        await member.remove_roles(role)
        print(f"Rôle poles retiré de {member.name}")

client.run(os.environ["TOKEN"])
