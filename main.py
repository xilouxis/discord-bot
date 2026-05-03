import discord
import os
import aiohttp
import psycopg2
import secrets
import asyncio
from datetime import date
from discord.ui import View, Button
from discord import SelectOption
from discord.ui import Select

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

SALAIRE_MESSAGE = 0.20
SALAIRE_HEBDO = 100
REWARD_SONDAGE_CREATEUR = 30
REWARD_SONDAGE_REPONSE = 20

blackjack_games = {}
blackjack_multi_games = {}
bus_games = {}
roulette_games = {}
poker_games = {}
horse_games = {}

# =================== BASE DE DONNÉES ===================

def get_conn():
    url = os.environ["DATABASE_URL"]
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return psycopg2.connect(url)

def init_db():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS bank (
                    user_id TEXT PRIMARY KEY,
                    solde REAL DEFAULT 0
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS sondage_log (
                    user_id TEXT,
                    jour DATE,
                    type TEXT,
                    PRIMARY KEY (user_id, jour, type)
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS poll_responses (
                    poll_message_id TEXT,
                    user_id TEXT,
                    PRIMARY KEY (poll_message_id, user_id)
                )
            """)
        conn.commit()

def get_solde(user_id):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT solde FROM bank WHERE user_id = %s", (str(user_id),))
            row = cur.fetchone()
            if not row:
                cur.execute("INSERT INTO bank (user_id, solde) VALUES (%s, 0) ON CONFLICT DO NOTHING", (str(user_id),))
                conn.commit()
                return 0
            return row[0]

def set_solde(user_id, montant):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO bank (user_id, solde) VALUES (%s, %s) ON CONFLICT (user_id) DO UPDATE SET solde = EXCLUDED.solde",
                (str(user_id), montant)
            )
        conn.commit()

def add_solde(user_id, montant):
    solde = get_solde(user_id)
    set_solde(user_id, round(solde + montant, 2))

def get_all_users():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT user_id FROM bank")
            return [row[0] for row in cur.fetchall()]

def peut_creer_sondage(user_id):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM sondage_log WHERE user_id=%s AND jour=%s AND type='creation'", (str(user_id), date.today()))
            return cur.fetchone() is None

def marquer_sondage_creation(user_id):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO sondage_log (user_id, jour, type) VALUES (%s, %s, 'creation') ON CONFLICT DO NOTHING", (str(user_id), date.today()))
        conn.commit()

def peut_repondre_sondage(poll_message_id, user_id):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM poll_responses WHERE poll_message_id=%s AND user_id=%s", (str(poll_message_id), str(user_id)))
            return cur.fetchone() is None

def marquer_reponse_sondage(poll_message_id, user_id):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO poll_responses (poll_message_id, user_id) VALUES (%s, %s) ON CONFLICT DO NOTHING", (str(poll_message_id), str(user_id)))
        conn.commit()

# =================== SALAIRE HEBDOMADAIRE ===================

async def salaire_hebdomadaire():
    await client.wait_until_ready()
    while not client.is_closed():
        await asyncio.sleep(7 * 24 * 3600)
        users = get_all_users()
        for user_id in users:
            add_solde(user_id, SALAIRE_HEBDO)
        print(f"Salaire hebdomadaire de ${SALAIRE_HEBDO} distribué à {len(users)} utilisateurs.")

# =================== CARTES ===================

ORDRE_CARTES = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]
COULEURS_CARTES = ["♠️", "♥️", "♦️", "♣️"]

def nouvelle_carte():
    return ORDRE_CARTES[secrets.randbelow(len(ORDRE_CARTES))]

def nouvelle_carte_complete():
    carte = ORDRE_CARTES[secrets.randbelow(len(ORDRE_CARTES))]
    couleur = COULEURS_CARTES[secrets.randbelow(len(COULEURS_CARTES))]
    return carte, couleur

def nouveau_deck():
    deck = [(c, s) for c in ORDRE_CARTES for s in COULEURS_CARTES]
    secrets.SystemRandom().shuffle(deck)
    return deck

def valeur_carte_bj(carte):
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
        v = carte if isinstance(carte, str) else carte[0]
        if v in ["J", "Q", "K"]:
            total += 10
        elif v == "A":
            total += 11
            as_count += 1
        else:
            total += int(v)
    while total > 21 and as_count:
        total -= 10
        as_count -= 1
    return total

def afficher_main(main):
    return " | ".join(main)

def resultat_bj(total_joueur, total_bot, mise, user_id):
    if total_joueur > 21:
        return f"😢 Bust ! -${mise}", discord.Color.red()
    elif total_bot > 21 or total_joueur > total_bot:
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
            embed.add_field(name="💰 Solde", value=f"${get_solde(self.user_id):.2f}", inline=False)
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
        embed.add_field(name="💰 Solde", value=f"${get_solde(self.user_id):.2f}", inline=False)
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
                name=name,
                value=f"{afficher_main(data['main'])} → **{total_joueur}**\n{msg}\n💰 Solde: ${get_solde(uid):.2f}",
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
            await interaction.response.send_message(f"❌ Pas assez d'argent ! Solde: ${solde:.2f}", ephemeral=True)
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

def nouvelle_carte_bus():
    carte = ORDRE_CARTES[secrets.randbelow(len(ORDRE_CARTES))]
    couleur = COULEURS_BUS[secrets.randbelow(len(COULEURS_BUS))]
    return carte, couleur

def est_plus_haut(nouvelle, precedente):
    return ORDRE_CARTES.index(nouvelle) > ORDRE_CARTES.index(precedente)

def est_plus_bas(nouvelle, precedente):
    return ORDRE_CARTES.index(nouvelle) < ORDRE_CARTES.index(precedente)

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
    embed.add_field(name="💰 Solde", value=f"${get_solde(user_id):.2f}", inline=False)
    await interaction.response.edit_message(embed=embed, view=None)

async def bus_etape1(interaction, user_id, choix):
    if interaction.user.id != user_id:
        await interaction.response.send_message("❌ C'est pas ta partie !", ephemeral=True)
        return
    game = bus_games[user_id]
    nouvelle, couleur_carte = nouvelle_carte_bus()
    couleur = "rouge" if couleur_carte in ["♥️ Coeur", "♦️ Carreau"] else "noir"
    gagne = choix == couleur
    game["cartes"].append(nouvelle)
    if not gagne:
        del bus_games[user_id]
        embed = discord.Embed(title="🚌 Ride the Bus - Perdu !", description=f"La carte était **{nouvelle} {couleur_carte}** ({couleur})\n\n😢 **Tu perds ta mise !**", color=discord.Color.red())
        embed.add_field(name="💰 Solde", value=f"${get_solde(user_id):.2f}", inline=False)
        await interaction.response.edit_message(embed=embed, view=None)
    else:
        game["gains"] = int(game["gains"] * 1.5)
        bus_games[user_id]["etape"] = 2
        embed = discord.Embed(title="🚌 Ride the Bus", color=discord.Color.purple())
        embed.add_field(name="✅ Bonne réponse !", value=f"La carte était **{nouvelle} {couleur_carte}** ({couleur})", inline=False)
        embed.add_field(name="💰 Gains actuels", value=f"${game['gains']}", inline=False)
        embed.add_field(name="Étape 2", value=f"La prochaine carte sera **plus haute** ou **plus basse** que **{nouvelle}** ?", inline=False)
        await interaction.response.edit_message(embed=embed, view=BusEtape2View(user_id))

async def bus_etape2(interaction, user_id, choix):
    if interaction.user.id != user_id:
        await interaction.response.send_message("❌ C'est pas ta partie !", ephemeral=True)
        return
    game = bus_games[user_id]
    carte_precedente = game["cartes"][-1]
    nouvelle, couleur_carte = nouvelle_carte_bus()
    game["cartes"].append(nouvelle)
    if nouvelle == carte_precedente:
        embed = discord.Embed(title="🚌 Ride the Bus", color=discord.Color.purple())
        embed.add_field(name="↔️ Égalité !", value=f"La carte était **{nouvelle} {couleur_carte}**, même valeur ! Rejoue.", inline=False)
        embed.add_field(name="💰 Gains actuels", value=f"${game['gains']}", inline=False)
        embed.add_field(name="Étape 2", value=f"La prochaine carte sera **plus haute** ou **plus basse** que **{nouvelle}** ?", inline=False)
        await interaction.response.edit_message(embed=embed, view=BusEtape2View(user_id))
        return
    gagne = (choix == "haut" and est_plus_haut(nouvelle, carte_precedente)) or \
            (choix == "bas" and est_plus_bas(nouvelle, carte_precedente))
    if not gagne:
        del bus_games[user_id]
        embed = discord.Embed(title="🚌 Ride the Bus - Perdu !", description=f"La carte était **{nouvelle} {couleur_carte}**\n\n😢 **Tu perds ta mise !**", color=discord.Color.red())
        embed.add_field(name="💰 Solde", value=f"${get_solde(user_id):.2f}", inline=False)
        await interaction.response.edit_message(embed=embed, view=None)
    else:
        game["gains"] = int(game["gains"] * 1.5)
        bus_games[user_id]["etape"] = 3
        c1 = game["cartes"][-2]
        c2 = game["cartes"][-1]
        vals = sorted([valeur_carte_bj(c1), valeur_carte_bj(c2)])
        embed = discord.Embed(title="🚌 Ride the Bus", color=discord.Color.purple())
        embed.add_field(name="✅ Bonne réponse !", value=f"La carte était **{nouvelle} {couleur_carte}**", inline=False)
        embed.add_field(name="💰 Gains actuels", value=f"${game['gains']}", inline=False)
        embed.add_field(name="Tes 2 dernières cartes", value=f"**{c1}** et **{c2}** (valeurs {vals[0]} et {vals[1]})", inline=False)
        embed.add_field(name="Étape 3", value="La prochaine carte sera **Inside** 🎯 ou **Outside** 💨 ?", inline=False)
        await interaction.response.edit_message(embed=embed, view=BusEtape3View(user_id))

async def bus_etape3(interaction, user_id, choix):
    if interaction.user.id != user_id:
        await interaction.response.send_message("❌ C'est pas ta partie !", ephemeral=True)
        return
    game = bus_games[user_id]
    nouvelle, couleur_carte = nouvelle_carte_bus()
    idx_c1 = ORDRE_CARTES.index(game["cartes"][-2])
    idx_c2 = ORDRE_CARTES.index(game["cartes"][-1])
    vals = sorted([idx_c1, idx_c2])
    idx_nouvelle = ORDRE_CARTES.index(nouvelle)
    if idx_nouvelle == vals[0] or idx_nouvelle == vals[1]:
        game["cartes"].append(nouvelle)
        c1 = game["cartes"][-3]
        c2 = game["cartes"][-2]
        v = sorted([valeur_carte_bj(c1), valeur_carte_bj(c2)])
        embed = discord.Embed(title="🚌 Ride the Bus", color=discord.Color.purple())
        embed.add_field(name="↔️ Égalité !", value=f"La carte était **{nouvelle} {couleur_carte}**, exactement sur la bordure ! Rejoue.", inline=False)
        embed.add_field(name="💰 Gains actuels", value=f"${game['gains']}", inline=False)
        embed.add_field(name="Tes 2 cartes", value=f"**{c1}** et **{c2}** (valeurs {v[0]} et {v[1]})", inline=False)
        embed.add_field(name="Étape 3", value="**Inside** 🎯 ou **Outside** 💨 ?", inline=False)
        await interaction.response.edit_message(embed=embed, view=BusEtape3View(user_id))
        return
    gagne = (choix == "inside" and vals[0] < idx_nouvelle < vals[1]) or \
            (choix == "outside" and (idx_nouvelle < vals[0] or idx_nouvelle > vals[1]))
    game["cartes"].append(nouvelle)
    if not gagne:
        del bus_games[user_id]
        embed = discord.Embed(title="🚌 Ride the Bus - Perdu !", description=f"La carte était **{nouvelle} {couleur_carte}**\n\n😢 **Tu perds ta mise !**", color=discord.Color.red())
        embed.add_field(name="💰 Solde", value=f"${get_solde(user_id):.2f}", inline=False)
        await interaction.response.edit_message(embed=embed, view=None)
    else:
        game["gains"] = int(game["gains"] * 1.5)
        bus_games[user_id]["etape"] = 4
        embed = discord.Embed(title="🚌 Ride the Bus", color=discord.Color.purple())
        embed.add_field(name="✅ Bonne réponse !", value=f"La carte était **{nouvelle} {couleur_carte}**", inline=False)
        embed.add_field(name="💰 Gains actuels", value=f"${game['gains']}", inline=False)
        embed.add_field(name="Étape 4 - Dernière chance !", value="Devine la **couleur** de la prochaine carte !", inline=False)
        await interaction.response.edit_message(embed=embed, view=BusEtape4View(user_id))

async def bus_etape4(interaction, user_id, choix):
    if interaction.user.id != user_id:
        await interaction.response.send_message("❌ C'est pas ta partie !", ephemeral=True)
        return
    game = bus_games[user_id]
    carte, couleur = nouvelle_carte_bus()
    gagne = choix == couleur
    gains = int(game["gains"] * 2) if gagne else 0
    del bus_games[user_id]
    if not gagne:
        embed = discord.Embed(title="🚌 Ride the Bus - Perdu !", description=f"La carte était **{carte} {couleur}**\n\n😢 **Tu perds ta mise !**", color=discord.Color.red())
        embed.add_field(name="💰 Solde", value=f"${get_solde(user_id):.2f}", inline=False)
    else:
        add_solde(user_id, gains)
        embed = discord.Embed(title="🚌 Ride the Bus - Gagné !", description=f"La carte était **{carte} {couleur}**\n\n🎉 **Tu gagnes ${gains} !**", color=discord.Color.green())
        embed.add_field(name="💰 Solde", value=f"${get_solde(user_id):.2f}", inline=False)
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
                resultats.append(f"✅ {name} gagne **${gain}** ! Solde: ${get_solde(uid):.2f}")
            else:
                resultats.append(f"❌ {name} perd **${pari['mise']}**. Solde: ${get_solde(uid):.2f}")
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
        await interaction.response.send_message(f"❌ Pas assez d'argent ! Solde: ${solde:.2f}", ephemeral=True)
        return
    if user_id in game["paris"]:
        await interaction.response.send_message("❌ Tu as déjà parié !", ephemeral=True)
        return
    add_solde(user_id, -mise)
    game["paris"][user_id] = {"type": type_pari, "mise": mise}
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

# =================== POKER TEXAS HOLD'EM ===================

MAINS_POKER = [
    "Carte haute", "Paire", "Double paire", "Brelan",
    "Suite", "Couleur", "Full house", "Carré", "Quinte flush", "Quinte flush royale"
]

def evaluer_main_poker(cartes):
    """Évalue une main de 5 cartes et retourne (rang, description)"""
    valeurs = [c[0] for c in cartes]
    couleurs = [c[1] for c in cartes]
    indices = sorted([ORDRE_CARTES.index(v) for v in valeurs], reverse=True)

    # Compter les occurrences
    counts = {}
    for i in indices:
        counts[i] = counts.get(i, 0) + 1
    sorted_counts = sorted(counts.items(), key=lambda x: (x[1], x[0]), reverse=True)
    freqs = [c for _, c in sorted_counts]

    flush = len(set(couleurs)) == 1
    suite = (max(indices) - min(indices) == 4 and len(set(indices)) == 5)
    # Cas spécial A-2-3-4-5
    as_bas = sorted(indices) == [0, 1, 2, 3, 12]
    if as_bas:
        suite = True
        indices = [3, 2, 1, 0, -1]

    if flush and suite:
        if min(indices) == 8:  # 10-J-Q-K-A
            return 9, "Quinte flush royale"
        return 8, "Quinte flush"
    if freqs[0] == 4:
        return 7, "Carré"
    if freqs[0] == 3 and freqs[1] == 2:
        return 6, "Full house"
    if flush:
        return 5, "Couleur"
    if suite:
        return 4, "Suite"
    if freqs[0] == 3:
        return 3, "Brelan"
    if freqs[0] == 2 and freqs[1] == 2:
        return 2, "Double paire"
    if freqs[0] == 2:
        return 1, "Paire"
    return 0, "Carte haute"

def meilleure_main(hole_cards, community_cards):
    """Trouve la meilleure main de 5 parmi 7 cartes"""
    from itertools import combinations
    toutes = hole_cards + community_cards
    meilleure = None
    desc = ""
    for combo in combinations(toutes, 5):
        rang, d = evaluer_main_poker(list(combo))
        if meilleure is None or rang > meilleure:
            meilleure = rang
            desc = d
    return meilleure, desc

def afficher_cartes(cartes):
    return " ".join([f"`{c[0]}{c[1]}`" for c in cartes])

class PokerJoinView(View):
    def __init__(self, game_id, mise):
        super().__init__(timeout=60)
        self.game_id = game_id
        self.mise = mise

    @discord.ui.button(label="Rejoindre 🃏", style=discord.ButtonStyle.green)
    async def rejoindre(self, interaction: discord.Interaction, button: Button):
        game = poker_games.get(self.game_id)
        if not game:
            await interaction.response.send_message("❌ Partie introuvable !", ephemeral=True)
            return
        user_id = interaction.user.id
        if user_id in game["joueurs"]:
            await interaction.response.send_message("❌ Tu es déjà dans la partie !", ephemeral=True)
            return
        if len(game["joueurs"]) >= 6:
            await interaction.response.send_message("❌ La partie est pleine (6 max) !", ephemeral=True)
            return
        solde = get_solde(user_id)
        if solde < self.mise:
            await interaction.response.send_message(f"❌ Pas assez d'argent ! Solde: ${solde:.2f}", ephemeral=True)
            return
        add_solde(user_id, -self.mise)
        game["joueurs"][user_id] = {"hole": [], "fold": False, "mise_totale": self.mise}
        member = interaction.guild.get_member(user_id)
        name = member.display_name if member else str(user_id)
        embed = discord.Embed(title="🃏 Poker Texas Hold'em", description=f"**{name}** a rejoint ! ({len(game['joueurs'])}/6 joueurs)", color=discord.Color.green())
        embed.add_field(name="Mise", value=f"${self.mise} par joueur", inline=False)
        embed.add_field(name="Joueurs", value="\n".join([
            interaction.guild.get_member(uid).display_name if interaction.guild.get_member(uid) else str(uid)
            for uid in game["joueurs"]
        ]), inline=False)
        embed.set_footer(text="L'hôte peut lancer quand il y a au moins 2 joueurs.")
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Lancer la partie ▶️", style=discord.ButtonStyle.blurple)
    async def lancer(self, interaction: discord.Interaction, button: Button):
        game = poker_games.get(self.game_id)
        if not game:
            await interaction.response.send_message("❌ Partie introuvable !", ephemeral=True)
            return
        if interaction.user.id != game["host"]:
            await interaction.response.send_message("❌ Seul l'hôte peut lancer !", ephemeral=True)
            return
        if len(game["joueurs"]) < 2:
            await interaction.response.send_message("❌ Il faut au moins 2 joueurs !", ephemeral=True)
            return
        self.stop()
        await demarrer_poker(interaction, self.game_id)

async def demarrer_poker(interaction, game_id):
    game = poker_games[game_id]
    deck = nouveau_deck()
    idx = 0
    # Distribuer 2 cartes à chaque joueur
    for uid in game["joueurs"]:
        game["joueurs"][uid]["hole"] = [deck[idx], deck[idx+1]]
        idx += 2
    # 5 cartes communes
    game["community"] = deck[idx:idx+5]
    game["phase"] = "preflop"
    game["pot"] = sum(d["mise_totale"] for d in game["joueurs"].values())

    # Envoyer cartes privées en DM à chaque joueur
    for uid, data in game["joueurs"].items():
        member = interaction.guild.get_member(uid)
        if member:
            try:
                await member.send(f"🃏 **Tes cartes privées (Poker #{game_id[:6]}):** {afficher_cartes(data['hole'])}")
            except:
                pass

    embed = discord.Embed(title="🃏 Poker Texas Hold'em - Preflop", color=discord.Color.green())
    embed.add_field(name="💰 Pot", value=f"${game['pot']}", inline=False)
    embed.add_field(name="Cartes communes", value="🂠 🂠 🂠 🂠 🂠 (pas encore révélées)", inline=False)
    embed.add_field(name="Joueurs", value="\n".join([
        interaction.guild.get_member(uid).display_name if interaction.guild.get_member(uid) else str(uid)
        for uid in game["joueurs"]
    ]), inline=False)
    embed.set_footer(text="Les cartes privées vous ont été envoyées en DM ! Cliquez Suivant pour le Flop.")
    await interaction.response.edit_message(embed=embed, view=PokerPhaseView(game_id))

class PokerPhaseView(View):
    def __init__(self, game_id):
        super().__init__(timeout=300)
        self.game_id = game_id

    @discord.ui.button(label="Flop 🂠🂠🂠", style=discord.ButtonStyle.blurple)
    async def flop(self, interaction: discord.Interaction, button: Button):
        game = poker_games.get(self.game_id)
        if not game:
            await interaction.response.send_message("❌ Partie introuvable !", ephemeral=True)
            return
        if interaction.user.id != game["host"]:
            await interaction.response.send_message("❌ Seul l'hôte peut avancer !", ephemeral=True)
            return
        game["phase"] = "flop"
        flop = game["community"][:3]
        embed = discord.Embed(title="🃏 Poker - Flop", color=discord.Color.green())
        embed.add_field(name="💰 Pot", value=f"${game['pot']}", inline=False)
        embed.add_field(name="Flop", value=afficher_cartes(flop), inline=False)
        await interaction.response.edit_message(embed=embed, view=PokerPhaseView2(self.game_id))

class PokerPhaseView2(View):
    def __init__(self, game_id):
        super().__init__(timeout=300)
        self.game_id = game_id

    @discord.ui.button(label="Turn 🂠", style=discord.ButtonStyle.blurple)
    async def turn(self, interaction: discord.Interaction, button: Button):
        game = poker_games.get(self.game_id)
        if not game:
            await interaction.response.send_message("❌ Partie introuvable !", ephemeral=True)
            return
        if interaction.user.id != game["host"]:
            await interaction.response.send_message("❌ Seul l'hôte peut avancer !", ephemeral=True)
            return
        game["phase"] = "turn"
        flop = game["community"][:3]
        turn = game["community"][3]
        embed = discord.Embed(title="🃏 Poker - Turn", color=discord.Color.green())
        embed.add_field(name="💰 Pot", value=f"${game['pot']}", inline=False)
        embed.add_field(name="Cartes communes", value=f"{afficher_cartes(flop)} + `{turn[0]}{turn[1]}`", inline=False)
        await interaction.response.edit_message(embed=embed, view=PokerPhaseView3(self.game_id))

class PokerPhaseView3(View):
    def __init__(self, game_id):
        super().__init__(timeout=300)
        self.game_id = game_id

    @discord.ui.button(label="River 🂠", style=discord.ButtonStyle.blurple)
    async def river(self, interaction: discord.Interaction, button: Button):
        game = poker_games.get(self.game_id)
        if not game:
            await interaction.response.send_message("❌ Partie introuvable !", ephemeral=True)
            return
        if interaction.user.id != game["host"]):
            await interaction.response.send_message("❌ Seul l'hôte peut avancer !", ephemeral=True)
            return
        game["phase"] = "river"
        community = game["community"]
        embed = discord.Embed(title="🃏 Poker - River", color=discord.Color.green())
        embed.add_field(name="💰 Pot", value=f"${game['pot']}", inline=False)
        embed.add_field(name="Cartes communes", value=afficher_cartes(community), inline=False)
        await interaction.response.edit_message(embed=embed, view=PokerShowdownView(self.game_id))

class PokerShowdownView(View):
    def __init__(self, game_id):
        super().__init__(timeout=300)
        self.game_id = game_id

    @discord.ui.button(label="Showdown 🏆", style=discord.ButtonStyle.green)
    async def showdown(self, interaction: discord.Interaction, button: Button):
        game = poker_games.get(self.game_id)
        if not game:
            await interaction.response.send_message("❌ Partie introuvable !", ephemeral=True)
            return
        if interaction.user.id != game["host"]:
            await interaction.response.send_message("❌ Seul l'hôte peut avancer !", ephemeral=True)
            return
        community = game["community"]
        resultats = []
        meilleur_rang = -1
        gagnants = []
        for uid, data in game["joueurs"].items():
            rang, desc = meilleure_main(data["hole"], community)
            member = interaction.guild.get_member(uid)
            name = member.display_name if member else str(uid)
            resultats.append((uid, name, rang, desc, data["hole"]))
            if rang > meilleur_rang:
                meilleur_rang = rang
                gagnants = [uid]
            elif rang == meilleur_rang:
                gagnants.append(uid)

        gain_par_gagnant = game["pot"] // len(gagnants)
        for uid in gagnants:
            add_solde(uid, gain_par_gagnant)

        embed = discord.Embed(title="🃏 Poker - Showdown !", color=discord.Color.gold())
        embed.add_field(name="Cartes communes", value=afficher_cartes(community), inline=False)
        for uid, name, rang, desc, hole in sorted(resultats, key=lambda x: x[2], reverse=True):
            gagne_str = " 🏆 GAGNANT !" if uid in gagnants else ""
            embed.add_field(
                name=f"{name}{gagne_str}",
                value=f"Cartes: {afficher_cartes(hole)}\nMain: **{desc}**\nSolde: ${get_solde(uid):.2f}",
                inline=False
            )
        embed.add_field(name="💰 Pot distribué", value=f"${gain_par_gagnant} à chaque gagnant", inline=False)
        del poker_games[self.game_id]
        self.stop()
        await interaction.response.edit_message(embed=embed, view=None)

# =================== COURSES DE CHEVAUX ===================

CHEVAUX = ["🐴 Éclair", "🐴 Tonnerre", "🐴 Tempête", "🐴 Rafale", "🐴 Foudre", "🐴 Mistral"]

class HorseJoinView(View):
    def __init__(self, game_id):
        super().__init__(timeout=60)
        self.game_id = game_id
        # Ajouter un select pour choisir le cheval
        select = Select(
            placeholder="Choisis ton cheval et ta mise...",
            options=[SelectOption(label=cheval, value=str(i)) for i, cheval in enumerate(CHEVAUX)]
        )
        select.callback = self.choisir_cheval
        self.add_item(select)

    async def choisir_cheval(self, interaction: discord.Interaction):
        game = horse_games.get(self.game_id)
        if not game:
            await interaction.response.send_message("❌ Course introuvable !", ephemeral=True)
            return
        user_id = interaction.user.id
        if user_id in game["paris"]:
            await interaction.response.send_message("❌ Tu as déjà parié !", ephemeral=True)
            return
        idx_cheval = int(self.children[0].values[0])
        mise = game["mise"]
        solde = get_solde(user_id)
        if solde < mise:
            await interaction.response.send_message(f"❌ Pas assez d'argent ! Solde: ${solde:.2f}", ephemeral=True)
            return
        add_solde(user_id, -mise)
        game["paris"][user_id] = idx_cheval
        member = interaction.guild.get_member(user_id)
        name = member.display_name if member else str(user_id)
        paris_list = []
        for uid, idx in game["paris"].items():
            m = interaction.guild.get_member(uid)
            n = m.display_name if m else str(uid)
            paris_list.append(f"{n} → {CHEVAUX[idx]}")
        embed = discord.Embed(title="🏇 Course de chevaux - Paris ouverts !", color=discord.Color.orange())
        embed.add_field(name="💰 Mise", value=f"${mise} par joueur", inline=False)
        embed.add_field(name="🐴 Chevaux disponibles", value="\n".join(CHEVAUX), inline=False)
        embed.add_field(name="Paris", value="\n".join(paris_list) if paris_list else "Aucun pari encore", inline=False)
        embed.set_footer(text="L'hôte lance la course quand tout le monde a parié !")
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="🏁 Lancer la course !", style=discord.ButtonStyle.green, row=1)
    async def lancer(self, interaction: discord.Interaction, button: Button):
        game = horse_games.get(self.game_id)
        if not game:
            await interaction.response.send_message("❌ Course introuvable !", ephemeral=True)
            return
        if interaction.user.id != game["host"]:
            await interaction.response.send_message("❌ Seul l'hôte peut lancer !", ephemeral=True)
            return
        if not game["paris"]:
            await interaction.response.send_message("❌ Personne n'a parié !", ephemeral=True)
            return
        self.stop()
        await lancer_course(interaction, self.game_id)

async def lancer_course(interaction, game_id):
    game = horse_games[game_id]
    mise = game["mise"]

    # Simuler la course — chaque cheval a une vitesse aléatoire
    positions = list(range(len(CHEVAUX)))
    secrets.SystemRandom().shuffle(positions)
    classement = [CHEVAUX[i] for i in positions]

    gagnant_idx = positions[0]
    gagnants = [uid for uid, idx in game["paris"].items() if idx == gagnant_idx]
    nb_gagnants = len(gagnants) if gagnants else 1
    pot_total = mise * len(game["paris"])
    gain = pot_total // nb_gagnants if gagnants else 0

    for uid in gagnants:
        add_solde(uid, gain)

    # Construire l'animation textuelle
    course_lines = []
    for place, cheval in enumerate(classement, 1):
        barre = "🟩" * (7 - place) + "⬜" * (place - 1)
        course_lines.append(f"`{place}.` {cheval} {barre}")

    embed = discord.Embed(title="🏇 Course de chevaux - Résultats !", color=discord.Color.orange())
    embed.add_field(name="🏁 Classement final", value="\n".join(course_lines), inline=False)
    embed.add_field(name="🏆 Gagnant", value=f"**{CHEVAUX[gagnant_idx]}** remporte la course !", inline=False)

    resultats = []
    for uid, idx in game["paris"].items():
        member = interaction.guild.get_member(uid)
        name = member.display_name if member else str(uid)
        if uid in gagnants:
            resultats.append(f"✅ {name} ({CHEVAUX[idx]}) gagne **${gain}** ! Solde: ${get_solde(uid):.2f}")
        else:
            resultats.append(f"❌ {name} ({CHEVAUX[idx]}) perd **${mise}**. Solde: ${get_solde(uid):.2f}")

    embed.add_field(name="💰 Résultats", value="\n".join(resultats), inline=False)
    del horse_games[game_id]
    await interaction.response.edit_message(embed=embed, view=None)

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
        await interaction.response.send_message(f"❌ Pas assez d'argent ! Solde: ${solde:.2f}", ephemeral=True)
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
        await interaction.response.send_message(f"❌ Pas assez d'argent ! Solde: ${solde:.2f}", ephemeral=True)
        return
    if adversaire.id == user_id:
        await interaction.response.send_message("❌ Tu peux pas jouer contre toi-même !", ephemeral=True)
        return
    add_solde(user_id, -mise)
    game_id = secrets.token_hex(8)
    blackjack_multi_games[game_id] = {
        "bot": [nouvelle_carte(), nouvelle_carte()],
        "joueurs": {user_id: {"main": [nouvelle_carte(), nouvelle_carte()], "stand": False, "mise": mise}}
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
        await interaction.response.send_message(f"❌ Pas assez d'argent ! Solde: ${solde:.2f}", ephemeral=True)
        return
    add_solde(user_id, -mise)
    carte, couleur_carte = nouvelle_carte_bus()
    bus_games[user_id] = {"etape": 1, "cartes": [carte], "gains": mise}
    embed = discord.Embed(title="🚌 Ride the Bus", color=discord.Color.purple())
    embed.add_field(name="Ta carte de départ", value=f"**{carte} {couleur_carte}**", inline=False)
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
        await interaction.response.send_message(f"❌ Pas assez d'argent ! Solde: ${solde:.2f}", ephemeral=True)
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
    embed.add_field(name="💰 Solde", value=f"${get_solde(user_id):.2f}", inline=False)
    await interaction.response.send_message(embed=embed)

@tree.command(name="poker", description="Lance une partie de Poker Texas Hold'em (2-6 joueurs) !")
@discord.app_commands.describe(mise="Mise par joueur")
async def poker(interaction: discord.Interaction, mise: int):
    if mise <= 0:
        await interaction.response.send_message("❌ La mise doit être positive !", ephemeral=True)
        return
    solde = get_solde(interaction.user.id)
    if mise > solde:
        await interaction.response.send_message(f"❌ Pas assez d'argent ! Solde: ${solde:.2f}", ephemeral=True)
        return
    game_id = secrets.token_hex(8)
    add_solde(interaction.user.id, -mise)
    poker_games[game_id] = {
        "host": interaction.user.id,
        "mise": mise,
        "joueurs": {interaction.user.id: {"hole": [], "fold": False, "mise_totale": mise}},
        "community": [],
        "phase": "lobby",
        "pot": mise
    }
    embed = discord.Embed(title="🃏 Poker Texas Hold'em", description=f"**{interaction.user.display_name}** crée une partie !\nMise: **${mise}** par joueur", color=discord.Color.green())
    embed.add_field(name="Joueurs (1/6)", value=interaction.user.display_name, inline=False)
    embed.set_footer(text="Rejoins la partie avant que l'hôte la lance !")
    await interaction.response.send_message(embed=embed, view=PokerJoinView(game_id, mise))

@tree.command(name="course", description="Lance une course de chevaux multijoueur !")
@discord.app_commands.describe(mise="Mise par joueur")
async def course(interaction: discord.Interaction, mise: int):
    if mise <= 0:
        await interaction.response.send_message("❌ La mise doit être positive !", ephemeral=True)
        return
    game_id = secrets.token_hex(8)
    horse_games[game_id] = {"host": interaction.user.id, "mise": mise, "paris": {}}
    embed = discord.Embed(title="🏇 Course de chevaux !", description=f"Mise : **${mise}** par joueur\nChoisis ton cheval dans le menu !\nL'hôte lance quand tout le monde a parié.", color=discord.Color.orange())
    embed.add_field(name="🐴 Chevaux", value="\n".join(CHEVAUX), inline=False)
    await interaction.response.send_message(embed=embed, view=HorseJoinView(game_id))

@tree.command(name="solde", description="Affiche ton solde !")
async def solde(interaction: discord.Interaction, membre: discord.Member = None):
    target = membre or interaction.user
    montant = get_solde(target.id)
    embed = discord.Embed(title=f"💰 Solde de {target.display_name}", description=f"**${montant:.2f}**", color=discord.Color.green())
    await interaction.response.send_message(embed=embed)

@tree.command(name="richesse", description="Top 10 des plus riches du serveur !")
async def richesse(interaction: discord.Interaction):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT user_id, solde FROM bank ORDER BY solde DESC LIMIT 10")
            rows = cur.fetchall()
    embed = discord.Embed(title="💰 Top 10 des plus riches", color=discord.Color.gold())
    for i, (user_id, s) in enumerate(rows):
        member = interaction.guild.get_member(int(user_id))
        name = member.display_name if member else "Inconnu"
        embed.add_field(name=f"#{i+1} {name}", value=f"${s:.2f}", inline=False)
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
    embed.add_field(name="🃏 /poker [mise]", value="Poker Texas Hold'em 2-6 joueurs", inline=False)
    embed.add_field(name="🎰 /roulette [mise]", value="Roulette multijoueur", inline=False)
    embed.add_field(name="🚌 /ridethebus [mise]", value="Ride the Bus avec Cash Out", inline=False)
    embed.add_field(name="🎰 /slots [mise]", value="Lance les slots", inline=False)
    embed.add_field(name="🏇 /course [mise]", value="Course de chevaux multijoueur", inline=False)
    embed.add_field(name="💰 /solde", value="Affiche ton solde", inline=False)
    embed.add_field(name="🏆 /richesse", value="Top 10 des plus riches", inline=False)
    embed.add_field(name="🪙 /pileouface", value="Lance une pièce", inline=False)
    embed.add_field(name="🎲 /de [faces]", value="Lance un dé", inline=False)
    embed.add_field(name="🎮 /steam [jeu]", value="Cherche un jeu sur Steam", inline=False)
    embed.add_field(name="😂 /dadjoke", value="Envoie un dad joke", inline=False)
    embed.set_footer(text=f"💵 +${SALAIRE_MESSAGE}/message • 📊 +${REWARD_SONDAGE_CREATEUR} créer sondage • ✅ +${REWARD_SONDAGE_REPONSE} répondre • 💰 +${SALAIRE_HEBDO}$/semaine")
    await interaction.response.send_message(embed=embed)

# =================== EVENTS ===================

@client.event
async def on_ready():
    init_db()
    await tree.sync()
    client.loop.create_task(salaire_hebdomadaire())
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
    add_solde(message.author.id, SALAIRE_MESSAGE)

    if message.channel.name == POLES_CHANNEL and message.poll:
        # Récompense création de sondage
        if peut_creer_sondage(message.author.id):
            marquer_sondage_creation(message.author.id)
            add_solde(message.author.id, REWARD_SONDAGE_CREATEUR)
            try:
                await message.author.send(f"📊 Tu as gagné **${REWARD_SONDAGE_CREATEUR}** pour avoir créé un sondage ! Solde: ${get_solde(message.author.id):.2f}")
            except:
                pass
        await message.create_thread(name="Discussion du sondage")
        role = message.guild.get_role(ROLE_POLES_ID)
        if role:
            await message.channel.send(role.mention)

@client.event
async def on_raw_reaction_add(payload):
    # Récompense réponse à un sondage
    guild = client.get_guild(payload.guild_id)
    if guild:
        channel = guild.get_channel(payload.channel_id)
        if channel and channel.name == POLES_CHANNEL:
            if peut_repondre_sondage(payload.message_id, payload.user_id):
                marquer_reponse_sondage(payload.message_id, payload.user_id)
                add_solde(payload.user_id, REWARD_SONDAGE_REPONSE)
                member = guild.get_member(payload.user_id)
                if member:
                    try:
                        await member.send(f"✅ Tu as gagné **${REWARD_SONDAGE_REPONSE}** pour avoir répondu à un sondage ! Solde: ${get_solde(payload.user_id):.2f}")
                    except:
                        pass

    if payload.emoji.name != REACTION_EMOJI:
        return
    if not guild:
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
