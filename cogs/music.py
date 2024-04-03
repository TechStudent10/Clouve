from typing import Any, List
import discord, os, time, re, json
from discord.ext import commands
from yt_dlp import YoutubeDL
from youtubesearchpython import VideosSearch, ResultMode
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

    def play(self):
        if os.path.exists("audio.m4a"):
            os.remove("audio.m4a")

        print(len(self.queue))
        if len(self.queue) == 0:
            return
        
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
            if len(self.queue) != 0:
                ydl.download([
                    f"https://youtube.com/watch?v={self.queue[0]['id']}"
                ])
                
                self.started_playing = time.time()
                self.votes = 0
                self.voters = []
                self.vc.play(
                    discord.FFmpegPCMAudio("audio.m4a"), after=self.play_next_in_queue  
                )

    def play_next_in_queue(self, error):
        if len(self.queue) != 0:
            self.queue.pop(0)
            self.play()

    @discord.slash_command(name="play", description="Plays a song or adds a song to the queue if one is already playing", guild_ids=[
        int(os.getenv("GUILD_ID", ""))
    ])
    @discord.option(
        "Song",
        description="The name of the song. This will search YouTube and grab the first result so make sure it's descriptive",
        required=True
    )
    async def add_to_queue(self, ctx: discord.ApplicationContext, song: str):
        await ctx.defer()
        if discord.utils.get(self.bot.voice_clients, guild=ctx.guild) == None:
            vc = ctx.author.voice
            if vc:
                self.vc = await vc.channel.connect()
            else:
                await ctx.followup.send(embed=discord.Embed(
                    description="**Enter a voice channel before using this command**"
                ))
                return

        if self.locked:
            await ctx.followup.send(
                embed=discord.Embed(
                    description="**Queue is currently locked.**"
                )
            )
            return

        self.queue_process = KThread(target=self._add_to_queue, args=(
            song, ctx.author
        )).start()

        await ctx.followup.send(embed=discord.Embed(
            description=f"**Added song to the queue**"
        ))


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

        search = VideosSearch(song, limit=1)
        _result = search.result()
        result = {}
        if isinstance(_result, str):
            result = json.loads(_result)
        elif isinstance(_result, dict):
            result = _result
        
        self.queue.append({
            "id": self.extract_youtube_video_id(
                result["result"][0]["link"]
            ),
            "name": result["result"][0]["title"],
            "added_by": author
        })

        if len(self.queue) == 1:
            self.current_process = KThread(target=self.play)
            self.current_process.start()

    
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
        if len(self.queue) == 0:
            await ctx.respond(embed=discord.Embed(
                description="**Nothing playing!**"
            ))
            return
        
        elapsed = time.strftime('%M:%S', time.gmtime(time.time() - self.started_playing))
        remaining = time.strftime('%M:%S', time.gmtime(TinyTag.get('audio.m4a').duration - (time.time() - self.started_playing)))

        embed = discord.Embed(
            title=f"{self.queue[0]['name']}",
            description=f"{elapsed}s elasped - {remaining}s remaining"
        )

        outter_self = self

        class SkipView(discord.ui.View):
            @discord.ui.button(
                label="Vote skip",
                style=discord.ButtonStyle.red
            )
            async def vote_skip_callback(self, button: discord.Button, interaction: discord.Interaction):
                if interaction.user.id in outter_self.voters:
                    await interaction.channel.send("You've already voted!")
                    return
                
                if interaction.user.id == outter_self.queue[0]["added_by"].id:
                    outter_self.votes += 3
                else:
                    outter_self.votes += 1


                outter_self.voters.append(interaction.user.id)

                if outter_self.votes >= 3:
                    await interaction.channel.send("Skipping song!")
                    outter_self.current_process.kill()
                    outter_self.vc.stop()

                    outter_self.current_process = KThread(target=outter_self.play)
                    outter_self.current_process.start()

                    button.disabled = True
                    button.label = "Song has been skipped"
                    await interaction.response.edit_message(embed=embed, view=self)
                else:
                    await interaction.channel.send("Vote cast!")

        await ctx.respond(embed=embed, view=SkipView())

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


def setup(bot):
    bot.add_cog(Music(bot))    
