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
MESSAGE_ID_POLES = 1499077252384559145
MESSAGE_ID_2 = 1499587568856203295
ROLE_POLES_ID = 1499196527728398437
ROLE_MEMBRE_ID = 1459044281368182884
ROLE_2_ID = 1499581112983359549

blackjack_games = {}

def nouvelle_carte():
    cartes = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]
    return random.choice(cartes)

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

    @discord.ui.button(label="Bust 💥", style=discord.ButtonStyle.gray)
    async def bust(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ C'est pas ta partie !", ephemeral=True)
            return
        if self.user_id in blackjack_games:
            del blackjack_games[self.user_id]
        self.stop()
        embed = discord.Embed(title="🃏 Blackjack - Bust !", description="💥 **Tu as abandonné la partie !**", color=discord.Color.gray())
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
    embed.add_field(name="🃏 /blackjack", value="Joue au blackjack (Hit/Stand/Bust)", inline=False)
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
