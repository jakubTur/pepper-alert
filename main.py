import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv
import os
import logging
import json
from bs4 import BeautifulSoup
import requests

logging.basicConfig(level=logging.INFO)
load_dotenv()
token = os.getenv("DISCORD_TOKEN")

handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

role_prefix = "PEPPERALERT "
db_file = "servers.json"
link_prefix = "https://www.pepper.pl/search?q="

bot = commands.Bot(command_prefix='!', intents=intents)
bot.manage_roles = True

@bot.event
async def on_ready():
    print("bot online")
    await scrap()

@bot.event
async def on_guild_join(context):
    await context.send("Witaj! PepperAlert to bot alertujący użytkowników o pojawianiu się nowych ofert na stronie pepper.pl\n"
    "Aby dodać alert i odpowiadającą mu rolę użyj !add_alert <fraza wyszukiwana na pepper.pl> "
    "na wybranym dla niego kanale\n"
    "Aby usunąć alert i odpowiadającą mu rolę użyj !remove_alert <fraza wyszukiwana na pepper.pl>\n"
    "Aby wybrać alerty, dla których chcesz otrzymywać powiadomienia użyj !pepper\n"
    "Po więcej informacji użyj !help")

@bot.command()
async def pepper(context):
    pass
    # TODO: default command, shows current avaliable alerts in button form and enables toggling between them through buttonns
    
@bot.command()
@commands.has_permissions(manage_roles=True)
async def add_alert(context, name):
    role_name = role_prefix + name
    role = discord.utils.get(context.guild.roles, name=role_name)
    if not role:
        await context.guild.create_role(name=role_name, mentionable=True)
        await context.send(f"{context.author.mention} Rola dla wyszukania {name} została utworzona.")
        role = discord.utils.get(context.guild.roles, name=role_name)
    with open(db_file, "r") as db:
        data = json.load(db)
    server_id = str(context.guild.id)
    channel_id = str(context.channel.id)
    role_id = str(role.id)
    if server_id not in data:
        data[server_id] = {}
    if channel_id not in data[server_id]:
        data[server_id][channel_id] = { name: None }
    else:
        data[server_id][channel_id].update({ name: None })
    with open(db_file, "w") as db:
        json.dump(data, db)

@bot.command()
@commands.has_permissions(manage_roles=True)
async def remove_alert(context, name):
    role_name = role_prefix + name
    role = discord.utils.get(context.message.guild.roles, name=role_name)
    if role:
        await role.delete()
    with open(db_file, "r") as db:
        data = json.load(db)
    server_id = str(context.guild.id)
    if server_id:
        for channel in data[server_id]:
            if name in data[server_id][channel]:
                data[server_id][channel].pop(name, None)
                await context.send(f"{context.author.mention} Usunięto alert")
                with open(db_file, "w") as db:
                    json.dump(data, db)
                return
    await context.send(f"{context.author.mention} Nie znaleziono alertu. Pamiętaj, aby podać samo wyszukiwanie, bez prefixu {role_prefix}")

@add_alert.error
@remove_alert.error
async def no_permissions(context, error):
    if(isinstance(error, commands.MissingPermissions)):
        await context.send(f"{context.author.mention} Nie masz uprawnień do zarządzania rolami - poproś admina o dodanie"
                            "lub usunięcie alertu.")

@bot.command()
async def alert_me(context, name): #move this to !pepper
    alert_role = discord.utils.get(context.guild.roles, role_prefix+name)
    if alert_role:
        await context.author.add_roles(alert_role)
        await context.send(f"{context.author.mention} Przyznano rolę.")
    else:
        await context.send(f"{context.author.mention} Brak roli dla podanego wyszukania - poproś admina serwera o dodanie alertu.")

@tasks.loop(minutes=5)
async def scrap():
    with open(db_file, "r") as db: # {"server_id": { "channel_id": { "query": "last listing link"}}}
        data = json.load(db)
    for server_id in data:
        server = bot.get_guild(int(server_id))
        for channel_id in data[server_id]:
            channel = server.get_channel(int(channel_id))
            for query in data[server_id][channel_id]:
                role = discord.utils.get(server.roles, name=role_prefix+query)
                search_page = requests.get(link_prefix + query)
                soup = BeautifulSoup(search_page.text, "html.parser")
                logging.log(logging.INFO, search_page.text)
                listings = soup.findAll("a", attrs={"class":"cept-tt thread-link linkPlain thread-title--list js-thread-title"})
                if role:
                    try:
                        if(not listings[0].href == data[server_id][channel_id][query]):
                            await channel.send(f"{role.mention} {listings[0].title} {listings[0].href}")
                            data[server_id][channel_id][query] = listings[0].href
                            with open(db_file, "w") as dbw:
                                json.dump(data, dbw)
                    except(IndexError):
                        print("index out of bounds")
                else:
                    await channel.send(f"Brak roli dla wyszukania {query} - poproś admina serwera o dodanie alertu.")

bot.run(token, log_handler=handler, log_level=logging.DEBUG)