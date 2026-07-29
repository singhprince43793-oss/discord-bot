import discord
from discord.ext import commands, tasks
import json
import os
import asyncio
from datetime import datetime, timezone

# --- CONFIG ---
TOKEN = os.getenv("TOKEN")
ALLOWED_CATEGORY_ID = 1515016181059420181
PLAN_ROLE_NAME = "reply member's"
FILE = "responses.json"
TEMP_FILE = "temproles.json"

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# --- LOAD/SAVE ---
def load_data(filename):
    if not os.path.exists(filename): return {}
    with open(filename, "r", encoding="utf-8") as f:
        try: return json.load(f)
        except: return {}

def save_data(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

# --- BACKGROUND TASK ---
@tasks.loop(minutes=1)
async def process_temproles():
    data = load_data(TEMP_FILE)
    if not data: return
    now = datetime.now(timezone.utc).timestamp()
    changed = False

    for key in list(data.keys()):
        info = data[key]
        if info["remove_at"] > now: continue
        guild = bot.get_guild(info["guild_id"])
        if guild:
            member = guild.get_member(info["member_id"])
            role = guild.get_role(info["role_id"])
            if member and role:
                try: await member.remove_roles(role)
                except: pass
        del data[key]
        changed = True
    if changed: save_data(TEMP_FILE, data)

# --- EVENTS ---
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    if not process_temproles.is_running():
        process_temproles.start()

@bot.event
async def on_message(message):
    if message.author.bot:
        await bot.process_commands(message)
        return
    if message.channel.category and message.channel.category.id == ALLOWED_CATEGORY_ID:
        data = load_data(FILE)
        for trigger, reply in data.items():
            if trigger.lower() in message.content.lower():
                sent_msg = await message.channel.send(reply)
                await asyncio.sleep(30)
                try: await sent_msg.delete()
                except: pass
                break
    await bot.process_commands(message)

# --- COMMANDS ---
@bot.command()
async def add(ctx, *, args: str):
    if "|" not in args: return await ctx.send("❌ Format: !add trigger | reply")
    parts = args.split("|", 1)
    data = load_data(FILE)
    data[parts[0].strip().lower()] = parts[1].strip()
    save_data(FILE, data)
    await ctx.send(f"✅ Added: {parts[0].strip()} → {parts[1].strip()}")

@bot.command(name="list")
async def list_replies(ctx):
    data = load_data(FILE)
    if not data: await ctx.send("No replies saved.")
    else: await ctx.send("**Saved Replies:**\n" + "\n".join([f"🔹 {k} → {v}" for k, v in data.items()]))

@bot.command()
@commands.has_permissions(manage_roles=True)
async def addplan(ctx, member: discord.Member, days: int):
    role = discord.utils.get(ctx.guild.roles, name=PLAN_ROLE_NAME)
    if not role: role = await ctx.guild.create_role(name=PLAN_ROLE_NAME)
    await member.add_roles(role)
    data = load_data(TEMP_FILE)
    data[f"{ctx.guild.id}-{member.id}-{role.id}"] = {
        "guild_id": ctx.guild.id, "member_id": member.id, "role_id": role.id,
        "remove_at": datetime.now(timezone.utc).timestamp() + (days * 86400)
    }
    save_data(TEMP_FILE, data)
    await ctx.send(f"✅ {member.mention} got **{role.name}** for {days} days.")

@bot.command()
@commands.has_permissions(manage_roles=True)
async def removeplan(ctx, member: discord.Member):
    role = discord.utils.get(ctx.guild.roles, name=PLAN_ROLE_NAME)
    if role in member.roles: await member.remove_roles(role)
    await ctx.send(f"✅ Removed plan from {member.mention}.")

@bot.command(name="plans")
@commands.has_permissions(manage_roles=True)
async def list_plans(ctx):
    data = load_data(TEMP_FILE)
    msg = "**Active Plans:**\n" + "\n".join([f"🔹 {v['member_id']}" for v in data.values()])
    await ctx.send(msg if data else "No active plans.")

bot.run(TOKEN)