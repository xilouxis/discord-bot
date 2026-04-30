import discord
import os

intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True
intents.members = True
client = discord.Client(intents=intents)

POLES_CHANNEL = "poles🤔"
REACTION_EMOJI = "okay"
MESSAGE_ID = 1499077252384559145
ROLE_POLES_ID = 1499196527728398437
ROLE_MEMBRE_ID = 1459044281368182884

@client.event
async def on_ready():
    print(f"Bot connecté : {client.user}")

@client.event
async def on_member_join(member):
    role = member.guild.get_role(ROLE_MEMBRE_ID)
    if role:
        await member.add_roles(role)
        print(f"Rôle membre ajouté à {member.name}")

@client.event
async def on_message(message):
    if message.author == client.user:
        return
    if message.channel.name != POLES_CHANNEL:
        return
    if message.poll:
        thread = await message.create_thread(name="Discussion du sondage")
        role = message.guild.get_role(ROLE_POLES_ID)
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
    role = guild.get_role(ROLE_POLES_ID)
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
    role = guild.get_role(ROLE_POLES_ID)
    if member and role:
        await member.remove_roles(role)
        print(f"Rôle poles retiré de {member.name}")

client.run(os.environ["TOKEN"])
