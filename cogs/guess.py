import discord, os, json, random, asyncio
from discord.ext import commands
from dataclasses import dataclass
# from dacite import from_dict

DIFFICULTIES = {
    "Easy": 1,
    "Medium": 2,
    "Hard": 3,
    "Extreme": 4
}

@dataclass
class Level:
    # Name of the level / The answer to the guess
    name: str
    # The path to the screenshot for said level
    file: str
    # Difficulty
    # 1 = Easy
    # 2 = Medium
    # 3 = Hard
    # 4 = Extreme
    diff: int

async def diff_autocomplete(ctx: discord.AutocompleteContext):
    return list(DIFFICULTIES.keys())

# group = discord.SlashCommandGroup("guess", "Guess the AudieoVisual level!", guild_ids=[
#     int(os.getenv("GUILD_ID", ""))
# ])

class Guess(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.levels: dict[str, list[dict]] = {}
        self.current_level: dict | None = None
        self.current_channel_id = 0
        self.still_guessing = False

        self.in_command = False

        self.load_levels()

    def load_levels(self):
        with open(os.path.join(os.getcwd(), "guess", "levels.json")) as f:
            self.levels: dict[str, list[dict]] = json.load(f)

    @discord.slash_command(
        name="guess", guild_ids=[
            int(os.getenv("GUILD_ID", ""))
        ]
    )
    @discord.option(
        "difficulty",
        parameter_name="_diff",
        autocomplete=diff_autocomplete
    )
    async def guess(self, ctx: discord.ApplicationContext, _diff: str):
        if self.in_command:
            return
        self.in_command = True
        if self.still_guessing:
            await ctx.respond("**Level guessing already in progress. Please try again later.**", ephemeral=True)
            return 
        
        self.still_guessing = True

        difficulty = DIFFICULTIES[_diff]
        levels = self.levels[str(difficulty)]
        lvl = random.choice(levels)
        lvl["id"] = random.randint(0, 1000)
        self.current_level = lvl

        self.current_channel_id = ctx.channel_id

        embed = discord.Embed(
            title="Guess the level!"
        )
        image = discord.File(os.path.join(os.getcwd(), "guess", "levels", self.current_level["name"], self.current_level["file"]), "file.png")
        embed.set_image(url="attachment://file.png")
        await ctx.respond(embed=embed, file=image)

        self.in_command = False

        await asyncio.sleep(45.0)
        if not self.still_guessing:
            return

        await ctx.send(embed=discord.Embed(
            description="**You didn't respond in time!**"
        ))
        self.current_level = None
        self.current_channel_id = 0
        self.still_guessing = False

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.channel.id != self.current_channel_id:
            return
        
        if self.bot.user.mention not in message.content:
            return
        
        if not self.still_guessing:
            return
        
        answer = message.content.replace(self.bot.user.mention, "").lstrip()
        if answer.lower() == self.current_level["name"].lower():
            await message.channel.send(f"{message.author.mention}", embed=discord.Embed(
                description=f"**Correct! The answer was \"{self.current_level['name']}\"**"
            ))
            self.current_level = None
            self.current_channel_id = 0
            self.still_guessing = False

def setup(bot):
    bot.add_cog(Guess(bot))
