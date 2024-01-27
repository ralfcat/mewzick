import discord
from discord.ext import commands
from discord import Intents
import youtube_dl
from collections import deque
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import yt_dlp
import asyncio

from discord.ui import Button, View
import discord

intents = Intents.default()
intents.messages = True
intents.message_content = True  # Enable the message content intent
intents.guilds = True
intents.voice_states = True  # This is crucial for music bots to work with voice channels

song_queues = {}

class MusicControls(View):
    def __init__(self, bot, ctx):
        super().__init__(timeout=None)  # No timeout for the view
        self.bot = bot
        self.ctx = ctx

    # Play/Pause Button
    @discord.ui.button(label="Pause", style=discord.ButtonStyle.grey, emoji="<:maxime:1055476858776453291>")
    async def toggle_pause(self, button: discord.ui.Button, interaction: discord.Interaction):
        if self.ctx.voice_client.is_playing():
            await self.ctx.voice_client.pause()
            button.label = "Play"
            button.emoji = ":maxime:"
        elif self.ctx.voice_client.is_paused():
            await self.ctx.voice_client.resume()
            button.label = "Pause"
            button.emoji = ":victor:"
        await interaction.response.edit_message(view=self)

    # Skip Button
    @discord.ui.button(label="Skip", style=discord.ButtonStyle.blurple, emoji="<:victor:1055476873058066442>")
    async def skip(self, button: discord.ui.Button, interaction: discord.Interaction):
        # Implementation for skipping a song
        pass  # Add your skip logic here

    # Stop Button
    @discord.ui.button(label="Stop", style=discord.ButtonStyle.red, emoji="<:anders:1132023797889900635>")
    async def stop(self, button: discord.ui.Button, interaction: discord.Interaction):
        await self.ctx.voice_client.disconnect()
        self.stop()  # Stop the view from listening to more interactions


# Spotify API setup
sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(client_id="2531747cc22f4edd9d102dd9185d45fc",
                                                           client_secret="bcae86795ee34ee7879b96c0c4247c34"))

bot = commands.Bot(command_prefix='£', intents=intents)
song_queue = deque()

# Function to get Spotify track details
def get_spotify_track(url):
    track_info = sp.track(url)
    track_name = track_info['name']
    artist_name = track_info['artists'][0]['name']
    return f"{track_name} {artist_name}"  # Return a search query for yt-dlp



# Function to get Spotify playlist tracks
def get_spotify_playlist_tracks(playlist_url):
    track_queries = []  # Store search queries instead of URLs
    playlist = sp.playlist(playlist_url)
    for item in playlist['tracks']['items']:
        track = item['track']
        # Form a search query combining the track's name and artist's name
        query = f"{track['name']} {track['artists'][0]['name']}"
        track_queries.append(query)  # Append the search query to the list
    return track_queries


# Play the next song in the queue
async def play_next_song(ctx):
     guild_id = ctx.guild.id  # Get the guild ID
     if ctx.voice_client and song_queues[guild_id]:  # Check if there are songs in the queue
        url = song_queues[guild_id].popleft()  # Use popleft() to remove and return the leftmost song
        ydl_opts = {
                'format': 'bestaudio/best',
                'default_search': 'ytsearch',  # This tells yt-dlp to search YouTube when a non-URL is provided
                'quiet': True,
                'source_address': '0.0.0.0'  # Bind to IPv4 since IPv6 addresses can cause issues sometimes
            }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            # Ensure you handle both direct URLs and search queries appropriately here
            video_url = info['url'] if 'url' in info else info['entries'][0]['url']
        FFMPEG_OPTIONS = {'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5'
                          ,'options': '-vn -c:a libopus -b:a 96k'}
        source = await discord.FFmpegOpusAudio.from_probe(video_url, **FFMPEG_OPTIONS)
        ctx.voice_client.play(source, after=lambda e: asyncio.run_coroutine_threadsafe(play_next_song(ctx), bot.loop))


@bot.event
async def on_ready():
    print(f'{bot.user.name} has connected to Discord!')

@bot.command(name='join', help='Join the voice channel')
async def join(ctx):
    if not ctx.message.author.voice:
        await ctx.send("You are not connected to a voice channel.")
        return
    channel = ctx.message.author.voice.channel
    await channel.connect()


@bot.command(name='play', help='Play a song from Spotify or YouTube link')
async def play(ctx, *, url):
    voice_channel = ctx.author.voice.channel if ctx.author.voice else None
    guild_id = ctx.guild.id  # Get the guild ID

    if not song_queues.get(guild_id):
        song_queues[guild_id] = deque()  # Initialize the guild's song queue if it doesn't exist

    if not voice_channel:
        await ctx.send("You are not connected to a voice channel.")
        return

    if 'spotify.com' in url:
        # Spotify URL handling
        if 'track' in url:
            query = get_spotify_track(url)  # Fetch Spotify track details
            song_queues[guild_id].append(query)  # Append track search query to queue
            await ctx.send("Spotify track added to queue.", view=MusicControls(bot,ctx))
        elif 'playlist' in url:
            track_queries = get_spotify_playlist_tracks(url)  # Fetch Spotify playlist track details
            song_queues[guild_id].extend(track_queries)  # Extend the queue with track search queries
            await ctx.send(f"Spotify playlist added to queue. {len(track_queries)} tracks queued.", view=MusicControls(bot,ctx))
    else:
        # YT-DLP for direct URLs or search queries
        ydl_opts = {
            'format': 'bestaudio/best',
            'default_search': 'ytsearch',  # This tells yt-dlp to search YouTube when a non-URL is provided
            'quiet': True,
            'source_address': '0.0.0.0'  # Bind to IPv4 since IPv6 addresses can cause issues sometimes
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            video_url = info['url'] if 'url' in info else info['entries'][0]['url']
            song_queues[guild_id].append(video_url)  # Append the video URL to the queue
            await ctx.send(f"Song added to queue: {info['title']}", view=MusicControls(bot,ctx))

    if not ctx.voice_client:
        await voice_channel.connect()

    if not ctx.voice_client.is_playing():
        await play_next_song(ctx)




@bot.command(name='pause', help='Pause the music')
async def pause(ctx):
    await ctx.voice_client.pause()
    await ctx.send("Music paused ⏸️")

@bot.command(name='test', help='Test command')
async def test(ctx):
    await ctx.send("Test command received!")
@bot.command(name='resume', help='Resume the music')
async def resume(ctx):
    await ctx.voice_client.resume()
    await ctx.send("Music resumed ▶️")

@bot.command(name='leave', help='Leave the voice channel')
async def leave(ctx):
    await ctx.voice_client.disconnect()

@bot.command(name='clear_queue', help='Clear the entire song queue')
async def clear_queue(ctx):
    guild_id = ctx.guild.id  # Get the guild ID

    # Check if there's a queue for the guild and clear it
    if guild_id in song_queues and song_queues[guild_id]:
        song_queues[guild_id].clear()  # Clear the deque for this guild
        await ctx.send("The song queue has been cleared.")
    else:
        await ctx.send("There are no songs in the queue.")
@bot.command(name='show_controls', help='Show music control buttons')
async def show_controls(ctx):
    await ctx.send("Here are the music control buttons:", view=MusicControls(bot, ctx))
bot.run('MTIwMDgzMDQ5NTAyMjM5OTYwOQ.Ga1wcT.1cX3uvxNtoVKzZJYx1mb-sHMT_7xBx_BLZDKZI')
