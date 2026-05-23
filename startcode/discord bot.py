import discord
from discord.ext import commands
from google import genai  # De officiële Google GenAI bibliotheek

# Vul hier jouw eigen sleutels in
GEMINI_API_KEY = "AIzaSyDKBwwb20vWo4SxPKt_5zlmTIC1pZRtn54"
DISCORD_TOKEN = "MTUwNzczODgyOTYwNjYyMTM1Ng.G3d43t.FC562J81URNYNrVqSO96cJoCudcdfshvKW0SG4"

# Initialiseer de Google Gemini client
ai_client = genai.Client(api_key=GEMINI_API_KEY)

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="$", intents=intents)


@bot.event
async def on_ready():
    print(f'We zijn ingelogd als {bot.user}')


@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    # Jouw originele commando's en reacties
    if message.content.lower() == 'ping':
        await message.reply('pong')
    elif message.content.lower() == '/admin':
        await message.reply('navaroke2512 is de admin. Land = :flag_be:.')
    elif 'lief' in message.content.lower():
        await message.add_reaction('🗑️')

    # Zorgt ervoor dat het $vraag commando hieronder blijft werken
    await bot.process_commands(message)


# --- HIER IS HET GRATIS AI COMMANDO ---

@bot.command()
async def vraag(ctx, *, bericht: str):
    """Typ $vraag [jouw bericht] om gratis met Gemini te praten"""
    async with ctx.typing():
        try:
            # We gebruiken het snelle en gratis 'gemini-1.5-flash' model
            response = ai_client.models.generate_content(
                model='gemini-1.5-flash',
                contents=bericht,
                config=genai.types.GenerateContentConfig(
                    system_instruction="Je bent een behulpzame Discord-assistent."
                )
            )

            # Stuur het antwoord terug naar Discord
            await ctx.reply(response.text)

        except Exception as e:
            await ctx.send("Er is een fout opgetreden bij het praten met Google Gemini.")
            print(f"Foutmelding: {e}")


# Start de bot
bot.run(DISCORD_TOKEN)
