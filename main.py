import discord
import os

intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True
intents.members = True
client = discord.Client(intents=intents)

POLES_CHANNEL = "poles🤔"
ANNONCES_CHANNEL = "annonces📣"
REACTION_EMOJI = "okay"
MESSAGE_ID = 1499077252384559145

@client.event
async def on_ready():
    print(f"Bot connecté : {client.user}")

@client.event
async def on_member_join(member):
    role = discord.utils.get(member.guild.roles, name="Membre")
    if role:
        await member.add_roles(role)
        print(f"Rôle Membre ajouté à {member.name}")

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
    if payload.emoji.name != REACTION_EMOJI:
        return
    if payload.message_id != MESSAGE_ID:
        return
    guild = client.get_guild(payload.guild_id)
    member = guild.get_member(payload.user_id)
    role = discord.utils.get(guild.roles, name="poles")
    if member and role:
        await member.add_roles(role)
        print(f"Rôle poles ajouté à {member.name}")

@client.event
async def on_raw_reaction_remove(payload):
    if payload.emoji.name != REACTION_EMOJI:
        return
    if payload.message_id != MESSAGE_ID:
        return
    guild = client.get_guild(payload.guild_id)
    member = guild.get_member(payload.user_id)
    role = discord.utils.get(guild.roles, name="poles")
    if member and role:
        await member.remove_roles(role)
        print(f"Rôle poles retiré de {member.name}")

client.run(os.environ["TOKEN"])
