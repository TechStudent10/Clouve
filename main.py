import discord, re, requests, getpass
import dotenv, os, random, json, sys, traceback
from discord.ext import commands, tasks
from easy_pil import Editor, load_image_async, Font
from emoji import emoji_count
import unicodedata, datetime, time, atexit

dotenv.load_dotenv(dotenv_path=".env")

# logging
# if not int(os.getenv("DEBUG", "0")):
#     log_folder_path = os.path.join(os.getcwd(), "logs")
#     if not os.path.exists(log_folder_path):
#         os.mkdir(log_folder_path)

#     # https://stackoverflow.com/questions/17866724/python-logging-print-statements-while-having-them-print-to-stdout
#     class Tee(object):
#         def __init__(self, *files):
#             self.files = files
#         def write(self, obj):
#             for f in self.files:
#                 f.write(obj)
#         def flush(self, *args, **kwagrs):
#             for f in self.files:
#                 f.close()

#     file_path = os.path.join(log_folder_path, f"{datetime.datetime.today().strftime('%Y-%m-%d %H %M %S')}.log")
#     file = open(file_path, "w")
#     latest_file = open(os.path.join(log_folder_path, "latest.log"), "w")
#     latest_file.write("")
#     sys.stdout = Tee(file, sys.stdout, latest_file)
#     print(f"redirecting stdout to \"{file_path}\"")

#     # def exit_handler():
#     #     print("program exit! closing log file!")
#     #     latest_file.close()
#     #     file.close()
    
#     # atexit.register(exit_handler)

if not os.path.exists("warns.json"):
    with open("warns.json", "w") as f:
        json.dump({}, f)

EMOJI_LIMIT = 6
BANNED_WORDS = []

WORD_BYPASSES = {
    "0": [
        "o"
    ],
    "1": [
        "i"
    ],
    "2": [
        "z"
    ],
    "3": [
        "m",
        "w",
        "e"
    ],
    "4": [
        "h",
        "y",
        "a"
    ],
    "5": [
        "s"
    ],
    "6": [
        "g",
        "b"
    ],
    "7": [
        "t"
    ],
    "8": [
        "x",
        "b"
    ],
    "9": [
        "g",
        "j",
        "p"
    ]
}

RESPONSES = []

with open("responses.txt", "r") as f:
    RESPONSES = f.read().split("\n")

with open("banned-words.txt", "r") as f:
    BANNED_WORDS = f.read().split("\n")


intents = discord.Intents.default()
intents.members = True
intents.messages = True
intents.message_content = True

bot = commands.Bot(
    intents=intents,
    activity=discord.Activity(type=discord.ActivityType.watching, name="The Sound Cloud"),
    status=discord.Status.do_not_disturb
)

infractions = {}

with open("warns.json", "r") as f:
    infractions = json.load(f)

async def commit_infractions():
    # print(infractions)
    with open("warns.json", "w") as f:
        json.dump(infractions, f, indent=4)
    # pass

def extract_invite_id(text):
    # Define regex pattern to match Discord invite links
    pattern = r'(?:https?://)?(?:www\.)?(?:discord\.(?:com|gg)/invite/|discord\.gg/)([a-zA-Z0-9]+)'
    # Search for the pattern in the input text
    match = re.search(pattern, text)
    if match:
        # Extract and return the invite ID
        return match.group(1)
    else:
        return None

async def warn_member(member: discord.User | discord.Member, reason: str, message: discord.Message | None = None):
    if message:
        await message.delete(reason=reason)
    
    if str(member.id) not in infractions:
        infractions[str(member.id)] = []

    infractions[str(member.id)].append({
        "reason": reason,
        "message": message.id,
        "clears": time.time() + 24 * 3600, # 24 * 3600 is an entire day in seconds
        "instanciated": time.time(),
        "cleared": False,
        "channel": message.channel.id
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
            name="Message",
            value=message.content
        )

    embed.add_field(
        name="Member",
        value=f"{member.mention}"
    )
    embed.add_field(
        name="Channel",
        value=f"{message.channel.mention}"
    )

    print(message.content)
    if extract_invite_id(message.content):
        invite_id = extract_invite_id(message.content)
        invite_guild = requests.get(f"https://discordapp.com/api/v6/invites/{invite_id}").json()

        embed.add_field(
            name="Invited server name",
            value=f"{invite_guild['guild']['name']}"
        )

    logs_channel = member.guild.get_channel(int(os.getenv("LOGS_CHANNEL", "")))

    await logs_channel.send(embed=embed)

    # Check if punishment is needed
    # len(...) + 1 is needed because len is used for indexes, and indexes start at 0, not 1.
    if len(infractions[str(member.id)]) == 5:
        await member.timeout_for(duration=datetime.timedelta(days=1), reason="5 infractions (warns) reached")

    if len(infractions[str(member.id)]) == 3:
        await member.timeout_for(duration=datetime.timedelta(hours=1), reason="3 infractions (warns) reached")

    if len(infractions[str(member.id)]) == 3 or len(infractions[str(member.id)]) == 5:    
        embed = discord.Embed(
            title=f"[TIMEOUT] {member.name}"
        )
        embed.add_field(
            name="Reason",
            value=f"Member reached {len(infractions[str(member.id)])} warns"
        )
        await logs_channel.send(embed=embed)

def is_zalgo_text(text):
    """
    Check if the given text contains Zalgo text.
    """
    # if text == "( ͡° ͜ʖ ͡°)": #     T  H  E   L  E  N  N  Y   O  V  E  R  R  I  D  E
    #     return False
    # for char in text:
    #     if unicodedata.combining(char):
    #         return True
    return False

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
    check_infractions.start()
    tech_logs_channel = bot.get_channel(int(os.getenv("TECH_LOGS", "")))
    await tech_logs_channel.send(embed=discord.Embed(description="**Clouve is afloat! Bot is up and running!**"))
    # await bot.sync_commands()

@bot.event
async def on_member_join(member: discord.Member):
    print(f"Member joined: {member.display_name}")

    await create_welcome_image(member)

async def process_message(message: discord.Message):
    if message.author.bot or message.author.id == 349977940198555660:
        print("bypassing warn")
        return
    
    if message.author.id == bot.user.id:
        return
    
    storm_role = discord.utils.find(lambda r: r.id == 845918904940232725, message.author.guild.roles)
    if storm_role in message.author.roles:
        return

    content = message.content

    # Remove spoilers
    content = content.replace("||", "")

    # Check if it's a discord.gg link (except for adverts)
    if str(message.channel.id) != os.getenv("ADVERTS_CHANNEL") and extract_invite_id(content):
        await warn_member(message.author, "Invite link outside adverts", message)
        await message.channel.send(f"{message.author.mention}", embed=discord.Embed(
            description="**Hey! Discord Invite links go in adverts**"
        ))
        return

    if is_zalgo_text(content):
        embed = discord.Embed(
            description="**Hey! Zalgo usage in messages is not permitted here.**"
        )
        await message.channel.send(f"{message.author.mention}", embed=embed)
        await warn_member(message.author, "Zalgo usage", message)
        return

    contains_banned_word = False
    filtered_content = content
    for bypass in WORD_BYPASSES.keys():
        for actual in WORD_BYPASSES[bypass]:
            filtered_content = filtered_content.replace(bypass, actual)
    
    # print(filtered_content)

    # converts thing like the freaky font into regular ASCII to be analyzed
    filtered_content = filtered_content.lower().split(" ")
    # print(filtered_content)
    for word in filtered_content:
        word = unicodedata.normalize("NFKC", word)
        # print(word)
        for banned_word in BANNED_WORDS:
            if banned_word.lower() == word or \
                banned_word.lower() == word.replace("i", "l") or\
                    banned_word.lower() == word.replace("m", "e"):
                contains_banned_word = True
                break
        # break

    if contains_banned_word:
        embed = discord.Embed(
            description="**Warned: Message contains a blocked word**"
        )
        await message.channel.send(f"{message.author.mention}", embed=embed)
        await warn_member(message.author, "Banned word", message)
        return

    content = message.clean_content
    content = content.replace("||", "")
    # print(content)

    if content.startswith("!bigboombu"):
        embed = discord.Embed(
            description=random.choice(["Big Boombu approves", "Big Boombu approves", "Big Boombu disapproves"])
        )
        file = discord.File("boombu.png", filename="boombu.png")
        embed.set_image(url="attachment://boombu.png")
        await message.channel.send(file=file, embed=embed)
        return

    count = emoji_count(content) + len(re.findall(r'<:[^:<>]*:[^:<>]*>', content)) # thank you ChatGPT for the RegeX ^_^
    if count > EMOJI_LIMIT:
        embed = discord.Embed(
            description=f"**Hey! You can only send up to {EMOJI_LIMIT} emojis in one message.**"
        )
        await message.channel.send(f"{message.author.mention}", embed=embed)
        await warn_member(message.author, "Emoji spam", message)


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot or message.author.id == 349977940198555660:
        print("bypassing warn")
        return
    
    if message.author.id == bot.user.id:
        return

    if isinstance(message.channel, discord.DMChannel):
        print("dms")
        await message.channel.send(random.choice(RESPONSES))
    else:
        await process_message(message)

@bot.event
async def on_message_edit(before: discord.Message, after: discord.Message):
    if after.author.bot or after.author.id == 349977940198555660:
        print("bypassing warn")
        return
    
    if after.author.id == bot.user.id:
        return
        
    await process_message(after)

@bot.event
async def on_member_remove(member: discord.Member):
    await member.guild.get_channel(int(os.getenv("WELCOME_CHANNEL", ""))).send(f"{member.name} has left the server. Kinda freaky NGL...")

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

@tasks.loop(minutes=30)
async def update_status():
    if bot.user.display_name != "Clouve Testing": return

    statuses = []
    with open("statuses.txt", "r") as f:
        statuses = f.read().split("\n")
    
    bot.activity = discord.Activity(type=discord.ActivityType.custom, name=random.choice(statuses))

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

    if str(member.id) in infractions:
        for infraction in infractions[str(member.id)]:
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

@bot.slash_command(name="purge", description="Deletes a bulk amount of commands", guilds=[os.getenv("GUILD_ID", "")])
@discord.option(
    "count",
    description="The amount of messages to delete",
    required=True
)
@discord.default_permissions(moderate_members=True)
async def purge(ctx: discord.ApplicationContext, count: int):
    await ctx.channel.purge(limit=count)
    await ctx.respond(embed=discord.Embed(description=f"**Succesfully purged {count} messages**"))

@bot.slash_command(name="clear_warns", description="Clears infractions (warns) on a member", guilds=[os.getenv("GUILD_ID", "")])
@discord.option(
    "member",
    description="The member whose infractions you want to remove",
    required=True
)
@discord.default_permissions(moderate_members=True)
async def clear_warns(ctx: discord.ApplicationContext, member: discord.Member):
    del infractions[str(member.id)]
    await ctx.respond(embed=discord.Embed(description=f"**Succesfully cleared the warns on {member.name}**"))

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

@bot.slash_command(name="resync", descripton="Resyncs commands")
@discord.default_permissions(manage_guild=True)
async def resync(ctx: discord.ApplicationContext):
    await bot.sync_commands()
    await ctx.respond(embed=discord.Embed(
        description="**Resync sucessful**"
    ))

@bot.slash_command(name="restart", description="[MOD ONLY] Restarts hte bot", guild_ids=[
    int(os.getenv("GUILD_ID", ""))
])
@discord.default_permissions(manage_guild=True)
async def restart_bot(ctx: discord.ApplicationContext):
    if int(os.getenv("IS_MAIN_SERV", "")) == 0:
        await ctx.respond("**Not main server!**", ephemeral=True)
        return
    
    await ctx.respond("Restarting bot!")
    tech_logs_channel = bot.get_channel(int(os.getenv("TECH_LOGS", "")))

    await tech_logs_channel.send(embed=discord.Embed(
        description="**Shutting down Clouve...**"
    ))
    os.system("cd && ./update-clouve.sh")

# @bot.slash_command(name="topic", description="topic convo", guild_ids=[
#     int(os.getenv("GUILD_ID", ""))
# ])
# async def topic(ctx: discord.ApplicationContext):
#     await ctx.defer()
#     messages = await ctx.channel.history(limit=6).flatten()
#     messages.reverse()

#     message_contents = [message.content for message in messages]

#     headers = {
#         "Authorization": f"Bearer no_token_for_u", # remember to make this an env var!
#         "Content-Type": "application/json"
#     }

#     message_content = ', '.join(message_contents)

#     print(json.dumps({
#             "inputs": {
#                 "text": f"The last 6 messages sent were: [{message_content}] What is the topic of this conversation?"
#             }
#         }))

#     response = requests.post(
#         "https://api-inference.huggingface.co/models/microsoft/DialoGPT-large",
#         headers=headers,
#         data=json.dumps({
#             "inputs": f"The last 6 messages sent were: [{message_content}] What is the topic of this conversation?"
#         })
#     ).json()

#     await ctx.followup.send(f"{response[0]["generated_text"]}", ephemeral=True)

# Error events
@bot.event
async def on_application_command_error(ctx: discord.ApplicationContext, error: discord.DiscordException):
    tech_logs_channel = bot.get_channel(int(os.getenv("TECH_LOGS", "")))
    await tech_logs_channel.send(embed=discord.Embed(
        title=f"Error occured!",
        description=f"""An error occured in <#{ctx.channel.id}>!
Error:
```python
{''.join(traceback.format_exception(error))}
```""".replace(getpass.getuser(), "*" * len(getpass.getuser()))
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
    "music"
]

for cog in cogs:
    bot.load_extension(f"cogs.{cog}")

bot.run(os.getenv("BOT_TOKEN"))
