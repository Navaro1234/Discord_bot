import os
import json
import discord
from discord.ext import commands
from google import genai
from dotenv import load_dotenv

# --- CONFIGURATIE EN BEHEERDERSGEGEVENS ---
ADMIN_USERNAME = "navaroke2512"  # Jouw exacte Discord gebruikersnaam

APPDATA_DIR = os.path.join(os.getenv("LOCALAPPDATA"), "Discord_bot")
ENV_FILE = os.path.join(APPDATA_DIR, ".env")
JSON_FILE = os.path.join(APPDATA_DIR, "chat_geschiedenis.json")

os.makedirs(APPDATA_DIR, exist_ok=True)


def configureer_env():
    if os.path.exists(ENV_FILE):
        load_dotenv(ENV_FILE)
        if os.getenv("DISCORD_TOKEN") and os.getenv("GEMINI_API_KEY"):
            return

    print("=" * 60)
    print(f"  ⚠️ GEEN CONFIGURATIE GEVONDEN IN: {APPDATA_DIR}")
    print("  Vul hieronder je gegevens in om de bot in te stellen.")
    print("=" * 60)

    discord_token = input("Plak je Discord Token en druk op Enter: ").strip()
    gemini_key = input("Plak je Google Gemini API Key en druk op Enter: ").strip()

    if not discord_token or not gemini_key:
        print("\n❌ Fout: Beide sleutels zijn verplicht!")
        exit(1)

    with open(ENV_FILE, "w", encoding="utf-8") as f:
        f.write(f"DISCORD_TOKEN={discord_token}\n")
        f.write(f"GEMINI_API_KEY={gemini_key}\n")

    print(f"\n✅ Het .env bestand is succesvol opgeslagen in:\n   {ENV_FILE}")
    print("=" * 60 + "\n")
    load_dotenv(ENV_FILE)


configureer_env()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

ai_client = genai.Client(api_key=GEMINI_API_KEY)

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="$", intents=intents)

# --- JSON GEHEUGEN EN GEBRUIKERS FUNCTIES ---
MAX_GEHEUGEN = 10


def laad_data_uit_json():
    if os.path.exists(JSON_FILE):
        try:
            with open(JSON_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if "geschiedenis" not in data: data["geschiedenis"] = {}
                if "gebruikers" not in data: data["gebruikers"] = []
                return data
        except Exception as e:
            print(f"Fout bij laden JSON, we herstarten de structuur: {e}")
    return {"geschiedenis": {}, "gebruikers": []}


def bewaar_data_in_json(data):
    try:
        with open(JSON_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Fout bij opslaan naar JSON: {e}")


def controleer_en_welkom_gebruiker(user):
    data = laad_data_uit_json()
    user_id_str = str(user.id)

    if user_id_str in data["gebruikers"]:
        return False

    data["gebruikers"].append(user_id_str)
    bewaar_data_in_json(data)
    print(f"🆕 Nieuwe gebruiker geregistreerd in JSON: {user.name} ({user_id_str})")
    return True


def voeg_toe_aan_geheugen(channel_id, rol, tekst):
    data = laad_data_uit_json()
    str_channel_id = str(channel_id)

    if str_channel_id not in data["geschiedenis"]:
        data["geschiedenis"][str_channel_id] = []

    api_rol = "user" if rol == "user" else "model"
    data["geschiedenis"][str_channel_id].append({"role": api_rol, "parts": [{"text": tekst}]})

    if len(data["geschiedenis"][str_channel_id]) > MAX_GEHEUGEN:
        data["geschiedenis"][str_channel_id].pop(0)

    bewaar_data_in_json(data)


def haal_geschiedenis_op(channel_id):
    data = laad_data_uit_json()
    return data["geschiedenis"].get(str(channel_id), [])


# HULPFUNCTIE: Knipt lange AI-antwoorden netjes op per 2000 tekens
async def stuur_lang_bericht(bestemming, tekst):
    if not tekst:
        await bestemming.send("Gemini gaf een leeg antwoord terug.")
        return
    for i in range(0, len(tekst), 1900):
        stukje = tekst[i:i + 1900]
        if isinstance(bestemming, discord.Message):
            await bestemming.reply(stukje)
        else:
            await bestemming.send(stukje)


@bot.event
async def on_ready():
    print(f'We zijn ingelogd als {bot.user}')
    print(f"Alles wordt succesvol geladen en opgeslagen in:\n-> {APPDATA_DIR}")


@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    # Controleer of het een privébericht (DM) is óf een serverkanaal
    is_dm = isinstance(message.channel, discord.DMChannel)

    # Verwerk welkomstberichten alleen in serverkanalen (niet in DM)
    if not is_dm:
        is_nieuw = controleer_en_welkom_gebruiker(message.author)
        if is_nieuw:
            await message.channel.send(
                f"👋 Hallo {message.author.mention}! Ik had je nog niet eerder gezien. Welkom bij de bot! Typ `$vraag` of tag me via `@Aap` om met me te praten.")

    # 1. Je originele handmatige reacties
    if message.content.lower() == 'ping':
        await message.reply('pong')
        return
    elif message.content.lower() == '/admin':
        await message.reply('navaroke2512 is de admin. Land = :flag_be:.')
        return
    elif 'lief' in message.content.lower():
        await message.add_reaction('🗑️')

    # 2. Reageren als de bot wordt getagd met @Aap óf als je in DM rechtstreeks praat
    if bot.user in message.mentions or is_dm:
        # Als het een DM is hoef je de bot niet te taggen, dus halen we de tag alleen weg als die er staat
        schone_tekst = message.content.replace(f'<@{bot.user.id}>', '').strip()

        # Voorkom dat de bot reageert op commando's die met $ beginnen in DM
        if schone_tekst.startswith("$"):
            await bot.process_commands(message)
            return

        if not schone_tekst:
            await message.reply("Waar kan ik je vandaag mee helpen?")
            return

        async with message.channel.typing():
            try:
                voeg_toe_aan_geheugen(message.channel.id, "user", schone_tekst)
                volledige_geschiedenis = haal_geschiedenis_op(message.channel.id)

                response = ai_client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=volledige_geschiedenis,
                    config={
                        "system_instruction": f"Je bent een behulpzame Discord-assistent genaamd Aap. Je praat nu met {message.author.name}. Antwoord beknopt waar mogelijk."
                    }
                )

                voeg_toe_aan_geheugen(message.channel.id, "model", response.text)
                await stuur_lang_bericht(message, response.text)

            except Exception as e:
                print(f"!!! GEMINI FOUTMELDING !!!: {e}")
                await message.channel.send("Er is een fout opgetreden bij het praten met Google Gemini.")
        return

    await bot.process_commands(message)


# --- EXCLUSIEF ADMIN COMMANDO (ALLEEN IN DM VOOR NAVAROKE2512) ---

@bot.command()
async def stats(ctx):
    """Toont botstatistieken. Werkt alleen in DM voor de beheerder."""
    # Controle 1: Is het een privéchat?
    if not isinstance(ctx.channel, discord.DMChannel):
        await ctx.reply("❌ Dit commando kan om veiligheidsredenen alleen in een privéchat (DM) worden gebruikt.")
        return

    # Controle 2: Ben jij het wel echt?
    if ctx.author.name != ADMIN_USERNAME:
        await ctx.reply("🔒 Je hebt geen toestemming om dit commando te gebruiken.")
        return

    # Gegevens ophalen uit de JSON
    data = laad_data_uit_json()
    aantal_gebruikers = len(data.get("gebruikers", []))
    aantal_kanalen = len(data.get("geschiedenis", {}))

    embed = discord.Embed(title="📊 Aap Bot Statistieken", color=discord.Color.blue())
    embed.add_field(name="Totaal geregistreerde gebruikers", value=f"👤 {aantal_gebruikers}", inline=False)
    embed.add_field(name="Kanalen met actieve geschiedenis", value=f"💬 {aantal_kanalen}", inline=False)
    embed.add_field(name="Opslaglocatie", value=f"📂 `{JSON_FILE}`", inline=False)

    await ctx.send(embed=embed)


@bot.command()
async def clear(ctx):
    """Wist de opgeslagen chatgeschiedenis in de JSON voor dit kanaal"""
    data = laad_data_uit_json()
    str_channel_id = str(ctx.channel.id)

    if str_channel_id in data["geschiedenis"]:
        del data["geschiedenis"][str_channel_id]
        bewaar_data_in_json(data)
        await ctx.reply("🧹 Het chatgeheugen voor dit kanaal is gewist uit de JSON!")
    else:
        await ctx.reply("Er was nog geen geschiedenis opgeslagen voor dit kanaal.")


# Start de bot
bot.run(DISCORD_TOKEN)
