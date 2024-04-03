from typing import Any, List
import discord, os, json, threading
from discord.ext import commands
from yt_dlp import YoutubeDL

class Music(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.queue: List[Any] = []

    def play(self):
        os.remove("audio.m4a")
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
                f"https://youtube.com/watch?v={self.queue[0]['id']}"
            ])
            
            self.vc.play(
                discord.FFmpegPCMAudio("audio.m4a"), after=self.play_next_in_queue  
            )

    def play_next_in_queue(self, error):
        self.queue.pop(0)
        if len(self.queue) != 0:
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

        threading.Thread(target=self._add_to_queue, args=(
            song, ctx.author
        )).start()

        await ctx.followup.send(embed=discord.Embed(
            description=f"**Added song to the queue**"
        ))


    def _add_to_queue(self, song: str, author: discord.User):
        with YoutubeDL({'format': 'bestaudio', 'noplaylist':'True'}) as ydl:
            results = ydl.extract_info(f"ytsearch:{song}", download=False)["entries"][0:5]
            first_result = results[0]
            self.queue.append({
                "id": first_result["id"],
                "name": first_result["title"],
                "added_by": author
            })

            if len(self.queue) == 1:
                threading.Thread(target=self.play).start()


    @discord.slash_command(name="queue", description="Displays the current music queue", guild_ids=[
        int(os.getenv("GUILD_ID", ""))
    ])
    async def display_queue(self, ctx: discord.ApplicationContext):
        embed = discord.Embed(title="Current queue")
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
        if song["added_by"].id != ctx.author.id or storm_role not in ctx.author.roles:
            await ctx.respond(embed=discord.Embed(
                description="**Cannot remove song (insufficient permissions)**"
            ))

        self.queue.pop(song_index)

def setup(bot):
    bot.add_cog(Music(bot))    
