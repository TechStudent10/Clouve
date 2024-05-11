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

REVERSE_DIFFICULTIES = {
    1: "Easy",
    2: "Medium",
    3: "Hard",
    4: "Extreme"
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
    return ["Random"] + list(DIFFICULTIES.keys())

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
        if str(ctx.channel_id) != os.getenv("GUESSING_CHANNEL"):
            await ctx.respond(f"**Level guessing is disabled in channels besides <#{os.getenv('GUESSING_CHANNEL')}>. Please go there for level guessing.**", ephemeral=True)
            return

        # if self.in_command:
        #     return
        # self.in_command = True
        if self.still_guessing:
            await ctx.respond("**Level guessing already in progress. Please try again later.**", ephemeral=True)
            return 
        

        if _diff == "Random":
            difficulty = DIFFICULTIES[random.choice(list(DIFFICULTIES.keys()))]
        else:
            difficulty = DIFFICULTIES[_diff]
        
        levels = self.levels[str(difficulty)]
        lvl = random.choice(levels)
        lvl["id"] = random.randint(0, 1000)
        self.current_level = lvl

        self.current_channel_id = ctx.channel_id

        class RestartView(discord.ui.View):
            @discord.ui.button(label="Start new game", style=discord.ButtonStyle.gray)
            async def new_game(self, button: discord.Button, interaction: discord.Interaction):
                pass


        embed = discord.Embed(
            title="Guess the level!",
            description=f"Difficulty: {REVERSE_DIFFICULTIES[difficulty]}"
        )
        embed.set_footer(text="Ping Clouve with your answer to guess!")
        image = discord.File(os.path.join(os.getcwd(), "guess", "levels", self.current_level["name"], self.current_level["file"]), "file.png")
        embed.set_image(url="attachment://file.png")
        self.still_guessing = True
        og_msg = await ctx.respond(embed=embed, file=image)

        await asyncio.sleep(25.0)
        if self.still_guessing == False:
            return
        
        if self.current_level["id"] != lvl["id"]:
            return

        await ctx.send(embed=discord.Embed(
            description="**You didn't respond in time!**"
        ))
        self.current_level = None
        self.current_channel_id = 0
        self.still_guessing = False

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        is_answer = False
        if message.channel.id != self.current_channel_id:
            return
            
        if not self.still_guessing:
            return
        
        if self.current_level is None:
            return
        
        # long and complex way to check if it's a reply to a Clouve message
        if message.reference is not None and not message.is_system() and message.reference.cached_message.author.id == self.bot.user.id:
            is_answer = True
        
        if self.bot.user.mention in message.content:
            is_answer = True
        
        
        if not is_answer:
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
