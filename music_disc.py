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
current_song = {}


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

# Function to get Spotify album tracks
def get_spotify_album_tracks(playlist_url):
    track_queries = []  # Store search queries instead of URLs
    album = sp.album(playlist_url)
    for item in album['tracks']['items']:
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
        elif 'album' in song:
            track_queries = get_spotify_album_tracks(song)
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
spotify_tracks_cache = {}

def get_cached_spotify_tracks(playlist_url):
    if playlist_url in spotify_tracks_cache:
        return spotify_tracks_cache[playlist_url]
    else:
        track_urls = get_spotify_playlist_tracks(playlist_url)
        spotify_tracks_cache[playlist_url] = track_urls
        return track_urls



# Revised start_music_quiz function to use cached tracks
async def start_music_quiz(interaction: discord.Interaction, category: str):
    playlist_url = category_playlists.get(category.lower())
    if not playlist_url:
        await interaction.response.send_message("Invalid category. Please choose from: rock, pop, rnb, rap.", ephemeral=True)
        return

    track_urls = get_cached_spotify_tracks(playlist_url)  # Use cached Spotify tracks
    # Rest of the function remains the same..
    random_track_url = random.choice(track_urls)

    guild_id = interaction.guild_id
    if guild_id not in song_queues:
        song_queues[guild_id] = deque()
    song_queues[guild_id].append(random_track_url)

    voice_client = interaction.guild.voice_client
    # Check if the bot is connected to a voice channel, if not try to connect
    if not voice_client:
        if interaction.user.voice:
            voice_channel = interaction.user.voice.channel
            voice_client = await voice_channel.connect()
            await interaction.response.send_message("Starting quiz... ⛱️", ephemeral=True)
        else:
            await interaction.followup.send("You need to be in a voice channel to start the quiz.")
            return

    # Now, you can safely check if the voice_client is playing
    if not voice_client.is_playing():
        await play_song_from_queue(interaction)

    options = [random_track_url] + random.sample(track_urls, 3)
    random.shuffle(options)
    correct_option_index = options.index(random_track_url)
    songs_played = 1
    quiz_controls = MusicQuizControls(bot, interaction, options, correct_option_index, playlist_url, songs_played)
    await interaction.followup.send("Let the quiz begin! Here's the initial scoreboard:", view=quiz_controls)
    await quiz_controls.send_scores(interaction)  # Display initial scores
    await interaction.followup.send("Guess the song:", view=quiz_controls)







@bot.tree.command(name='quiz_category', description='Choose a category for the music quiz')
@app_commands.describe(category='The category for the quiz: rock, pop, rnb, rap')
async def quiz_category(interaction: discord.Interaction, category: str):
    await interaction.response.defer()
    await start_music_quiz(interaction, category)



###### QUIZ BUTTONS #########
class MusicQuizControls(View):
    def __init__(self, bot, interaction, options, correct_option_index, playlist_url, songs_played=0):
        super().__init__(timeout=None)
        self.bot = bot
        self.interaction = interaction
        self.options = options
        self.correct_option_index = correct_option_index
        self.playlist_url = playlist_url
        self.songs_played = songs_played
        self.correct_guessed = False
        self.joined_users = set()  # Track users who have joined the quiz

        self.add_join_button()
        self.add_option_buttons()

    def add_join_button(self):
        join_button = discord.ui.Button(label="Join Quiz", style=discord.ButtonStyle.green)

        async def join_callback(interaction: discord.Interaction, button: discord.ui.Button):
            self.joined_users.add(interaction.user.id)
            await interaction.response.send_message(f"{interaction.user.display_name} has joined the quiz! 🎉", ephemeral=True)
            button.disabled = True
            await interaction.message.edit(view=self)

        join_button.callback = join_callback
        self.add_item(join_button)

    async def start(self):
        await asyncio.sleep(20)  # Wait for 20 seconds
        self.remove_item(self.children[0])  # Assuming the "Join Quiz" button is the first item added
        await self.interaction.edit_original_response(view=self)
        await self.send_scores("Quiz participants 📋:")

    def add_option_buttons(self):
        for idx, option in enumerate(self.options):
            label = (option[:77] + '...') if len(option) > 80 else option
            button = discord.ui.Button(label=label, style=discord.ButtonStyle.secondary)

            async def option_callback(button_interaction: discord.Interaction, idx=idx, self=self):
                await button_interaction.response.defer()
                await self.handle_guess(button_interaction, idx)

            button.callback = option_callback
            self.add_item(button)

    async def handle_guess(self, button_interaction: discord.Interaction, guess_index):
        user_id = button_interaction.user.id
        user_points[user_id] = user_points.get(user_id, 0)

        if guess_index == self.correct_option_index:
            user_points[user_id] += 1
            response = f"Correct! +1 point. {button_interaction.user.mention} guessed it right."
            self.correct_guessed = True
        else:
            user_points[user_id] -= 1
            response = f"Incorrect! Zero points awarded. {button_interaction.user.mention} guessed it wrong."

        # Initially defer the response if there's any delay expected in processing
        await button_interaction.response.defer(ephemeral=True)

        # Use followup.send to send the response message
        await button_interaction.followup.send(response, ephemeral=True)

        if guess_index == self.correct_option_index:
            await self.change_song(button_interaction)  # Change song immediately after correct guess
        else:
            asyncio.create_task(self.delayed_song_change(button_interaction))  # Delayed song change for incorrect guess


        # Disable the guessed button to prevent multiple guesses
        for item in self.children:
            if isinstance(item, discord.ui.Button) and item.label == self.options[guess_index]:
                item.disabled = True
                await button_interaction.message.edit(view=self)
                break

    async def send_scores(self, message_prefix="Current scores 🏆:"):
        scores_message = message_prefix + "\n"
        for user_id in self.joined_users:
            points = user_points.get(user_id, 0)
            user = await self.bot.fetch_user(user_id)
            scores_message += f"{user.name}: {points} points\n"

        await self.interaction.followup.send(scores_message, ephemeral=True)

    async def delayed_song_change(self, interaction):
        await asyncio.sleep(30)  # Wait for 30 seconds before changing the song
        if not self.correct_guessed:  # Only change the song if the correct answer hasn't been guessed
            await self.change_song(interaction)

    async def next_song_timeout(self, interaction):
        await asyncio.sleep(60)  # Wait for 60 seconds
        if not self.correct_guessed:  # Check if the correct answer was not guessed
            await self.change_song(self.interaction)  # Move to the next song


    async def change_song(self, interaction):
        # Stop the current song and automatically trigger the next song in the queue
        self.songs_played += 1  # Increment the song counter

        if self.songs_played >= 6:
            # The quiz ends after 10 songs
            await self.send_final_scores(interaction)
            await self.reset_quiz(interaction)
            return  # Exit the method to prevent starting a new song
        await skip_logic(interaction.guild)
        self.correct_guessed = False
        # Send the updated scores before starting the new song
        await self.send_scores(interaction)

        # Fetch new track URLs from the Spotify playlist for the next quiz question
        track_urls = get_spotify_playlist_tracks(self.playlist_url)
        new_track_urls = [url for url in track_urls if url not in self.options]  # Ensure new songs are not repeats
        random_track_url = random.choice(new_track_urls)

        # Update the queue with the new song for the next quiz question
        guild_id = interaction.guild_id
        if guild_id not in song_queues:
            song_queues[guild_id] = deque()
        song_queues[guild_id].clear()  # Clear the current queue
        song_queues[guild_id].append(random_track_url)  # Add the new song to the queue

        # Play the new song
        if interaction.guild.voice_client.is_playing() or interaction.guild.voice_client.is_paused():
            interaction.guild.voice_client.stop()
        await play_song_from_queue(interaction)

        # Generate new quiz options ensuring they are unique and not repeating the previous ones
        new_options = [random_track_url] + random.sample([url for url in new_track_urls if url != random_track_url], 3)
        random.shuffle(new_options)  # Shuffle the new options
        new_correct_option_index = new_options.index(random_track_url)  # Find the index of the correct option

        # Create a new instance of MusicQuizControls with the new options for the next quiz question
        new_quiz_controls = MusicQuizControls(self.bot, interaction, new_options, new_correct_option_index, self.playlist_url, songs_played=self.songs_played)

        # Send a new message with the new quiz question and options
        await interaction.followup.send("Guess the new song:", view=new_quiz_controls)
        asyncio.create_task(self.next_song_timeout(interaction))



    async def reset_quiz(self, interaction):
        # Reset the scores
        user_points.clear()

        # Clear the song queue for the guild
        guild_id = interaction.guild_id
        if guild_id in song_queues:
            song_queues[guild_id].clear()

        # Optionally, send a message indicating the end of the quiz round and the reset
        await interaction.followup.send("The quiz round has ended. Scores have been reset. Starting a new round...")

    async def send_final_scores(self, interaction):
        await self.send_scores("🎉 The music quiz is over! Final scores 🎼:")
    # Remember to add buttons for options when initializing MusicQuizControls


# When initializing MusicQuizControls, also call add_buttons to add the option buttons

### TOKEN TO RUN THE BOT ####
bot.run('')