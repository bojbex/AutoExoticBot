import os
import discord
from discord.ext import commands
from discord import app_commands
from flask import Flask
from threading import Thread

# Keep-alive server
app = Flask('')

@app.route('/')
def home():
    return "Bot is running!"

def keep_alive():
    Thread(target=lambda: app.run(host='0.0.0.0', port=8080)).start()

TOKEN = os.environ.get("TOKEN")
GUILD_ID = int(os.environ.get("GUILD_ID"))
AKTIVITA_CHANNEL_ID = int(os.environ.get("AKTIVITA_CHANNEL_ID"))

intents = discord.Intents.default()
intents.members = True
client = commands.Bot(command_prefix="!", intents=intents)

user_scores = {}

def has_role(interaction: discord.Interaction, role_name: str):
    return any(role.name == role_name for role in interaction.user.roles)

def has_vedeni_role(interaction):
    return has_role(interaction, "Vedení")

def has_zamestnanec_role(interaction):
    return has_role(interaction, "Zaměstnanec")

@client.event
async def on_ready():
    await client.wait_until_ready()
    try:
        synced = await client.tree.sync(guild=discord.Object(id=GUILD_ID))
        print(f"✅ Slash příkazy synchronizovány: {len(synced)}")
    except Exception as e:
        print(f"❌ Chyba při synchronizaci: {e}")

# --- Slash příkazy ---

@client.tree.command(name="omluvenka", description="Odešli omluvenku", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(od="Datum OD", do="Datum DO", ic_duvod="Důvod (IC)", ooc_duvod="Důvod (OOC)")
async def omluvenka(interaction: discord.Interaction, od: str, do: str, ic_duvod: str, ooc_duvod: str):
    if not has_zamestnanec_role(interaction):
        await interaction.response.send_message("❌ Tento příkaz může použít jen role 'Zaměstnanec'.", ephemeral=True)
        return

    embed = discord.Embed(title="📘 Omluvenka", color=discord.Color.blue())
    embed.add_field(name="👤 Uživatel", value=interaction.user.mention, inline=False)
    embed.add_field(name="📅 Od", value=od, inline=True)
    embed.add_field(name="📅 Do", value=do, inline=True)
    embed.add_field(name="🎭 IC Důvod", value=ic_duvod, inline=False)
    embed.add_field(name="🧠 OOC Důvod", value=ooc_duvod, inline=False)

    await interaction.channel.send(embed=embed)
    await interaction.response.send_message("✅ Omluvenka byla zaznamenána zde v kanálu.", ephemeral=True)

@client.tree.command(name="aktivita", description="Zaznamenej svou aktivitu", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(od="Od kdy jsi aktivní", do="Do kdy jsi aktivní")
async def aktivita(interaction: discord.Interaction, od: str, do: str):
    log_channel = client.get_channel(AKTIVITA_CHANNEL_ID)
    if not log_channel:
        await interaction.response.send_message("❌ Kanál pro logování aktivity nebyl nalezen.", ephemeral=True)
        return

    embed = discord.Embed(title="📋 Aktivita", color=discord.Color.green())
    embed.add_field(name="👤 Uživatel", value=interaction.user.mention, inline=False)
    embed.add_field(name="📅 Od", value=od, inline=True)
    embed.add_field(name="📅 Do", value=do, inline=True)

    await log_channel.send(embed=embed)
    await interaction.response.send_message("✅ Tvoje aktivita byla zaznamenána.", ephemeral=True)

@client.tree.command(name="strike", description="Udělí hráči strike", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(user="Komu udělit strike")
async def strike(interaction: discord.Interaction, user: discord.Member):
    if not has_vedeni_role(interaction):
        await interaction.response.send_message("❌ Tento příkaz může použít jen role 'Vedení'.", ephemeral=True)
        return

    uid = str(user.id)
    user_scores.setdefault(uid, {"strike": 0, "pochvala": 0})
    if user_scores[uid]["pochvala"] > 0:
        user_scores[uid]["pochvala"] -= 1
    elif user_scores[uid]["strike"] < 3:
        user_scores[uid]["strike"] += 1
    await interaction.response.send_message(f"⚠️ {user.mention} má striky: {user_scores[uid]['strike']}/3, pochvaly: {user_scores[uid]['pochvala']}/3")

@client.tree.command(name="pochvala", description="Udělí hráči pochvalu", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(user="Komu udělit pochvalu")
async def pochvala(interaction: discord.Interaction, user: discord.Member):
    if not has_vedeni_role(interaction):
        await interaction.response.send_message("❌ Tento příkaz může použít jen role 'Vedení'.", ephemeral=True)
        return

    uid = str(user.id)
    user_scores.setdefault(uid, {"strike": 0, "pochvala": 0})
    if user_scores[uid]["strike"] > 0:
        user_scores[uid]["strike"] -= 1
    elif user_scores[uid]["pochvala"] < 3:
        user_scores[uid]["pochvala"] += 1
    await interaction.response.send_message(f"👍 {user.mention} má pochvaly: {user_scores[uid]['pochvala']}/3, striky: {user_scores[uid]['strike']}/3")

@client.tree.command(name="stav", description="Zobrazí stav striků a pochval", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(user="(pouze pro Vedení) zobrazit stav jiného člena")
async def stav(interaction: discord.Interaction, user: discord.Member = None):
    if user and not has_vedeni_role(interaction):
        await interaction.response.send_message("❌ Jen role 'Vedení' může kontrolovat ostatní.", ephemeral=True)
        return

    target = user if user else interaction.user
    uid = str(target.id)
    user_scores.setdefault(uid, {"strike": 0, "pochvala": 0})
    await interaction.response.send_message(f"📊 {target.mention}: Striky {user_scores[uid]['strike']}/3, Pochvaly {user_scores[uid]['pochvala']}/3", ephemeral=True)

@client.tree.command(name="stavvsechny", description="Zobrazí stav všech členů", guild=discord.Object(id=GUILD_ID))
async def stavvsechny(interaction: discord.Interaction):
    if not has_vedeni_role(interaction):
        await interaction.response.send_message("❌ Tento příkaz může použít jen role 'Vedení'.", ephemeral=True)
        return

    if not user_scores:
        await interaction.response.send_message("📭 Nikdo zatím nemá strike ani pochvalu.")
        return

    message = "📋 Přehled všech členů:\n"
    for uid, data in user_scores.items():
        user = await client.fetch_user(int(uid))
        message += f"👤 {user.name} – Striky: {data['strike']}/3, Pochvaly: {data['pochvala']}/3\n"
    await interaction.response.send_message(message)

# Spuštění
keep_alive()
client.run(TOKEN)


