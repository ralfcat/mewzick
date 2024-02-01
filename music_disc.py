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
import random
import functools
from functools import partial
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

    ####  PLAYS HÄR KOMMER MASTER YI WHEN PRESSED ######
    @discord.ui.button(label="The Master Yi", style=discord.ButtonStyle.green)
    async def master_yi_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        # Check if the interaction is in a guild
        if self.interaction.guild is None:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return

        guild_id = self.interaction.guild_id

        # Define the song to play
        master_yi_song = "Här kommer Master Yi"

        # Ensure the song queue for the guild exists
        if not song_queues.get(guild_id):
            song_queues[guild_id] = deque()
        song_queues[guild_id].append(master_yi_song)

        # Send a response to acknowledge the button press
        await self.interaction.response.send_message("Här kommer han... 🏄 🏄", ephemeral=True)
        await skip_logic(self.interaction.guild) 
        # Connect to the voice channel if not already connected and start playing if not already playing
        voice_client = self.interaction.guild.voice_client
        if voice_client is None:
            if self.interaction.user.voice:
                voice_channel = self.interaction.user.voice.channel
                await voice_channel.connect()
                voice_client = self.interaction.guild.voice_client
            else:
                await self.interaction.followup.send("You need to be in a voice channel to use this command.", ephemeral=True)
                return

        if not voice_client.is_playing():
            await play_song_from_queue(self.interaction)


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
        await self.interaction.response.edit_message(view=self)

    # Skip Button
    @discord.ui.button(label="Skip", style=discord.ButtonStyle.blurple, emoji="<:victor:1055476873058066442>")
    async def skip_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        await skip_logic(self.interaction.guild)  # Use the new skip logic function
        await self.interaction.response.send_message("Skipping song...", ephemeral=True)

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

async def play_song_from_queue(interaction):
    guild_id = interaction.guild_id
    if song_queues.get(guild_id):  # Ensure the queue exists for the guild
        if song_queues[guild_id]:  # Check if there are songs in the queue
            url = song_queues[guild_id].popleft()  # Remove the next song from the queue
            
            # Setup yt_dlp options
            ydl_opts = {
                'format': 'bestaudio/best',
                'default_search': 'auto',  # Use 'auto' for automatic direct or search handling
                'quiet': True,
                'source_address': '0.0.0.0'  # Bind to IPv4
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                video_url = info['url'] if 'url' in info else info['entries'][0]['url']  # Extract the video URL
            
            # Access the guild's voice client
            voice_client = interaction.guild.voice_client
            if voice_client:  # Ensure the voice client exists
                FFMPEG_OPTIONS = {
                    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
                    'options': '-vn -c:a libopus -b:a 96k'
                }
                source = await discord.FFmpegOpusAudio.from_probe(video_url, **FFMPEG_OPTIONS)
                voice_client.play(source, after=lambda e: asyncio.run_coroutine_threadsafe(play_song_from_queue(interaction), interaction.client.loop))
            else:
                # Handle the case where the bot is not connected to a voice channel
                await interaction.followup.send("Bot is not connected to a voice channel.")
        else:
            # Optionally send a message when the queue is empty after skipping
            await interaction.followup.send("Queue is empty.")
    else:
        # Queue does not exist for the guild
        await interaction.followup.send("No active queue.")



@bot.tree.command(name='skip', description='Skip the Current Song')
async def skip(interaction: discord.Interaction):
    await skip_logic(interaction.guild)  # Use the new skip logic function
    await interaction.response.send_message("Skipping current song...")


@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f'{bot.user.name} has connected to Discord!')


## HANDLES THE PLAY COMMAND ###
import re

@bot.tree.command(name='play', description='Play a song from Spotify, YouTube link, or search by name')
@app_commands.describe(song='The Spotify or YouTube URL of the song or a search query')
async def play(interaction: discord.Interaction, song: str):
    voice_channel = interaction.user.voice.channel if interaction.user.voice else None
    guild_id = interaction.guild_id

    if not song_queues.get(guild_id):
        song_queues[guild_id] = deque()

    if not voice_channel:
        await interaction.response.send_message("You are not connected to a voice channel.")
        return

    await interaction.response.defer()

    if 'spotify.com' in song:
        # Handle Spotify links as before
        if 'track' in song:
            query = get_spotify_track(song)
            song_queues[guild_id].append(query)
        elif 'playlist' in song:
            track_queries = get_spotify_playlist_tracks(song)
            song_queues[guild_id].extend(track_queries)
        await interaction.followup.send("Spotify content added to queue.")
    else:
        # YT-DLP for direct URLs or search queries
        ydl_opts = {
            'format': 'bestaudio/best',
            'default_search': 'ytsearch',
            'quiet': True,
            'source_address': '0.0.0.0'
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Check if 'song' is a URL or a search query
            if re.match(r'https?://(?:www\.)?.+', song):
                info = ydl.extract_info(song, download=False)
            else:
                info = ydl.extract_info(f"ytsearch:{song}", download=False)['entries'][0]

            video_url = info.get('url', None)
            if video_url:
                song_queues[guild_id].append(video_url)
                await interaction.followup.send(f"Song added to queue: {info['title']}")
            else:
                await interaction.followup.send("Could not find the song.")

    voice_client = interaction.guild.voice_client
    if not voice_client:
        await voice_channel.connect()
        voice_client = interaction.guild.voice_client

    if not voice_client.is_playing():
        await play_song_from_queue(interaction)
    controls = MusicControls(bot,interaction)
    await interaction.followup.send("Control your audio 🍹:", view=controls)


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


#####   EXPERIMENTAL QUIZ FUNCTION   #########
category_playlists = {
    "rock": "https://open.spotify.com/playlist/37i9dQZF1DWXRqgorJj26U?si=87788895d0c54873",
    "pop": "https://open.spotify.com/playlist/37i9dQZF1EQncLwOalG3K7?si=8e2a070cf0cc43d3",
    "rnb": "https://open.spotify.com/playlist/37i9dQZF1EQoqCH7BwIYb7?si=1df72bc335b04fe0",
    "rap": "https://open.spotify.com/playlist/37i9dQZF1EQnqst5TRi17F?si=9d310e14a27e4a53",
}

user_points = {}

@bot.tree.command(name='quiz', description='Start a music quiz')
async def quiz(interaction: discord.Interaction):
    category_buttons = View(timeout=30)

    for category in category_playlists.keys():
        button = Button(label=category.capitalize(), style=discord.ButtonStyle.secondary)

        async def button_callback(interaction: discord.Interaction, category=category):
            await start_music_quiz(interaction, category)

        button.callback = functools.partial(button_callback, category=category)
        category_buttons.add_item(button)

    await interaction.response.send_message("Choose a category:", view=category_buttons, ephemeral=True)



from collections import deque  # Ensure deque is imported at the top of your script

async def start_music_quiz(interaction: discord.Interaction, category: str):
    playlist_url = category_playlists.get(category.lower())
    if not playlist_url:
        await interaction.response.send_message("Invalid category. Please choose from: rock, pop, rnb, rap.", ephemeral=True)
        return

    # Fetch track URLs from the Spotify playlist
    track_urls = get_spotify_playlist_tracks(playlist_url)
    random_track_url = random.choice(track_urls)  # Choose a random track URL from the playlist

    guild_id = interaction.guild_id
    # Initialize the song queue for the guild if it does not exist
    if guild_id not in song_queues:
        song_queues[guild_id] = deque()

    # Add the selected track to the queue for playback
    song_queues[guild_id].append(random_track_url)
    if not interaction.guild.voice_client.is_playing():
        await play_song_from_queue(interaction)

    # Generate quiz options and display controls
    options = [random_track_url] + random.sample(track_urls, 3)  # Choose 3 random tracks as incorrect options
    random.shuffle(options)
    correct_option_index = options.index(random_track_url)

    # Show the quiz controls with the options
    quiz_controls = MusicQuizControls(bot, interaction, options, correct_option_index)
    await interaction.followup.send("Guess the song:", view=quiz_controls)






@bot.tree.command(name='quiz_category', description='Choose a category for the music quiz')
@app_commands.describe(category='The category for the quiz: rock, pop, rnb, rap')
async def quiz_category(interaction: discord.Interaction, category: str):
    await interaction.response.defer()
    await start_music_quiz(interaction, category)



###### QUIZ BUTTONS #########
class MusicQuizControls(View):
    def __init__(self, bot, interaction, options, correct_option_index):
        super().__init__(timeout=None)
        self.bot = bot
        self.interaction = interaction
        self.options = options
        self.correct_option_index = correct_option_index

    async def handle_guess(self, interaction: discord.Interaction, button: discord.ui.Button, guess_index):
        user_id = self.interaction.user.id
        user_points[user_id] = user_points.get(user_id, 0)

        if guess_index == self.correct_option_index:
            user_points[user_id] += 1
            response = "Correct! +1 point."
        else:
            user_points[user_id] -= 1
            response = "Incorrect! -1 point."

        await self.interaction.response.send_message(response, ephemeral=True)
        await asyncio.sleep(15)  # Optional delay after a correct guess
        await self.send_scores(interaction)

    async def send_scores(self, interaction):
        scores_message = "Current scores:\n"
        for user_id, points in user_points.items():
            user = await self.bot.fetch_user(user_id)
            scores_message += f"{user.name}: {points} points\n"
        await self.interaction.followup.send(scores_message, ephemeral=False)

    # Remember to add buttons for options when initializing MusicQuizControls


# When initializing MusicQuizControls, also call add_buttons to add the option buttons

### TOKEN TO RUN THE BOT ####
bot.run('MTIwMDgzMDQ5NTAyMjM5OTYwOQ.Ga1wcT.1cX3uvxNtoVKzZJYx1mb-sHMT_7xBx_BLZDKZI')
