import discord
from discord.ext import commands
from discord import Intents
import youtube_dl
from collections import deque
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from youtubesearchpython import VideosSearch

from discord.ui import Button, View
import discord

intents = Intents.default()
intents.messages = True
intents.message_content = True  # Enable the message content intent
intents.guilds = True
intents.voice_states = True  # This is crucial for music bots to work with voice channels

class MusicControls(View):
    def __init__(self, bot, ctx):
        super().__init__(timeout=None)  # No timeout for the view
        self.bot = bot
        self.ctx = ctx

    # Play/Pause Button
    @discord.ui.button(label="Pause", style=discord.ButtonStyle.grey, emoji="⏯️")
    async def toggle_pause(self, button: discord.ui.Button, interaction: discord.Interaction):
        if self.ctx.voice_client.is_playing():
            await self.ctx.voice_client.pause()
            button.label = "Play"
            button.emoji = "▶️"
        elif self.ctx.voice_client.is_paused():
            await self.ctx.voice_client.resume()
            button.label = "Pause"
            button.emoji = "⏸️"
        await interaction.response.edit_message(view=self)

    # Skip Button
    @discord.ui.button(label="Skip", style=discord.ButtonStyle.blurple, emoji="⏭️")
    async def skip(self, button: discord.ui.Button, interaction: discord.Interaction):
        # Implementation for skipping a song
        pass  # Add your skip logic here

    # Stop Button
    @discord.ui.button(label="Stop", style=discord.ButtonStyle.red, emoji="⏹️")
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
    return f"{track_name} {artist_name}"

# Function to search for a YouTube equivalent
def search_youtube(query):
    videos_search = VideosSearch(query, limit=1)
    return videos_search.result()['result'][0]['link']

# Function to get Spotify playlist tracks
def get_spotify_playlist_tracks(playlist_url):
    track_urls = []
    playlist = sp.playlist(playlist_url)
    for item in playlist['tracks']['items']:
        track = item['track']
        query = f"{track['name']} {track['artists'][0]['name']}"
        youtube_url = search_youtube(query)
        track_urls.append(youtube_url)
    return track_urls

# Play the next song in the queue
async def play_next(ctx):
    if song_queue:
        song_url = song_queue.popleft()
        await play(ctx, song_url)
    else:
        await ctx.voice_client.disconnect()

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
async def play(ctx, url):
    if 'spotify.com' in url:
        if 'track' in url:
            query = get_spotify_track(url)
        elif 'playlist' in url:
            track_urls = get_spotify_playlist_tracks(url)
            for track_url in track_urls:
                song_queue.append(track_url)
            await ctx.send("Spotify playlist added to queue.")
            return
        youtube_url = search_youtube(query)
    else:
        youtube_url = url

    if not ctx.voice_client:
        await join(ctx)
    ctx.voice_client.stop()
    FFMPEG_OPTIONS = {'options': '-vn'}
    YDL_OPTIONS = {'format': 'bestaudio'}
    vc = ctx.voice_client

    with youtube_dl.YoutubeDL(YDL_OPTIONS) as ydl:
        info = ydl.extract_info(youtube_url, download=False)
        url2 = info['formats'][0]['url']
        source = await discord.FFmpegOpusAudio.from_probe(url2, **FFMPEG_OPTIONS)
        vc.play(source, after=lambda e: play_next(ctx))
    controls = MusicControls(bot, ctx)
    await ctx.send("Playing your song! Use the controls below to manage playback.", view=controls)
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

bot.run('MTIwMDgzMDQ5NTAyMjM5OTYwOQ.Ga1wcT.1cX3uvxNtoVKzZJYx1mb-sHMT_7xBx_BLZDKZI')
