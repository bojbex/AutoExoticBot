import os
import json
import discord
from discord.ext import commands
from discord import app_commands
from flask import Flask
from threading import Thread
from datetime import datetime

# 🔁 Funkce pro JSON
def load_activity():
    path = "aktivita_data.json"
    if not os.path.exists(path):
        print("ℹ️ Soubor neexistuje, inicializuji nový.")
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = f.read().strip()
            if not data:
                print("⚠️ Soubor je prázdný, inicializuji nový.")
                return {}
            return json.loads(data)
    except (json.JSONDecodeError, OSError) as e:
        print(f"❌ Chyba při načítání JSON: {e}")
        return {}

def save_activity(data):
    with open("aktivita_data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# 🌐 Web pro keep_alive
app = Flask('')

@app.route('/')
def home():
    return "Bot is running!"

def keep_alive():
    Thread(target=lambda: app.run(host='0.0.0.0', port=8080)).start()

# 📦 ENV načtení
TOKEN = os.environ.get("TOKEN")
GUILD_ID = int(os.environ.get("GUILD_ID"))
OMLUVENKA_CHANNEL_ID = int(os.environ.get("OMLUVENKA_CHANNEL_ID"))
AKTIVITA_CHANNEL_ID = int(os.environ.get("AKTIVITA_CHANNEL_ID"))

# 🤖 Discord client
intents = discord.Intents.default()
intents.members = True
client = commands.Bot(command_prefix="!", intents=intents)

user_scores = {}
user_activity_minutes = load_activity()

# 🧾 Role check
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

# 📘 Omluvenka
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

# 📗 Aktivita
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
        save_activity(user_activity_minutes)

        member = interaction.guild.get_member(interaction.user.id)
        display_name = member.display_name if member else interaction.user.name

        embed = discord.Embed(title="📗 Aktivita", color=discord.Color.green())
        embed.add_field(name="👤 Uživatel", value=display_name, inline=False)
        embed.add_field(name="⏱️ Čas", value=f"{od} – {do}", inline=True)
        embed.add_field(name="🕒 Doba", value=f"{minutes} minut", inline=True)
        embed.add_field(name="📊 Celkem", value=f"{user_activity_minutes[uid]} minut", inline=False)

        await interaction.response.send_message("✅ Aktivita zaznamenána.", ephemeral=True)

        channel = client.get_channel(AKTIVITA_CHANNEL_ID)
        if channel:
            await channel.send(embed=embed)

    except ValueError:
        await interaction.response.send_message("❌ Nesprávný formát času. Použij HH:MM.", ephemeral=True)

# 📋 Aktivita všech
@client.tree.command(name="aktivita_všichni", description="Zobrazí celkovou aktivitu všech", guild=discord.Object(id=GUILD_ID))
async def aktivita_vsech(interaction: discord.Interaction):
    if not has_vedeni_role(interaction):
        await interaction.response.send_message("❌ Tento příkaz může použít jen role 'Vedení'.", ephemeral=True)
        return

    if not user_activity_minutes:
        await interaction.response.send_message("📭 Zatím není zaznamenána žádná aktivita.")
        return

    message = "📊 Aktivita všech členů:\n"
    for uid, minutes in sorted(user_activity_minutes.items(), key=lambda x: -x[1]):
        member = interaction.guild.get_member(int(uid))
        name = member.display_name if member else f"ID {uid}"
        message += f"👤 {name}: {minutes} minut\n"

    await interaction.response.send_message(message)

# ⚠️ Strike / Pochvala / Stav
user_scores = {}

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
@app_commands.describe(user="(volitelné) Jiný člen")
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

# ▶️ Spuštění
keep_alive()
client.run(TOKEN)
