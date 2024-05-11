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
        self._diff = 0

        self.current_context: discord.ApplicationContext | None = None

        self.in_command = False

        self.load_levels()

    def load_levels(self):
        with open(os.path.join(os.getcwd(), "guess", "levels.json")) as f:
            self.levels: dict[str, list[dict]] = json.load(f)
        
        levels_v2_path = os.path.join(os.getcwd(), "guess", "levels-v2")
        for intdiff in os.listdir(levels_v2_path):
            levels_of_diff = os.listdir(os.path.join(levels_v2_path, intdiff))
            for levelname in levels_of_diff:
                files = os.listdir(os.path.join(levels_v2_path, intdiff, levelname))
                for filename in files:
                    self.levels[str(intdiff)].append({
                        "name": levelname,
                        "file": filename,
                        "diff": int(intdiff),
                        "v2": True
                    })

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
        

        self.current_context = ctx
        self._diff = _diff

        if _diff == "Random":
            difficulty = DIFFICULTIES[random.choice(list(DIFFICULTIES.keys()))]
        else:
            difficulty = DIFFICULTIES[_diff]
        
        levels = self.levels[str(difficulty)]
        lvl = random.choice(levels)
        lvl["id"] = random.randint(0, 1000)
        self.current_level = lvl

        self.current_channel_id = ctx.channel_id



        embed = discord.Embed(
            title="Guess the level!",
            description=f"Difficulty: {REVERSE_DIFFICULTIES[difficulty]}"
        )
        embed.set_footer(text="Ping Clouve with your answer to guess!")
        file_path = os.path.join(os.getcwd(), "guess", "levels", self.current_level["name"], self.current_level["file"])
        if "v2" in self.current_level:
            if self.current_level["v2"]:
                file_path = os.path.join(os.getcwd(), "guess", "levels-v2", str(self.current_level["diff"]), self.current_level["name"], self.current_level["file"])

        image = discord.File(file_path, "file.png")
        embed.set_image(url="attachment://file.png")
        self.still_guessing = True
        og_msg = await ctx.respond(embed=embed, file=image)

        await asyncio.sleep(25.0)
        if self.still_guessing == False:
            return
        
        if self.current_level["id"] != lvl["id"]:
            return

        command = self.guess

        class RestartView(discord.ui.View):
            @discord.ui.button(label="Start new game", style=discord.ButtonStyle.gray)
            async def new_game(self, button: discord.Button, interaction: discord.Interaction):
                await ctx.invoke(command, _diff=_diff)

        await ctx.send(embed=discord.Embed(
            description="**You didn't respond in time!**"
        ), view=RestartView())

        self.reset()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        is_answer = False
        if message.channel.id != self.current_channel_id:
            return

        if not self.still_guessing:
            return
        
        if self.current_level is None:
            return
        
        if self.current_context is None:
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
            command = self.guess
            ctx = self.current_context
            _diff = self._diff

            class RestartView(discord.ui.View):
                @discord.ui.button(label="Start new game", style=discord.ButtonStyle.gray)
                async def new_game(self, button: discord.Button, interaction: discord.Interaction):
                    await ctx.invoke(command, _diff=_diff)

            await message.channel.send(f"{message.author.mention}", embed=discord.Embed(
                description=f"**Correct! The answer was \"{self.current_level['name']}\"**"
            ), view=RestartView())
            
            self.reset()

    @discord.slash_command(
        name="reset_game", description="[MODERATOR ONLY] Only use command when bot breaks", guild_ids=[
            int(os.getenv("GUILD_ID", ""))
        ]
    )
    @discord.default_permissions(moderate_members=True)
    async def reset_game(self, ctx: discord.ApplicationContext):
        self.reset()
        await ctx.respond(
            "**Game successfully reset**"
        )

    def reset(self):
        self.current_level = None
        self.current_channel_id = 0
        self.still_guessing = False
        self.current_context = None
        self._diff = ""

def setup(bot):
    bot.add_cog(Guess(bot))
