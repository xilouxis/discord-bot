import discord
import os
import random
import aiohttp
import sqlite3
import secrets
from discord.ui import View, Button
from dotenv import load_dotenv

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True
intents.members = True

client = discord.Client(intents=intents)
tree = discord.app_commands.CommandTree(client)

POLES_CHANNEL = "poles🤔"
REACTION_EMOJI = "okay"
MESSAGE_ID_POLES = 1499077252384559145
MESSAGE_ID_2 = 1499587568856203295
ROLE_POLES_ID = 1499196527728398437
ROLE_MEMBRE_ID = 1459044281368182884
ROLE_2_ID = 1499581112983359549

blackjack_games = {}
blackjack_multi_games = {}
bus_games = {}
roulette_games = {}

# =================== BASE DE DONNÉES ===================

conn = sqlite3.connect("bank.db")
cursor = conn.cursor()
cursor.execute("""
    CREATE TABLE IF NOT EXISTS bank (
        user_id TEXT PRIMARY KEY,
        solde INTEGER DEFAULT 0
    )
""")
conn.commit()

def get_solde(user_id):
    cursor.execute("SELECT solde FROM bank WHERE user_id = ?", (str(user_id),))
    row = cursor.fetchone()
    if not row:
        cursor.execute("INSERT INTO bank (user_id, solde) VALUES (?, 0)", (str(user_id),))
        conn.commit()
        return 0
    return row[0]

def set_solde(user_id, montant):
    cursor.execute("INSERT OR REPLACE INTO bank (user_id, solde) VALUES (?, ?)", (str(user_id), montant))
    conn.commit()

def add_solde(user_id, montant):
    solde = get_solde(user_id)
    set_solde(user_id, solde + montant)

# =================== CARTES ===================

def nouvelle_carte():
    cartes = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]
    return cartes[secrets.randbelow(len(cartes))]

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

def resultat_bj(total_joueur, total_bot, mise, user_id):
    if total_bot > 21 or total_joueur > total_bot:
        add_solde(user_id, mise * 2)
        return f"🎉 Gagné ! +${mise}", discord.Color.green()
    elif total_joueur == total_bot:
        add_solde(user_id, mise)
        return f"🤝 Égalité ! Mise remboursée.", discord.Color.yellow()
    else:
        return f"😢 Perdu ! -${mise}", discord.Color.red()

# =================== BLACKJACK SOLO ===================

class BlackjackView(View):
    def __init__(self, user_id, mise):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.mise = mise

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
            embed = discord.Embed(title="🃏 Blackjack - Perdu !", description=f"💥 Bust ! Tu perds **${self.mise}**", color=discord.Color.red())
            embed.add_field(name="Ta main", value=f"{afficher_main(game['joueur'])} → **{total}**", inline=False)
            embed.add_field(name="💰 Solde", value=f"${get_solde(self.user_id)}", inline=False)
            await interaction.response.edit_message(embed=embed, view=None)
        else:
            embed = discord.Embed(title="🃏 Blackjack", color=discord.Color.green())
            embed.add_field(name="Ta main", value=f"{afficher_main(game['joueur'])} → **{total}**", inline=False)
            embed.add_field(name="Croupier", value=f"{game['bot'][0]} | ?", inline=False)
            embed.add_field(name="💰 Mise", value=f"${self.mise}", inline=False)
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
        msg, color = resultat_bj(total_joueur, total_bot, self.mise, self.user_id)
        embed = discord.Embed(title="🃏 Blackjack - Résultat", description=msg, color=color)
        embed.add_field(name="Ta main", value=f"{afficher_main(game['joueur'])} → **{total_joueur}**", inline=False)
        embed.add_field(name="Croupier", value=f"{afficher_main(game['bot'])} → **{total_bot}**", inline=False)
        embed.add_field(name="💰 Solde", value=f"${get_solde(self.user_id)}", inline=False)
        await interaction.response.edit_message(embed=embed, view=None)

# =================== BLACKJACK MULTIJOUEUR ===================

class BlackjackMultiView(View):
    def __init__(self, game_id):
        super().__init__(timeout=120)
        self.game_id = game_id

    async def update_embed(self, interaction):
        game = blackjack_multi_games[self.game_id]
        embed = discord.Embed(title="🃏 Blackjack Multijoueur", color=discord.Color.green())
        for uid, data in game["joueurs"].items():
            member = interaction.guild.get_member(uid)
            name = member.display_name if member else str(uid)
            status = "✅ Stand" if data["stand"] else "🎮 En jeu"
            bust = " 💥 Bust!" if valeur_main(data["main"]) > 21 else ""
            embed.add_field(
                name=f"{name} (Mise: ${data['mise']}) {status}{bust}",
                value=f"{afficher_main(data['main'])} → **{valeur_main(data['main'])}**",
                inline=False
            )
        embed.add_field(name="Croupier", value=f"{game['bot'][0]} | ?", inline=False)
        return embed

    @discord.ui.button(label="Hit 🃏", style=discord.ButtonStyle.green)
    async def hit(self, interaction: discord.Interaction, button: Button):
        game = blackjack_multi_games.get(self.game_id)
        if not game:
            await interaction.response.send_message("❌ Partie introuvable !", ephemeral=True)
            return
        user_id = interaction.user.id
        if user_id not in game["joueurs"]:
            await interaction.response.send_message("❌ Tu n'es pas dans cette partie !", ephemeral=True)
            return
        if game["joueurs"][user_id]["stand"]:
            await interaction.response.send_message("❌ Tu as déjà stand !", ephemeral=True)
            return
        game["joueurs"][user_id]["main"].append(nouvelle_carte())
        total = valeur_main(game["joueurs"][user_id]["main"])
        if total > 21:
            game["joueurs"][user_id]["stand"] = True
        embed = await self.update_embed(interaction)
        tous_finis = all(d["stand"] or valeur_main(d["main"]) > 21 for d in game["joueurs"].values())
        if tous_finis:
            await self.finir_partie(interaction, embed)
        else:
            await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Stand 🛑", style=discord.ButtonStyle.red)
    async def stand(self, interaction: discord.Interaction, button: Button):
        game = blackjack_multi_games.get(self.game_id)
        if not game:
            await interaction.response.send_message("❌ Partie introuvable !", ephemeral=True)
            return
        user_id = interaction.user.id
        if user_id not in game["joueurs"]:
            await interaction.response.send_message("❌ Tu n'es pas dans cette partie !", ephemeral=True)
            return
        if game["joueurs"][user_id]["stand"]:
            await interaction.response.send_message("❌ Tu as déjà stand !", ephemeral=True)
            return
        game["joueurs"][user_id]["stand"] = True
        embed = await self.update_embed(interaction)
        tous_finis = all(d["stand"] for d in game["joueurs"].values())
        if tous_finis:
            await self.finir_partie(interaction, embed)
        else:
            await interaction.response.edit_message(embed=embed, view=self)

    async def finir_partie(self, interaction, embed):
        game = blackjack_multi_games[self.game_id]
        while valeur_main(game["bot"]) < 17:
            game["bot"].append(nouvelle_carte())
        total_bot = valeur_main(game["bot"])
        embed = discord.Embed(title="🃏 Blackjack Multijoueur - Résultat", color=discord.Color.blue())
        embed.add_field(name="Croupier", value=f"{afficher_main(game['bot'])} → **{total_bot}**", inline=False)
        for uid, data in game["joueurs"].items():
            member = interaction.guild.get_member(uid)
            name = member.display_name if member else str(uid)
            total_joueur = valeur_main(data["main"])
            msg, _ = resultat_bj(total_joueur, total_bot, data["mise"], uid)
            embed.add_field(
                name=f"{name}",
                value=f"{afficher_main(data['main'])} → **{total_joueur}**\n{msg}\n💰 Solde: ${get_solde(uid)}",
                inline=False
            )
        del blackjack_multi_games[self.game_id]
        self.stop()
        await interaction.response.edit_message(embed=embed, view=None)

class JoinBlackjackView(View):
    def __init__(self, game_id, host_id, mise):
        super().__init__(timeout=30)
        self.game_id = game_id
        self.host_id = host_id
        self.mise = mise

    @discord.ui.button(label="Rejoindre !", style=discord.ButtonStyle.green)
    async def rejoindre(self, interaction: discord.Interaction, button: Button):
        game = blackjack_multi_games.get(self.game_id)
        if not game:
            await interaction.response.send_message("❌ Partie introuvable !", ephemeral=True)
            return
        user_id = interaction.user.id
        if user_id in game["joueurs"]:
            await interaction.response.send_message("❌ Tu es déjà dans la partie !", ephemeral=True)
            return
        solde = get_solde(user_id)
        if solde < self.mise:
            await interaction.response.send_message(f"❌ Pas assez d'argent ! Solde: ${solde}", ephemeral=True)
            return
        add_solde(user_id, -self.mise)
        game["joueurs"][user_id] = {"main": [nouvelle_carte(), nouvelle_carte()], "stand": False, "mise": self.mise}
        self.stop()
        embed = discord.Embed(title="🃏 Blackjack Multijoueur", description="La partie commence !", color=discord.Color.green())
        for uid, data in game["joueurs"].items():
            member = interaction.guild.get_member(uid)
            name = member.display_name if member else str(uid)
            embed.add_field(name=f"{name} (Mise: ${data['mise']})", value=f"{afficher_main(data['main'])} → **{valeur_main(data['main'])}**", inline=False)
        embed.add_field(name="Croupier", value=f"{game['bot'][0]} | ?", inline=False)
        await interaction.response.edit_message(embed=embed, view=BlackjackMultiView(self.game_id))

# =================== RIDE THE BUS ===================

COULEURS_BUS = ["♠️ Pique", "♥️ Coeur", "♦️ Carreau", "♣️ Trèfle"]

def nouvelle_carte_complete():
    cartes = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]
    carte = cartes[secrets.randbelow(len(cartes))]
    couleur = COULEURS_BUS[secrets.randbelow(len(COULEURS_BUS))]
    return carte, couleur

def valeur_carte(carte):
    if carte in ["J", "Q", "K"]:
        return 10
    elif carte == "A":
        return 11
    else:
        return int(carte)

def est_haut(carte):
    ordre = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]
    return ordre.index(carte) >= 6

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

    @discord.ui.button(label="Cash Out 💵", style=discord.ButtonStyle.green)
    async def cashout(self, interaction: discord.Interaction, button: Button):
        await bus_cashout(interaction, self.user_id)

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

    @discord.ui.button(label="Cash Out 💵", style=discord.ButtonStyle.green)
    async def cashout(self, interaction: discord.Interaction, button: Button):
        await bus_cashout(interaction, self.user_id)

class BusEtape3View(View):
    def __init__(self, user_id):
        super().__init__(timeout=60)
        self.user_id = user_id

    @discord.ui.button(label="Inside 🎯", style=discord.ButtonStyle.green)
    async def inside(self, interaction: discord.Interaction, button: Button):
        await bus_etape3(interaction, self.user_id, "inside")

    @discord.ui.button(label="Outside 💨", style=discord.ButtonStyle.red)
    async def outside(self, interaction: discord.Interaction, button: Button):
        await bus_etape3(interaction, self.user_id, "outside")

    @discord.ui.button(label="Cash Out 💵", style=discord.ButtonStyle.green)
    async def cashout(self, interaction: discord.Interaction, button: Button):
        await bus_cashout(interaction, self.user_id)

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

    @discord.ui.button(label="Cash Out 💵", style=discord.ButtonStyle.green)
    async def cashout(self, interaction: discord.Interaction, button: Button):
        await bus_cashout(interaction, self.user_id)

async def bus_cashout(interaction, user_id):
    if interaction.user.id != user_id:
        await interaction.response.send_message("❌ C'est pas ta partie !", ephemeral=True)
        return
    game = bus_games[user_id]
    gains = game["gains"]
    add_solde(user_id, gains)
    del bus_games[user_id]
    embed = discord.Embed(title="🚌 Ride the Bus - Cash Out !", description=f"💵 **Tu repars avec ${gains} !**", color=discord.Color.green())
    embed.add_field(name="💰 Solde", value=f"${get_solde(user_id)}", inline=False)
    await interaction.response.edit_message(embed=embed, view=None)

async def bus_etape1(interaction, user_id, choix):
    if interaction.user.id != user_id:
        await interaction.response.send_message("❌ C'est pas ta partie !", ephemeral=True)
        return
    game = bus_games[user_id]
    nouvelle = nouvelle_carte()
    couleur = ["rouge", "noir"][secrets.randbelow(2)]
    gagne = choix == couleur
    game["cartes"].append(nouvelle)
    if not gagne:
        del bus_games[user_id]
        embed = discord.Embed(title="🚌 Ride the Bus - Perdu !", description=f"La carte était **{nouvelle}** ({couleur})\n\n😢 **Tu perds ta mise !**", color=discord.Color.red())
        embed.add_field(name="💰 Solde", value=f"${get_solde(user_id)}", inline=False)
        await interaction.response.edit_message(embed=embed, view=None)
    else:
        game["gains"] = int(game["gains"] * 1.5)
        bus_games[user_id]["etape"] = 2
        embed = discord.Embed(title="🚌 Ride the Bus", color=discord.Color.purple())
        embed.add_field(name="✅ Bonne réponse !", value=f"La carte était **{nouvelle}** ({couleur})", inline=False)
        embed.add_field(name="💰 Gains actuels", value=f"${game['gains']}", inline=False)
        embed.add_field(name="Étape 2", value=f"La prochaine carte sera **plus haute** ou **plus basse** que **{nouvelle}** ?", inline=False)
        await interaction.response.edit_message(embed=embed, view=BusEtape2View(user_id))

async def bus_etape2(interaction, user_id, choix):
    if interaction.user.id != user_id:
        await interaction.response.send_message("❌ C'est pas ta partie !", ephemeral=True)
        return
    game = bus_games[user_id]
    nouvelle = nouvelle_carte()
    gagne = (choix == "haut" and est_haut(nouvelle)) or (choix == "bas" and not est_haut(nouvelle))
    game["cartes"].append(nouvelle)
    if not gagne:
        del bus_games[user_id]
        embed = discord.Embed(title="🚌 Ride the Bus - Perdu !", description=f"La carte était **{nouvelle}**\n\n😢 **Tu perds ta mise !**", color=discord.Color.red())
        embed.add_field(name="💰 Solde", value=f"${get_solde(user_id)}", inline=False)
        await interaction.response.edit_message(embed=embed, view=None)
    else:
        game["gains"] = int(game["gains"] * 1.5)
        bus_games[user_id]["etape"] = 3
        c1 = game["cartes"][-2]
        c2 = game["cartes"][-1]
        vals = sorted([valeur_carte(c1), valeur_carte(c2)])
        embed = discord.Embed(title="🚌 Ride the Bus", color=discord.Color.purple())
        embed.add_field(name="✅ Bonne réponse !", value=f"La carte était **{nouvelle}**", inline=False)
        embed.add_field(name="💰 Gains actuels", value=f"${game['gains']}", inline=False)
        embed.add_field(name="Tes 2 dernières cartes", value=f"**{c1}** et **{c2}** (valeurs {vals[0]} et {vals[1]})", inline=False)
        embed.add_field(name="Étape 3", value="La prochaine carte sera **Inside** 🎯 ou **Outside** 💨 ?", inline=False)
        await interaction.response.edit_message(embed=embed, view=BusEtape3View(user_id))

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
        embed = discord.Embed(title="🚌 Ride the Bus - Perdu !", description=f"La carte était **{nouvelle}**\n\n😢 **Tu perds ta mise !**", color=discord.Color.red())
        embed.add_field(name="💰 Solde", value=f"${get_solde(user_id)}", inline=False)
        await interaction.response.edit_message(embed=embed, view=None)
    else:
        game["gains"] = int(game["gains"] * 1.5)
        bus_games[user_id]["etape"] = 4
        embed = discord.Embed(title="🚌 Ride the Bus", color=discord.Color.purple())
        embed.add_field(name="✅ Bonne réponse !", value=f"La carte était **{nouvelle}**", inline=False)
        embed.add_field(name="💰 Gains actuels", value=f"${game['gains']}", inline=False)
        embed.add_field(name="Étape 4 - Dernière chance !", value="Devine la **couleur** de la prochaine carte !", inline=False)
        await interaction.response.edit_message(embed=embed, view=BusEtape4View(user_id))

async def bus_etape4(interaction, user_id, choix):
    if interaction.user.id != user_id:
        await interaction.response.send_message("❌ C'est pas ta partie !", ephemeral=True)
        return
    game = bus_games[user_id]
    carte, couleur = nouvelle_carte_complete()
    gagne = choix == couleur
    gains = int(game["gains"] * 2) if gagne else 0
    del bus_games[user_id]
    if not gagne:
        embed = discord.Embed(title="🚌 Ride the Bus - Perdu !", description=f"La carte était **{carte} {couleur}**\n\n😢 **Tu perds ta mise !**", color=discord.Color.red())
        embed.add_field(name="💰 Solde", value=f"${get_solde(user_id)}", inline=False)
    else:
        add_solde(user_id, gains)
        embed = discord.Embed(title="🚌 Ride the Bus - Gagné !", description=f"La carte était **{carte} {couleur}**\n\n🎉 **Tu gagnes ${gains} !**", color=discord.Color.green())
        embed.add_field(name="💰 Solde", value=f"${get_solde(user_id)}", inline=False)
    await interaction.response.edit_message(embed=embed, view=None)

# =================== ROULETTE ===================

class RouletteView(View):
    def __init__(self, game_id):
        super().__init__(timeout=30)
        self.game_id = game_id

    @discord.ui.button(label="Rouge ❤️", style=discord.ButtonStyle.red)
    async def rouge(self, interaction: discord.Interaction, button: Button):
        await roulette_parier(interaction, self.game_id, "rouge")

    @discord.ui.button(label="Noir 🖤", style=discord.ButtonStyle.gray)
    async def noir(self, interaction: discord.Interaction, button: Button):
        await roulette_parier(interaction, self.game_id, "noir")

    @discord.ui.button(label="Pair 2️⃣", style=discord.ButtonStyle.blurple)
    async def pair(self, interaction: discord.Interaction, button: Button):
        await roulette_parier(interaction, self.game_id, "pair")

    @discord.ui.button(label="Impair 1️⃣", style=discord.ButtonStyle.blurple)
    async def impair(self, interaction: discord.Interaction, button: Button):
        await roulette_parier(interaction, self.game_id, "impair")

    @discord.ui.button(label="🎰 Lancer !", style=discord.ButtonStyle.green)
    async def lancer(self, interaction: discord.Interaction, button: Button):
        game = roulette_games.get(self.game_id)
        if not game:
            await interaction.response.send_message("❌ Partie introuvable !", ephemeral=True)
            return
        if interaction.user.id != game["host"]:
            await interaction.response.send_message("❌ Seul l'hôte peut lancer la roulette !", ephemeral=True)
            return
        if not game["paris"]:
            await interaction.response.send_message("❌ Personne n'a parié !", ephemeral=True)
            return
        numero = secrets.randbelow(37)
        rouge = [1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36]
        couleur = "rouge ❤️" if numero in rouge else ("vert 💚" if numero == 0 else "noir 🖤")
        parite = "pair" if numero != 0 and numero % 2 == 0 else "impair"
        embed = discord.Embed(title="🎰 Roulette - Résultat !", color=discord.Color.gold())
        embed.add_field(name="Numéro", value=f"**{numero}** {couleur}", inline=False)
        resultats = []
        for uid, pari in game["paris"].items():
            member = interaction.guild.get_member(uid)
            name = member.display_name if member else str(uid)
            gagne = False
            if pari["type"] == "rouge" and "rouge" in couleur:
                gagne = True
            elif pari["type"] == "noir" and "noir" in couleur:
                gagne = True
            elif pari["type"] == "pair" and parite == "pair":
                gagne = True
            elif pari["type"] == "impair" and parite == "impair":
                gagne = True
            if gagne:
                gain = pari["mise"] * 2
                add_solde(uid, gain)
                resultats.append(f"✅ {name} gagne **${gain}** ! Solde: ${get_solde(uid)}")
            else:
                resultats.append(f"❌ {name} perd **${pari['mise']}**. Solde: ${get_solde(uid)}")
        embed.add_field(name="Résultats", value="\n".join(resultats), inline=False)
        del roulette_games[self.game_id]
        self.stop()
        await interaction.response.edit_message(embed=embed, view=None)

async def roulette_parier(interaction, game_id, type_pari):
    game = roulette_games.get(game_id)
    if not game:
        await interaction.response.send_message("❌ Partie introuvable !", ephemeral=True)
        return
    user_id = interaction.user.id
    mise = game["mise"]
    solde = get_solde(user_id)
    if solde < mise:
        await interaction.response.send_message(f"❌ Pas assez d'argent ! Solde: ${solde}", ephemeral=True)
        return
    if user_id in game["paris"]:
        await interaction.response.send_message("❌ Tu as déjà parié !", ephemeral=True)
        return
    add_solde(user_id, -mise)
    game["paris"][user_id] = {"type": type_pari, "mise": mise}
    member = interaction.guild.get_member(user_id)
    name = member.display_name if member else str(user_id)
    embed = discord.Embed(title="🎰 Roulette - Paris en cours", color=discord.Color.gold())
    embed.add_field(name="Mise", value=f"${mise} par joueur", inline=False)
    paris_list = []
    for uid, p in game["paris"].items():
        m = interaction.guild.get_member(uid)
        n = m.display_name if m else str(uid)
        paris_list.append(f"{n} → {p['type']} (${p['mise']})")
    embed.add_field(name="Paris", value="\n".join(paris_list), inline=False)
    embed.set_footer(text="L'hôte peut lancer quand tout le monde a parié !")
    await interaction.response.edit_message(embed=embed, view=RouletteView(game_id))

# =================== COMMANDES ===================

@tree.command(name="blackjack", description="Joue au blackjack solo !")
@discord.app_commands.describe(mise="Combien tu veux miser ?")
async def blackjack(interaction: discord.Interaction, mise: int):
    user_id = interaction.user.id
    solde = get_solde(user_id)
    if mise <= 0:
        await interaction.response.send_message("❌ La mise doit être positive !", ephemeral=True)
        return
    if mise > solde:
        await interaction.response.send_message(f"❌ Pas assez d'argent ! Solde: ${solde}", ephemeral=True)
        return
    if user_id in blackjack_games:
        await interaction.response.send_message("❌ Partie en cours !", ephemeral=True)
        return
    add_solde(user_id, -mise)
    main_joueur = [nouvelle_carte(), nouvelle_carte()]
    main_bot = [nouvelle_carte(), nouvelle_carte()]
    blackjack_games[user_id] = {"joueur": main_joueur, "bot": main_bot}
    embed = discord.Embed(title="🃏 Blackjack", color=discord.Color.green())
    embed.add_field(name="Ta main", value=f"{afficher_main(main_joueur)} → **{valeur_main(main_joueur)}**", inline=False)
    embed.add_field(name="Croupier", value=f"{main_bot[0]} | ?", inline=False)
    embed.add_field(name="💰 Mise", value=f"${mise}", inline=False)
    await interaction.response.send_message(embed=embed, view=BlackjackView(user_id, mise))

@tree.command(name="blackjack2", description="Joue au blackjack multijoueur !")
@discord.app_commands.describe(mise="Mise par joueur", adversaire="Le membre à inviter")
async def blackjack2(interaction: discord.Interaction, mise: int, adversaire: discord.Member):
    user_id = interaction.user.id
    solde = get_solde(user_id)
    if mise <= 0:
        await interaction.response.send_message("❌ La mise doit être positive !", ephemeral=True)
        return
    if mise > solde:
        await interaction.response.send_message(f"❌ Pas assez d'argent ! Solde: ${solde}", ephemeral=True)
        return
    if adversaire.id == user_id:
        await interaction.response.send_message("❌ Tu peux pas jouer contre toi-même !", ephemeral=True)
        return
    add_solde(user_id, -mise)
    game_id = secrets.token_hex(8)
    blackjack_multi_games[game_id] = {
        "bot": [nouvelle_carte(), nouvelle_carte()],
        "joueurs": {
            user_id: {"main": [nouvelle_carte(), nouvelle_carte()], "stand": False, "mise": mise}
        }
    }
    embed = discord.Embed(title="🃏 Blackjack Multijoueur", description=f"{adversaire.mention} tu es invité à jouer ! Mise: **${mise}**", color=discord.Color.green())
    embed.add_field(name=f"{interaction.user.display_name}", value=f"{afficher_main(blackjack_multi_games[game_id]['joueurs'][user_id]['main'])}", inline=False)
    embed.add_field(name="Croupier", value=f"{blackjack_multi_games[game_id]['bot'][0]} | ?", inline=False)
    await interaction.response.send_message(embed=embed, view=JoinBlackjackView(game_id, user_id, mise))

@tree.command(name="roulette", description="Lance une roulette multijoueur !")
@discord.app_commands.describe(mise="Mise par joueur")
async def roulette(interaction: discord.Interaction, mise: int):
    if mise <= 0:
        await interaction.response.send_message("❌ La mise doit être positive !", ephemeral=True)
        return
    game_id = secrets.token_hex(8)
    roulette_games[game_id] = {"host": interaction.user.id, "mise": mise, "paris": {}}
    embed = discord.Embed(title="🎰 Roulette", description=f"Mise : **${mise}** par joueur\nPariez sur Rouge, Noir, Pair ou Impair !\nL'hôte lance quand tout le monde a parié.", color=discord.Color.gold())
    await interaction.response.send_message(embed=embed, view=RouletteView(game_id))

@tree.command(name="ridethebus", description="Joue à Ride the Bus !")
@discord.app_commands.describe(mise="Combien tu veux miser ?")
async def ridethebus(interaction: discord.Interaction, mise: int):
    user_id = interaction.user.id
    solde = get_solde(user_id)
    if mise <= 0:
        await interaction.response.send_message("❌ La mise doit être positive !", ephemeral=True)
        return
    if mise > solde:
        await interaction.response.send_message(f"❌ Pas assez d'argent ! Solde: ${solde}", ephemeral=True)
        return
    add_solde(user_id, -mise)
    carte = nouvelle_carte()
    bus_games[user_id] = {"carte": carte, "etape": 1, "cartes": [carte], "gains": mise}
    embed = discord.Embed(title="🚌 Ride the Bus", color=discord.Color.purple())
    embed.add_field(name="Ta carte de départ", value=f"**{carte}**", inline=False)
    embed.add_field(name="💰 Mise", value=f"${mise}", inline=False)
    embed.add_field(name="Étape 1", value="La prochaine carte sera **Rouge** ❤️ ou **Noir** 🖤 ?", inline=False)
    embed.set_footer(text="Cash Out à tout moment pour repartir avec tes gains !")
    await interaction.response.send_message(embed=embed, view=BusEtape1View(user_id))

@tree.command(name="slots", description="Lance les slots !")
@discord.app_commands.describe(mise="Combien tu veux miser ?")
async def slots(interaction: discord.Interaction, mise: int):
    user_id = interaction.user.id
    solde = get_solde(user_id)
    if mise <= 0:
        await interaction.response.send_message("❌ La mise doit être positive !", ephemeral=True)
        return
    if mise > solde:
        await interaction.response.send_message(f"❌ Pas assez d'argent ! Solde: ${solde}", ephemeral=True)
        return
    add_solde(user_id, -mise)
    symboles = ["🍒", "🍋", "🍊", "⭐", "💎", "7️⃣"]
    resultat = [symboles[secrets.randbelow(len(symboles))] for _ in range(3)]
    ligne = " | ".join(resultat)
    if resultat[0] == resultat[1] == resultat[2]:
        if resultat[0] == "💎":
            gain = mise * 10
            msg = f"{ligne}\n\n💎 **JACKPOT DIAMANT ! +${gain}**"
        elif resultat[0] == "7️⃣":
            gain = mise * 5
            msg = f"{ligne}\n\n7️⃣ **TRIPLE 7 ! +${gain}**"
        else:
            gain = mise * 3
            msg = f"{ligne}\n\n🎉 **JACKPOT ! +${gain}**"
        add_solde(user_id, gain)
    elif resultat[0] == resultat[1] or resultat[1] == resultat[2]:
        gain = mise
        add_solde(user_id, gain)
        msg = f"{ligne}\n\n✨ Deux identiques ! Mise remboursée !"
    else:
        msg = f"{ligne}\n\n😢 Perdu ! -${mise}"
    embed = discord.Embed(title="🎰 Slots", description=msg, color=discord.Color.gold())
    embed.add_field(name="💰 Solde", value=f"${get_solde(user_id)}", inline=False)
    await interaction.response.send_message(embed=embed)

@tree.command(name="solde", description="Affiche ton solde !")
async def solde(interaction: discord.Interaction, membre: discord.Member = None):
    target = membre or interaction.user
    montant = get_solde(target.id)
    embed = discord.Embed(title=f"💰 Solde de {target.display_name}", description=f"**${montant}**", color=discord.Color.green())
    await interaction.response.send_message(embed=embed)

@tree.command(name="richesse", description="Top 10 des plus riches du serveur !")
async def richesse(interaction: discord.Interaction):
    cursor.execute("SELECT user_id, solde FROM bank ORDER BY solde DESC LIMIT 10")
    rows = cursor.fetchall()
    embed = discord.Embed(title="💰 Top 10 des plus riches", color=discord.Color.gold())
    for i, (user_id, s) in enumerate(rows):
        member = interaction.guild.get_member(int(user_id))
        name = member.display_name if member else "Inconnu"
        embed.add_field(name=f"#{i+1} {name}", value=f"${s}", inline=False)
    await interaction.response.send_message(embed=embed)

@tree.command(name="pileouface", description="Lance une pièce !")
async def pileouface(interaction: discord.Interaction):
    resultat = ["Pile 🪙", "Face 🪙"][secrets.randbelow(2)]
    await interaction.response.send_message(resultat)

@tree.command(name="de", description="Lance un dé !")
@discord.app_commands.describe(faces="Nombre de faces du dé (défaut: 6)")
async def de(interaction: discord.Interaction, faces: int = 6):
    resultat = secrets.randbelow(faces) + 1
    await interaction.response.send_message(f"🎲 Tu as obtenu : **{resultat}** (d{faces})")

@tree.command(name="steam", description="Cherche un jeu sur Steam !")
@discord.app_commands.describe(jeu="Le nom du jeu à chercher")
async def steam(interaction: discord.Interaction, jeu: str):
    await interaction.response.defer()
    async with aiohttp.ClientSession() as session:
        async with session.get(f"https://store.steampowered.com/api/storesearch/?term={jeu}&l=french&cc=CA") as resp:
            data = await resp.json()
            if not data["items"]:
                await interaction.followup.send("❌ Jeu introuvable !")
                return
            app_id = data["items"][0]["id"]
        async with session.get(f"https://store.steampowered.com/api/appdetails?appids={app_id}&l=french&cc=CA") as resp:
            details = await resp.json()
            game = details[str(app_id)]["data"]
    prix = game.get("price_overview", {}).get("final_formatted", "Gratuit")
    description = game.get("short_description", "Pas de description")[:300]
    image = game.get("header_image", "")
    nom = game.get("name", jeu)
    lien = f"https://store.steampowered.com/app/{app_id}"
    embed = discord.Embed(title=f"🎮 {nom}", description=description, color=discord.Color.blue())
    embed.add_field(name="💰 Prix", value=prix, inline=True)
    embed.add_field(name="🔗 Lien", value=f"[Voir sur Steam]({lien})", inline=True)
    embed.set_image(url=image)
    await interaction.followup.send(embed=embed)

@tree.command(name="dadjoke", description="Envoie un dad joke !")
async def dadjoke(interaction: discord.Interaction):
    async with aiohttp.ClientSession() as session:
        async with session.get("https://icanhazdadjoke.com/", headers={"Accept": "application/json"}) as resp:
            data = await resp.json()
            joke = data["joke"]
    embed = discord.Embed(description=f"😂 {joke}", color=discord.Color.yellow())
    await interaction.response.send_message(embed=embed)

@tree.command(name="help", description="Affiche toutes les commandes du bot !")
async def help(interaction: discord.Interaction):
    embed = discord.Embed(title="📖 Commandes du bot", color=discord.Color.blue())
    embed.add_field(name="🃏 /blackjack [mise]", value="Blackjack solo", inline=False)
    embed.add_field(name="🃏 /blackjack2 [mise] [membre]", value="Blackjack multijoueur", inline=False)
    embed.add_field(name="🎰 /roulette [mise]", value="Roulette multijoueur", inline=False)
    embed.add_field(name="🚌 /ridethebus [mise]", value="Ride the Bus avec Cash Out", inline=False)
    embed.add_field(name="🎰 /slots [mise]", value="Lance les slots", inline=False)
    embed.add_field(name="💰 /solde", value="Affiche ton solde", inline=False)
    embed.add_field(name="🏆 /richesse", value="Top 10 des plus riches", inline=False)
    embed.add_field(name="🪙 /pileouface", value="Lance une pièce", inline=False)
    embed.add_field(name="🎲 /de [faces]", value="Lance un dé", inline=False)
    embed.add_field(name="🎮 /steam [jeu]", value="Cherche un jeu sur Steam", inline=False)
    embed.add_field(name="😂 /dadjoke", value="Envoie un dad joke", inline=False)
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
    add_solde(message.author.id, 4)
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
    guild = client.get_guild(payload.guild_id)
    member = guild.get_member(payload.user_id)
    if payload.message_id == MESSAGE_ID_POLES:
        role = guild.get_role(ROLE_POLES_ID)
        if member and role:
            await member.add_roles(role)
    elif payload.message_id == MESSAGE_ID_2:
        role = guild.get_role(ROLE_2_ID)
        if member and role:
            await member.add_roles(role)

@client.event
async def on_raw_reaction_remove(payload):
    if payload.emoji.name != REACTION_EMOJI:
        return
    guild = client.get_guild(payload.guild_id)
    member = guild.get_member(payload.user_id)
    if payload.message_id == MESSAGE_ID_POLES:
        role = guild.get_role(ROLE_POLES_ID)
        if member and role:
            await member.remove_roles(role)
    elif payload.message_id == MESSAGE_ID_2:
        role = guild.get_role(ROLE_2_ID)
        if member and role:
            await member.remove_roles(role)

client.run(os.environ["TOKEN"])
