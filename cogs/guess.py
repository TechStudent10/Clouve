from operator import itemgetter
import discord, os, json, random, asyncio, time
from discord.ext import commands, tasks
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

GUESSING_JSON_PATH = os.path.join(os.getcwd(), "guessing.json")

if not os.path.exists(GUESSING_JSON_PATH):
    with open(GUESSING_JSON_PATH, "w") as f:
        json.dump({
            "members": {}
        }, f, indent=4)

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
        self.current_channel_id = 0
        self.still_guessing: dict[int, bool] = {}
        self.current_levels: dict[int | None, dict] = {}
        self._diff: dict[int, str] = {}
        self.current_streak: dict[int, dict[str, int]] = {}

        self.user_guessing_data: dict[str, dict[str, dict[str, int]]] = {}

        self.current_contexts: dict[int, discord.ApplicationContext | None] = {}

        for ch_id in os.getenv("GUESSING_CHANNEL", "").split(","):
            self.still_guessing[int(ch_id)] = False
            self.current_contexts[int(ch_id)] = None
            self._diff[int(ch_id)] = ""
            self.current_streak[int(ch_id)] = {
                "member": 0,
                "length": 0
            }

        self.in_command = False

        self.start_times = {}

        self.load_levels()
        self.load_user_guessing_data()
        self.assure_time_ended.start()

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

    def load_user_guessing_data(self):
        with open(GUESSING_JSON_PATH, "r") as f:
            self.user_guessing_data = json.load(f)

    @tasks.loop(seconds=5)
    async def assure_time_ended(self):
        print("this should work every 5 seconds")
        for channel_id in self.start_times:
            start_time = self.start_times[channel_id]
            if time.time() - start_time >= 30:
                self.reset(channel_id)
                self.bot.get_channel(channel_id).send(
                    embed=discord.Embed(
                        description="**The game has been auto-reset! You may now get back to guessing!**"
                    )
                )
                print(f"i can't believe it... {'a game hasnt started yet' if start_time == 0 else 'it broke'}...")

    async def process_answer_for_exp(self, member: discord.Member | discord.User, diff: int, correct: bool, channel_id: int):
        if str(member.id) not in self.user_guessing_data["members"]:
            self.user_guessing_data["members"][str(member.id)] = {
                "member_id": member.id,
                "exp": 0,
                "total_answers": 0,
                "correct_answers": 0
            }

        current_member = self.user_guessing_data["members"][str(member.id)]

        if correct:
            current_member["correct_answers"] += 1
            exp_awarded = 0
            match diff:
                case 1:
                    exp_awarded = 1
                case 2:
                    exp_awarded = 3
                case 3:
                    exp_awarded = 5
                case 4:
                    exp_awarded = 10
            
            streak_bonus = 1
            if self.current_streak[channel_id]["length"] > 1:
                streak_bonus = 1 + self.current_streak[channel_id]["length"] / 10
            
            current_member["exp"] += round(exp_awarded * streak_bonus)

        current_member["total_answers"] += 1

        self.user_guessing_data["members"][str(member.id)] = current_member
        await self.commit_guessing_data()
    
    async def commit_guessing_data(self):
        with open(GUESSING_JSON_PATH, "w") as f:
            json.dump(self.user_guessing_data, f)

    @discord.slash_command(
        name="profile", description="View the guessing profile for a specific member!", guild_ids=[
            int(os.getenv("GUILD_ID", ""))
        ]
    )
    @discord.option(
        "member",
        description="The member whose profile you want to view",
        required=True
    )
    async def view_profile(self, ctx: discord.ApplicationContext, member: discord.Member):
        if str(member.id) not in self.user_guessing_data["members"]:
            await ctx.respond(f"**Member {member.name} has not made guesses in level guessing.**")
            return
        
        current_member = self.user_guessing_data["members"][str(member.id)]
        embed = discord.Embed(
            title=f"Profile for {member.name}"
        )
        if member.id != self.bot.user.id:
            embed.add_field(
                name="**EXP**",
                value=f"**{current_member['exp']}** EXP",
                inline=False
            )
            embed.add_field(
                name="**Completion Rate**",
                value=f"**{round(int(current_member['correct_answers']) / int(current_member['total_answers']) * 100)}%**",
                inline=False
            )
            embed.add_field(
                name="**Correct Guesses**",
                value=f"**{current_member['correct_answers']}**",
                inline=True
            )
            embed.add_field(
                name="**Total Guesses**",
                value=f"**{current_member['total_answers']}**",
                inline=True
            )
        else:
            embed.add_field(
                name="**Total Questions Asked (Estimate)**",
                value=f"**{current_member['total_answers']}**",
                inline=False
            )
        await ctx.respond(embed=embed)

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
        if str(ctx.channel_id) not in os.getenv("GUESSING_CHANNEL", "").split(","):
            await ctx.respond(f"**Level guessing is disabled in channels besides <#{os.getenv('GUESSING_CHANNEL')}>. Please go there for level guessing.**", ephemeral=True)
            return

        # if self.in_command:
        #     return
        # self.in_command = True
        if self.still_guessing[ctx.channel.id]:
            await ctx.respond("**Level guessing already in progress. Please try again later.**", ephemeral=True)
            return 
        
        self.start_times[ctx.channel.id] = time.time()

        self.current_contexts[ctx.channel.id] = ctx
        self._diff[ctx.channel.id] = _diff

        if _diff == "Random":
            difficulty = DIFFICULTIES[random.choice(list(DIFFICULTIES.keys()))]
        else:
            difficulty = DIFFICULTIES[_diff]
        
        levels = self.levels[str(difficulty)]
        lvl = random.choice(levels)
        lvl["id"] = random.randint(0, 1000)
        self.current_levels[ctx.channel_id] = lvl

        self.current_channel_id = ctx.channel_id

        current_level = lvl

        embed = discord.Embed(
            title="Guess the level!",
            description=f"Difficulty: {REVERSE_DIFFICULTIES[difficulty]}"
        )
        embed.set_footer(text="Ping Clouve with your answer to guess!")
        file_path = os.path.join(os.getcwd(), "guess", "levels", current_level["name"], current_level["file"])
        if "v2" in current_level:
            if current_level["v2"]:
                file_path = os.path.join(os.getcwd(), "guess", "levels-v2", str(current_level["diff"]), current_level["name"], current_level["file"])

        image = discord.File(file_path, "file.png")
        embed.set_image(url="attachment://file.png")
        self.still_guessing[ctx.channel.id] = True
        og_msg = await ctx.respond(embed=embed, file=image)

        await asyncio.sleep(30.0)
        if self.still_guessing[ctx.channel.id] == False:
            return
        
        if self.current_levels[ctx.channel.id]["id"] != lvl["id"]:
            return

        command = self.guess
        outer_self = self

        class RestartView(discord.ui.View):
            @discord.ui.button(label="Start new game", style=discord.ButtonStyle.gray)
            async def new_game(self, button: discord.Button, interaction: discord.Interaction):
                if outer_self.still_guessing[ctx.channel.id]:
                    await interaction.respond("**Guessing in still progess!**", ephemeral=True)
                    return
                
                await ctx.invoke(command, _diff=_diff)

        await ctx.send(embed=discord.Embed(
            description="**You didn't respond in time!**"
        ), view=RestartView())
        self.current_streak[ctx.channel.id] = {
            "member": 0,
            "length": 0
        }

        self.reset(ctx.channel.id)

    @discord.slash_command(
        name="leaderboard", description="View the level guessing leaderboard!", guild_ids=[
            int(os.getenv("GUILD_ID", ""))
        ]
    )
    async def view_leaderboard(self, ctx: discord.ApplicationContext):
        embed = discord.Embed(
            title="Level Guessing Leaderboard"
        )
        members = self.user_guessing_data["members"]
        unordered_list = list(members.values())
        sorted_list = sorted(unordered_list, key=itemgetter("exp"), reverse=True)
        top_ten = sorted_list[:10]
        for member_i in range(len(top_ten)):
            member = top_ten[member_i]
            if member['member_id'] == self.bot.user.id:
                continue

            embed.add_field(
                name=f"",
                value=f"""**{member_i + 1}.** <@{member['member_id']}> **{member['exp']}** EXP
Completion Rate: **{round(member['correct_answers'] / member['total_answers'] * 100)}**%
{member['correct_answers']} Correct / {member['total_answers']} Total""",
                inline=False
            )

        await ctx.respond(embed=embed)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        is_answer = False
        if str(message.channel.id) not in os.getenv("GUESSING_CHANNEL", "").split(","):
            print("did not pass channel check")
            return

        if not self.still_guessing[message.channel.id]:
            print("not self.guessing")
            return
        
        if message.channel.id not in self.current_levels:
            return
        
        if self.current_contexts[message.channel.id] is None:
            return

        # # long and complex way to check if it's a reply to a Clouve message
        if message.reference is not None and not message.is_system() and message.reference.cached_message.author.id == self.bot.user.id:
            is_answer = True
        
        if self.bot.user.mention in message.content:
            is_answer = True
        
        
        if not is_answer:
            return

        answer = message.content.replace(self.bot.user.mention, "").lstrip()
        
        is_correct = False

        current_level = self.current_levels[message.channel.id]
        if current_level is None:
            return

        if answer.lower() == current_level["name"].lower():
            is_correct = True
            command = self.guess
            ctx = self.current_contexts[message.channel.id]
            _diff = self._diff[message.channel.id]

            if self.current_streak[message.channel.id]["member"] == message.author.id:
                self.current_streak[message.channel.id]["length"] += 1
            elif self.current_streak[message.channel.id]["member"] != message.author.id:
                self.current_streak[message.channel.id]["member"] = message.author.id
                self.current_streak[message.channel.id]["length"] = 1

            print(json.dumps(self.current_streak[message.channel.id], indent=4))

            outer_self = self
            class RestartView(discord.ui.View):
                @discord.ui.button(label="Start new game", style=discord.ButtonStyle.gray)
                async def new_game(self, button: discord.Button, interaction: discord.Interaction):
                    if outer_self.still_guessing[ctx.channel.id]:
                        await interaction.respond("**Guessing in still progess!**", ephemeral=True)
                        return
                    
                    await ctx.invoke(command, _diff=_diff)

            streak_str = '\nYou are on a {length}X streak!'.format(length=self.current_streak[message.channel.id]['length']) if self.current_streak[message.channel.id]['length'] > 1 else ''

            await message.channel.send(f"{message.author.mention}", embed=discord.Embed(
                description=f"**Correct! The answer was \"{current_level['name']}\"{streak_str}**"
            ), view=RestartView())
            
            try:
                await self.process_answer_for_exp(message.author, current_level["diff"], is_correct, message.channel.id)
            except TypeError:
                print("haha no")
            self.reset(message.channel.id)

        try:
            await self.process_answer_for_exp(message.author, current_level["diff"], is_correct, message.channel.id)
        except TypeError:
            print("haha no")

    @discord.slash_command(
        name="reset_game", description="[MODERATOR ONLY] Only use command when bot breaks", guild_ids=[
            int(os.getenv("GUILD_ID", ""))
        ]
    )
    @discord.default_permissions(moderate_members=True)
    async def reset_game(self, ctx: discord.ApplicationContext):
        debug_info = f"""```current_levels: {json.dumps(self.current_levels, indent=4)}
current_channel_id: {self.current_channel_id}
still_guessing: {json.dumps(self.still_guessing, indent=4)}
current_contexts: {json.dumps(self.current_contexts, indent=4)}
_diff: {json.dumps(self._diff, indent=4)}
start_times: {json.dumps(self.start_times, indent=4)}
time.time() - start_time: {time.time() - self.start_times[ctx.channel.id]}
time.time() - start_time >= 30: {time.time() - self.start_times[ctx.channel.id] >= 30}
```"""
        self.reset(ctx.channel.id)

        await ctx.respond(
            f"<@851210524254928907>\n\nDebug Info: \n{debug_info}\n**Game successfully reset**"
        )

    def reset(self, channel_id: int):
        self.current_levels[channel_id] = {}
        self.current_channel_id = 0
        self.still_guessing[channel_id] = False
        self.current_contexts[channel_id] = None
        self._diff[channel_id] = ""
        self.start_times[channel_id] = 0

def setup(bot):
    bot.add_cog(Guess(bot))
