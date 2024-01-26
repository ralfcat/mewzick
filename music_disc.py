import discord
from discord.ext import commands
import youtube_dl
from collections import deque
from discord.ui import Button, View

bot = commands.Bot(command_prefix='!')
song_queue = deque()

# Function to play the next song in the queue
async def play_next(ctx):
    if song_queue:
        song_url = song_queue.popleft()
        await play(ctx, song_url)
    else:
        await ctx.voice_client.disconnect()

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')

@bot.command(name='join', help='Tells the bot to join the voice channel')
async def join(ctx):
    if not ctx.message.author.voice:
        await ctx.send("You are not connected to a voice channel.")
        return
    else:
        channel = ctx.message.author.voice.channel
    await channel.connect()

@bot.command(name='play', help='To play song')
async def play(ctx, url):
    if not ctx.voice_client:
        await join(ctx)
    ctx.voice_client.stop()
    FFMPEG_OPTIONS = {'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5', 'options': '-vn'}
    YDL_OPTIONS = {'format': 'bestaudio'}
    vc = ctx.voice_client

    try:
        with youtube_dl.YoutubeDL(YDL_OPTIONS) as ydl:
            info = ydl.extract_info(url, download=False)
            url2 = info['formats'][0]['url']
            source = await discord.FFmpegOpusAudio.from_probe(url2, **FFMPEG_OPTIONS)
            vc.play(source, after=lambda e: play_next(ctx))
    except Exception as e:
        await ctx.send(f"An error occurred: {str(e)}")

@bot.command(name='pause', help='This command pauses the song')
async def pause(ctx):
    await ctx.voice_client.pause()
    await ctx.send("Paused ⏸️")

@bot.command(name='resume', help='Resumes the song')
async def resume(ctx):
    await ctx.voice_client.resume()
    await ctx.send("Resuming ▶️")

@bot.command(name='leave', help='To make the bot leave the voice channel')
async def leave(ctx):
    await ctx.voice_client.disconnect()

@bot.command(name='queue', help='Add a song to the queue')
async def queue(ctx, url):
    song_queue.append(url)
    await ctx.send(f"Song added to queue. Position: {len(song_queue)}")

@bot.command(name='music_controls', help='Show music control buttons')
async def music_controls(ctx):
    view = View()
    view.add_item(Button(label="Pause", style=discord.ButtonStyle.red, custom_id="pause_button"))
    # Add more buttons for play, skip, stop
    await ctx.send("Control the music:", view=view)

@bot.event
async def on_button_click(interaction):
    if interaction.custom_id == "pause_button":
        await pause(interaction)
    # Handle other buttons

bot.run('YOUR_BOT_TOKEN')
