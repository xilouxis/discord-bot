import discord
import os
import random

intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True
intents.members = True

client = discord.Client(intents=intents)
tree = discord.app_commands.CommandTree(client)

POLES_CHANNEL = "poles🤔"
REACTION_EMOJI = "okay"
MESSAGE_ID = 1499077252384559145
ROLE_POLES_ID = 1499196527728398437
ROLE_MEMBRE_ID = 1459044281368182884
LEVEL_UP_CHANNEL_ID = 1458933891112112400

# Blackjack en cours
blackjack_games = {}

def nouvelle_carte():
    cartes = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]
    return random.choice(cartes)

def valeur_main(main):
    total = 0
    as_count = 0
    for carte in main:
        if carte in ["J", "Q", "K"]:
            total += 10
        elif carte == "A":
            total += 11
            as_count += 1
        else:
            total += int(carte)
    while total > 21 and as_count:
        total -= 10
        as_count -= 1
    return total

def afficher_main(main):
    return " | ".join(main)

@client.event
async def on_ready():
    await tree.sync()
    print(f"Bot connecté : {client.user}")

@client.event
async def on_member_join(member):
    role = member.guild.get_role(ROLE_MEMBRE_ID)
    if role:
        await member.add_roles(role)

@client.event
async def on_message(message):
    if message.author == client.user or message.author.bot:
        return
    if message.channel.name == POLES_CHANNEL:
        if message.poll:
            await message.create_thread(name="Discussion du sondage")
            role = message.guild.get_role(ROLE_POLES_ID)
            if role:
                await message.channel.send(role.mention)

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

# 🎰 SLOTS
@tree.command(name="slots", description="Lance les slots !")
async def slots(interaction: discord.Interaction):
    symboles = ["🍒", "🍋", "🍊", "⭐", "💎", "7️⃣"]
    resultat = [random.choice(symboles) for _ in range(3)]
    ligne = " | ".join(resultat)

    if resultat[0] == resultat[1] == resultat[2]:
        if resultat[0] == "💎":
            msg = f"{ligne}\n\n💎 **JACKPOT DIAMANT !** Tu as tout gagné !"
        elif resultat[0] == "7️⃣":
            msg = f"{ligne}\n\n7️⃣ **TRIPLE 7 !** Énorme gain !"
        else:
            msg = f"{ligne}\n\n🎉 **JACKPOT !** Tu as gagné !"
    elif resultat[0] == resultat[1] or resultat[1] == resultat[2]:
        msg = f"{ligne}\n\n✨ Deux identiques, presque !"
    else:
        msg = f"{ligne}\n\n😢 Perdu ! Retente ta chance."

    embed = discord.Embed(title="🎰 Slots", description=msg, color=discord.Color.gold())
    await interaction.response.send_message(embed=embed)

# 🃏 BLACKJACK - Démarrer
@tree.command(name="blackjack", description="Joue au blackjack !")
async def blackjack(interaction: discord.Interaction):
    user_id = interaction.user.id
    if user_id in blackjack_games:
        await interaction.response.send_message("❌ Tu as déjà une partie en cours ! Utilise `/tirer` ou `/rester`.", ephemeral=True)
        return

    main_joueur = [nouvelle_carte(), nouvelle_carte()]
    main_bot = [nouvelle_carte(), nouvelle_carte()]
    blackjack_games[user_id] = {"joueur": main_joueur, "bot": main_bot}

    embed = discord.Embed(title="🃏 Blackjack", color=discord.Color.green())
    embed.add_field(name="Ta main", value=f"{afficher_main(main_joueur)} → **{valeur_main(main_joueur)}**", inline=False)
    embed.add_field(name="Main du croupier", value=f"{main_bot[0]} | ?", inline=False)
    embed.set_footer(text="Utilise /tirer pour une carte ou /rester pour arrêter")
    await interaction.response.send_message(embed=embed)

# 🃏 BLACKJACK - Tirer
@tree.command(name="tirer", description="Tire une carte au blackjack !")
async def tirer(interaction: discord.Interaction):
    user_id = interaction.user.id
    if user_id not in blackjack_games:
        await interaction.response.send_message("❌ Pas de partie en cours ! Utilise `/blackjack`.", ephemeral=True)
        return

    game = blackjack_games[user_id]
    game["joueur"].append(nouvelle_carte())
    total = valeur_main(game["joueur"])

    if total > 21:
        del blackjack_games[user_id]
        embed = discord.Embed(title="🃏 Blackjack - Bust !", color=discord.Color.red())
        embed.add_field(name="Ta main", value=f"{afficher_main(game['joueur'])} → **{total}**", inline=False)
        embed.description = "💥 **Bust ! Tu dépasses 21, tu as perdu !**"
        await interaction.response.send_message(embed=embed)
    else:
        embed = discord.Embed(title="🃏 Blackjack", color=discord.Color.green())
        embed.add_field(name="Ta main", value=f"{afficher_main(game['joueur'])} → **{total}**", inline=False)
        embed.add_field(name="Main du croupier", value=f"{game['bot'][0]} | ?", inline=False)
        embed.set_footer(text="Utilise /tirer pour une carte ou /rester pour arrêter")
        await interaction.response.send_message(embed=embed)

# 🃏 BLACKJACK - Rester
@tree.command(name="rester", description="Reste sur ta main au blackjack !")
async def rester(interaction: discord.Interaction):
    user_id = interaction.user.id
    if user_id not in blackjack_games:
        await interaction.response.send_message("❌ Pas de partie en cours ! Utilise `/blackjack`.", ephemeral=True)
        return

    game = blackjack_games[user_id]
    while valeur_main(game["bot"]) < 17:
        game["bot"].append(nouvelle_carte())

    total_joueur = valeur_main(game["joueur"])
    total_bot = valeur_main(game["bot"])
    del blackjack_games[user_id]

    embed = discord.Embed(title="🃏 Blackjack - Résultat", color=discord.Color.blue())
    embed.add_field(name="Ta main", value=f"{afficher_main(game['joueur'])} → **{total_joueur}**", inline=False)
    embed.add_field(name="Main du croupier", value=f"{afficher_main(game['bot'])} → **{total_bot}**", inline=False)

    if total_bot > 21 or total_joueur > total_bot:
        embed.description = "🎉 **Tu as gagné !**"
        embed.color = discord.Color.green()
    elif total_joueur == total_bot:
        embed.description = "🤝 **Égalité !**"
        embed.color = discord.Color.yellow()
    else:
        embed.description = "😢 **Le croupier gagne !**"
        embed.color = discord.Color.red()

    await interaction.response.send_message(embed=embed)

# ℹ️ HELP
@tree.command(name="help", description="Affiche toutes les commandes du bot !")
async def help(interaction: discord.Interaction):
    embed = discord.Embed(title="📖 Commandes du bot", color=discord.Color.blue())
    embed.add_field(name="/blackjack", value="Démarre une partie de blackjack 🃏", inline=False)
    embed.add_field(name="/tirer", value="Tire une carte au blackjack", inline=False)
    embed.add_field(name="/rester", value="Reste sur ta main au blackjack", inline=False)
    embed.add_field(name="/slots", value="Lance les slots 🎰", inline=False)
    embed.add_field(name="/pileouface", value="Lance une pièce 🪙", inline=False)
    embed.add_field(name="/de [faces]", value="Lance un dé 🎲 (défaut: 6 faces)", inline=False)
    embed.add_field(name="/help", value="Affiche ce message 📖", inline=False)
    await interaction.response.send_message(embed=embed)

@tree.command(name="pileouface", description="Lance une pièce !")
async def pileouface(interaction: discord.Interaction):
    resultat = random.choice(["Pile 🪙", "Face 🪙"])
    await interaction.response.send_message(resultat)

@tree.command(name="de", description="Lance un dé !")
@discord.app_commands.describe(faces="Nombre de faces du dé (défaut: 6)")
async def de(interaction: discord.Interaction, faces: int = 6):
    resultat = random.randint(1, faces)
    await interaction.response.send_message(f"🎲 Tu as obtenu : **{resultat}** (d{faces})")

client.run(os.environ["TOKEN"])
