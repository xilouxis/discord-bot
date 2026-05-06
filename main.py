import discord
import os
import aiohttp
import mysql.connector
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

SALAIRE_MESSAGE = 1
SALAIRE_HEBDO = 100
REWARD_SONDAGE_CREATION = 50       # Reçu immédiatement à la création
REWARD_SONDAGE_VOTE_VOTEUR = 30    # Reçu par chaque voteur à la clôture
REWARD_SONDAGE_VOTE_CREATEUR = 10  # Reçu par le créateur PAR vote à la clôture

DAILY_BASE = 50
DAILY_MAX_STREAK = 7
DAILY_MAX_BONUS = 250

blackjack_games = {}
blackjack_multi_games = {}
bus_games = {}
roulette_games = {}
poker_games = {}
horse_games = {}

# =================== BASE DE DONNÉES ===================

def get_conn():
    return mysql.connector.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        user=os.environ.get("DB_USER", "discordbot"),
        password=os.environ.get("DB_PASSWORD", ""),
        database=os.environ.get("DB_NAME", "discordbot"),
        autocommit=False
    )

def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS bank (
            user_id VARCHAR(20) PRIMARY KEY,
            solde FLOAT DEFAULT 0
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS sondage_log (
            user_id VARCHAR(20),
            jour DATE,
            PRIMARY KEY (user_id, jour)
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS poll_responses (
            poll_message_id VARCHAR(20),
            user_id VARCHAR(20),
            PRIMARY KEY (poll_message_id, user_id)
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS poll_creators (
            poll_message_id VARCHAR(20) PRIMARY KEY,
            creator_id VARCHAR(20),
            rewarded TINYINT DEFAULT 0
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS stats (
            user_id VARCHAR(20) PRIMARY KEY,
            parties_jouees INTEGER DEFAULT 0,
            parties_gagnees INTEGER DEFAULT 0,
            gains_totaux FLOAT DEFAULT 0,
            pertes_totales FLOAT DEFAULT 0
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS daily (
            user_id VARCHAR(20) PRIMARY KEY,
            last_claim DATE,
            streak INTEGER DEFAULT 0
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS profile (
            user_id VARCHAR(20) PRIMARY KEY,
            messages_envoyes INTEGER DEFAULT 0,
            sondages_crees INTEGER DEFAULT 0,
            votes_donnes INTEGER DEFAULT 0,
            votes_recus INTEGER DEFAULT 0,
            gains_totaux_global FLOAT DEFAULT 0
        )
    """)
    conn.commit()
    cur.close()
    conn.close()

def get_solde(user_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT solde FROM bank WHERE user_id = %s", (str(user_id),))
    row = cur.fetchone()
    if not row:
        cur.execute("INSERT IGNORE INTO bank (user_id, solde) VALUES (%s, 0)", (str(user_id),))
        conn.commit()
        cur.close()
        conn.close()
        return 0
    cur.close()
    conn.close()
    return row[0]

def set_solde(user_id, montant):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO bank (user_id, solde) VALUES (%s, %s) ON DUPLICATE KEY UPDATE solde = VALUES(solde)",
        (str(user_id), montant)
    )
    conn.commit()
    cur.close()
    conn.close()

def add_solde(user_id, montant):
    solde = get_solde(user_id)
    set_solde(user_id, round(solde + montant, 2))

def get_all_users():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM bank")
    rows = [row[0] for row in cur.fetchall()]
    cur.close()
    conn.close()
    return rows

def peut_creer_sondage(user_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM sondage_log WHERE user_id=%s AND jour=%s", (str(user_id), date.today()))
    result = cur.fetchone() is None
    cur.close()
    conn.close()
    return result

def marquer_sondage_creation(user_id, poll_message_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("INSERT IGNORE INTO sondage_log (user_id, jour) VALUES (%s, %s)", (str(user_id), date.today()))
    cur.execute("INSERT IGNORE INTO poll_creators (poll_message_id, creator_id) VALUES (%s, %s)", (str(poll_message_id), str(user_id)))
    conn.commit()
    cur.close()
    conn.close()

def get_poll_creator(poll_message_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT creator_id FROM poll_creators WHERE poll_message_id=%s AND rewarded=0", (str(poll_message_id),))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row[0] if row else None

def peut_voter_sondage(poll_message_id, user_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM poll_responses WHERE poll_message_id=%s AND user_id=%s", (str(poll_message_id), str(user_id)))
    result = cur.fetchone() is None
    cur.close()
    conn.close()
    return result

def marquer_vote_sondage(poll_message_id, user_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("INSERT IGNORE INTO poll_responses (poll_message_id, user_id) VALUES (%s, %s)", (str(poll_message_id), str(user_id)))
    conn.commit()
    cur.close()
    conn.close()

def get_poll_voters(poll_message_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM poll_responses WHERE poll_message_id=%s", (str(poll_message_id),))
    rows = [row[0] for row in cur.fetchall()]
    cur.close()
    conn.close()
    return rows

def marquer_sondage_recompense(poll_message_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE poll_creators SET rewarded=1 WHERE poll_message_id=%s", (str(poll_message_id),))
    conn.commit()
    cur.close()
    conn.close()

def add_stat(user_id, gagne, montant):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO stats (user_id, parties_jouees, parties_gagnees, gains_totaux, pertes_totales)
        VALUES (%s, 1, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            parties_jouees = parties_jouees + 1,
            parties_gagnees = parties_gagnees + %s,
            gains_totaux = gains_totaux + %s,
            pertes_totales = pertes_totales + %s
    """, (
        str(user_id),
        1 if gagne else 0,
        montant if gagne else 0,
        0 if gagne else montant,
        1 if gagne else 0,
        montant if gagne else 0,
        0 if gagne else montant
    ))
    conn.commit()
    cur.close()
    conn.close()

def get_stats(user_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM stats WHERE user_id = %s", (str(user_id),))
    row = cur.fetchone()
    cur.close()
    conn.close()
    if not row:
        return {"parties_jouees": 0, "parties_gagnees": 0, "gains_totaux": 0, "pertes_totales": 0}
    return {
        "parties_jouees": row[1],
        "parties_gagnees": row[2],
        "gains_totaux": row[3],
        "pertes_totales": row[4]
    }

def get_daily_info(user_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT last_claim, streak FROM daily WHERE user_id = %s", (str(user_id),))
    row = cur.fetchone()
    cur.close()
    conn.close()
    if not row:
        return {"last_claim": None, "streak": 0}
    return {"last_claim": row[0], "streak": row[1]}

def get_profile(user_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT messages_envoyes, sondages_crees, votes_donnes, votes_recus, gains_totaux_global FROM profile WHERE user_id=%s", (str(user_id),))
    row = cur.fetchone()
    cur.close()
    conn.close()
    if not row:
        return {"messages_envoyes": 0, "sondages_crees": 0, "votes_donnes": 0, "votes_recus": 0, "gains_totaux_global": 0}
    return {"messages_envoyes": row[0], "sondages_crees": row[1], "votes_donnes": row[2], "votes_recus": row[3], "gains_totaux_global": row[4]}

def profile_add(user_id, messages=0, sondages=0, votes_donnes=0, votes_recus=0, gains=0):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO profile (user_id, messages_envoyes, sondages_crees, votes_donnes, votes_recus, gains_totaux_global)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            messages_envoyes = messages_envoyes + VALUES(messages_envoyes),
            sondages_crees = sondages_crees + VALUES(sondages_crees),
            votes_donnes = votes_donnes + VALUES(votes_donnes),
            votes_recus = votes_recus + VALUES(votes_recus),
            gains_totaux_global = gains_totaux_global + VALUES(gains_totaux_global)
    """, (str(user_id), messages, sondages, votes_donnes, votes_recus, gains))
    conn.commit()
    cur.close()
    conn.close()

def get_classement_richesse(user_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*)+1 FROM bank WHERE solde > (SELECT solde FROM bank WHERE user_id=%s)", (str(user_id),))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row[0] if row else "?"

def claim_daily(user_id):
    from datetime import date, timedelta
    today = date.today()
    info = get_daily_info(user_id)
    last = info["last_claim"]
    streak = info["streak"]

    if last == today:
        return None, streak, "already"

    yesterday = today - timedelta(days=1)
    if last == yesterday:
        new_streak = min(streak + 1, DAILY_MAX_STREAK)
    else:
        new_streak = 1

    montant = DAILY_BASE + (new_streak - 1) * ((DAILY_MAX_BONUS - DAILY_BASE) // (DAILY_MAX_STREAK - 1))

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO daily (user_id, last_claim, streak) VALUES (%s, %s, %s)
        ON DUPLICATE KEY UPDATE last_claim = VALUES(last_claim), streak = VALUES(streak)
    """, (str(user_id), today, new_streak))
    conn.commit()
    cur.close()
    conn.close()

    add_solde(user_id, montant)
    return montant, new_streak, "ok"

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
        add_stat(user_id, False, mise)
        return f"😢 Bust ! -${mise}", discord.Color.red()
    elif total_bot > 21 or total_joueur > total_bot:
        add_solde(user_id, mise * 2)
        add_stat(user_id, True, mise)
        return f"🎉 Gagné ! +${mise}", discord.Color.green()
    elif total_joueur == total_bot:
        add_solde(user_id, mise)
        return f"🤝 Égalité ! Mise remboursée.", discord.Color.yellow()
    else:
        add_stat(user_id, False, mise)
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
            add_stat(self.user_id, False, self.mise)
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
    add_stat(user_id, True, gains - game["mise_initiale"])
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
        add_stat(user_id, False, game["mise_initiale"])
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
        add_stat(user_id, False, game["mise_initiale"])
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
        add_stat(user_id, False, game["mise_initiale"])
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
        add_stat(user_id, False, game["mise_initiale"])
        embed = discord.Embed(title="🚌 Ride the Bus - Perdu !", description=f"La carte était **{carte} {couleur}**\n\n😢 **Tu perds ta mise !**", color=discord.Color.red())
        embed.add_field(name="💰 Solde", value=f"${get_solde(user_id):.2f}", inline=False)
    else:
        add_solde(user_id, gains)
        add_stat(user_id, True, gains - game["mise_initiale"])
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
                add_stat(uid, True, pari["mise"])
                resultats.append(f"✅ {name} gagne **${gain}** ! Solde: ${get_solde(uid):.2f}")
            else:
                add_stat(uid, False, pari["mise"])
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

def evaluer_main_poker(cartes):
    valeurs = [c[0] for c in cartes]
    couleurs = [c[1] for c in cartes]
    indices = sorted([ORDRE_CARTES.index(v) for v in valeurs], reverse=True)
    counts = {}
    for i in indices:
        counts[i] = counts.get(i, 0) + 1
    sorted_counts = sorted(counts.items(), key=lambda x: (x[1], x[0]), reverse=True)
    freqs = [c for _, c in sorted_counts]
    flush = len(set(couleurs)) == 1
    suite = (max(indices) - min(indices) == 4 and len(set(indices)) == 5)
    as_bas = sorted(indices) == [0, 1, 2, 3, 12]
    if as_bas:
        suite = True
        indices = [3, 2, 1, 0, -1]
    if flush and suite:
        if min(indices) == 8:
            return (9, indices), "Quinte flush royale"
        return (8, indices), "Quinte flush"
    if freqs[0] == 4:
        return (7, indices), "Carré"
    if freqs[0] == 3 and len(freqs) > 1 and freqs[1] == 2:
        return (6, indices), "Full house"
    if flush:
        return (5, indices), "Couleur"
    if suite:
        return (4, indices), "Suite"
    if freqs[0] == 3:
        return (3, indices), "Brelan"
    if freqs[0] == 2 and len(freqs) > 1 and freqs[1] == 2:
        return (2, indices), "Double paire"
    if freqs[0] == 2:
        return (1, indices), "Paire"
    return (0, indices), "Carte haute"


def meilleure_main(hole_cards, community_cards):
    from itertools import combinations
    toutes = hole_cards + community_cards
    if len(toutes) < 5:
        return (0, []), "Carte haute"
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

def get_joueurs_actifs(game):
    return [uid for uid, d in game["joueurs"].items() if not d["fold"] and not d.get("allin", False)]

def get_joueurs_en_jeu(game):
    return [uid for uid, d in game["joueurs"].items() if not d["fold"]]

def get_nom(guild, uid):
    m = guild.get_member(uid)
    return m.display_name if m else str(uid)

def get_phase_label(phase):
    labels = {"preflop": "Preflop", "flop": "Flop", "turn": "Turn", "river": "River"}
    return labels.get(phase, phase.capitalize())

def build_poker_embed(game, guild):
    phase = game.get("phase", "preflop")
    community = game.get("community", [])
    ordre = game.get("ordre", [])
    tour_index = game.get("tour_index", 0)

    current_uid = None
    if ordre:
        for i in range(len(ordre)):
            uid = ordre[(tour_index + i) % len(ordre)]
            d = game["joueurs"][uid]
            if not d["fold"] and not d.get("allin", False):
                current_uid = uid
                break

    embed = discord.Embed(title=f"🃏 Poker - {get_phase_label(phase)}", color=discord.Color.green())
    embed.add_field(name="💰 Pot", value=f"**${game['pot']}**", inline=True)
    embed.add_field(name="Mise à suivre", value=f"**${game['mise_courante']}**", inline=True)

    if phase == "preflop":
        embed.add_field(name="Cartes communes", value="🂠 🂠 🂠 🂠 🂠", inline=False)
    elif phase == "flop":
        embed.add_field(name="Cartes communes", value=afficher_cartes(community[:3]) + " 🂠 🂠", inline=False)
    elif phase == "turn":
        embed.add_field(name="Cartes communes", value=afficher_cartes(community[:4]) + " 🂠", inline=False)
    else:
        embed.add_field(name="Cartes communes", value=afficher_cartes(community), inline=False)

    bb_uid = game.get("big_blind_uid")
    sb_uid = game.get("small_blind_uid")
    joueurs_str = ""
    for uid in ordre:
        d = game["joueurs"][uid]
        nom = get_nom(guild, uid)
        role_tag = ""
        if uid == bb_uid:
            role_tag = " [BB]"
        elif uid == sb_uid:
            role_tag = " [SB]"
        if d["fold"]:
            statut = "❌ Fold"
        elif d.get("allin", False):
            statut = "💥 All-in"
        elif d["mise_phase"] >= game["mise_courante"] and uid in game.get("joueurs_parle", set()):
            statut = "✅ Suivi"
        else:
            statut = "⏳ En attente"
        arrow = " 👈" if uid == current_uid else ""
        joueurs_str += f"**{nom}**{role_tag}: ${d['mise_phase']} misé — {statut}{arrow}\n"

    embed.add_field(name="Joueurs", value=joueurs_str or "Aucun", inline=False)

    if current_uid:
        solde_actuel = get_solde(current_uid)
        embed.set_footer(text=f"Tour de {get_nom(guild, current_uid)} | Solde: ${solde_actuel:.2f}")

    return embed

async def poker_fin_un_joueur(interaction, game_id):
    game = poker_games[game_id]
    en_jeu = get_joueurs_en_jeu(game)
    uid = en_jeu[0]
    add_solde(uid, game["pot"])
    add_stat(uid, True, game["pot"] - game["joueurs"][uid]["mise_totale"])
    for u, d in game["joueurs"].items():
        if u != uid:
            add_stat(u, False, d["mise_totale"])
    nom = get_nom(interaction.guild, uid)
    embed = discord.Embed(title="🃏 Poker - Fin de partie !", description=f"🏆 **{nom}** gagne **${game['pot']}** — tous les autres ont fold !", color=discord.Color.gold())
    embed.add_field(name="💰 Nouveau solde", value=f"${get_solde(uid):.2f}", inline=False)
    del poker_games[game_id]
    await interaction.response.edit_message(embed=embed, view=None)

async def poker_showdown(interaction, game_id):
    game = poker_games[game_id]
    community = game["community"]
    en_jeu = get_joueurs_en_jeu(game)
    resultats = []

    for uid in en_jeu:
        data = game["joueurs"][uid]
        rang, desc = meilleure_main(data["hole"], community)
        nom = get_nom(interaction.guild, uid)
        resultats.append((uid, nom, rang, desc, data["hole"]))

    # Trier par rang décroissant — rang est maintenant un tuple (score, [indices]) pour départager
    resultats.sort(key=lambda x: x[2], reverse=True)

    # Déterminer le seul gagnant : le premier après tri (rang le plus élevé + meilleurs kickers)
    meilleur_rang = resultats[0][2]
    # S'il y a strictement égalité parfaite sur tous les kickers, on partage (rare mais possible)
    gagnants = [r for r in resultats if r[2] == meilleur_rang]

    gain_par_gagnant = game["pot"] // len(gagnants)
    gagnants_ids = [r[0] for r in gagnants]

    for uid in gagnants_ids:
        add_solde(uid, gain_par_gagnant)
        add_stat(uid, True, gain_par_gagnant - game["joueurs"][uid]["mise_totale"])
    for uid, data in game["joueurs"].items():
        if uid not in gagnants_ids:
            add_stat(uid, False, data["mise_totale"])

    embed = discord.Embed(title="🃏 Poker - Showdown !", color=discord.Color.gold())
    embed.add_field(name="Cartes communes", value=afficher_cartes(community), inline=False)

    for uid, nom, rang, desc, hole in resultats:
        est_gagnant = uid in gagnants_ids
        gagne_str = " 🏆 GAGNANT !" if est_gagnant else ""
        embed.add_field(
            name=f"{nom}{gagne_str}",
            value=f"Cartes: {afficher_cartes(hole)}\nMain: **{desc}**\nSolde: ${get_solde(uid):.2f}",
            inline=False
        )

    if len(gagnants) == 1:
        embed.add_field(name="💰 Pot gagné", value=f"**{gagnants[0][1]}** remporte **${game['pot']}** !", inline=False)
    else:
        embed.add_field(name="💰 Égalité parfaite !", value=f"Pot de ${game['pot']} partagé — ${gain_par_gagnant} chacun.", inline=False)

    del poker_games[game_id]
    await interaction.response.edit_message(embed=embed, view=None)

async def poker_next_phase(interaction, game_id):
    game = poker_games[game_id]
    en_jeu = get_joueurs_en_jeu(game)

    if len(en_jeu) <= 1:
        await poker_fin_un_joueur(interaction, game_id)
        return

    phase = game["phase"]

    for uid in game["joueurs"]:
        game["joueurs"][uid]["mise_phase"] = 0
    game["mise_courante"] = 0
    game["joueurs_parle"] = set()

    actifs_non_allin = get_joueurs_actifs(game)
    game["ordre"] = [uid for uid in game["ordre"] if not game["joueurs"][uid]["fold"]]
    game["tour_index"] = 0

    if phase == "preflop":
        game["phase"] = "flop"
    elif phase == "flop":
        game["phase"] = "turn"
    elif phase == "turn":
        game["phase"] = "river"
    elif phase == "river":
        await poker_showdown(interaction, game_id)
        return

    if len(actifs_non_allin) == 0:
        game["phase"] = "river"
        await poker_showdown(interaction, game_id)
        return

    embed = build_poker_embed(game, interaction.guild)
    await interaction.response.edit_message(embed=embed, view=PokerActionView(game_id))

def avancer_tour(game):
    ordre = game["ordre"]
    n = len(ordre)
    for i in range(1, n + 1):
        uid = ordre[(game["tour_index"] + i) % n]
        d = game["joueurs"][uid]
        if not d["fold"] and not d.get("allin", False):
            game["tour_index"] = (game["tour_index"] + i) % n
            return uid
    return None

class RaiseModal(discord.ui.Modal, title="Relancer"):
    montant = discord.ui.TextInput(
        label="Montant à relancer",
        placeholder="Ex: 50 (en plus de la mise courante)",
        required=True,
        max_length=10
    )

    def __init__(self, game_id):
        super().__init__()
        self.game_id = game_id

    async def on_submit(self, interaction: discord.Interaction):
        game = poker_games.get(self.game_id)
        if not game:
            await interaction.response.send_message("❌ Partie introuvable !", ephemeral=True)
            return
        user_id = interaction.user.id
        try:
            raise_amount = int(self.montant.value)
            if raise_amount <= 0:
                raise ValueError
        except ValueError:
            await interaction.response.send_message("❌ Montant invalide !", ephemeral=True)
            return

        a_suivre = game["mise_courante"] - game["joueurs"][user_id]["mise_phase"]
        total_a_payer = a_suivre + raise_amount
        solde = get_solde(user_id)

        if total_a_payer > solde:
            await interaction.response.send_message(f"❌ Pas assez d'argent ! Il te faut ${total_a_payer}, solde: ${solde:.2f}", ephemeral=True)
            return

        add_solde(user_id, -total_a_payer)
        game["joueurs"][user_id]["mise_phase"] += total_a_payer
        game["joueurs"][user_id]["mise_totale"] += total_a_payer
        game["pot"] += total_a_payer
        game["mise_courante"] = game["joueurs"][user_id]["mise_phase"]
        game["joueurs_parle"] = {user_id}
        avancer_tour(game)
        embed = build_poker_embed(game, interaction.guild)
        await interaction.response.edit_message(embed=embed, view=PokerActionView(self.game_id))

class PokerActionView(View):
    def __init__(self, game_id):
        super().__init__(timeout=180)
        self.game_id = game_id

    def get_current_player(self):
        game = poker_games.get(self.game_id)
        if not game or not game["ordre"]:
            return None
        ordre = game["ordre"]
        idx = game["tour_index"] % len(ordre)
        uid = ordre[idx]
        d = game["joueurs"][uid]
        if d["fold"] or d.get("allin", False):
            return avancer_tour(game)
        return uid

    async def check_tour_fini(self, interaction):
        game = poker_games.get(self.game_id)
        if not game:
            return
        en_jeu = get_joueurs_en_jeu(game)
        if len(en_jeu) <= 1:
            await poker_fin_un_joueur(interaction, self.game_id)
            return
        actifs = get_joueurs_actifs(game)
        tous_parle = all(uid in game["joueurs_parle"] for uid in actifs)
        tous_egaux = all(
            game["joueurs"][uid]["mise_phase"] == game["mise_courante"]
            for uid in actifs
        )
        if tous_parle and tous_egaux:
            await poker_next_phase(interaction, self.game_id)
        else:
            avancer_tour(game)
            embed = build_poker_embed(game, interaction.guild)
            await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Check ✋", style=discord.ButtonStyle.gray, row=0)
    async def check(self, interaction: discord.Interaction, button: Button):
        game = poker_games.get(self.game_id)
        if not game:
            await interaction.response.send_message("❌ Partie introuvable !", ephemeral=True)
            return
        user_id = interaction.user.id
        current = self.get_current_player()
        if user_id != current:
            await interaction.response.send_message("❌ C'est pas ton tour !", ephemeral=True)
            return
        if game["mise_courante"] > game["joueurs"][user_id]["mise_phase"]:
            await interaction.response.send_message("❌ Tu peux pas check — il y a une mise à suivre !", ephemeral=True)
            return
        game["joueurs_parle"].add(user_id)
        await self.check_tour_fini(interaction)

    @discord.ui.button(label="Suivre 💰", style=discord.ButtonStyle.green, row=0)
    async def suivre(self, interaction: discord.Interaction, button: Button):
        game = poker_games.get(self.game_id)
        if not game:
            await interaction.response.send_message("❌ Partie introuvable !", ephemeral=True)
            return
        user_id = interaction.user.id
        current = self.get_current_player()
        if user_id != current:
            await interaction.response.send_message("❌ C'est pas ton tour !", ephemeral=True)
            return
        a_payer = game["mise_courante"] - game["joueurs"][user_id]["mise_phase"]
        if a_payer <= 0:
            await interaction.response.send_message("❌ Rien à suivre, utilise Check !", ephemeral=True)
            return
        solde = get_solde(user_id)
        if solde < a_payer:
            await interaction.response.send_message(f"❌ Pas assez d'argent ! Il te faut ${a_payer}, solde: ${solde:.2f}", ephemeral=True)
            return
        add_solde(user_id, -a_payer)
        game["joueurs"][user_id]["mise_phase"] += a_payer
        game["joueurs"][user_id]["mise_totale"] += a_payer
        game["pot"] += a_payer
        game["joueurs_parle"].add(user_id)
        await self.check_tour_fini(interaction)

    @discord.ui.button(label="Relancer 📈", style=discord.ButtonStyle.blurple, row=0)
    async def relancer(self, interaction: discord.Interaction, button: Button):
        game = poker_games.get(self.game_id)
        if not game:
            await interaction.response.send_message("❌ Partie introuvable !", ephemeral=True)
            return
        user_id = interaction.user.id
        current = self.get_current_player()
        if user_id != current:
            await interaction.response.send_message("❌ C'est pas ton tour !", ephemeral=True)
            return
        await interaction.response.send_modal(RaiseModal(self.game_id))

    @discord.ui.button(label="All-in 💥", style=discord.ButtonStyle.danger, row=0)
    async def allin(self, interaction: discord.Interaction, button: Button):
        game = poker_games.get(self.game_id)
        if not game:
            await interaction.response.send_message("❌ Partie introuvable !", ephemeral=True)
            return
        user_id = interaction.user.id
        current = self.get_current_player()
        if user_id != current:
            await interaction.response.send_message("❌ C'est pas ton tour !", ephemeral=True)
            return
        solde = get_solde(user_id)
        if solde <= 0:
            await interaction.response.send_message("❌ Tu n'as plus d'argent !", ephemeral=True)
            return
        add_solde(user_id, -solde)
        game["joueurs"][user_id]["mise_phase"] += solde
        game["joueurs"][user_id]["mise_totale"] += solde
        game["pot"] += solde
        if game["joueurs"][user_id]["mise_phase"] > game["mise_courante"]:
            game["mise_courante"] = game["joueurs"][user_id]["mise_phase"]
            game["joueurs_parle"] = {user_id}
        else:
            game["joueurs_parle"].add(user_id)
        game["joueurs"][user_id]["allin"] = True
        await self.check_tour_fini(interaction)

    @discord.ui.button(label="Fold 🏳️", style=discord.ButtonStyle.red, row=1)
    async def fold(self, interaction: discord.Interaction, button: Button):
        game = poker_games.get(self.game_id)
        if not game:
            await interaction.response.send_message("❌ Partie introuvable !", ephemeral=True)
            return
        user_id = interaction.user.id
        current = self.get_current_player()
        if user_id != current:
            await interaction.response.send_message("❌ C'est pas ton tour !", ephemeral=True)
            return
        game["joueurs"][user_id]["fold"] = True
        game["joueurs_parle"].add(user_id)
        await self.check_tour_fini(interaction)

class PokerJoinView(View):
    def __init__(self, game_id, big_blind):
        super().__init__(timeout=120)
        self.game_id = game_id
        self.big_blind = big_blind

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
        if user_id == game["host"]:
            await interaction.response.send_message("❌ L'hôte (Big Blind) est déjà dans la partie !", ephemeral=True)
            return
        if len(game["joueurs"]) >= 6:
            await interaction.response.send_message("❌ La partie est pleine (6 max) !", ephemeral=True)
            return
        is_small_blind = len(game["joueurs"]) == 1
        montant_entree = self.big_blind // 2 if is_small_blind else 0
        solde = get_solde(user_id)
        if solde < montant_entree and is_small_blind:
            await interaction.response.send_message(f"❌ Pas assez pour le small blind (${montant_entree}) ! Solde: ${solde:.2f}", ephemeral=True)
            return
        if is_small_blind and montant_entree > 0:
            add_solde(user_id, -montant_entree)
            game["pot"] += montant_entree
            game["small_blind_uid"] = user_id
        game["joueurs"][user_id] = {
            "hole": [],
            "fold": False,
            "allin": False,
            "mise_totale": montant_entree,
            "mise_phase": montant_entree,
        }
        role = "Small Blind" if is_small_blind else "Joueur"
        montant_str = f" (${montant_entree} small blind payé)" if is_small_blind else ""
        embed = discord.Embed(
            title="🃏 Poker Texas Hold'em — Lobby",
            description=f"**{get_nom(interaction.guild, user_id)}** a rejoint comme **{role}**{montant_str} !",
            color=discord.Color.green()
        )
        embed.add_field(name="Big Blind", value=f"${self.big_blind} (hôte)", inline=True)
        embed.add_field(name="Small Blind", value=f"${self.big_blind // 2} (2e joueur)", inline=True)
        embed.add_field(name="💰 Pot actuel", value=f"${game['pot']}", inline=False)
        joueurs_lines = []
        for uid in game["joueurs"]:
            nom = get_nom(interaction.guild, uid)
            r = "BB" if uid == game["host"] else ("SB" if uid == game.get("small_blind_uid") else "—")
            joueurs_lines.append(f"{nom} [{r}]")
        embed.add_field(name=f"Joueurs ({len(game['joueurs'])}/6)", value="\n".join(joueurs_lines), inline=False)
        embed.set_footer(text="L'hôte lance quand tout le monde est prêt !")
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Lancer ▶️", style=discord.ButtonStyle.blurple)
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
    big_blind = game["blind"]
    host_id = game["host"]
    sb_uid = game.get("small_blind_uid")

    ordre = [host_id]
    if sb_uid:
        ordre.append(sb_uid)
    for uid in game["joueurs"]:
        if uid not in ordre:
            ordre.append(uid)
    game["ordre"] = ordre

    deck = nouveau_deck()
    idx = 0
    for uid in ordre:
        game["joueurs"][uid]["hole"] = [deck[idx], deck[idx+1]]
        idx += 2
    game["community"] = deck[idx:idx+5]
    game["phase"] = "preflop"
    game["mise_courante"] = big_blind
    game["joueurs_parle"] = set()

    if len(ordre) == 2:
        game["tour_index"] = 0
    else:
        game["tour_index"] = 2

    for uid, data in game["joueurs"].items():
        member = interaction.guild.get_member(uid)
        if member:
            try:
                await member.send(f"🃏 **Tes cartes privées (Poker #{game_id[:6]}):** {afficher_cartes(data['hole'])}")
            except:
                pass

    embed = build_poker_embed(game, interaction.guild)
    embed.set_footer(text="🂠 Cartes privées envoyées en DM ! Les blinds sont posés, c'est parti !")
    await interaction.response.edit_message(embed=embed, view=PokerActionView(game_id))

# =================== COURSES DE CHEVAUX ===================

CHEVAUX = ["🐴 Éclair", "🐴 Tonnerre", "🐴 Tempête", "🐴 Rafale", "🐴 Foudre", "🐴 Mistral"]

# Multiplicateurs de gains par place (1er, 2e, 3e)
HORSE_MULTIPLICATEURS = [3.0, 2.0, 1.5]

class HorseSelect(Select):
    def __init__(self, game_id, mise):
        self.game_id = game_id
        self.mise = mise
        super().__init__(
            placeholder="Choisis ton cheval...",
            options=[SelectOption(label=cheval, value=str(i)) for i, cheval in enumerate(CHEVAUX)]
        )

    async def callback(self, interaction: discord.Interaction):
        game = horse_games.get(self.game_id)
        if not game:
            await interaction.response.send_message("❌ Course introuvable !", ephemeral=True)
            return
        user_id = interaction.user.id
        if user_id in game["paris"]:
            await interaction.response.send_message("❌ Tu as déjà parié !", ephemeral=True)
            return
        idx_cheval = int(self.values[0])
        mise = game["mise"]
        solde = get_solde(user_id)
        if solde < mise:
            await interaction.response.send_message(f"❌ Pas assez d'argent ! Solde: ${solde:.2f}", ephemeral=True)
            return
        add_solde(user_id, -mise)
        game["paris"][user_id] = idx_cheval
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
        await interaction.response.edit_message(embed=embed, view=self.view)

class HorseJoinView(View):
    def __init__(self, game_id, mise):
        super().__init__(timeout=60)
        self.game_id = game_id
        self.add_item(HorseSelect(game_id, mise))

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

    # Mélanger les chevaux pour obtenir un classement aléatoire complet
    positions = list(range(len(CHEVAUX)))
    secrets.SystemRandom().shuffle(positions)
    classement = [CHEVAUX[i] for i in positions]  # classement[0] = 1er, [1] = 2e, etc.

    # Indices des chevaux aux 3 premières places
    idx_1er = positions[0]
    idx_2e  = positions[1]
    idx_3e  = positions[2]

    # Affichage de la course avec une barre de progression visuelle
    course_lines = []
    for place, cheval in enumerate(classement, 1):
        barre = "🟩" * (7 - place) + "⬜" * (place - 1)
        medaille = ["🥇", "🥈", "🥉"][place - 1] if place <= 3 else f"`{place}.`"
        course_lines.append(f"{medaille} {cheval} {barre}")

    embed = discord.Embed(title="🏇 Course de chevaux - Résultats !", color=discord.Color.orange())
    embed.add_field(name="🏁 Classement final", value="\n".join(course_lines), inline=False)
    embed.add_field(
        name="🏆 Podium",
        value=(
            f"🥇 **{classement[0]}** — x{HORSE_MULTIPLICATEURS[0]:.1f}\n"
            f"🥈 **{classement[1]}** — x{HORSE_MULTIPLICATEURS[1]:.1f}\n"
            f"🥉 **{classement[2]}** — x{HORSE_MULTIPLICATEURS[2]:.1f}"
        ),
        inline=False
    )

    # Calculer les gains pour chaque parieur selon la place de son cheval
    resultats = []
    for uid, idx_cheval in game["paris"].items():
        member = interaction.guild.get_member(uid)
        name = member.display_name if member else str(uid)

        if idx_cheval == idx_1er:
            gain = int(mise * HORSE_MULTIPLICATEURS[0])
            add_solde(uid, gain)
            add_stat(uid, True, gain - mise)
            resultats.append(f"🥇 {name} ({CHEVAUX[idx_cheval]}) gagne **${gain}** (x{HORSE_MULTIPLICATEURS[0]:.1f}) ! Solde: ${get_solde(uid):.2f}")
        elif idx_cheval == idx_2e:
            gain = int(mise * HORSE_MULTIPLICATEURS[1])
            add_solde(uid, gain)
            add_stat(uid, True, gain - mise)
            resultats.append(f"🥈 {name} ({CHEVAUX[idx_cheval]}) gagne **${gain}** (x{HORSE_MULTIPLICATEURS[1]:.1f}) ! Solde: ${get_solde(uid):.2f}")
        elif idx_cheval == idx_3e:
            gain = int(mise * HORSE_MULTIPLICATEURS[2])
            add_solde(uid, gain)
            add_stat(uid, True, gain - mise)
            resultats.append(f"🥉 {name} ({CHEVAUX[idx_cheval]}) gagne **${gain}** (x{HORSE_MULTIPLICATEURS[2]:.1f}) ! Solde: ${get_solde(uid):.2f}")
        else:
            add_stat(uid, False, mise)
            resultats.append(f"❌ {name} ({CHEVAUX[idx_cheval]}) perd **${mise}**. Solde: ${get_solde(uid):.2f}")

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
    bus_games[user_id] = {"etape": 1, "cartes": [carte], "gains": mise, "mise_initiale": mise}
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
        add_stat(user_id, True, gain - mise)
    elif resultat[0] == resultat[1] or resultat[1] == resultat[2]:
        gain = mise
        add_solde(user_id, gain)
        add_stat(user_id, True, 0)
        msg = f"{ligne}\n\n✨ Deux identiques ! Mise remboursée !"
    else:
        add_stat(user_id, False, mise)
        msg = f"{ligne}\n\n😢 Perdu ! -${mise}"
    embed = discord.Embed(title="🎰 Slots", description=msg, color=discord.Color.gold())
    embed.add_field(name="💰 Solde", value=f"${get_solde(user_id):.2f}", inline=False)
    await interaction.response.send_message(embed=embed)

@tree.command(name="poker", description="Lance une partie de Poker Texas Hold'em (2-6 joueurs) !")
@discord.app_commands.describe(blind="Mise de départ (blind) par joueur")
async def poker(interaction: discord.Interaction, blind: int):
    if blind <= 0:
        await interaction.response.send_message("❌ La mise doit être positive !", ephemeral=True)
        return
    solde = get_solde(interaction.user.id)
    if blind > solde:
        await interaction.response.send_message(f"❌ Pas assez d'argent ! Solde: ${solde:.2f}", ephemeral=True)
        return
    game_id = secrets.token_hex(8)
    add_solde(interaction.user.id, -blind)
    poker_games[game_id] = {
        "host": interaction.user.id,
        "blind": blind,
        "joueurs": {
            interaction.user.id: {
                "hole": [],
                "fold": False,
                "mise_totale": blind,
                "mise_phase": blind,
            }
        },
        "community": [],
        "phase": "lobby",
        "pot": blind,
        "mise_courante": blind,
        "ordre": [],
        "tour_index": 0,
        "joueurs_parle": set(),
    }
    embed = discord.Embed(title="🃏 Poker Texas Hold'em", description=f"**{interaction.user.display_name}** crée une partie !\nBlind: **${blind}** par joueur", color=discord.Color.green())
    embed.add_field(name="💰 Pot", value=f"${blind}", inline=False)
    embed.add_field(name="Joueurs (1/6)", value=interaction.user.display_name, inline=False)
    embed.set_footer(text="Rejoins la partie avant que l'hôte la lance !")
    await interaction.response.send_message(embed=embed, view=PokerJoinView(game_id, blind))

@tree.command(name="course", description="Lance une course de chevaux multijoueur !")
@discord.app_commands.describe(mise="Mise par joueur")
async def course(interaction: discord.Interaction, mise: int):
    await interaction.response.defer()
    if mise <= 0:
        await interaction.followup.send("❌ La mise doit être positive !", ephemeral=True)
        return
    game_id = secrets.token_hex(8)
    horse_games[game_id] = {"host": interaction.user.id, "mise": mise, "paris": {}}
    embed = discord.Embed(title="🏇 Course de chevaux !", description=f"Mise : **${mise}** par joueur\nChoisis ton cheval dans le menu !\nL'hôte lance quand tout le monde a parié.", color=discord.Color.orange())
    embed.add_field(name="🐴 Chevaux", value="\n".join(CHEVAUX), inline=False)
    embed.add_field(name="🏆 Gains", value="🥇 1er place → x3.0\n🥈 2e place → x2.0\n🥉 3e place → x1.5", inline=False)
    await interaction.followup.send(embed=embed, view=HorseJoinView(game_id, mise))

@tree.command(name="solde", description="Affiche ton solde !")
async def solde(interaction: discord.Interaction, membre: discord.Member = None):
    target = membre or interaction.user
    montant = get_solde(target.id)
    embed = discord.Embed(title=f"💰 Solde de {target.display_name}", description=f"**${montant:.2f}**", color=discord.Color.green())
    await interaction.response.send_message(embed=embed)

@tree.command(name="richesse", description="Top 10 des plus riches du serveur !")
async def richesse(interaction: discord.Interaction):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT user_id, solde FROM bank ORDER BY solde DESC LIMIT 10")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    embed = discord.Embed(title="💰 Top 10 des plus riches", color=discord.Color.gold())
    for i, (user_id, s) in enumerate(rows):
        member = interaction.guild.get_member(int(user_id))
        name = member.display_name if member else "Inconnu"
        embed.add_field(name=f"#{i+1} {name}", value=f"${s:.2f}", inline=False)
    await interaction.response.send_message(embed=embed)

@tree.command(name="donner", description="Donne de l'argent à quelqu'un !")
@discord.app_commands.describe(membre="Le membre à qui donner", montant="Combien donner")
async def donner(interaction: discord.Interaction, membre: discord.Member, montant: int):
    user_id = interaction.user.id
    if montant <= 0:
        await interaction.response.send_message("❌ Le montant doit être positif !", ephemeral=True)
        return
    if membre.id == user_id:
        await interaction.response.send_message("❌ Tu peux pas te donner de l'argent à toi-même !", ephemeral=True)
        return
    if membre.bot:
        await interaction.response.send_message("❌ Tu peux pas donner de l'argent à un bot !", ephemeral=True)
        return
    solde = get_solde(user_id)
    if montant > solde:
        await interaction.response.send_message(f"❌ Pas assez d'argent ! Solde: ${solde:.2f}", ephemeral=True)
        return
    add_solde(user_id, -montant)
    add_solde(membre.id, montant)
    embed = discord.Embed(title="💸 Transfert effectué !", color=discord.Color.green())
    embed.add_field(name="De", value=interaction.user.display_name, inline=True)
    embed.add_field(name="À", value=membre.display_name, inline=True)
    embed.add_field(name="Montant", value=f"${montant}", inline=True)
    embed.add_field(name="Ton solde", value=f"${get_solde(user_id):.2f}", inline=False)
    embed.add_field(name=f"Solde de {membre.display_name}", value=f"${get_solde(membre.id):.2f}", inline=False)
    await interaction.response.send_message(embed=embed)

@tree.command(name="stats", description="Affiche les statistiques complètes d'un membre !")
@discord.app_commands.describe(membre="Le membre dont tu veux voir les stats")
async def stats(interaction: discord.Interaction, membre: discord.Member = None):
    target = membre or interaction.user
    uid = target.id

    s = get_stats(uid)
    daily = get_daily_info(uid)
    profil = get_profile(uid)
    solde = get_solde(uid)
    classement = get_classement_richesse(uid)

    # Ratio victoires gambling
    ratio = round((s["parties_gagnees"] / s["parties_jouees"]) * 100) if s["parties_jouees"] > 0 else 0

    # Streak daily
    streak = daily["streak"]
    last_claim = daily["last_claim"]
    if last_claim:
        last_str = last_claim.strftime("%d/%m/%Y")
        streak_bar = "🔥" * min(streak, DAILY_MAX_STREAK) + "⬜" * (DAILY_MAX_STREAK - min(streak, DAILY_MAX_STREAK))
    else:
        last_str = "Jamais"
        streak_bar = "⬜" * DAILY_MAX_STREAK

    # Gains totaux toutes sources confondues
    gains_gambling = s["gains_totaux"]
    gains_autres = profil["gains_totaux_global"]  # messages + sondages + votes
    gains_total = gains_gambling + gains_autres

    embed = discord.Embed(
        title=f"📊 Profil de {target.display_name}",
        color=discord.Color.blue()
    )
    embed.set_thumbnail(url=target.display_avatar.url)

    # ── Économie ──
    embed.add_field(name="💰 Solde actuel", value=f"**${solde:.2f}**", inline=True)
    embed.add_field(name="🏅 Classement", value=f"**#{classement}** sur le serveur", inline=True)
    embed.add_field(name="💵 Gains totaux (toutes sources)", value=f"**${gains_total:.2f}**", inline=True)

    # ── Daily ──
    embed.add_field(
        name="🔥 Daily streak",
        value=f"{streak_bar}\nJour **{streak}/{DAILY_MAX_STREAK}** — Dernier claim : {last_str}",
        inline=False
    )

    # ── Sondages ──
    embed.add_field(name="📊 Sondages créés", value=f"**{profil['sondages_crees']}**", inline=True)
    embed.add_field(name="🗳️ Votes donnés", value=f"**{profil['votes_donnes']}**", inline=True)
    embed.add_field(name="📥 Votes reçus", value=f"**{profil['votes_recus']}**", inline=True)

    # ── Messages ──
    embed.add_field(name="💬 Messages envoyés", value=f"**{profil['messages_envoyes']}**", inline=True)
    embed.add_field(name="\u200b", value="\u200b", inline=True)
    embed.add_field(name="\u200b", value="\u200b", inline=True)

    # ── Gambling ──
    embed.add_field(
        name="🎰 Gambling",
        value=(
            f"Parties jouées : **{s['parties_jouees']}**\n"
            f"Parties gagnées : **{s['parties_gagnees']}** ({ratio}%)\n"
            f"Gains : **${s['gains_totaux']:.2f}** | Pertes : **${s['pertes_totales']:.2f}**\n"
            f"Bilan net : **${s['gains_totaux'] - s['pertes_totales']:.2f}**"
        ),
        inline=False
    )

    await interaction.response.send_message(embed=embed)

@tree.command(name="steamgratuit", description="Affiche les jeux gratuits à 100% sur Steam !")
async def steamgratuit(interaction: discord.Interaction):
    await interaction.response.defer()
    async with aiohttp.ClientSession() as session:
        async with session.get(
            "https://store.steampowered.com/search/results/",
            params={"specials": "1", "maxprice": "free", "json": "1", "count": "50"},
            headers={"User-Agent": "Mozilla/5.0"}
        ) as resp:
            data = await resp.json(content_type=None)
    embed = discord.Embed(title="🎮 Jeux gratuits à 100% sur Steam !", color=discord.Color.blue())
    found = 0
    for item in data.get("items", []):
        nom = item.get("name", "Inconnu")
        app_id = item.get("id")
        lien = f"https://store.steampowered.com/app/{app_id}"
        embed.add_field(name=f"🎁 {nom}", value=f"[Voir sur Steam]({lien})", inline=False)
        found += 1
    if found == 0:
        embed.description = "😢 Aucun jeu gratuit à 100% trouvé en ce moment !"
    await interaction.followup.send(embed=embed)

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

@tree.command(name="instructions", description="Affiche les instructions d'un jeu !")
@discord.app_commands.describe(jeu="Le jeu dont tu veux les instructions")
@discord.app_commands.choices(jeu=[
    discord.app_commands.Choice(name="Blackjack", value="blackjack"),
    discord.app_commands.Choice(name="Roulette", value="roulette"),
    discord.app_commands.Choice(name="Ride the Bus", value="ridethebus"),
    discord.app_commands.Choice(name="Slots", value="slots"),
    discord.app_commands.Choice(name="Poker", value="poker"),
    discord.app_commands.Choice(name="Course de chevaux", value="course"),
])
async def instructions(interaction: discord.Interaction, jeu: str):
    embeds = {
        "blackjack": discord.Embed(title="🃏 Instructions - Blackjack", color=discord.Color.green())
            .add_field(name="But", value="Avoir une main la plus proche de 21 sans dépasser !", inline=False)
            .add_field(name="Comment jouer", value="• `/blackjack [mise]` pour jouer solo\n• `/blackjack2 [mise] [membre]` pour jouer contre quelqu'un", inline=False)
            .add_field(name="Cartes", value="• J/Q/K = 10 points\n• As = 1 ou 11 points\n• Autres = valeur nominale", inline=False)
            .add_field(name="Actions", value="• **Hit** = Prendre une carte\n• **Stand** = Rester avec ta main", inline=False)
            .add_field(name="Gains", value="• Gagné = mise x2\n• Égalité = mise remboursée\n• Perdu = mise perdue", inline=False),
        "roulette": discord.Embed(title="🎰 Instructions - Roulette", color=discord.Color.gold())
            .add_field(name="But", value="Parier sur la bonne couleur ou parité du numéro !", inline=False)
            .add_field(name="Comment jouer", value="• `/roulette [mise]` pour lancer une partie\n• Tout le monde parie, l'hôte lance", inline=False)
            .add_field(name="Paris disponibles", value="• **Rouge** = numéros rouges\n• **Noir** = numéros noirs\n• **Pair** = numéros pairs\n• **Impair** = numéros impairs", inline=False)
            .add_field(name="Gains", value="• Gagné = mise x2\n• Perdu = mise perdue\n• 0 = tout le monde perd", inline=False),
        "ridethebus": discord.Embed(title="🚌 Instructions - Ride the Bus", color=discord.Color.purple())
            .add_field(name="But", value="Survivre aux 4 étapes pour multiplier ta mise !", inline=False)
            .add_field(name="Comment jouer", value="• `/ridethebus [mise]` pour commencer", inline=False)
            .add_field(name="Étapes", value="• **Étape 1** = Rouge ou Noir ?\n• **Étape 2** = Plus haute ou plus basse ?\n• **Étape 3** = Inside ou Outside ?\n• **Étape 4** = Quelle couleur (♠️♥️♦️♣️) ?", inline=False)
            .add_field(name="Gains", value="• Chaque bonne réponse = gains x1.5\n• Étape 4 réussie = gains x2\n• Cash Out à tout moment pour sécuriser tes gains !", inline=False),
        "slots": discord.Embed(title="🎰 Instructions - Slots", color=discord.Color.gold())
            .add_field(name="But", value="Aligner des symboles identiques pour gagner !", inline=False)
            .add_field(name="Comment jouer", value="• `/slots [mise]` pour lancer", inline=False)
            .add_field(name="Gains", value="• 3x 💎 = mise x10 (Jackpot Diamant !)\n• 3x 7️⃣ = mise x5 (Triple 7 !)\n• 3x autre = mise x3 (Jackpot !)\n• 2 identiques = mise remboursée\n• Rien = mise perdue", inline=False),
        "poker": discord.Embed(title="🃏 Instructions - Poker Texas Hold'em", color=discord.Color.green())
            .add_field(name="But", value="Avoir la meilleure main de 5 cartes parmi les 7 disponibles !", inline=False)
            .add_field(name="Comment jouer", value="• `/poker [blind]` pour créer une partie (2-6 joueurs)\n• Les joueurs rejoignent et paient le blind\n• L'hôte lance la partie\n• Les cartes privées sont envoyées en DM !", inline=False)
            .add_field(name="Actions", value="• **Check** = Passer sans miser (si personne n'a misé)\n• **Suivre** = Égaler la mise courante\n• **Relancer** = Augmenter la mise\n• **Fold** = Se coucher et perdre sa mise", inline=False)
            .add_field(name="Phases", value="• **Preflop** = Cartes privées distribuées\n• **Flop** = 3 cartes communes\n• **Turn** = 4ème carte commune\n• **River** = 5ème carte commune\n• **Showdown** = Révélation automatique", inline=False)
            .add_field(name="Hiérarchie des mains", value="1. Carte haute\n2. Paire\n3. Double paire\n4. Brelan\n5. Suite\n6. Couleur\n7. Full house\n8. Carré\n9. Quinte flush\n10. Quinte flush royale 👑", inline=False)
            .add_field(name="Gains", value="• Un seul gagnant par partie — le meilleur kicker départage !\n• Si tout le monde fold sauf un, il gagne automatiquement !\n• Égalité parfaite sur tous les kickers = pot partagé (très rare)", inline=False),
        "course": discord.Embed(title="🏇 Instructions - Course de chevaux", color=discord.Color.orange())
            .add_field(name="But", value="Parier sur le bon cheval pour monter sur le podium !", inline=False)
            .add_field(name="Comment jouer", value="• `/course [mise]` pour créer une course\n• Chaque joueur choisit son cheval dans le menu\n• L'hôte lance la course", inline=False)
            .add_field(name="Chevaux", value="\n".join(CHEVAUX), inline=False)
            .add_field(name="Gains", value="• 🥇 1er place → mise x3.0\n• 🥈 2e place → mise x2.0\n• 🥉 3e place → mise x1.5\n• Hors podium → mise perdue", inline=False),
    }
    await interaction.response.send_message(embed=embeds[jeu])

@tree.command(name="daily", description="Réclame ton bonus quotidien ! (streak jusqu'à 250$/jour)")
async def daily(interaction: discord.Interaction):
    user_id = interaction.user.id
    montant, streak, status = claim_daily(user_id)

    if status == "already":
        info = get_daily_info(user_id)
        embed = discord.Embed(title="⏳ Daily déjà réclamé !", color=discord.Color.red())
        embed.add_field(name="Streak actuel", value=f"🔥 Jour {info['streak']}/{DAILY_MAX_STREAK}", inline=True)
        embed.add_field(name="Prochain daily", value="Demain !", inline=True)
        embed.add_field(name="💰 Solde", value=f"${get_solde(user_id):.2f}", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    next_streak = min(streak + 1, DAILY_MAX_STREAK)
    next_montant = DAILY_BASE + (next_streak - 1) * ((DAILY_MAX_BONUS - DAILY_BASE) // (DAILY_MAX_STREAK - 1))
    barre = "🔥" * streak + "⬜" * (DAILY_MAX_STREAK - streak)

    embed = discord.Embed(title="🎁 Daily réclamé !", color=discord.Color.gold())
    embed.add_field(name="Gains", value=f"**+${montant}**", inline=True)
    embed.add_field(name="Streak", value=f"🔥 Jour {streak}/{DAILY_MAX_STREAK}", inline=True)
    embed.add_field(name="Progression", value=barre, inline=False)
    if streak < DAILY_MAX_STREAK:
        embed.add_field(name="Demain", value=f"**+${next_montant}** si tu reviens !", inline=False)
    else:
        embed.add_field(name="Streak MAX !", value=f"🏆 Tu es au maximum — **+${DAILY_MAX_BONUS}**/jour !", inline=False)
    embed.add_field(name="💰 Solde", value=f"${get_solde(user_id):.2f}", inline=False)
    await interaction.response.send_message(embed=embed)

@tree.command(name="retirer", description="[Modo] Retire de l'argent à un membre avec un rôle moins important")
@discord.app_commands.describe(membre="Le membre ciblé", montant="Montant à retirer", raison="Raison du retrait")
async def retirer(interaction: discord.Interaction, membre: discord.Member, montant: int, raison: str = "Aucune raison fournie"):
    role_admin = discord.utils.get(interaction.guild.roles, name="Admins")
    if role_admin is None:
        await interaction.response.send_message("❌ Le rôle 'Admins' n'existe pas sur ce serveur !", ephemeral=True)
        return
    if interaction.user.top_role < role_admin:
        await interaction.response.send_message("❌ Tu dois avoir le rôle **Admins** ou supérieur pour utiliser cette commande !", ephemeral=True)
        return
    if membre.bot:
        await interaction.response.send_message("❌ Tu peux pas retirer de l'argent à un bot !", ephemeral=True)
        return
    if membre.id == interaction.user.id:
        await interaction.response.send_message("❌ Tu peux pas te retirer de l'argent à toi-même !", ephemeral=True)
        return
    if montant <= 0:
        await interaction.response.send_message("❌ Le montant doit être positif !", ephemeral=True)
        return
    solde_cible = get_solde(membre.id)
    retrait_reel = min(montant, solde_cible)
    add_solde(membre.id, -retrait_reel)
    embed = discord.Embed(title="💸 Retrait effectué par un modérateur", color=discord.Color.red())
    embed.add_field(name="Modérateur", value=interaction.user.display_name, inline=True)
    embed.add_field(name="Membre", value=membre.display_name, inline=True)
    embed.add_field(name="Montant retiré", value=f"${retrait_reel}", inline=True)
    embed.add_field(name="Raison", value=raison, inline=False)
    embed.add_field(name=f"Nouveau solde de {membre.display_name}", value=f"${get_solde(membre.id):.2f}", inline=False)
    await interaction.response.send_message(embed=embed)
    try:
        await membre.send(f"💸 **{interaction.user.display_name}** t'a retiré **${retrait_reel}**.\nRaison: {raison}\nNouveau solde: ${get_solde(membre.id):.2f}")
    except:
        pass

# =================== EVENTS ===================

@client.event
async def on_ready():
    init_db()
    try:
        guild = discord.Object(id=1458933425460482164)
        tree.copy_global_to(guild=guild)
        await tree.sync(guild=guild)
        print(f"Commandes syncées : {[cmd.name for cmd in tree.get_commands()]}")
    except Exception as e:
        print(f"Erreur sync : {e}")
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
    profile_add(message.author.id, messages=1, gains=SALAIRE_MESSAGE)
    if message.channel.name == POLES_CHANNEL and message.poll:
        if not peut_creer_sondage(message.author.id):
            # Déjà créé un sondage aujourd'hui — supprimer le message et avertir
            try:
                await message.delete()
                await message.author.send(
                    "❌ Tu as déjà créé un sondage aujourd'hui ! Tu ne peux en créer qu'**un seul par jour**."
                )
            except:
                pass
            return
        marquer_sondage_creation(message.author.id, message.id)
        add_solde(message.author.id, REWARD_SONDAGE_CREATION)
        profile_add(message.author.id, sondages=1, gains=REWARD_SONDAGE_CREATION)
        try:
            await message.author.send(
                f"📊 Sondage créé ! Tu reçois **+${REWARD_SONDAGE_CREATION}$** immédiatement.\n"
                f"Tu gagneras également **+${REWARD_SONDAGE_VOTE_CREATEUR}$** par vote à la clôture du sondage !\n"
                f"Solde actuel : **${get_solde(message.author.id):.2f}**"
            )
        except:
            pass
        await message.create_thread(name="Discussion du sondage")
        role = message.guild.get_role(ROLE_POLES_ID)
        if role:
            await message.channel.send(role.mention)

@client.event
async def on_raw_reaction_add(payload):
    guild = client.get_guild(payload.guild_id)
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
async def on_raw_poll_vote_add(payload):
    """Enregistre chaque vote sur un sondage Discord natif."""
    guild = client.get_guild(payload.guild_id)
    if not guild:
        return
    channel = guild.get_channel(payload.channel_id)
    if not channel or channel.name != POLES_CHANNEL:
        return
    user_id = payload.user_id
    poll_message_id = payload.message_id
    member = guild.get_member(user_id)
    if not member or member.bot:
        return
    if not peut_voter_sondage(poll_message_id, user_id):
        return  # Déjà enregistré ce voteur
    marquer_vote_sondage(poll_message_id, user_id)
    profile_add(user_id, votes_donnes=1)

@client.event
async def on_raw_poll_vote_remove(payload):
    """Retire l'enregistrement si quelqu'un retire son vote avant la clôture."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM poll_responses WHERE poll_message_id=%s AND user_id=%s",
        (str(payload.message_id), str(payload.user_id))
    )
    conn.commit()
    cur.close()
    conn.close()

@client.event
async def on_message_edit(before, after):
    """Détecte la clôture d'un sondage Discord (poll.is_finalized passe à True)."""
    if not after.poll:
        return
    if not after.poll.is_finalized:
        return
    if before.channel.name != POLES_CHANNEL:
        return

    poll_message_id = str(after.id)
    creator_id = get_poll_creator(poll_message_id)
    if not creator_id:
        return  # Déjà récompensé ou sondage inconnu

    voters = get_poll_voters(poll_message_id)
    nb_votes = len(voters)

    # Récompenser chaque voteur
    for uid in voters:
        add_solde(int(uid), REWARD_SONDAGE_VOTE_VOTEUR)
        profile_add(int(uid), gains=REWARD_SONDAGE_VOTE_VOTEUR)
        member = after.guild.get_member(int(uid))
        if member:
            try:
                await member.send(
                    f"✅ Le sondage s'est clôturé ! Tu reçois **+${REWARD_SONDAGE_VOTE_VOTEUR}$** pour avoir voté.\n"
                    f"Solde actuel : **${get_solde(int(uid)):.2f}**"
                )
            except:
                pass

    # Récompenser le créateur selon le nombre de votes
    gain_createur = REWARD_SONDAGE_VOTE_CREATEUR * nb_votes
    add_solde(int(creator_id), gain_createur)
    profile_add(int(creator_id), votes_recus=nb_votes, gains=gain_createur)
    marquer_sondage_recompense(poll_message_id)

    creator_member = after.guild.get_member(int(creator_id))
    if creator_member:
        try:
            await creator_member.send(
                f"🏆 Ton sondage s'est clôturé avec **{nb_votes} vote(s)** !\n"
                f"Tu reçois **+${gain_createur}$** ({nb_votes} × ${REWARD_SONDAGE_VOTE_CREATEUR}$).\n"
                f"Solde actuel : **${get_solde(int(creator_id)):.2f}**"
            )
        except:
            pass

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
