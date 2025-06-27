
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



# === /approve ===
async def approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return await update.message.reply_text("Unauthorized.")
    if not context.args:
        return await update.message.reply_text("Usage: /approve <user_id>")
    try:
        user_id = int(context.args[0])
        DB.table("approved").upsert({"id": user_id}, UserQ.id == user_id)
        await update.message.reply_text(f"✅ Approved user {user_id}")
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID")

# === /unapprove ===
async def unapprove(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return await update.message.reply_text("Unauthorized.")
    if not context.args:
        return await update.message.reply_text("Usage: /unapprove <user_id>")
    try:
        user_id = int(context.args[0])
        DB.table("approved").remove(UserQ.id == user_id)
        await update.message.reply_text(f"🚫 Unapproved user {user_id}")
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID")

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
    lines = ["🎯 Today's tasks:"]
    for t in data["tasks"]:
        if t["type"] == "key":
            lines.append(f"🔑 Collect {t['min']}–{t['max']} keys")
        elif t["type"] == "slug":
            lines.append(f"🐌 Find {t['count']} × {t['name'].capitalize()}")
        elif t["type"] == "daily_limit":
            lines.append("⚡ Finish your daily limit on @Slugterraa_bot")
    await update.message.reply_text("\n".join(lines))

# === /profile ===
async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not DB.table("approved").contains(UserQ.id == user_id):
        return await update.message.reply_text("❌ You are not approved.")
    progress = DB.table("progress").get(UserQ.id == user_id) or {}
    keys = progress.get("keys", 0)
    slugs = progress.get("slugs", {})
    limit_done = progress.get("limit_done", False)
    lines = [f"🧾 Profile of {user_id}:", f"🔑 Keys: {keys}"]
    for name, count in slugs.items():
        lines.append(f"🐌 {name.capitalize()}: {count}")
    lines.append(f"⚡ Daily Limit: {'✅' if limit_done else '❌'}")
    await update.message.reply_text("\n".join(lines))

# === /get (admin check user profile) ===
async def get(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return await update.message.reply_text("Unauthorized.")
    if not update.message.reply_to_message:
        return await update.message.reply_text("❌ Reply to a user to get their profile.")
    user_id = update.message.reply_to_message.from_user.id
    progress = DB.table("progress").get(UserQ.id == user_id) or {}
    keys = progress.get("keys", 0)
    slugs = progress.get("slugs", {})
    limit_done = progress.get("limit_done", False)
    lines = [f"🧾 Profile of {user_id}:", f"🔑 Keys: {keys}"]
    for name, count in slugs.items():
        lines.append(f"🐌 {name.capitalize()}: {count}")
    lines.append(f"⚡ Daily Limit: {'✅' if limit_done else '❌'}")
    await update.message.reply_text("\n".join(lines))

# === /start ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not DB.table("approved").contains(UserQ.id == user_id):
        return await update.message.reply_text("❌ You are not approved.")
    await update.message.reply_text("👋 Welcome! Use /task to view your task.")

# === Setup Bot ===
app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("approve", approve))
app.add_handler(CommandHandler("unapprove", unapprove))
app.add_handler(CommandHandler("settask1", settask1))
app.add_handler(CommandHandler("settask2", settask2))
app.add_handler(CommandHandler("settask3", settask3))
app.add_handler(CommandHandler("task", task))
app.add_handler(CommandHandler("profile", profile))
app.add_handler(CommandHandler("get", get))

print("🤖 Bot is running...")
app.run_polling()
