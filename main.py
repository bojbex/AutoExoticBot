import os
import discord
from discord.ext import commands
from discord import app_commands
from flask import Flask
from threading import Thread
from datetime import datetime

# Web server pro udržení bota naživu
app = Flask('')

@app.route('/')
def home():
    return "Bot is running!"

def keep_alive():
    Thread(target=lambda: app.run(host='0.0.0.0', port=8080)).start()

# Načti tokeny a ID serveru
TOKEN = os.environ.get("TOKEN")
GUILD_ID = int(os.environ.get("GUILD_ID"))
OMLUVENKA_CHANNEL_ID = int(os.environ.get("OMLUVENKA_CHANNEL_ID"))
AKTIVITA_CHANNEL_ID = int(os.environ.get("AKTIVITA_CHANNEL_ID"))

intents = discord.Intents.default()
intents.members = True
client = commands.Bot(command_prefix="!", intents=intents)

user_scores = {}
user_activity_minutes = {}

# Role kontrola
def has_role(interaction: discord.Interaction, role_name: str):
    return any(role.name == role_name for role in interaction.user.roles)

def has_vedeni_role(interaction):
    return has_role(interaction, "Vedení")

def has_zamestnanec_role(interaction):
    return has_role(interaction, "Zaměstnanec")

# Při spuštění
@client.event
async def on_ready():
    await client.wait_until_ready()
    try:
        synced = await client.tree.sync(guild=discord.Object(id=GUILD_ID))
        print(f"✅ Slash příkazy synchronizovány: {len(synced)}")
    except Exception as e:
        print(f"❌ Chyba při synchronizaci: {e}")

# Omluvenka
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

    await interaction.response.send_message("✅ Omluvenka byla zaznamenána.", ephemeral=True)

    channel = client.get_channel(OMLUVENKA_CHANNEL_ID)
    if channel:
        await channel.send(embed=embed)

# Aktivita
@client.tree.command(name="aktivita", description="Zaznamenej aktivitu ve formátu HH:MM", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(od="Čas začátku (HH:MM)", do="Čas konce (HH:MM)")
async def aktivita(interaction: discord.Interaction, od: str, do: str):
    try:
        time_format = "%H:%M"
        od_time = datetime.strptime(od, time_format)
        do_time = datetime.strptime(do, time_format)

        if od_time >= do_time:
            await interaction.response.send_message("❌ Čas 'OD' musí být dříve než 'DO'.", ephemeral=True)
            return

        delta = do_time - od_time
        minutes = int(delta.total_seconds() // 60)

        uid = str(interaction.user.id)
        user_activity_minutes[uid] = user_activity_minutes.get(uid, 0) + minutes

        embed = discord.Embed(title="📗 Aktivita", color=discord.Color.green())
        embed.add_field(name="👤 Uživatel", value=interaction.user.mention, inline=False)
        embed.add_field(name="⏱️ Čas", value=f"{od} – {do}", inline=True)
        embed.add_field(name="🕒 Doba", value=f"{minutes} minut", inline=True)
        embed.add_field(name="📊 Celkem", value=f"{user_activity_minutes[uid]} minut", inline=False)

        await interaction.response.send_message("✅ Aktivita zaznamenána.", ephemeral=True)

        channel = client.get_channel(AKTIVITA_CHANNEL_ID)
        if channel:
            await channel.send(embed=embed)

    except ValueError:
        await interaction.response.send_message("❌ Nesprávný formát času. Použij HH:MM.", ephemeral=True)

# Strike
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

# Pochvala
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

# Stav
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

# Stav všech
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

# Aktivita všech
@client.tree.command(name="aktivita_všichni", description="Zobrazí celkovou aktivitu všech členů", guild=discord.Object(id=GUILD_ID))
async def aktivita_vsech(interaction: discord.Interaction):
    if not has_vedeni_role(interaction):
        await interaction.response.send_message("❌ Tento příkaz může použít jen role 'Vedení'.", ephemeral=True)
        return

    if not user_activity_minutes:
        await interaction.response.send_message("📭 Zatím nebyla zaznamenána žádná aktivita.", ephemeral=True)
        return

    message = "📊 **Celková aktivita všech členů:**\n"
    for uid, minutes in user_activity_minutes.items():
        user = await client.fetch_user(int(uid))
        message += f"👤 {user.name}: {minutes} minut\n"

    await interaction.response.send_message(message, ephemeral=True)

# Start bota
keep_alive()
client.run(TOKEN)

