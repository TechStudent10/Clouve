from typing import Any, List
import discord, os, time, re, json, math, random
from discord.ext import commands
from yt_dlp import YoutubeDL
from youtubesearchpython import VideosSearch
from .kthread import KThread
from tinytag import TinyTag

class Music(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.queue: List[Any] = []
        self.started_playing: float = 0
        self.current_process: KThread | None = None
        self.queue_process: KThread | None = None
        self.votes = 0
        self.voters = []
        self.locked = False
        self.current_song: dict | None = None
        self.skip_scores = {}
        self.music_timeouts = {}

    def play(self, error: Exception | None = None):
        if os.path.exists("audio.m4a"):
            os.remove("audio.m4a")

        for skip_score_user in self.skip_scores.keys():
            skip_score = self.skip_scores[skip_score_user]
            if skip_score_user not in self.voters and skip_score != 0:
                self.skip_scores[skip_score_user] -= 1

        print(len(self.queue))
        if len(self.queue) == 0:
            self.current_song = None
            return

        self.current_song = self.queue[0]
        
        with YoutubeDL(
            {
                'outtmpl': {'default': 'audio.m4a'},
                'format': 'm4a/bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'm4a'
                }]
            }
        ) as ydl:
            ydl.download([
                f"https://youtube.com/watch?v={self.current_song['id']}"
            ])
            
            self.started_playing = time.time()
            self.votes = 0
            self.voters = []
            self.vc.play(
                discord.FFmpegPCMAudio("audio.m4a"), after=self.play  
            )
            self.queue.pop(0)

    @discord.slash_command(name="play", description="Plays a song or adds a song to the queue if one is already playing", guild_ids=[
        int(os.getenv("GUILD_ID", ""))
    ])
    @discord.option(
        "Song",
        description="The name of the song. This will search YouTube and grab the first result so make sure it's descriptive",
        required=True
    )
    async def add_to_queue(self, ctx: discord.ApplicationContext, song: str):
        if await self.check_timeout(ctx.author):
            await ctx.respond("You're on music timeout! Try again later", ephemeral=True)
            return
        
        await ctx.defer()
        in_vc = True
        if discord.utils.get(self.bot.voice_clients, guild=ctx.guild) == None:
            vc = ctx.author.voice
            if vc:
                self.channel = vc.channel
                self.vc = await self.channel.connect()
            else:
                await ctx.followup.send(embed=discord.Embed(
                    description="**Enter a voice channel before using this command**"
                ))
                in_vc = False
                return

        if not in_vc:
            await ctx.followup.send(embed=discord.Embed(
                description="**You must be in a Voice Channel to add songs to the queue**"
            ))
            return

        if self.locked:
            await ctx.followup.send(
                embed=discord.Embed(
                    description="**Queue is currently locked.**"
                )
            )
            return

        # self.queue_process = KThread(target=self._add_to_queue, args=(
        #     song, ctx.author
        # )).start()

        search = VideosSearch(song, limit=1)
        _result = search.result()
        result = {}
        if isinstance(_result, str):
            result = json.loads(_result)
        elif isinstance(_result, dict):
            result = _result
        
        video = result["result"][0]

        times: List[str] = video["duration"].split(":")
        if len(times) > 2 or int(times[0]) > 15:
            await ctx.followup.send(embed=discord.Embed(
                description="**The length limit for songs is 15 minutes. If the selected song is a collection of many separate songs (e.g. albums or EPs), then try adding each individual song.**"
            ))
            return

        self.queue.append({
            "id": self.extract_youtube_video_id(
                video["link"]
            ),
            "name": video["title"],
            "added_by": ctx.author
        })

        await ctx.followup.send(embed=discord.Embed(
            description=f"**Added \"{video['title']}\" to the queue at position {len(self.queue)}**"
        ))

        if self.current_song is None:
            self.current_process = KThread(target=self.play)
            self.current_process.start()



    def _add_to_queue(self, song: str, author: discord.User):
        # with YoutubeDL({'format': 'bestaudio', 'noplaylist':'True'}) as ydl:
        #     results = ydl.extract_info(f"ytsearch:{song}", download=False)["entries"][0:5]
        #     first_result = results[0]
        #     if self.vc:
        #         self.queue.append({
        #             "id": first_result["id"],
        #             "name": first_result["title"],
        #             "added_by": author
        #         })

        pass

    
    def is_youtube_link(self, link: str):
        # Regular expression pattern to match YouTube URLs
        pattern = r'(https?://)?(www\.)?(youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]+)'
        match = re.match(pattern, link)
        return match is not None
    
    def extract_youtube_video_id(self, link: str):
        # Regular expression pattern to match YouTube URLs
        pattern = r'(?:https?://)?(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]+)'
        match = re.search(pattern, link)
        if match:
            return match.group(1)
        else:
            return None


    @discord.slash_command(name="queue", description="Displays the current music queue", guild_ids=[
        int(os.getenv("GUILD_ID", ""))
    ])
    async def display_queue(self, ctx: discord.ApplicationContext):
        embed = discord.Embed(title=f"{'[LOCKED] ' if self.locked else ''}Current queue")
        for item_index in range(len(self.queue)):
            item = self.queue[item_index]
            embed.add_field(
                name=f"{item_index + 1}. {item['name']}",
                value=f"Added by {item['added_by'].display_name}",
                inline=False
            )
        await ctx.respond(
            embed=embed
        )

    @discord.slash_command(name="remove_queue", description="Removes a song from the queue", guild_ids=[
        int(os.getenv("GUILD_ID", ""))
    ])
    @discord.option(
        name="Position in queue",
        parameter_name="song",
        description="The song to remove's position in the queue"
    )
    async def remove_from_queue(self, ctx: discord.ApplicationContext, _song: int):
        if await self.check_timeout(ctx.author):
            await ctx.respond("You're on music timeout! Try again later", ephemeral=True)
            return
        
        song_index = _song - 1
        if song_index <= 0:
            await ctx.respond(embed=discord.Embed(
                description="**Cannot remove the currently playing song.**"
            ))
            return

        storm_role = discord.utils.find(lambda r: r.id == 845918904940232725, ctx.author.guild.roles)
        song = self.queue[song_index]
        if song["added_by"].id != ctx.author.id or not storm_role in ctx.author.roles:
            await ctx.respond(embed=discord.Embed(
                description="**Cannot remove song (insufficient permissions)**"
            ))
            return

        self.queue.pop(song_index)

    @discord.slash_command(name="now_playing", desciption="Displays the currently playing song in the music queue", guild_ids=[
        int(os.getenv("GUILD_ID", ""))
    ])
    async def now_playing(self, ctx: discord.ApplicationContext):
        if self.current_song is None or not os.path.exists("audio.m4a"):
            await ctx.respond(embed=discord.Embed(
                description="**Nothing playing!**"
            ))
            return
        
        elapsed = time.strftime('%M:%S', time.gmtime(time.time() - self.started_playing))
        remaining = time.strftime('%M:%S', time.gmtime(TinyTag.get('audio.m4a').duration - (time.time() - self.started_playing)))

        embed = discord.Embed(
            title=f"{self.current_song['name']}",
            description=f"{elapsed}s elasped - {remaining}s remaining"
        )

        outter_self = self
        votes_required = int(math.ceil(len(self.channel.members) * 0.7))

        class SkipView(discord.ui.View):
            @discord.ui.button(
                label="Vote skip",
                style=discord.ButtonStyle.red
            )
            async def vote_skip_callback(self, button: discord.Button, interaction: discord.Interaction):
                if interaction.user.id in outter_self.voters:
                    await interaction.channel.send("You've already voted!")
                    return
                
                if await outter_self.check_timeout(interaction.user):
                    await interaction.channel.send("You're on music timeout! Try again later")
                    return
                
                if interaction.user.id == outter_self.current_song["added_by"].id or \
                    discord.utils.get(ctx.guild.roles, id=845918904940232725) in interaction.user.roles:
                    outter_self.votes += votes_required
                else:
                    outter_self.votes += 1
                    if interaction.user.id not in outter_self.skip_scores:
                        outter_self.skip_scores[interaction.user.id] = 0
                    
                    outter_self.skip_scores[interaction.user.id]+=1

                for skip_score_user in outter_self.skip_scores.keys():
                    skip_score = outter_self.skip_scores[skip_score_user]
                    if skip_score >= 5:
                        outter_self.music_timeouts[interaction.user.id] = time.time()
                        await interaction.channel.send(f"{interaction.user.mention}", embed=discord.Embed(
                            description="**Hey! You've been skipping a lot of songs and have been placed on Music Timeout. Think about your actions for the next 10 minutes as you will not be able to add nor remove songs from the queue and you will, of course, be not allowed to vote skip songs.**"
                        ))

                outter_self.voters.append(interaction.user.id)

                if outter_self.votes >= votes_required:
                    await interaction.channel.send("Skipping song!")
                    outter_self.current_process.kill()
                    outter_self.vc.stop()

                    outter_self.current_process = KThread(target=outter_self.play)
                    outter_self.current_process.start()

                    button.disabled = True
                    button.label = "Song has been skipped"
                    await interaction.response.edit_message(embed=embed, view=self)
                else:
                    await interaction.channel.send(f"{interaction.user.mention} Vote cast! {votes_required - outter_self.votes} needed to skip!")

        await ctx.respond(embed=embed, view=SkipView())

    async def check_timeout(self, member: discord.Member | discord.User | None):
        is_on_timeout = False
        if member.id in self.music_timeouts:
            if (time.time() - self.music_timeouts[member.id]) < 10 * 60: # 10 * 60 is 10 minutes converted to seconds
                is_on_timeout = True
            else:
                del self.music_timeouts[member.id]

        return is_on_timeout

    @discord.slash_command(name="lock_queue", description="Locks the queue", guild_ids=[
        int(os.getenv("GUILD_ID", ""))
    ])
    @discord.default_permissions(moderate_members=True)
    async def lock_queue(self, ctx: discord.ApplicationContext):
        self.locked = not self.locked

        embed = discord.Embed()
        if self.locked:
            embed.description = "**Locked the queue**"
        else:
            embed.description = "**Unlocked queue**"

        await ctx.respond(embed=embed)

    @discord.slash_command(name="leave_vc", description="Leaves the current voice channel", guild_ids=[
        int(os.getenv("GUILD_ID", ""))
    ])
    @discord.default_permissions(moderate_members=True)
    async def leave_vc(self, ctx: discord.ApplicationContext):
        if discord.utils.get(self.bot.voice_clients, guild=ctx.guild) == None:
            await ctx.respond(embed=discord.Embed(
                description="**I'm already not in a VC though...**"
            ))
            return
        
        if self.current_process:
            self.current_process.kill()
        if self.queue_process:
            self.queue_process.kill()
            
        self.vc.stop()
        await self.vc.disconnect()
        self.vc = None
        await ctx.respond(embed=discord.Embed(
            description="**Left VC succesfully**"
        ))

    @discord.slash_command(name="move_vc", description="Moves Clouve to a different voice channel", guild_ids=[
        int(os.getenv("GUILD_ID", ""))
    ])
    @discord.default_permissions(moderate_members=True)
    @discord.option(
        name="vc",
        description="The voice channel to move to"
    )
    async def move_vc(self, ctx: discord.ApplicationContext, vc: discord.VoiceChannel):
        if discord.utils.get(self.bot.voice_clients, guild=ctx.guild) == None:
            await ctx.respond(embed=discord.Embed(
                description="**I'm already not in a VC though...**"
            ))
            return
        
        await self.vc.disconnect()
        self.vc = await vc.connect()
        if self.current_process:
            self.current_process.kill()
        if self.queue_process:
            self.queue_process.kill()
        self.vc.stop()
        self.current_process = KThread(target=self.play)
        self.current_process.start()

        await ctx.respond(embed=discord.Embed(
            description="**Moved VC succesfully**"
        ))

    @discord.slash_command(name="clear_music_timeout", description="Clears a music timeout on a member", guild_ids=[
        int(os.getenv("GUILD_ID", ""))
    ])
    @discord.default_permissions(moderate_members=True)
    @discord.option(
        name="member",
        description="The member whose timeout you want to clear"
    )
    async def clear_music_timeout(self, ctx: discord.ApplicationContext, member: discord.Member):
        if member.id in self.music_timeouts:
            del self.music_timeouts[member.id]

            await ctx.respond(embed=discord.Embed(
                description=f"**Cleared {member.name} timeout succesfully**"
            ))
        else:
            await ctx.respond(embed=discord.Embed(
                description=f"**User \"{member.name}\" did not have any timeout**"
            ))

    @discord.slash_command(name="shuffle", description="Shuffles the queue", guild_ids=[
        int(os.getenv("GUILD_ID", ""))
    ])
    @commands.cooldown(1, 5 * 60)
    async def shuffle_queue(self, ctx: discord.ApplicationContext):
        if await self.check_timeout(ctx.author):
            await ctx.respond("You're on music timeout! Try again later", ephemeral=True)
            return
        
        random.shuffle(self.queue)
        await ctx.respond(embed=discord.Embed(
            description="**Shuffled the queue!**"
        ))

    @shuffle_queue.error
    async def on_shuffle_error(self, interaction: discord.Interaction, error: discord.errors.ApplicationCommandError):
        await interaction.response.send_message(embed=discord.Embed(
            description=f"**{str(error)}**"
        ), ephemeral=True)


def setup(bot):
    bot.add_cog(Music(bot))    
