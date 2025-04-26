import discord
import dotenv, os, random
from discord.ext import commands, tasks
from easy_pil import Editor, load_image_async, Font
import datetime

dotenv.load_dotenv()

RESPONSES = []
CLOUVE_SELFMUTE_PREFIX = "[CLOUVE USER-REQUESTED SELF MUTE]"

with open("responses.txt", "r") as f:
    RESPONSES = f.read().split("\n")

intents = discord.Intents.default()
intents.members = True
intents.messages = True
intents.message_content = True

bot = commands.Bot(
    intents=intents,
    activity=discord.Activity(type=discord.ActivityType.watching, name="The Sound Cloud"),
    status=discord.Status.do_not_disturb
)

async def create_welcome_image(member: discord.Member):
    background = Editor("welcome-bg.png")
    bold_font = Font.poppins(size=20, variant="bold")
    smaller_bold_font = Font.poppins(size=15, variant="bold")
    regular_font = Font.poppins(size=12, variant="regular")

    text_x = 250
    if member.avatar:
        text_x = 270
        avatar = Editor(await load_image_async(str(member.avatar.url))).resize((70, 70)).circle_image()

        background.paste(avatar, (50, 40))

    background.text((text_x, 57), f"{member.name} has joined!", bold_font if len(member.name) <= 20 else smaller_bold_font, color="white", align="center")
    background.text((text_x, 85), f"You are member #{member.guild.member_count}", regular_font, color="white", align="center")

    file = discord.File(background.image_bytes, filename="welcome.jpg")

    await member.guild.get_channel(int(os.getenv("WELCOME_CHANNEL", ""))).send(f"Hey {member.mention}, welcome to **The Sound Cloud**!!!! Be sure to read the rules in <#845930016449232898> before joining in on the fun!", file=file)


@bot.event
async def on_ready():
    print("Clouve is afloat!")
    tech_logs_channel = bot.get_channel(int(os.getenv("TECH_LOGS", "")))
    await tech_logs_channel.send(embed=discord.Embed(description="**Clouve is afloat! Bot is up and running!**"))
    # await bot.sync_commands()

@bot.event
async def on_member_join(member: discord.Member):
    print(f"Member joined: {member.display_name}")

    await create_welcome_image(member)

@bot.event
async def on_member_remove(member: discord.Member):
    await member.guild.get_channel(int(os.getenv("WELCOME_CHANNEL", ""))).send(f"{member.mention} ({member.name}) has left the server. Kinda freaky NGL...........")

@tasks.loop(minutes=30)
async def update_status():
    # why does this line exist, commented
    # if bot.user.display_name != "Clouve Testing": return

    statuses = []
    with open("statuses.txt", "r") as f:
        statuses = f.read().split("\n")
    
    bot.activity = discord.Activity(type=discord.ActivityType.custom, name=random.choice(statuses))

# Added by Skittey
@bot.slash_command(name="user", description="Gives information about a user.")
@discord.option(
    "member",
    description="User to get information about",
    required=True
)
async def user(ctx, member: discord.Member):
    target_user=member

    embed=discord.Embed(
        title=target_user.name
    )
    if target_user.avatar:
        embed.set_thumbnail(url=str(target_user.avatar.url))
    embed.add_field(name='Joined Discord on', value=target_user.created_at.strftime("%a %b %d %Y"), inline=False)
    embed.add_field(name=f'Joined {ctx.guild.name} on', value=target_user.joined_at.strftime("%a %b %d %Y"), inline=False)
    embed.add_field(name='User ID', value=str(target_user.id), inline=False)
    embed.add_field(name=f'Roles [{len(target_user.roles)}]', value=', '.join([role.name for role in target_user.roles]), inline=False)
    embed.set_footer(text='User Information')
    embed.timestamp=datetime.datetime.now()

    await ctx.respond(embed=embed)

@bot.slash_command(name="avatar", description="Shows a user\'s avatar.")
@discord.option(
    "member",
    description="User to get the avatar from",
    required=True
)
async def avatar(ctx, member: discord.Member):
    target_user=member

    embed=discord.Embed(
        title=f'{target_user.name}\'s Avatar'
    )
    if target_user.avatar:
        embed.set_image(url=str(target_user.avatar.url))
    embed.set_footer(text='User Avatar')
    embed.timestamp=datetime.datetime.now()

    await ctx.respond(embed=embed)

@bot.slash_command(name="server", description="Gives information about this server.")
async def server(ctx):
    server=ctx.guild

    embed=discord.Embed(
        title=server.name
    )
    if server.icon:
        embed.set_thumbnail(url=str(server.icon.url))
    embed.add_field(name='Owner', value=f'<@{server.owner.id}>', inline=False)
    embed.add_field(name='Created on', value=server.created_at.strftime("%a %b %d %Y"), inline=False)
    embed.add_field(name='Members', value=server.member_count, inline=False)
    embed.add_field(name=f'Server ID', value=server.id, inline=False)
    embed.add_field(name='Channels', value=str(len(server.channels)))
    embed.set_footer(text='Server Information')
    embed.timestamp=datetime.datetime.now()

    await ctx.respond(embed=embed)
# End of commands added by Skittey

@bot.slash_command(name="selfmute", description="Mute yourself (for whatever reason)", guild_ids=[
    int(os.getenv("GUILD_ID", ""))
])
async def disabled_selfmute(ctx):
   await ctx.respond(embed=discord.Embed(description="**Selfmute has been disabled!**"))

#@discord.option("duration", parameter_name="duration_str")
async def selfmute(ctx: discord.ApplicationContext, duration_str: str):
    multipliers = {
        "s": 1,
        "m": 60,
        "h": 3600,
        "d": 3600 * 24,
        "w": 3600 * 24 * 7,
        # "m": 3600 * 24 * 7 * 30,
        "y": 3600 * 24 * 7 * 30 * 12
    }

    duration_list = list(duration_str)
    multiplier = duration_list.pop().lower()
    try:
        duration_sec = int(
            "".join(duration_list)
        ) * multipliers[multiplier]
    except IndexError:
        await ctx.respond("**Invalid time multiplier. Please use `s, m, h, d, w, or y`**")

    if duration_sec > 2 * multipliers["d"]:
        responses = [
            "im not doing that",
            # "are you stupid?? a year??",
            "Dude, what",
            "Are you sure you won't leave the server before then?",
            "Do you need rehab?",
            "You are absolutely not okay bro",
            "For HOW long now?!?!",
            "If you want to be muted THAT long,, leave the sevrer. do it. i DARE you.",
            "no what",
            "why do you want this",
            "i understand having silly ideas, but no.",
            "why are you like this",
            "listen, im just gonna be blunt, absolutely goddamn not.",
            "if you wanna be muted for that long just leave forever never come back",
            "ik youre addicted to this place you couldnt survive this lol",
            "i dont think i can even mute people for 2 days how do you expect me to do this",
            """why im not gonna do this
1. its stupid
2. i literally cant do that
3. just leave if you want to be muted for that long""",
            "<:boarsplode:1034281725750153267>",
            "<:ayo:988904731588067368>"
        ]
        await ctx.respond(random.choice(responses))
        return
    
    await ctx.author.timeout_for(datetime.timedelta(seconds=duration_sec), reason=f"{CLOUVE_SELFMUTE_PREFIX} This timeout was requested bu this member.")
    await ctx.respond(embed=discord.Embed(
        description="Succesfully timed you out!"
    ))

# STOP. TONGUE. REACTING.
@bot.event
async def on_reaction_remove(reaction: discord.Reaction, user: discord.Member):
    if reaction.emoji == "👅":
        tech_logs_channel = bot.get_channel(int(os.getenv("TECH_LOGS", "")))
        await tech_logs_channel.send(embed=discord.Embed(
            title="Uh-Oh! Someone tongue reacted!",
            description=f"Have we found our tongue reactor?\n\nChannel: <#{reaction.message.channel.id}>\nUser: <@{user.id}>\nMessage: {reaction.message.jump_url}"
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

# keep_alive()
cogs = [
    "guess",
    "music",
    "moderation"
]

for cog in cogs:
    bot.load_extension(f"cogs.{cog}")

bot.run(os.getenv("BOT_TOKEN"))
