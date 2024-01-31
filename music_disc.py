import discord 
from discord.ext import commands
from discord import Intents
import youtube_dl
from collections import deque
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import yt_dlp
import asyncio
from discord import app_commands


from discord.ui import Button, View
import discord



intents = Intents.default()
intents.messages = True
intents.message_content = True  # Enable the message content intent
intents.guilds = True
intents.voice_states = True  # This is crucial for music bots to work with voice channels

song_queues = {}

class MusicControls(View):
    def __init__(self, bot, interaction):
        super().__init__(timeout=None)  # No timeout for the view
        self.bot = bot
        self.interaction = interaction

    # Play/Pause Button
    @discord.ui.button(label="Pause", style=discord.ButtonStyle.grey, emoji="<:maxime:1055476858776453291>")
    async def toggle_pause(self, button: discord.ui.Button, interaction: discord.Interaction):
        voice_client = self.interaction.guild.voice_client
        if voice_client.is_playing():
            await voice_client.pause()
            button.label = "Play"
            button.emoji = ":maxime:"
        elif voice_client.is_paused():
            await voice_client.resume()
            button.label = "Pause"
            button.emoji = ":victor:"
        await interaction.response.edit_message(view=self)

    # Skip Button
    @discord.ui.button(label="Skip", style=discord.ButtonStyle.blurple, emoji="<:victor:1055476873058066442>")
    async def skip_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        await skip_logic(interaction.guild)  # Use the new skip logic function
        await interaction.response.send_message("Skipping song...", ephemeral=True)

    # Stop Button
    @discord.ui.button(label="Stop", style=discord.ButtonStyle.red, emoji="<:anders:1132023797889900635>")
    async def stop(self, button: discord.ui.Button, interaction: discord.Interaction):
        voice_client = self.interaction.guild.voice_client
        if voice_client:
            await voice_client.disconnect()
        self.stop()  # Stop the view from listening to more interactions


#### HANDLES ALL SPOTIFY LINKS. AS OF NOW ONLY TRACK AND PLAYLISTS LINKS ARE ALLOWED. PODCAST DO NOT WORK ###
# Spotify API setup
sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(client_id="2531747cc22f4edd9d102dd9185d45fc",
                                                           client_secret="bcae86795ee34ee7879b96c0c4247c34"))


bot = commands.Bot(command_prefix='£', intents=intents)
tree = bot.tree  # Reference to the app command tree for easier access

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

async def skip_logic(guild):
    voice_client = guild.voice_client
    if voice_client and voice_client.is_playing():
        voice_client.stop()  # Stopping the current song should automatically play the next song if your play_song_from_queue logic handles it



## CRUCIAL FUNCTION TO PLAY THE ACTUAL SONG. KEY-STEP HERE IS THE FFMPEG AUDIO SETTINGS ##
async def play_song_from_queue(ctx):
    guild_id = ctx.guild.id
    if song_queues.get(guild_id):  # Ensure the queue exists for the guild
        if song_queues[guild_id]:  # Check if there are songs in the queue
            url = song_queues[guild_id].popleft()  # Remove the next song from the queue
            ydl_opts = {
                'format': 'bestaudio/best',
                'default_search': 'ytsearch',  # Search YouTube for non-URLs
                'quiet': True,
                'source_address': '0.0.0.0'  # Avoid IPv6 issues
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                video_url = info['url'] if 'url' in info else info['entries'][0]['url']
            
            FFMPEG_OPTIONS = {
                'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
                'options': '-vn -c:a libopus -b:a 96k'
            }
            source = await discord.FFmpegOpusAudio.from_probe(video_url, **FFMPEG_OPTIONS)
            ctx.voice_client.play(source, after=lambda e: asyncio.run_coroutine_threadsafe(play_song_from_queue(ctx), bot.loop))
        else:
            # Optionally send a message when the queue is empty after skipping
            await ctx.send("Queue is empty.")
    else:
        # Queue does not exist for the guild
        await ctx.send("No active queue.")

@bot.tree.command(name='skip', description='Skip the Current Song')
async def skip(interaction: discord.Interaction):
    await skip_logic(interaction.guild)  # Use the new skip logic function
    await interaction.response.send_message("Skipping current song...")


@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f'{bot.user.name} has connected to Discord!')


## HANDLES THE PLAY COMMAND ###
@bot.tree.command(name='play', description='Play a song from Spotify or YouTube link')
@app_commands.describe(url='Song name or URL')
async def play(interaction: discord.Interaction, url: str):
    voice_channel = interaction.user.voice.channel if interaction.user.voice else None
    guild_id = interaction.guild_id  # Use interaction.guild_id for slash commands

    if not song_queues.get(guild_id):
        song_queues[guild_id] = deque()  # Initialize the guild's song queue if it doesn't exist

    if not voice_channel:
        await interaction.response.send_message("You are not connected to a voice channel.")
        return

    if 'spotify.com' in url:
        # Spotify URL handling
        if 'track' in url:
            query = get_spotify_track(url)  # Fetch Spotify track details
            song_queues[guild_id].append(query)  # Append track search query to queue
            await interaction.response.send_message("Spotify track added to queue.")
        elif 'playlist' in url:
            track_queries = get_spotify_playlist_tracks(url)  # Fetch Spotify playlist track details
            song_queues[guild_id].extend(track_queries)  # Extend the queue with track search queries
            await interaction.response.send_message(f"Spotify playlist added to queue. {len(track_queries)} tracks queued.")
    else:
        # YT-DLP for direct URLs or search queries
        ydl_opts = {
            'format': 'bestaudio/best',
            'default_search': 'ytsearch',
            'quiet': True,
            'source_address': '0.0.0.0'
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            video_url = info['url'] if 'url' in info else info['entries'][0]['url']
            song_queues[guild_id].append(video_url)  # Append the video URL to the queue
            await interaction.response.send_message(f"Song added to queue: {info['title']}")

    if not interaction.guild.voice_client:
        await voice_channel.connect()

    if not interaction.guild.voice_client.is_playing():
        await play_song_from_queue(interaction)


########   SIMPLE COMMANDS  ###########

@bot.tree.command(name='pause', description='Pause the music')
async def pause(interaction: discord.Interaction):
    voice_client = interaction.guild.voice_client
    if voice_client and voice_client.is_playing():
        await voice_client.pause()
        await interaction.response.send_message("Music paused ⏸️")
    else:
        await interaction.response.send_message("No music is currently playing.")


@bot.tree.command(name='test', description='Test command')
async def test(interaction: discord.Interaction):
    await interaction.response.send_message("Test command received!")

@bot.tree.command(name='resume', description='Resume the music')
async def resume(interaction: discord.Interaction):
    voice_client = interaction.guild.voice_client
    if voice_client and voice_client.is_paused():
        await voice_client.resume()
        await interaction.response.send_message("Music resumed ▶️")
    else:
        await interaction.response.send_message("Music is not paused.")


@bot.tree.command(name='leave', description='Leave the voice channel')
async def leave(interaction: discord.Interaction):
    voice_client = interaction.guild.voice_client
    if voice_client:
        await voice_client.disconnect()
        await interaction.response.send_message("Disconnected from the voice channel.")
    else:
        await interaction.response.send_message("Not connected to any voice channel.")


@bot.tree.command(name='join', description='Join the voice channel')
async def join(interaction: discord.Interaction):
    if interaction.user.voice:
        channel = interaction.user.voice.channel
        await channel.connect()
        await interaction.response.send_message(f"Joined {channel.name}.")
    else:
        await interaction.response.send_message("You are not connected to a voice channel.")


@bot.tree.command(name='clear_queue', description='Clear the entire song queue')
async def clear_queue(interaction: discord.Interaction):
    guild_id = interaction.guild_id
    if guild_id in song_queues and song_queues[guild_id]:
        song_queues[guild_id].clear()
        await interaction.response.send_message("The song queue has been cleared.")
    else:
        await interaction.response.send_message("There are no songs in the queue.")

@bot.tree.command(name='show_controls', description='Show music control buttons')
async def show_controls(interaction: discord.Interaction):
    await interaction.response.send_message("Here are the music control buttons:", view=MusicControls(bot, interaction))

@bot.event
async def on_message(message):
    # Check if the message is from a bot or doesn't start with the "£" prefix
    if message.author.bot or not message.content.startswith('£'):
        return

    # Send a message informing about the change to slash commands
    await message.channel.send("We changed the way we play your music. Use \"/\" instead! ⛱️")

    # Process commands if any. This line is necessary if you have other non-slash commands or features that rely on message content.
    await bot.process_commands(message)

bot.run('MTIwMDgzMDQ5NTAyMjM5OTYwOQ.Ga1wcT.1cX3uvxNtoVKzZJYx1mb-sHMT_7xBx_BLZDKZI')
