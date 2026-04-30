import discord
import os
import random
from discord.ui import View, Button

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

blackjack_games = {}
bus_games = {}

COULEURS = ["♠️ Pique", "♥️ Coeur", "♦️ Carreau", "♣️ Trèfle"]

def nouvelle_carte():
    cartes = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]
    return random.choice(cartes)

def nouvelle_carte_complete():
    cartes = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]
    carte = random.choice(cartes)
    couleur = random.choice(COULEURS)
    return carte, couleur

def valeur_carte(carte):
    if carte in ["J", "Q", "K"]:
        return 10
    elif carte == "A":
        return 11
    else:
        return int(carte)

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

def est_haut(carte):
    ordre = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]
    return ordre.index(carte) >= 6

# =================== BLACKJACK ===================

class BlackjackView(View):
    def __init__(self, user_id):
        super().__init__(timeout=60)
        self.user_id = user_id

    @discord.ui.button(label="Hit 🃏", style=discord.ButtonStyle.green)
    async def hit(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ C'est pas ta partie !", ephemeral=True)
            return
        game = blackjack_games[self.user_id]
        game["joueur"].append(nouvelle_carte())
        total = valeur_main(game["joueur"])
        if total > 21:
            del blackjack_games[self.user_id]
            self.stop()
            embed = discord.Embed(title="🃏 Blackjack - Bust !", description="💥 **Tu dépasses 21, tu as perdu !**", color=discord.Color.red())
            embed.add_field(name="Ta main", value=f"{afficher_main(game['joueur'])} → **{total}**", inline=False)
            await interaction.response.edit_message(embed=embed, view=None)
        else:
            embed = discord.Embed(title="🃏 Blackjack", color=discord.Color.green())
            embed.add_field(name="Ta main", value=f"{afficher_main(game['joueur'])} → **{total}**", inline=False)
            embed.add_field(name="Croupier", value=f"{game['bot'][0]} | ?", inline=False)
            await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Stand 🛑", style=discord.ButtonStyle.red)
    async def stand(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ C'est pas ta partie !", ephemeral=True)
            return
        game = blackjack_games[self.user_id]
        while valeur_main(game["bot"]) < 17:
            game["bot"].append(nouvelle_carte())
        total_joueur = valeur_main(game["joueur"])
        total_bot = valeur_main(game["bot"])
        del blackjack_games[self.user_id]
        self.stop()
        embed = discord.Embed(title="🃏 Blackjack - Résultat", color=discord.Color.blue())
        embed.add_field(name="Ta main", value=f"{afficher_main(game['joueur'])} → **{total_joueur}**", inline=False)
        embed.add_field(name="Croupier", value=f"{afficher_main(game['bot'])} → **{total_bot}**", inline=False)
        if total_bot > 21 or total_joueur > total_bot:
            embed.description = "🎉 **Tu as gagné !**"
            embed.color = discord.Color.green()
        elif total_joueur == total_bot:
            embed.description = "🤝 **Égalité !**"
            embed.color = discord.Color.yellow()
        else:
            embed.description = "😢 **Le croupier gagne !**"
            embed.color = discord.Color.red()
        await interaction.response.edit_message(embed=embed, view=None)

    @discord.ui.button(label="Forfait 🏳️", style=discord.ButtonStyle.gray)
    async def forfait(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ C'est pas ta partie !", ephemeral=True)
            return
        if self.user_id in blackjack_games:
            del blackjack_games[self.user_id]
        self.stop()
        embed = discord.Embed(title="🃏 Blackjack - Forfait", description="🏳️ **Tu as abandonné la partie !**", color=discord.Color.gray())
        await interaction.response.edit_message(embed=embed, view=None)

# =================== RIDE THE BUS ===================

class BusEtape1View(View):
    def __init__(self, user_id):
        super().__init__(timeout=60)
        self.user_id = user_id

    @discord.ui.button(label="Rouge ❤️", style=discord.ButtonStyle.red)
    async def rouge(self, interaction: discord.Interaction, button: Button):
        await bus_etape1(interaction, self.user_id, "rouge")

    @discord.ui.button(label="Noir 🖤", style=discord.ButtonStyle.gray)
    async def noir(self, interaction: discord.Interaction, button: Button):
        await bus_etape1(interaction, self.user_id, "noir")

    @discord.ui.button(label="Forfait 🏳️", style=discord.ButtonStyle.gray)
    async def forfait(self, interaction: discord.Interaction, button: Button):
        await bus_forfait(interaction, self.user_id)

class BusEtape2View(View):
    def __init__(self, user_id):
        super().__init__(timeout=60)
        self.user_id = user_id

    @discord.ui.button(label="Plus haut ⬆️", style=discord.ButtonStyle.green)
    async def haut(self, interaction: discord.Interaction, button: Button):
        await bus_etape2(interaction, self.user_id, "haut")

    @discord.ui.button(label="Plus bas ⬇️", style=discord.ButtonStyle.red)
    async def bas(self, interaction: discord.Interaction, button: Button):
        await bus_etape2(interaction, self.user_id, "bas")

    @discord.ui.button(label="Forfait 🏳️", style=discord.ButtonStyle.gray)
    async def forfait(self, interaction: discord.Interaction, button: Button):
        await bus_forfait(interaction, self.user_id)

class BusEtape3View(View):
    def __init__(self, user_id, carte1, carte2):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.carte1 = carte1
        self.carte2 = carte2

    @discord.ui.button(label="Inside 🎯", style=discord.ButtonStyle.green)
    async def inside(self, interaction: discord.Interaction, button: Button):
        await bus_etape3(interaction, self.user_id, "inside")

    @discord.ui.button(label="Outside 💨", style=discord.ButtonStyle.red)
    async def outside(self, interaction: discord.Interaction, button: Button):
        await bus_etape3(interaction, self.user_id, "outside")

    @discord.ui.button(label="Forfait 🏳️", style=discord.ButtonStyle.gray)
    async def forfait(self, interaction: discord.Interaction, button: Button):
        await bus_forfait(interaction, self.user_id)

class BusEtape4View(View):
    def __init__(self, user_id):
        super().__init__(timeout=60)
        self.user_id = user_id

    @discord.ui.button(label="♠️ Pique", style=discord.ButtonStyle.gray)
    async def pique(self, interaction: discord.Interaction, button: Button):
        await bus_etape4(interaction, self.user_id, "♠️ Pique")

    @discord.ui.button(label="♥️ Coeur", style=discord.ButtonStyle.red)
    async def coeur(self, interaction: discord.Interaction, button: Button):
        await bus_etape4(interaction, self.user_id, "♥️ Coeur")

    @discord.ui.button(label="♦️ Carreau", style=discord.ButtonStyle.red)
    async def carreau(self, interaction: discord.Interaction, button: Button):
        await bus_etape4(interaction, self.user_id, "♦️ Carreau")

    @discord.ui.button(label="♣️ Trèfle", style=discord.ButtonStyle.gray)
    async def trefle(self, interaction: discord.Interaction, button: Button):
        await bus_etape4(interaction, self.user_id, "♣️ Trèfle")

    @discord.ui.button(label="Forfait 🏳️", style=discord.ButtonStyle.gray)
    async def forfait(self, interaction: discord.Interaction, button: Button):
        await bus_forfait(interaction, self.user_id)

async def bus_forfait(interaction, user_id):
    if interaction.user.id != user_id:
        await interaction.response.send_message("❌ C'est pas ta partie !", ephemeral=True)
        return
    if user_id in bus_games:
        del bus_games[user_id]
    embed = discord.Embed(title="🚌 Ride the Bus - Forfait", description="🏳️ **Tu as abandonné... tu prends quand même un shot !** 😂", color=discord.Color.gray())
    await interaction.response.edit_message(embed=embed, view=None)

async def bus_etape1(interaction, user_id, choix):
    if interaction.user.id != user_id:
        await interaction.response.send_message("❌ C'est pas ta partie !", ephemeral=True)
        return
    game = bus_games[user_id]
    nouvelle = nouvelle_carte()
    couleur = random.choice(["rouge", "noir"])
    gagne = choix == couleur
    game["cartes"].append(nouvelle)
    if not gagne:
        del bus_games[user_id]
        embed = discord.Embed(title="🚌 Ride the Bus - Perdu !", description=f"La carte était **{nouvelle}** ({couleur})\n\n😢 **Tu prends un shot !**", color=discord.Color.red())
        await interaction.response.edit_message(embed=embed, view=None)
    else:
        bus_games[user_id]["etape"] = 2
        embed = discord.Embed(title="🚌 Ride the Bus", color=discord.Color.purple())
        embed.add_field(name="✅ Bonne réponse !", value=f"La carte était **{nouvelle}** ({couleur})", inline=False)
        embed.add_field(name="Étape 2", value="La prochaine carte sera **plus haute** ou **plus basse** que **{nouvelle}** ?", inline=False)
        await interaction.response.edit_message(embed=embed, view=BusEtape2View(user_id))

async def bus_etape2(interaction, user_id, choix):
    if interaction.user.id != user_id:
        await interaction.response.send_message("❌ C'est pas ta partie !", ephemeral=True)
        return
    game = bus_games[user_id]
    derniere = game["cartes"][-1]
    nouvelle = nouvelle_carte()
    gagne = (choix == "haut" and est_haut(nouvelle)) or (choix == "bas" and not est_haut(nouvelle))
    game["cartes"].append(nouvelle)
    if not gagne:
        del bus_games[user_id]
        embed = discord.Embed(title="🚌 Ride the Bus - Perdu !", description=f"La carte était **{nouvelle}**\n\n😢 **Tu prends un shot !**", color=discord.Color.red())
        await interaction.response.edit_message(embed=embed, view=None)
    else:
        bus_games[user_id]["etape"] = 3
        c1 = game["cartes"][-2]
        c2 = game["cartes"][-1]
        vals = sorted([valeur_carte(c1), valeur_carte(c2)])
        embed = discord.Embed(title="🚌 Ride the Bus", color=discord.Color.purple())
        embed.add_field(name="✅ Bonne réponse !", value=f"La carte était **{nouvelle}**", inline=False)
        embed.add_field(name="Tes 2 dernières cartes", value=f"**{c1}** et **{c2}** (entre {vals[0]} et {vals[1]})", inline=False)
        embed.add_field(name="Étape 3", value="La prochaine carte sera **inside** (entre tes 2 cartes) ou **outside** (en dehors) ?", inline=False)
        await interaction.response.edit_message(embed=embed, view=BusEtape3View(user_id, c1, c2))

async def bus_etape3(interaction, user_id, choix):
    if interaction.user.id != user_id:
        await interaction.response.send_message("❌ C'est pas ta partie !", ephemeral=True)
        return
    game = bus_games[user_id]
    nouvelle = nouvelle_carte()
    vals = sorted([valeur_carte(c) for c in game["cartes"][-2:]])
    val_nouvelle = valeur_carte(nouvelle)
    gagne = (choix == "inside" and vals[0] < val_nouvelle < vals[1]) or \
            (choix == "outside" and (val_nouvelle < vals[0] or val_nouvelle > vals[1]))
    game["cartes"].append(nouvelle)
    if not gagne:
        del bus_games[user_id]
        embed = discord.Embed(title="🚌 Ride the Bus - Perdu !", description=f"La carte était **{nouvelle}** (valeur {val_nouvelle})\n\n😢 **Tu prends un shot !**", color=discord.Color.red())
        await interaction.response.edit_message(embed=embed, view=None)
    else:
        bus_games[user_id]["etape"] = 4
        embed = discord.Embed(title="🚌 Ride the Bus", color=discord.Color.purple())
        embed.add_field(name="✅ Bonne réponse !", value=f"La carte était **{nouvelle}**", inline=False)
        embed.add_field(name="Étape 4 - Dernière chance !", value="Devine la **couleur** de la prochaine carte !", inline=False)
        await interaction.response.edit_message(embed=embed, view=BusEtape4View(user_id))

async def bus_etape4(interaction, user_id, choix):
    if interaction.user.id != user_id:
        await interaction.response.send_message("❌ C'est pas ta partie !", ephemeral=True)
        return
    carte, couleur = nouvelle_carte_complete()
    gagne = choix == couleur
    del bus_games[user_id]
    if not gagne:
        embed = discord.Embed(title="🚌 Ride the Bus - Perdu !", description=f"La carte était **{carte} {couleur}**\n\n😢 **Tu prends un shot !**", color=discord.Color.red())
    else:
        embed = discord.Embed(title="🚌 Ride the Bus - Gagné !", description=f"La carte était **{carte} {couleur}**\n\n🎉 **Tu as survécu au bus !**", color=discord.Color.green())
    await interaction.response.edit_message(embed=embed, view=None)

# =================== COMMANDES ===================

@tree.command(name="blackjack", description="Joue au blackjack !")
async def blackjack(interaction: discord.Interaction):
    user_id = interaction.user.id
    if user_id in blackjack_games:
        await interaction.response.send_message("❌ Partie en cours !", ephemeral=True)
        return
    main_joueur = [nouvelle_carte(), nouvelle_carte()]
    main_bot = [nouvelle_carte(), nouvelle_carte()]
    blackjack_games[user_id] = {"joueur": main_joueur, "bot": main_bot}
    embed = discord.Embed(title="🃏 Blackjack", color=discord.Color.green())
    embed.add_field(name="Ta main", value=f"{afficher_main(main_joueur)} → **{valeur_main(main_joueur)}**", inline=False)
    embed.add_field(name="Croupier", value=f"{main_bot[0]} | ?", inline=False)
    await interaction.response.send_message(embed=embed, view=BlackjackView(user_id))

@tree.command(name="ridethebus", description="Joue à Ride the Bus !")
async def ridethebus(interaction: discord.Interaction):
    user_id = interaction.user.id
    carte = nouvelle_carte()
    bus_games[user_id] = {"carte": carte, "etape": 1, "cartes": [carte]}
    embed = discord.Embed(title="🚌 Ride the Bus", color=discord.Color.purple())
    embed.add_field(name="Ta carte de départ", value=f"**{carte}**", inline=False)
    embed.add_field(name="Étape 1", value="La prochaine carte sera **Rouge** ❤️ ou **Noir** 🖤 ?", inline=False)
    await interaction.response.send_message(embed=embed, view=BusEtape1View(user_id))

@tree.command(name="slots", description="Lance les slots !")
async def slots(interaction: discord.Interaction):
    symboles = ["🍒", "🍋", "🍊", "⭐", "💎", "7️⃣"]
    resultat = [random.choice(symboles) for _ in range(3)]
    ligne = " | ".join(resultat)
    if resultat[0] == resultat[1] == resultat[2]:
        if resultat[0] == "💎":
            msg = f"{ligne}\n\n💎 **JACKPOT DIAMANT !**"
        elif resultat[0] == "7️⃣":
            msg = f"{ligne}\n\n7️⃣ **TRIPLE 7 !**"
        else:
            msg = f"{ligne}\n\n🎉 **JACKPOT !**"
    elif resultat[0] == resultat[1] or resultat[1] == resultat[2]:
        msg = f"{ligne}\n\n✨ Deux identiques, presque !"
    else:
        msg = f"{ligne}\n\n😢 Perdu !"
    embed = discord.Embed(title="🎰 Slots", description=msg, color=discord.Color.gold())
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

@tree.command(name="help", description="Affiche toutes les commandes du bot !")
async def help(interaction: discord.Interaction):
    embed = discord.Embed(title="📖 Commandes du bot", color=discord.Color.blue())
    embed.add_field(name="🃏 /blackjack", value="Joue au blackjack (Hit/Stand/Forfait)", inline=False)
    embed.add_field(name="🚌 /ridethebus", value="Joue à Ride the Bus en 4 étapes", inline=False)
    embed.add_field(name="🎰 /slots", value="Lance les slots", inline=False)
    embed.add_field(name="🪙 /pileouface", value="Lance une pièce", inline=False)
    embed.add_field(name="🎲 /de [faces]", value="Lance un dé", inline=False)
    await interaction.response.send_message(embed=embed)

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

client.run(os.environ["TOKEN"])
