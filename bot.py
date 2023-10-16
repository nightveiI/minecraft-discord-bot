
import asyncio
import time
import random
import string
import discord  # pip install discord.py
from discord.ext import commands, tasks # pip install discord.py
from mcstatus import JavaServer  # pip install mcstatus
from jproperties import Properties # pip install jproperties
import serverhandler

# defs
confirmation_timeout_in_seconds = 30

# globals
mcserver = serverhandler.ServerHandler()
service_active = False  # an internal flag that says whether the server is running. mostly used for the watchdog
watchdog_patted = True   # an internal flag; when toggled to True from false, the server sends a message to the dev channel
active_player_check_failed = False  # an internal flag used to indicate whether a previous status message had no one playing. used for server spindown control
permanently_on = False  # a command flag that latches the server on (i.e. it doesn't switch off if no one is playing)
stop_request_time = None  # holds the time of the last !stop request, so another !stop within the next x seconds can shut the server down

configs = Properties() 
with open('bot.properties', 'rb') as read_prop: 
    configs.load(read_prop)



helptext = "I'm theMinecraft Bot! I have the following ACTs:" \
           "\n\t**!help, !h** - get this message!" \
           "\n\t**!status** - find out whether or not the minecraft server is running" \
           "\n\t**!start** - start the minecraft server, if it isn't running but I'm online" \
            "\n\t**!latch** - toggle the server latch. If the server is latched, it will stay on even if no one is playing" \
            "\n\t**!say** - say something in the server chat" \
            "\n\t**!whitelist** - add someone to the whitelist" \
            "\n\t**!save** - save the server" \
            "\n\t**!_stop** - stop the server manually, even if someone is playing" \
          f"\n\t**!stop** - stop the server manually, if no one is playing" 

# get bot properties
bot_properties = dict()
with open("bot.properties", "r") as fi:
    for line in fi.readlines():
        try:
            splitline = [x.strip() for x in line.split("=")]
            bot_properties[splitline[0]] = splitline[1]
        except:
            print(f"Bad line in bot.properties: {line}")

# get admins
admins = set()
with open("admin.properties", "r") as fi:
    for line in fi.readlines():
        try:
            admins.add(line.strip())
        except:
            print(f"Bad line in admin.properties: {line}")



bot = commands.Bot(
     intents=discord.Intents.all(),
    command_prefix='!',
    help_command=None
)

def getAuthor(ctx):
    return str(ctx.author).strip()


def confirmAdmin(ctx):
    """
    Make sure that I'm sending the debug commands. Raise an exception otherwise.
    :param ctx: message context
    :return:
    """
    if getAuthor(ctx) not in admins:
        raise Exception(f"{ctx.author} tried to use a mod command.")


@bot.command()
async def help(ctx):
    """
    Bot command to display helptext.
    :param ctx: message context (internal)
    :return: None
    """
    await ctx.send(helptext)


@bot.command()
async def h(ctx):
    """
    Bot command to display helptext.
    :param ctx: message context (internal)
    :return: None
    """
    await ctx.send(helptext)


@bot.command()
async def start(ctx):
    """
    Bot command to start the server, if it isn't already started.
    :param ctx: message context (internal)
    :return: None
    """
    try:
        server = JavaServer.lookup("127.0.0.1:25565")
        server_status = server.status()

        if server_status.players.online:
            already_on = True
        else:
            already_on = False
    except:  # not sure if this raises exception or just returns False by default
        already_on = False

    if already_on:
        await ctx.send(f"The server is already online! There are {server_status.players.online} players connected.")
    else:
        await ctx.send('Starting server! Give me a sec...')
        try:
            mcserver.start()
        except Exception as e:
            print(e)


@bot.command()
async def stop(ctx):
    """
    Bot command to stop the server if no one is currently playing.
    :param ctx: message context (internal)
    :return: None
    """
    global stop_request_time
    global service_active
    current_players = 0
    current_time = time.time()

    try:
        server = JavaServer.lookup("127.0.0.1:25565")
        server_status = server.status()
        current_players = server_status.players.online
    except:
        pass

    if current_players > 0:
        await ctx.send(f"There are currently players ({current_players}) on the server, so I'm not going to listen to you!")
    else:
        if stop_request_time is None or (current_time - stop_request_time) > 10:
            stop_request_time = current_time
            await ctx.send('To manually stop the server, please use !stop again within 10 seconds.')
        else:
            await ctx.send('Stopping server. Thanks!')
            service_active = False  # sure hope we don't end up in a race condition
            mcserver.stop()


@bot.command()
async def _stop(ctx):
    """
    Bot command to stop the server even if someone is playing.
    :param ctx: message context (internal)
    :return: None
    """
    global stop_request_time
    global service_active
    current_players = 0
    current_time = time.time()

    try:
        server = JavaServer.lookup("127.0.0.1:25565")
        server_status = server.status()
    except:
        pass

    if stop_request_time is None or (current_time - stop_request_time) > 10:
        stop_request_time = current_time
        await ctx.send('To manually stop the server, please use !_stop again within 10 seconds.')
    else:
        await ctx.send('Stopping server. Thanks!')
        service_active = False  # sure hope we don't end up in a race condition
        mcserver.stop()


@bot.command()
async def latch(ctx):
    """
    Bot command to keep the server running when no players are active (or disable this behaviour)
    :param ctx: message context (internal)
    :return: None
    """
    global permanently_on
    confirmAdmin(ctx)
    if permanently_on:
        permanently_on = False
        await ctx.send('Server is delatched and will switch off after 10 minutes of 0 players.')
    else:
        permanently_on = True
        await ctx.send('Server is latched and will stay on permanently.')


@bot.command()
async def status(ctx):
    """
    Bot command to provide an indicator of server activity.
    :param ctx: message context (internal)
    :return: None
    """
    global service_active
    global permanently_on
    server = JavaServer.lookup("127.0.0.1:25565")
    borked = False

    if service_active:
        try:
            server_status = server.status()
            status_message = f"The server has been online since {mcserver.uptimeAsString()}.\n" \
                             f"There are {server_status.players.online} players connected.\n" \
                             f"Server latch state is {permanently_on}."
        except:
            borked = True
    else:
        status_message = f"The server is offline."

    if borked:
        await ctx.send('The server is currently [[DATA EXPUNGED]]')
    else:
        await ctx.send(status_message)


@bot.command()
async def say(ctx, *args):
    confirmAdmin(ctx)
    mcserver.sendRcon(f"/say Minecraft Bot says: {' '.join(args)}")


@bot.command()
async def whitelist(ctx, arg):
    confirmAdmin(ctx)
    mcserver.sendRcon(f"/whitelist add {arg}")


@bot.command()
async def save(ctx):
    confirmAdmin(ctx)
    mcserver.sendRcon(f"/save-all")


# watchdog/service checker
async def serviceCheck():
    global service_active
    global watchdog_patted
    borked = False
    server = None
    mcChannel = bot.get_channel(int(configs.get("server_status_channel_id").data))
    devChannel = bot.get_channel(int(configs.get("automessage_channel_id").data))
    # if the service is running, act as a watchdog and alert the dev channel if something goes wrong
    # if the service is not running, keep checking to see when it is, then update the server-status channel

    while not bot.is_closed():
        if not service_active:
            try:
                server = JavaServer.lookup("127.0.0.1:25565")
                server.status()
                service_active = True
                await mcChannel.send("The server is now available!")
            except:
                pass
        else:
            try:
                server.status()
            except:
                borked = True

        if borked:
            if watchdog_patted:
                watchdog_patted = False
                await devChannel.send("Watchdog wasn't patted! Something went wrong.")

        await asyncio.sleep(60)  # check every 1 minute

# create a check to see if there are any players online and if not, shut down the server
async def activePlayerCheck():
    global active_player_check_failed
    global service_active
    global watchdog_patted
    global permanently_on
    global stop_request_time
    mcChannel = bot.get_channel(int(configs.get("server_status_channel_id").data))
    devChannel = bot.get_channel(int(configs.get("automessage_channel_id").data))
    # if the service is running, act as a watchdog and alert the dev channel if something goes wrong
    # if the service is not running, keep checking to see when it is, then update the server-status channel

    while not bot.is_closed():
        try:
            server = JavaServer.lookup("127.0.0.1:25565")
            server_status = server.status()
            current_players = server_status.players.online
            if current_players == 0 and not permanently_on:
                if not active_player_check_failed:
                    active_player_check_failed = True
                else:
                    await mcChannel.send("No one is playing! Shutting down in 10 minutes.")
                    await asyncio.sleep(600)
                    if server_status.players.online == 0:
                        await mcChannel.send("No one is playing! Shutting down now.")
                        service_active = False
                        mcserver.stop()
                        active_player_check_failed = False
            else:
                active_player_check_failed = False
        except:
            pass


@bot.event
async def on_ready():
    print(f"{bot.user} has connected to Discord!")
    channel = bot.get_channel(int(configs.get("server_status_channel_id").data))
    await channel.send("Hello! Use the command !start to start the server, or !help to see what else I can do.")

@bot.event
async def on_message(message):
    if message.content == 'test':
        await message.channel.send('Testing 1 2 3')
    elif message.content == '!help' or "!h":
        await bot.process_commands(message)
    elif message.content == '!start':
        await bot.process_commands(message)
    elif message.content == '!stop':
        await bot.process_commands(message)
    elif message.content == '!latch':
        await bot.process_commands(message)
    elif message.content == '!status':
        await bot.process_commands(message)
    elif message.content == '!say':
        await bot.process_commands(message)
    elif message.content == '!whitelist':
        await bot.process_commands(message)
    elif message.content == '!save':
        await bot.process_commands(message)
    elif message.content == '!_stop':
        await bot.process_commands(message)
    elif message.content == '!activePlayerCheck':
        await bot.process_commands(message)
    elif message.content == '!serviceCheck':
        await bot.process_commands(message)
    else:
        await message.channel.send("I don't understand that command. Try !help to see what I can do.")
        

async def main():
    async with bot:
        bot.loop.create_task(activePlayerCheck())
        bot.loop.create_task(serviceCheck())
        await bot.start(configs.get("token").data)

asyncio.run(main())

# start bot
bot.run(
    configs.get("token").data
)
