import discord, re
import dotenv, os, random, json
from discord.ext import commands, tasks
from easy_pil import Editor, load_image_async, Font
from emoji import emoji_count
import unicodedata, datetime, time
from webserver import keep_alive

EMOJI_LIMIT = 6
BANNED_WORDS = []

with open("banned-words.txt", "r") as f:
    BANNED_WORDS = f.read().split("\n")

infractions = {}

with open("infractions.json", "r") as f:
    infractions = json.load(f)

dotenv.load_dotenv()

intents = discord.Intents.default()
intents.members = True
intents.messages = True
intents.message_content = True

bot = commands.Bot(intents=intents)

async def commit_infractions():
    # with open("infractions.json", "w") as f:
    #     json.dump(infractions, f)
    pass

async def warn_member(member: discord.User | discord.Member, reason: str, message: discord.Message | None = None):
    if member.id not in infractions:
        infractions[member.id] = []

    infractions[member.id].append({
        "reason": reason,
        "message": message,
        "clears": time.time() + 24 * 3600, # 24 * 3600 is an entire day in seconds
        "instanciated": time.time(),
        "cleared": False
    })

    await commit_infractions()

    embed = discord.Embed(
        title=f"[WARN] {member.name}"
    )

    embed.add_field(
        name="Reason",
        value=reason
    )

    if message:
        embed.add_field(
            name="Meesage",
            value=message.content
        )

    logs_channel = member.guild.get_channel(int(os.getenv("LOGS_CHANNEL", "")))

    await logs_channel.send(embed=embed)

    # Check if punishment is needed
    # len(...) + 1 is needed because len is used for indexes, and indexes start at 0, not 1.
    if len(infractions[member.id]) + 1 == 5:
        await member.timeout_for(duration=datetime.timedelta(days=1), reason="5 infractions (warns) reached")

    if len(infractions[member.id]) + 1 == 3:
        await member.timeout_for(duration=datetime.timedelta(hours=1), reason="3 infractions (warns) reached")

    if len(infractions[member.id]) + 1 == 3 or len(infractions[member.id]) + 1 == 5:    
        embed = discord.Embed(
            title=f"[TIMEOUT] {member.name}"
        )
        embed.add_field(
            name="Reason",
            value=f"Member reached {len(infractions[member.id]) + 1} warns"
        )
        await logs_channel.send(embed=embed)

def is_zalgo_text(text):
    """
    Check if the given text contains Zalgo text.
    """
    for char in text:
        if unicodedata.combining(char):
            return True
    return False

async def create_welcome_image(member: discord.Member):
    background = Editor("welcome-bg.png")
    bold_font = Font.poppins(size=20, variant="bold")
    regular_font = Font.poppins(size=12, variant="regular")

    avatar = Editor(await load_image_async(str(member.avatar.url))).resize((70, 70)).circle_image()

    background.paste(avatar, (50, 40))

    background.text((270, 57), f"{member.display_name} has joined!", bold_font, color="white", align="center")
    background.text((270, 85), f"You are member #{member.guild.member_count}", regular_font, color="white", align="center")

    file = discord.File(background.image_bytes, filename="welcome.jpg")

    await member.guild.get_channel(int(os.getenv("WELCOME_CHANNEL", ""))).send(f"Hey {member.mention}, welcome to **The Sound Cloud**!!!! Be sure to read the rules in #info-rules before joining in on the fun!", file=file)


@bot.event
async def on_ready():
    print("Clouve is afloat!")
    check_infractions.start()
    # await bot.sync_commands()

@bot.event
async def on_member_join(member: discord.Member):
    print(f"Member joined: {member.display_name}")

    await create_welcome_image(member)

async def process_message(message: discord.Message):
    content = message.content

    # Remove spoilers
    content = content.replace("||", "")

    if is_zalgo_text(content):
        await message.delete(reason="Zalgo usage")
        embed = discord.Embed(
            description="**Hey! Zalgo usage in messages is not permitted here.**"
        )
        await message.channel.send(f"{message.author.mention}", embed=embed)
        await warn_member(message.author, "Zalgo usage", message)
        return

    contains_banned_word = False
    for word in BANNED_WORDS:
        if word.lower() in content.lower():
            contains_banned_word = True
            break

    if contains_banned_word:
        await message.delete(reason="Banned word")
        embed = discord.Embed(
            description="**Warned: Message contains a blocked word**"
        )
        await message.channel.send(f"{message.author.mention}", embed=embed)
        await warn_member(message.author, "Banned word", message)
        return

    content = message.clean_content
    content = content.replace("||", "")

    if content.startswith("!bigboombu"):
        embed = discord.Embed(
            description=random.choice(["Big Boombu approves", "Big Boombu disapproves"])
        )
        embed.set_image(url="https://cdn-longterm.mee6.xyz/plugins/commands/images/845918445220659200/888236f2f8498c9d92111ee733936b9a29b0de61161479afcdcc6558532dc280.png")
        await message.channel.send(embed=embed)
        return

    count = emoji_count(content) + len(re.findall(r'<:[^:<>]*:[^:<>]*>', content)) # thank you ChatGPT for the RegeX ^_^
    if count > EMOJI_LIMIT:
        await message.delete(reason="Emoji Spam")
        embed = discord.Embed(
            description=f"**Hey! You can only send {EMOJI_LIMIT} emojis in one message.**"
        )
        await message.channel.send(f"{message.author.mention}", embed=embed)
        await warn_member(message.author, "Emoji spam", message)


@bot.event
async def on_message(message: discord.Message):
    await process_message(message)

@bot.event
async def on_message_edit(before: discord.Message, after: discord.Message):
    await process_message(after)

@bot.event
async def on_member_remove(member: discord.Member):
    await member.guild.get_channel(int(os.getenv("WELCOME_CHANNEL", ""))).send(f"{member.mention} has left the server. Kinda freaky NGL")

@bot.event
async def on_member_update(before: discord.Member, after: discord.Member):
    old_nick = before.nick
    new_nick = after.nick
    if old_nick == new_nick:
        return
    embed = discord.Embed(
        title=f"[Nick Change] {after.name}",
        description=f"{old_nick} :arrow_forward: {new_nick}"
    )
    logs_channel = after.guild.get_channel(int(os.getenv("LOGS_CHANNEL", "")))
    await logs_channel.send(embed=embed)

@tasks.loop(seconds=5)
async def check_infractions():
    for userID in infractions.keys():
        infractions[userID] = [x for x in infractions[userID] if time.time() < x["clears"]]

    await commit_infractions()

@bot.slash_command(name="infractions", description="View the infractions (warns) for a specific member")
@discord.option(
    "member",
    description="The member whose infractions you want to view",
    required=True
)
@discord.default_permissions(moderate_members=True)
async def list_infractions(ctx: discord.ApplicationContext, member: discord.Member):
    embed = discord.Embed(
        title=f"Infractions for {member.name}"
    )

    if member.id in infractions:
        for infraction in infractions[member.id]:
            embed.add_field(
                name=infraction["reason"],
                value=f"Expires in {time.strftime('%H:%M:%S', time.gmtime(infraction['clears'] - time.time()))}s"
            )
    else:  
        embed.description = "Nothing found"

    await ctx.respond(embed=embed)

@bot.slash_command(name="unmute", description="Unmutes (untimeouts) a member if they were timed out")
@discord.option(
    "member",
    description="The member whose infractions you want to view",
    required=True
)
@discord.default_permissions(moderate_members=True)
async def unmute(ctx: discord.ApplicationContext, member: discord.Member):
    embed = discord.Embed()
    if member.timed_out:
        await member.remove_timeout(reason="Moderator removed timeout")
        embed.description = f"**Unmuted {member.mention}**"
    else:
        embed.description = "**Member was not muted**"
    await ctx.respond(embed=embed)

@bot.slash_command(name="resync", descripton="Resyncs commands")
@discord.default_permissions(manage_guild=True)
async def resync(ctx: discord.ApplicationContext):
    await bot.sync_commands()
    await ctx.respond(embed=discord.Embed(
        description="**Resync sucessful**"
    ))

# https://guide.pycord.dev/extensions/commands/help-command
class MyHelp(commands.HelpCommand):
    async def send_bot_help(self, mapping):
        embed = discord.Embed(title="Help")
        for cog, commands in mapping.items():
           command_signatures = [self.get_command_signature(c) for c in commands]
           if command_signatures:
                cog_name = getattr(cog, "qualified_name", "No Category")
                embed.add_field(name=cog_name, value="\n".join(command_signatures), inline=False)

        channel = self.get_destination()
        await channel.send(embed=embed)

    async def send_error_message(self, error):
        embed = discord.Embed(title="Error", description=error, color=discord.Color.red())
        channel = self.get_destination()

        await channel.send(embed=embed)

bot.help_command = MyHelp()

keep_alive()
bot.run(os.getenv("BOT_TOKEN"))