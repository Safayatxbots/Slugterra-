
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from tinydb import TinyDB, Query
from datetime import datetime, timezone
import hashlib

# === CONFIG ===
BOT_TOKEN = "7803226404:AAGx-YvdgquS9qU3rzULa09zQBsoYgYUcjY"
OWNER_ID = 6279412066
DB = TinyDB("datta.json")
UserQ = Query()



import os
import json
from tinydb import TinyDB, Query
from datetime import datetime, timezone

DB_PATH = "bot_data.json"

# 🛡️ Check and fix empty DB file
if os.path.exists(DB_PATH) and os.path.getsize(DB_PATH) == 0:
    with open(DB_PATH, 'w') as f:
        json.dump({}, f)  # write an empty dict to make it valid JSON

DB = TinyDB(DB_PATH)
UserQ = Query()

today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
task_table = DB.table("tasks")
LOG_GROUP_ID = -1002893931329

REWARD_VALUES = {
    "key": {"gems": 450, "coins": 10000},
    "slug": {"gems": 1100, "coins": 80000},
    "daily_limit": {"gems": 700, "coins": 30000},
}

try:
    today_task = task_table.get(UserQ.date == today)
    if not isinstance(today_task, dict):
        raise TypeError("Corrupted data structure")
except Exception as e:
    print("💥 Error reading task table:", e)
    task_table.truncate()
    today_task = {"date": today, "tasks": []}

from tinydb import where
today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
task_table = DB.table("tasks")  # ✅ define it first

try:
    today_task = task_table.get(UserQ.date == today)
    if not isinstance(today_task, dict):
        raise TypeError("Corrupted data structure")
except Exception as e:
    print("💥 Error reading task table:", e)
    task_table.truncate()
    today_task = {"date": today, "tasks": []}

from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()

def reset_profiles():
    progress_table = DB.table("progress")
    for user in progress_table.all():
        user_id = user["id"]
        progress_table.update({
            "count": 0,
            "keys": 0,
            "slugs": {},
            "limit_done": False,
            "message_ids": []
        }, UserQ.id == user_id)
    print("✅ All user profiles reset for new day.")

async def on_startup(app):
    scheduler.add_job(reset_profiles, "cron", hour=0, minute=0)
    scheduler.start()
    print("🕛 Scheduler started.")



async def log_task_completion(context: ContextTypes.DEFAULT_TYPE, user_id: int):
    user = await context.bot.get_chat(user_id)
    progress_table = DB.table("progress")
    task_data = DB.table("tasks").get(UserQ.date == datetime.now(timezone.utc).strftime("%Y-%m-%d")) or {"tasks": []}
    user_data = progress_table.get(UserQ.id == user_id) or {}
    completed_before = user_data.get("completed_tasks", [])

    new_completed = []
    total_gems = 0
    total_coins = 0

    for idx, task in enumerate(task_data["tasks"], 1):
        if str(idx) in completed_before:
            continue  # already logged

        if task["type"] == "key":
            if user_data.get("keys", 0) >= task["min"]:
                new_completed.append(str(idx))
                total_gems += REWARD_VALUES["key"]["gems"]
                total_coins += REWARD_VALUES["key"]["coins"]
        elif task["type"] == "slug":
            slug_count = user_data.get("slugs", {}).get(task["name"].lower(), 0)
            if slug_count >= task["count"]:
                new_completed.append(str(idx))
                total_gems += REWARD_VALUES["slug"]["gems"]
                total_coins += REWARD_VALUES["slug"]["coins"]
        elif task["type"] == "daily_limit":
            if user_data.get("limit_done", False):
                new_completed.append(str(idx))
                total_gems += REWARD_VALUES["daily_limit"]["gems"]
                total_coins += REWARD_VALUES["daily_limit"]["coins"]

    if not new_completed:
        return  # Nothing new completed

    message = (
        f"👤 Name: {user.first_name}\n"
        f"🆔 ID: `{user.id}`\n"
        f"🔗 Username: @{user.username or 'N/A'}\n"
        f"✅ Completed Tasks: {', '.join(new_completed)}\n"
        f"💎 Gems to Send: {total_gems}\n"
        f"🪙 Coins to Send: {total_coins}"
    )

    # Send logs
    await context.bot.send_message(chat_id=OWNER_ID, text=message, parse_mode="Markdown")
    await context.bot.send_message(chat_id=LOG_GROUP_ID, text=message, parse_mode="Markdown")

    # Mark as completed
    updated = list(set(completed_before + new_completed))
    progress_table.update({"completed_tasks": updated}, UserQ.id == user_id)




# === /approve ===
async def approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return await update.message.reply_text("Unauthorized.")

    if update.message.reply_to_message:
        user_id = update.message.reply_to_message.from_user.id
    elif context.args:
        try:
            user_id = int(context.args[0])
        except ValueError:
            return await update.message.reply_text("❌ Invalid user ID.")
    else:
        return await update.message.reply_text("Usage: Reply to a user or /approve <user_id>")

    DB.table("approved").upsert({"id": user_id}, UserQ.id == user_id)
    await update.message.reply_text(f"✅ Approved user `{user_id}`", parse_mode="Markdown")

# === /unapprove ===
async def unapprove(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return await update.message.reply_text("Unauthorized.")

    if update.message.reply_to_message:
        user_id = update.message.reply_to_message.from_user.id
    elif context.args:
        try:
            user_id = int(context.args[0])
        except ValueError:
            return await update.message.reply_text("❌ Invalid user ID.")
    else:
        return await update.message.reply_text("Usage: Reply to a user or /unapprove <user_id>")

    DB.table("approved").remove(UserQ.id == user_id)
    await update.message.reply_text(f"🚫 Unapproved user `{user_id}`", parse_mode="Markdown")

# === /settask1 (key task) ===
async def settask1(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return await update.message.reply_text("Unauthorized.")
    if len(context.args) < 2:
        return await update.message.reply_text("Usage: /settask1 <min> <max>")
    try:
        min_keys = int(context.args[0])
        max_keys = int(context.args[1])
        if min_keys > max_keys:
            return await update.message.reply_text("❌ Min cannot be greater than max.")
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        task_table = DB.table("tasks")
        today_task = task_table.get(UserQ.date == today) or {"date": today, "tasks": []}
        today_task["tasks"].append({"type": "key", "min": min_keys, "max": max_keys})
        task_table.upsert(today_task, UserQ.date == today)
        await update.message.reply_text("✅ Key task added.")
    except ValueError:
        await update.message.reply_text("❌ Invalid input.")

# === /settask2 (slug task) ===
async def settask2(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return await update.message.reply_text("Unauthorized.")
    if len(context.args) < 2:
        return await update.message.reply_text("Usage: /settask2 <slugname> <count>")

    try:
        slug = context.args[0].lower()
        count = int(context.args[1])
    except ValueError:
        return await update.message.reply_text("❌ Count must be a number.")

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    task_table = DB.table("tasks")
    
    today_task = task_table.get(UserQ.date == today)
    if not isinstance(today_task, dict):
        today_task = {"date": today, "tasks": []}

    today_task["tasks"].append({"type": "slug", "name": slug, "count": count})
    task_table.upsert(today_task, UserQ.date == today)

    await update.message.reply_text(f"✅ Slug task added: {slug.capitalize()} × {count}")



# === /settask3 (daily limit task) ===
async def settask3(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return await update.message.reply_text("Unauthorized.")
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    task_table = DB.table("tasks")
    today_task = task_table.get(UserQ.date == today) or {"date": today, "tasks": []}
    today_task["tasks"].append({"type": "daily_limit"})
    task_table.upsert(today_task, UserQ.date == today)
    await update.message.reply_text("✅ Daily Limit task added.")

# === /task ===
async def task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not DB.table("approved").contains(UserQ.id == user_id):
        return await update.message.reply_text("❌ You are not approved.")
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    data = DB.table("tasks").get(UserQ.date == today)
    if not data:
        return await update.message.reply_text("⚠️ No tasks set for today.")
    lines = ["🎯 𝗧𝗼𝗱𝗮𝘆'𝘀 𝗧𝗮𝘀𝗸 :\n\n"]
    for t in data["tasks"]:
        if t["type"] == "key":
            lines.append(f"🔑 Collect {t['min']}–{t['max']} keys")
        elif t["type"] == "slug":
            lines.append(f"🐌 Find {t['count']} × {t['name'].capitalize()}")
        elif t["type"] == "daily_limit":
            lines.append("⚡ Finish your daily limit on @Slugterraa_bot")
    await update.message.reply_text("\n".join(lines))

# === /profile ===
# === /profile ===
async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name
    if not DB.table("approved").contains(UserQ.id == user_id):
        return await update.message.reply_text("❌ You are not approved.")
    
    progress = DB.table("progress").get(UserQ.id == user_id) or {}
    keys = progress.get("keys", 0)
    slugs = progress.get("slugs", {})
    limit_done = progress.get("limit_done", False)
    
    lines = [
        f"✵ Name : {user_name}",
        f"► ID : `{user_id}`",
        f"► Keys : {keys}",
        f"► Slugs :"
    ]
    
    if slugs:
        for name, count in slugs.items():
            lines.append(f"{name.capitalize()} : {count}")
    else:
        lines.append("   ┗ None")
    
    lines.append(f"► Daily limit : {'✅' if limit_done else '❌'}")
    
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

# === /get (admin check user profile) ===
# === /get (admin check user profile) ===
async def get(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return await update.message.reply_text("Unauthorized.")
    
    if not update.message.reply_to_message:
        return await update.message.reply_text("❌ Reply to a user to get their profile.")
    
    user = update.message.reply_to_message.from_user
    user_id = user.id
    user_name = user.first_name
    
    progress = DB.table("progress").get(UserQ.id == user_id) or {}
    keys = progress.get("keys", 0)
    slugs = progress.get("slugs", {})
    limit_done = progress.get("limit_done", False)
    
    lines = [
        f"✵ Name : {user_name}",
        f"► ID : `{user_id}`",
        f"► Keys : {keys}",
        f"► Slugs :"
    ]
    
    if slugs:
        for name, count in slugs.items():
            lines.append(f"{name.capitalize()} : {count}")
    else:
        lines.append("   ┗ None")
    
    lines.append(f"► Daily limit : {'✅' if limit_done else '❌'}")
    
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

# === /start ===
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def reset_profiles():
    progress_table = DB.table("progress")
    for user in progress_table.all():
        user_id = user["id"]
        progress_table.update({
            "count": 0,
            "keys": 0,
            "slugs": {},
            "limit_done": False,
            "message_ids": [],
            "completed_tasks": []  # ← add this
        }, UserQ.id == user_id)
    print("✅ All user profiles reset for new day.")

async def addkey(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not DB.table("approved").contains(UserQ.id == user_id):
        return await update.message.reply_text("❌ You are not approved.")
    progress_table = DB.table("progress")
    user_data = progress_table.get(UserQ.id == user_id) or {"id": user_id}
    user_data["keys"] = user_data.get("keys", 0) + 1
    progress_table.upsert(user_data, UserQ.id == user_id)

    await update.message.reply_text("🔑 Key added.")
    await log_task_completion(context, user_id)  # 👈 log check

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not DB.table("approved").contains(UserQ.id == user_id):
        return await update.message.reply_text("❌ You are not approved.")

    keyboard = [
        [
            InlineKeyboardButton("⚡ Support", url="https://t.me/AshxSupport"),
            InlineKeyboardButton("🔥 Updates", url="https://t.me/Ashxbots")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    caption = (
        "👋 Welcome to the 𝗥𝗲𝘄𝗮𝗿𝗱𝘀 𝗼𝗳 𝗦𝗵𝗮𝗻𝗲 𝗚𝗮𝗻𝗴\n\n"
        "I gives daily task 🗒️. Complete and get Rewards 💎 from Gang Admins"
    )

    await context.bot.send_photo(
        chat_id=update.effective_chat.id,
        photo="https://envs.sh/2P5.jpg",  # Replace with your image URL
        caption=caption,
        reply_markup=reply_markup
    )


# === Setup Bot ===
app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("apv", approve))
app.add_handler(CommandHandler("unapv", unapprove))
app.add_handler(CommandHandler("settask1", settask1))
app.add_handler(CommandHandler("settask2", settask2))
app.add_handler(CommandHandler("settask3", settask3))
app.add_handler(CommandHandler("task", task))
app.add_handler(CommandHandler("myprofile", profile))
app.add_handler(CommandHandler("get", get))

print("🤖 Bot is running...")
app.run_polling()
