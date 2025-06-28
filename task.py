from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from tinydb import TinyDB, Query
from datetime import datetime, timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import hashlib
import os
import json

# === CONFIG ===
BOT_TOKEN = "7803226404:AAGx-YvdgquS9qU3rzULa09zQBsoYgYUcjY"
OWNER_ID = 6279412066
ADMINS = [6279412066, 5903871499]  # Add other admin IDs here
import json
import os
import json
import shutil
from tinydb import TinyDB, Query

DB_PATH = "datta.json"

# Step 1: Check for corruption or blank file
def ensure_valid_db_file():
    # If file doesn't exist or is empty
    if not os.path.exists(DB_PATH) or os.path.getsize(DB_PATH) == 0:
        with open(DB_PATH, "w") as f:
            json.dump({}, f)
        return

    try:
        with open(DB_PATH, "r") as f:
            data = json.load(f)
            if not isinstance(data, dict):
                raise ValueError("Top-level JSON must be an object.")
    except (json.JSONDecodeError, ValueError) as e:
        print(f"❌ Invalid DB file: {e}")
        backup_path = DB_PATH + ".bak"
        shutil.move(DB_PATH, backup_path)
        print(f"🔁 Old DB backed up to: {backup_path}")
        with open(DB_PATH, "w") as f:
            json.dump({}, f)

# Step 2: Run the validation
ensure_valid_db_file()

# Step 3: Now safely connect to DB
DB = TinyDB(DB_PATH)
UserQ = Query()

import shutil

try:
    with open(DB_PATH, "r") as f:
        json.load(f)
except json.JSONDecodeError:
    print("❌ datta.json is corrupted. Backing up and resetting...")
    shutil.move(DB_PATH, DB_PATH + ".bak")
    with open(DB_PATH, "w") as f:
        json.dump({}, f)

UserQ = Query()
task_table = DB.table("tasks")
today_task = task_table.get(UserQ.date == "2025-06-28") or {"date": "2025-06-28", "tasks": []}
today_task["tasks"].append({"type": "key", "min": 5, "max": 10})
task_table.upsert(today_task, UserQ.date == "2025-06-28")

REWARD_VALUES = {
    "key": {"gems": 450, "coins": 10000},
    "slug": {"gems": 700, "coins": 30000},
    "daily_limit": {"gems": 1100, "coins": 80000}
}

# === Helpers ===
def is_owner(user_id):
    return user_id == OWNER_ID

def is_admin(user_id):
    return user_id in ADMINS

def is_approved(user_id):
    return DB.table("approved").contains(UserQ.id == user_id)

# === Scheduler ===
scheduler = AsyncIOScheduler()

def reset_profiles():
    progress_table = DB.table("progress")
    for user in progress_table.all():
        progress_table.update({
            "count": 0,
            "keys": 0,
            "slugs": {},
            "limit_done": False,
            "message_ids": [],
            "completed_tasks": []
        }, UserQ.id == user["id"])
    print("✅ All user profiles reset for new day.")

async def on_startup(app):
    scheduler.add_job(reset_profiles, "cron", hour=0, minute=0)
    scheduler.start()
    print("🕛 Scheduler started.")

# === Reward Logger ===
async def log_task_completion(context: ContextTypes.DEFAULT_TYPE, user_id: int):
    user = await context.bot.get_chat(user_id)
    progress_table = DB.table("progress")
    task_data = task_table.get(UserQ.date == datetime.now(timezone.utc).strftime("%Y-%m-%d")) or {"tasks": []}
    user_data = progress_table.get(UserQ.id == user_id) or {}
    completed_before = user_data.get("completed_tasks", [])

    new_completed = []
    total_gems = 0
    total_coins = 0

    for idx, task in enumerate(task_data["tasks"], 1):
        if str(idx) in completed_before:
            continue

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
        return

    message = (
        f"👤 Name: {user.first_name}\n"
        f"🆔 ID: `{user.id}`\n"
        f"🔗 Username: @{user.username or 'N/A'}\n"
        f"✅ Completed Tasks: {', '.join(new_completed)}\n"
        f"💎 Gems to Send: {total_gems}\n"
        f"🪙 Coins to Send: {total_coins}"
    )

    await context.bot.send_message(chat_id=OWNER_ID, text=message, parse_mode="Markdown")
    await context.bot.send_message(chat_id=LOG_GROUP_ID, text=message, parse_mode="Markdown")
    updated = list(set(completed_before + new_completed))
    progress_table.update({"completed_tasks": updated}, UserQ.id == user_id)

progress_table = DB.table("progress")
user_data = progress_table.get(UserQ.id == user_id)
if not user_data:
    user_data = {
        "id": user_id,
        "keys": 0,
        "slugs": {},
        "limit_done": False,
        "message_hashes": [],
        "completed_tasks": []
    }


# === (continued below with rest of 424+ lines code...)
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



# === Handle Forwarded Slugterraa Messages with Hash Check ===
async def handle_forward(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    msg = update.message

    sender_username = (
        msg.forward_from.username if msg.forward_from else
        msg.forward_from_chat.username if msg.forward_from_chat else None
    )

    if sender_username is None or sender_username.lower() != "slugterraa_bot":
        return await msg.reply_text("❌ Message not from @Slugterraa_bot.")
    if not msg.text or not msg.forward_date:
        return await msg.reply_text("❌ Invalid forwarded message.")

    today_utc = datetime.now(timezone.utc).date()
    if msg.forward_date.date() != today_utc:
        return await msg.reply_text("❌ Message not from today.")

    # ✅ Create unique hash
    message_hash = hashlib.md5((msg.text + str(msg.forward_date)).encode()).hexdigest()
    global_table = DB.table("global_seen")
    progress_table = DB.table("progress")

    if global_table.contains(UserQ.hash == message_hash):
        return await msg.reply_text("❌ Message already used by another user.")

    # Get or create user profile
    user_data = progress_table.get(UserQ.id == user_id)
    if not user_data:
        user_data = {
            "id": user_id,
            "keys": 0,
            "slugs": {},
            "limit_done": False,
            "message_hashes": [],
            "completed_tasks": []
        }

    if message_hash in user_data.get("message_hashes", []):
        return await msg.reply_text("⚠️ You've already used this message.")

    # 🧠 Analyze message
    updated = False
    text_lower = msg.text.lower()

    if "you found a key" in text_lower:
        user_data["keys"] += 1
        await msg.reply_text(f"✅ Key found! Total: {user_data['keys']}")
        updated = True

    elif "your luck is good you got" in text_lower:
        try:
            slug_name = msg.text.split("got", 1)[1].strip().split()[0].strip(".!").lower()
            slugs = user_data.get("slugs", {})
            slugs[slug_name] = slugs.get(slug_name, 0) + 1
            user_data["slugs"] = slugs
            await msg.reply_text(f"✅ Slug found: {slug_name.capitalize()}")
            updated = True
        except Exception:
            await msg.reply_text("❌ Couldn't parse slug name.")

    elif "daily limit reached" in text_lower:
        user_data["limit_done"] = True
        await msg.reply_text("✅ Daily limit marked as complete.")
        updated = True

    # Add hash
    user_data["message_hashes"] = user_data.get("message_hashes", []) + [message_hash]

    if updated:
        progress_table.upsert(user_data, UserQ.id == user_id)
        global_table.insert({"hash": message_hash})
        await log_task_completion(context, user_id)

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
        lines.append("None")

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
        lines.append("None")

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
            "completed_tasks": []  # ← add this
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
    await log_task_completion(context, user_id)  # 👈 log check

async def limitdone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not DB.table("approved").contains(UserQ.id == user_id):
        return await update.message.reply_text("❌ You are not approved.")
    progress_table = DB.table("progress")
    user_data = progress_table.get(UserQ.id == user_id) or {"id": user_id}
    user_data["limit_done"] = True
    progress_table.upsert(user_data, UserQ.id == user_id)

    await update.message.reply_text("⚡ Daily limit marked as completed.")
    await log_task_completion(context, user_id)

async def addslug(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not DB.table("approved").contains(UserQ.id == user_id):
        return await update.message.reply_text("❌ You are not approved.")
    if not context.args:
        return await update.message.reply_text("Usage: /addslug <slug_name>")

    slug_name = context.args[0].lower()
    progress_table = DB.table("progress")
    user_data = progress_table.get(UserQ.id == user_id) or {"id": user_id, "slugs": {}}

    slugs = user_data.get("slugs", {})
    slugs[slug_name] = slugs.get(slug_name, 0) + 1
    user_data["slugs"] = slugs
    progress_table.upsert(user_data, UserQ.id == user_id)

    await update.message.reply_text(f"🐌 Slug added: {slug_name.capitalize()}")
    await log_task_completion(context, user_id)


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
app.add_handler(CommandHandler("addkey", addkey))
app.add_handler(CommandHandler("addslug", addslug))
app.add_handler(CommandHandler("limitdone", limitdone))

# ✅ Fix: Add this line again here
app.add_handler(MessageHandler(filters.FORWARDED & filters.TEXT & (~filters.COMMAND), handle_forward))

print("🤖 Bot is running...")
app.run_polling()
