import discord, \
    json, \
    os, \
    time, \
    requests, \
    datetime, \
    random, \
    re, \
    dotenv

dotenv.load_dotenv()

from discord.ext import commands, tasks
from . import checks
from .checks import WarnReason, EMOJI_LIMIT


if not os.path.exists("warns.json"):
    with open("warns.json", "w") as f:
        json.dump({}, f)



class Moderation(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.infractions = {}
        self.gearbot = 349977940198555660

        self.check_infractions.start()

    async def process_message(self, message: discord.Message):
        content = message.content

        # Remove spoilers
        content = content.replace("||", "")

        if content.startswith("!bigboombu"):
            embed = discord.Embed(
                description=random.choice(["Big Boombu approves", "Big Boombu approves", "Big Boombu disapproves"])
            )
            file = discord.File("boombu.png", filename="boombu.png")
            embed.set_image(url="attachment://boombu.png")
            await message.channel.send(file=file, embed=embed)

        if message.author.bot or message.author.id == self.gearbot:
            return
        
        if message.author.id == self.bot.user.id:
            return
        
        storm_role = discord.utils.find(lambda r: r.id == 845918904940232725, message.author.guild.roles)
        if storm_role in message.author.roles:
            return
        
        # Check for zalgo content
        # if self.is_zalgo_text(content):
        #     embed = discord.Embed(
        #         description=f"**{self.string_for_warn_reason(WarnReason.ZALGO)}**"
        #     )
        #     await message.channel.send(f"{message.author.mention}", embed=embed)
        #     await self.warn_member(message.author, WarnReason.ZALGO, message)
        #     return
        
        warn_checks = [
            checks.banned_word_bypasses,
            checks.banned_word_normalization,
            checks.banned_word_punctuation,
            checks.banned_word_raw,
            checks.emoji_check,
            checks.advertisements
        ]

        result: tuple[bool, WarnReason] | None = None
        for check in warn_checks:
            check_result = await check(message.content, message.clean_content, message.channel.id)
            if check_result[0]:
                result = check_result
                break

        if result is not None:
            embed = discord.Embed(
                description=f"**{self.string_for_warn_reason(result[1])}**"
            )
            await message.channel.send(f"{message.author.mention}", embed=embed)
            await self.warn_member(message.author, result[1], message)
            return
        
        content = message.clean_content
        content = content.replace("||", "")
        # print(content)

    # events
    @discord.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or message.author.id == self.gearbot:
            return
        
        if message.author.id == self.bot.user.id:
            return

        await self.process_message(message)

    @discord.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if after.author.bot or after.author.id == self.gearbot:
            return
        
        if after.author.id == self.bot.user.id:
            return
            
        await self.process_message(after)

    @discord.Cog.listener()
    async def on_ready(self):
        self.log_channel = self.bot.get_channel(int(os.getenv("LOGS_CHANNEL", "")))

    @discord.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        old_nick = before.nick
        new_nick = after.nick
        if old_nick == new_nick:
            return
        embed = discord.Embed(
            title=f"[Nick Change] {after.name}",
            description=f"{old_nick} :arrow_forward: {new_nick}"
        )
        await self.log_channel.send(embed=embed)

    @tasks.loop(seconds=5)
    async def check_infractions(self):
        for userID in self.infractions.keys():
            self.infractions[userID] = [x for x in self.infractions[userID] if time.time() < x["clears"]]

        await self.commit_infractions()

    # commands
    @discord.slash_command(name="infractions", description="View the infractions (warns) for a specific member")
    @discord.option(
        "member",
        description="The member whose infractions you want to view",
        required=True
    )
    @discord.default_permissions(moderate_members=True)
    async def list_infractions(self, ctx: discord.ApplicationContext, member: discord.Member):
        embed = discord.Embed(
            title=f"Infractions for {member.name}"
        )

        if str(member.id) in self.infractions:
            for infraction in self.infractions[str(member.id)]:
                embed.add_field(
                    name=infraction["reason"],
                    value=f"Expires in {time.strftime('%H:%M:%S', time.gmtime(infraction['clears'] - time.time()))}s"
                )
        else:  
            embed.description = "Nothing found"

        await ctx.respond(embed=embed)

    @discord.slash_command(name="unmute", description="Unmutes (untimeouts) a member if they were timed out")
    @discord.option(
        "member",
        description="The member whose infractions you want to view",
        required=True
    )
    @discord.default_permissions(moderate_members=True)
    async def unmute(self, ctx: discord.ApplicationContext, member: discord.Member):
        embed = discord.Embed()
        if member.timed_out:
            await member.remove_timeout(reason="Moderator removed timeout")
            embed.description = f"**Unmuted {member.mention}**"
        else:
            embed.description = "**Member was not muted**"
        await ctx.respond(embed=embed)

    @discord.slash_command(name="purge", description="Deletes a bulk amount of commands", guilds=[os.getenv("GUILD_ID", "")])
    @discord.option(
        "count",
        description="The amount of messages to delete",
        required=True
    )
    @discord.default_permissions(moderate_members=True)
    async def purge(self, ctx: discord.ApplicationContext, count: int):
        await ctx.channel.purge(limit=count)
        await ctx.respond(embed=discord.Embed(description=f"**Succesfully purged {count} messages**"))

    @discord.slash_command(name="clear_warns", description="Clears infractions (warns) on a member", guilds=[os.getenv("GUILD_ID", "")])
    @discord.option(
        "member",
        description="The member whose infractions you want to remove",
        required=True
    )
    @discord.default_permissions(moderate_members=True)
    async def clear_warns(self, ctx: discord.ApplicationContext, member: discord.Member):
        del self.infractions[str(member.id)]
        await ctx.respond(embed=discord.Embed(description=f"**Succesfully cleared the warns on {member.name}**"))

    def load_infractions(self):
        with open("warns.json", "r") as f:
            if f.read() == "":
                self.infractions = {}
                return
            
            self.infractions = json.load(f)

    def extract_invite_id(self, text):
        # Define regex pattern to match Discord invite links
        pattern = r'(?:https?://)?(?:www\.)?(?:discord\.(?:com|gg)/invite/|discord\.gg/)([a-zA-Z0-9]+)'
        # Search for the pattern in the input text
        match = re.search(pattern, text)
        if match:
            # Extract and return the invite ID
            return match.group(1)
        else:
            return None
        
    def is_zalgo_text(self, text):
        """
        Check if the given text contains Zalgo text.
        """
        # if text == "( ͡° ͜ʖ ͡°)": #     T  H  E   L  E  N  N  Y   O  V  E  R  R  I  D  E
        #     return False
        # for char in text:
        #     if unicodedata.combining(char):
        #         return True
        return False


    async def commit_infractions(self):
        with open("warns.json", "w") as f:
            json.dump(self.infractions, f, indent=4)

    async def warn_member(self, member: discord.User | discord.Member, reason: WarnReason, message: discord.Message | None = None):
        if message:
            await message.delete(reason=self.string_for_warn_reason(reason))
        
        if str(member.id) not in self.infractions:
            self.infractions[str(member.id)] = []

        self.infractions[str(member.id)].append({
            "reason": self.string_for_warn_reason(reason),
            "message": message.id,
            "clears": time.time() + 24 * 3600, # 24 * 3600 is an entire day in seconds
            "instanciated": time.time(),
            "cleared": False,
            "channel": message.channel.id
        })

        await self.commit_infractions()
        await self.log_channel.send(embed=await self.create_log_embed(member, reason, message))
        await member.send(embed=await self.create_user_embed(reason, message))
        await self.check_user_standing(member)

    async def check_user_standing(self, member: discord.User | discord.Member):
        timed_out = False

        if len(self.infractions[str(member.id)]) == 5:
            await member.timeout_for(duration=datetime.timedelta(days=1), reason="5 infractions (warns) reached")
            timed_out = True

        if len(self.infractions[str(member.id)]) == 3:
            await member.timeout_for(duration=datetime.timedelta(hours=1), reason="3 infractions (warns) reached")
            timed_out = True

        if timed_out:    
            embed = discord.Embed(
                title=f"[TIMEOUT] {member.name}"
            )
            embed.add_field(
                name="Reason",
                value=f"Member reached {len(self.infractions[str(member.id)])} warns"
            )
            await self.log_channel.send(embed=embed)

    async def create_log_embed(self, member: discord.User | discord.Member, reason: WarnReason, message: discord.Message | None = None):
        embed = discord.Embed(
            title=f"[WARN] {member.nick or member.display_name} (`{member.name}`)"
        )

        embed.add_field(
            name="Reason",
            value=self.string_for_warn_reason(reason),
            inline=False
        )

        embed.add_field(
            name="Message",
            value=message.content,
            inline=False   
        )

        embed.add_field(
            name="Member",
            value=member.mention,
            inline=False
        )

        embed.add_field(
            name="Channel",
            value=message.channel.mention,
            inline=False
        )

        if reason is WarnReason.DISCORD_LINK:
            invite_id = self.extract_invite_id(message.content)
            invite_guild = requests.get(f"https://discordapp.com/api/v6/invites/{invite_id}").json()

            embed.add_field(
                name="Invited server name",
                value=f"{invite_guild['guild']['name']}",
                inline=False
            )

        return embed

    async def create_user_embed(self, reason: WarnReason, message: discord.Message | None = None):
        user_embed = discord.Embed(
            title="You were warned in the Sound Cloud",
            description="Future warns could impact your standing in the server"
        )
        user_embed.add_field(
            name="Offending content",
            value=message.content,
            inline=False   
        )
        user_embed.add_field(
            name="Channel",
            value=f"{message.channel.mention}",
            inline=False
        )
        user_embed.add_field(
            name="Reason",
            value=self.string_for_warn_reason(reason),
            inline=False
        )

        return user_embed

    def string_for_warn_reason(self, reason: WarnReason):
        match (reason):
            case WarnReason.BANNED_WORD: return "The message contained a banned phrase"
            case WarnReason.ZALGO: return "The message contained zalgo content, which may make the chat unreadable"
            case WarnReason.DISCORD_LINK: return "The message contained a Discord invite link where it is not permitted. These should go in the adverts channel"
            case WarnReason.EMOJI: return f"The message exceeded the emoji limit of {EMOJI_LIMIT}."

def setup(bot):
    bot.add_cog(Moderation(bot))
