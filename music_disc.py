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
        self.original_interaction = interaction

    ####  PLAYS HÄR KOMMER MASTER YI WHEN PRESSED ######
    @discord.ui.button(label="The Master Yi", style=discord.ButtonStyle.green)
    async def master_yi_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Check if the interaction is in a guild
        if self.original_interaction.guild is None:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return

        guild_id = self.original_interaction.guild_id

        # Define the song to play
        master_yi_song = "Här kommer Master Yi"

        # Ensure the song queue for the guild exists
        if not song_queues.get(guild_id):
            song_queues[guild_id] = deque()
        song_queues[guild_id].append(master_yi_song)

        # Send a response to acknowledge the button press
        await self.original_interaction.response.send_message("Här kommer han... 🏄 🏄", ephemeral=True)
        await skip_logic(self.original_interaction.guild) 
        # Connect to the voice channel if not already connected and start playing if not already playing
        voice_client = self.original_interaction.guild.voice_client
        if voice_client is None:
            if self.original_interaction.user.voice:
                voice_channel = self.original_interaction.user.voice.channel
                await voice_channel.connect()
                voice_client = self.original_interaction.guild.voice_client
            else:
                await self.original_interaction.followup.send("You need to be in a voice channel to use this command.", ephemeral=True)
                return

        if not voice_client.is_playing():
            await play_song_from_queue(self.interaction)


    # Play/Pause Button
    @discord.ui.button(label="Pause", style=discord.ButtonStyle.grey, emoji="<:maxime:1055476858776453291>")
    async def toggle_pause(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        voice_client = self.original_interaction.guild.voice_client
        if voice_client.is_playing():
            await voice_client.pause()
            button.label = "Play"
            button.emoji = ":maxime:"
        elif voice_client.is_paused():
            await voice_client.resume()
            button.label = "Pause"
            button.emoji = ":victor:"
        await self.original_interaction.response.edit_message(view=self)

    # Skip Button
    @discord.ui.button(label="Skip", style=discord.ButtonStyle.blurple, emoji="<:victor:1055476873058066442>")
    async def skip_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await skip_logic(self.original_interaction.guild)  # Use the new skip logic function
        await self.original_interaction.response.send_message("Skipping song...", ephemeral=True)

    # Stop Button
    @discord.ui.button(label="Stop", style=discord.ButtonStyle.red, emoji="<:anders:1132023797889900635>")
    async def stop(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        voice_client = self.original_interaction.guild.voice_client
        if voice_client:
            await voice_client.disconnect()
        self.stop()  # Stop the view from listening to more interactions



#### HANDLES ALL SPOTIFY LINKS. AS OF NOW ONLY TRACK AND PLAYLISTS LINKS ARE ALLOWED. PODCAST DO NOT WORK ###
# Spotify API setup
spot_api_id = "insert here"
spot_api_secret = "insert here"
sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(client_id = spot_api_id,
                                                           client_secret = spot_api_secret))


bot = commands.Bot(command_prefix='£', intents=intents)
tree = bot.tree  # Reference to the app command tree for easier access

song_queue = deque()

# Function to get Spotify track details
def get_spotify_track(url):
    track_info = sp.track(url)
    track_name = track_info['name']
    artist_id = track_info['artists'][0]['id']  # Fetch the artist's ID
    artist_name = track_info['artists'][0]['name']
    return f"{track_name} {artist_name}",artist_id  # Return a search query for yt-dlp



# Function to get Spotify playlist tracks including artist IDs
def get_spotify_playlist_tracks(playlist_url):
    track_queries_and_ids = []  # Store tuples of search queries and artist IDs
    playlist = sp.playlist(playlist_url)
    for item in playlist['tracks']['items']:
        track = item['track']
        artist_id = track['artists'][0]['id']  # Fetch the artist's ID
        # Form a tuple with the search query and the artist's ID
        query_and_id = (f"{track['name']} {track['artists'][0]['name']}", artist_id)
        track_queries_and_ids.append(query_and_id)
    return track_queries_and_ids

# Function to get Spotify album tracks including artist IDs
def get_spotify_album_tracks(album_url):
    track_queries_and_ids = []  # Store tuples of search queries and artist IDs
    album = sp.album(album_url)
    for item in album['tracks']['items']:
        artist_id = item['artists'][0]['id']  # Fetch the artist's ID
        # Form a tuple with the search query and the artist's ID
        query_and_id = (f"{item['name']} {item['artists'][0]['name']}", artist_id)
        track_queries_and_ids.append(query_and_id)
    return track_queries_and_ids

# Function to fetch artist's genre
def get_artist_genre(artist_id):
    artist_info = sp.artist(artist_id)
    genres = artist_info['genres']
    return ', '.join(genres) if genres else 'Unknown'


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
            log_interaction(interaction, "Playing Song", url)

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
    log_interaction(interaction, "Skip", "Skipped song")
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
        if 'track' in song:
            query, artist_id = get_spotify_track(song)
            genre = get_artist_genre(artist_id)  # Assume this function fetches genre based on artist_id
            song_queues[guild_id].append((query, genre))
        elif 'playlist' in song:
            track_queries_and_genres = [(query, get_artist_genre(artist_id)) for query, artist_id in get_spotify_playlist_tracks(song)]
            song_queues[guild_id].extend(track_queries_and_genres)
        elif 'album' in song:
            track_queries_and_genres = [(query, get_artist_genre(artist_id)) for query, artist_id in get_spotify_album_tracks(song)]
            song_queues[guild_id].extend(track_queries_and_genres)
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
    join_view = JoinQuizView(bot)
    join_view.initial_interaction = interaction  # Set the interaction here
    await interaction.response.send_message("🎉 Click to join the music quiz! 🎵", view=join_view)




class JoinQuizView(View):
    def __init__(self, bot, timeout=20):
        super().__init__(timeout=timeout)
        self.bot = bot
        self.joined_users = set()
        self.initial_interaction = None  # Initialize a placeholder for the interaction

    @discord.ui.button(label="Join Quiz", style=discord.ButtonStyle.green)
    async def join_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        log_quiz_interaction(interaction, "Join Quiz", f"{interaction.user.display_name} joined the quiz")
        if self.initial_interaction is None:
            self.initial_interaction = interaction  # Store the interaction when the button is first pressed
        self.joined_users.add(interaction.user.id)
        await interaction.response.send_message(f"✅ {interaction.user.display_name}, you've successfully joined the quiz! Get ready to vote for the genre! 🎶", ephemeral=True)
        button.disabled = True
        await interaction.message.edit(view=self)

    async def on_timeout(self):
        
        for item in self.children:
            item.disabled = True
        if self.initial_interaction:
            await self.initial_interaction.edit_original_response(view=self)
            await self.start_genre_voting(self.initial_interaction, self.joined_users)
            log_quiz_interaction(self.initial_interaction, "Start Genre Voting", "Genre voting started")
        else:
            print("No interaction available for genre voting.")



    async def start_genre_voting(self, interaction, joined_users):
        # Initialize and display the GenreVotingView for genre voting
        genre_voting_view = GenreVotingView(self.bot, interaction, joined_users)  # Include the interaction here
        await interaction.followup.send("🗳️ Vote for your preferred music genre:", view=genre_voting_view)


class GenreVotingView(View):
    def __init__(self, bot, interaction, joined_users, timeout=20):
        super().__init__(timeout=timeout)
        self.bot = bot
        self.interaction = interaction  # Store the interaction
        self.joined_users = joined_users
        self.votes = {genre: 0 for genre in category_playlists.keys()}
        self.add_genre_buttons()

    def add_genre_buttons(self):
        for genre in category_playlists.keys():
            button = discord.ui.Button(label=genre.capitalize(), style=discord.ButtonStyle.secondary)

            async def vote_callback(interaction: discord.Interaction, genre=genre, button=button):
                if interaction.user.id in self.joined_users:
                    self.votes[genre] += 1
                    await interaction.response.send_message(f"{interaction.user.display_name} voted for {genre}!", ephemeral=True)
                    log_quiz_interaction(interaction, "Vote Genre", f"{interaction.user.display_name} voted for {genre}")
                    button.disabled = True
                    await interaction.message.edit(view=self)
                else:
                    await interaction.response.send_message("You need to join the quiz to vote!", ephemeral=True)
    
            button.callback = functools.partial(vote_callback, genre=genre)
            self.add_item(button)

    async def on_timeout(self):
        # Determine the winning genre after voting ends
        winning_genre = max(self.votes, key=self.votes.get)
        # Start the quiz with the winning genre using the stored interaction
        await self.interaction.followup.send(f"The winning genre is {winning_genre}! Starting the quiz... ⛱️")
        log_quiz_interaction(self.interaction, "End Genre Voting", f"Winning genre: {winning_genre}")
        # Call the function to start the quiz with the winning genre
        # Ensure that the function you're calling is designed to start the quiz and handle the interaction properly
        await start_music_quiz(self.interaction, winning_genre, self.joined_users)





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
async def start_music_quiz(interaction: discord.Interaction, category: str, joined_users):
    # Log quiz interaction
    log_quiz_interaction(interaction, "Quiz Start", f"Category: {category}, Participants: {len(joined_users)}")

    # Get playlist URL from category
    playlist_url = category_playlists.get(category.lower())
    if not playlist_url:
        await interaction.response.send_message("Invalid category. Please choose from: rock, pop, rnb, rap.", ephemeral=True)
        return

    # Use cached Spotify tracks
    track_urls = get_cached_spotify_tracks(playlist_url)
    if not track_urls:
        await interaction.response.send_message("Failed to load songs. Please try again later.", ephemeral=True)
        return

    # Select a random track URL
    random_track_url = random.choice(track_urls)

    # Initialize song queue for the guild
    guild_id = interaction.guild_id
    song_queues.setdefault(guild_id, deque()).append(random_track_url)

    # Connect to voice channel if not already connected
    voice_client = interaction.guild.voice_client
    if not voice_client:
        if interaction.user.voice:
            voice_channel = interaction.user.voice.channel
            try:
                voice_client = await voice_channel.connect()
            except Exception as e:
                await interaction.followup.send(f"Failed to connect to voice channel: {e}", ephemeral=True)
                return
        else:
            await interaction.followup.send("You need to be in a voice channel to start the quiz.", ephemeral=True)
            return

    # Play song if not already playing
    if not voice_client.is_playing():
        await play_song_from_queue(interaction)

    # Generate options for the quiz question
    options = [random_track_url] + random.sample(track_urls, 3)
    random.shuffle(options)
    correct_option_index = options.index(random_track_url)

    # Initialize quiz controls and send initial messages
    quiz_controls = MusicQuizControls(bot, interaction, options, correct_option_index, playlist_url, 1, joined_users)
    await interaction.followup.send("Let the quiz begin! Here's the initial scoreboard:", ephemeral=True)
    await quiz_controls.send_scores("Quiz participants 📋:")
    await interaction.followup.send("Guess the song:", view=quiz_controls, ephemeral=True)




@bot.tree.command(name='quiz_category', description='Choose a category for the music quiz')
@app_commands.describe(category='The category for the quiz: rock, pop, rnb, rap')
async def quiz_category(interaction: discord.Interaction, category: str):
    await interaction.response.defer()
    await start_music_quiz(interaction, category)



###### QUIZ BUTTONS #########
import time

class MusicQuizControls(discord.ui.View):
    def __init__(self, bot, interaction, options, correct_option_index, playlist_url, songs_played=0, joined_users=None):
        super().__init__(timeout=None)  # No timeout for the view
        self.bot = bot
        self.interaction = interaction
        self.options = options
        self.correct_option_index = correct_option_index
        self.playlist_url = playlist_url
        self.songs_played = songs_played
        self.joined_users = joined_users if joined_users is not None else set()
        self.correct_guessed = False
        self.song_start_time = time.time()
        self.vote_started = False
        self.user_points = {user_id: 0 for user_id in self.joined_users}  # Initialize user points for joined users
        self.add_option_buttons()

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
        if not self.vote_started:
            self.vote_started = True

        user_id = button_interaction.user.id
        # Ensure the user is marked as joined if they make a guess
        self.joined_users.add(user_id)

        # Initialize user points if not present
        if user_id not in self.user_points:
            self.user_points[user_id] = 0

        # Handle guess and update points
        if guess_index == self.correct_option_index:
            self.user_points[user_id] += 1
            response = f"Correct! +1 point. {button_interaction.user.mention} guessed it right."
            self.correct_guessed = True
        else:
            self.user_points[user_id] -= 1
            response = f"Incorrect! -1 point. {button_interaction.user.mention} guessed it wrong."


        # Send feedback to the user
        await button_interaction.followup.send(response, ephemeral=True)

        # Disable further guesses and handle song change logic
        if self.correct_guessed or time.time() - self.song_start_time >= 60:
            for item in self.children:
                if isinstance(item, discord.ui.Button):
                    item.disabled = True

            if self.correct_guessed:
                # Wait for 10 seconds before changing the song
                await asyncio.sleep(10)
            elif time.time() - self.song_start_time >= 60:
                # Change the song immediately if 60 seconds have passed without a correct guess
                pass  # No additional wait required

            await self.change_song(button_interaction)




    async def send_scores(self, message_prefix=""):
        scores_message = message_prefix + "\n"
        for user_id, score in self.user_points.items():  # Iterate through user_points dictionary
            user = await self.bot.fetch_user(user_id)
            scores_message += f"🔹 {user.name}: {score} points\n"

        # Use followup.send to make the scores message visible to everyone
        await self.interaction.followup.send(scores_message)



    async def change_song(self, interaction):
        # Check if the quiz has reached the limit of songs to be played
        if self.songs_played >= 5:
            # Send final scores and reset the quiz
            await self.send_final_scores(interaction)
            await self.reset_quiz(interaction)
            return

        self.songs_played += 1  # Increment the song counter
        self.correct_guessed = False  # Reset for the next song

        # Send the updated scores before starting the new song
        await self.send_scores("Current score 📋:")

        # Fetch new track URLs from the Spotify playlist for the next quiz question
        track_urls = get_spotify_playlist_tracks(self.playlist_url)
        new_track_urls = [url for url in track_urls if url not in self.options]  # Avoid repeating songs
        random_track_url = random.choice(new_track_urls)

        # Update the song queue for the next quiz question
        guild_id = interaction.guild_id
        song_queues[guild_id] = deque([random_track_url])  # Reset the queue with the new song

        # Play the new song
        if interaction.guild.voice_client:
            interaction.guild.voice_client.stop()  # Stop the current song if any

        await play_song_from_queue(interaction)

        # Generate new quiz options ensuring they are unique and do not repeat the previous ones
        new_options = [random_track_url] + random.sample([url for url in new_track_urls if url != random_track_url], 3)
        random.shuffle(new_options)  # Shuffle the new options to randomize the display order
        new_correct_option_index = new_options.index(random_track_url)  # Find the index of the correct option in the new options list

        # Create a new instance of MusicQuizControls with the new options for the next quiz question
        new_quiz_controls = MusicQuizControls(self.bot, interaction, new_options, new_correct_option_index, self.playlist_url, self.songs_played, self.joined_users)

        # Send a new message with the new quiz question and options
        await interaction.followup.send("🎵 Guess the new song:", view=new_quiz_controls)






    async def reset_quiz(self, interaction):
        # Reset the scores
        user_points.clear()

        # Clear the song queue for the guild
        guild_id = interaction.guild_id
        if guild_id in song_queues:
            song_queues[guild_id].clear()

    async def send_final_scores(self):
        await self.send_scores("🎉 The music quiz is over! Final scores 🎼:")
            # Leave the voice channel after sending the final scores
        voice_client = self.interaction.guild.voice_client
        if voice_client and voice_client.is_connected():
            await voice_client.disconnect()
    # Remember to add buttons for options when initializing MusicQuizControls


# When initializing MusicQuizControls, also call add_buttons to add the option buttons


###### LOGGING FOR DATA ANALYSES OF THE BOT  ###############
import csv
import datetime
def log_interaction(interaction, action, details):
    with open('bot_interactions.csv', 'a', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        current_time = datetime.datetime.now().isoformat()
        writer.writerow([interaction.user.id, interaction.user.name, action, details, str(interaction.created_at), current_time])

def log_quiz_interaction(interaction, action, details):
    with open('music_quiz_interactions.csv', 'a', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        current_time = datetime.datetime.now().isoformat()  # Use the current time
        writer.writerow([
            interaction.user.id,
            interaction.user.name,
            action,
            details,
            current_time  # Log the current timestamp instead of interaction.created_at
        ])


### TOKEN TO RUN THE BOT ####

bot.run('')

