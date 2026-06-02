import os
import asyncio
import json
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

TOKEN = os.environ.get("8792609955:AAHKgSFAYQWQg-DKWUnJ2sZ94vNv-V5gZoQ")
OWNER_ID = 1483930338

DATA_FILE = "user_data.json"

def load_user_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"users": {}, "blocked": [], "stats": {"total_users": 0, "total_messages": 0}}

user_data_store = load_user_data()
user_chat_map = {}
blocked_users = set(user_data_store.get("blocked", []))
stats = user_data_store.get("stats", {"total_users": 0, "total_messages": 0})

def save_user_data():
    global user_data_store
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(user_data_store, f, ensure_ascii=False, indent=2)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    user_chat_map[user_id] = update.effective_chat.id
    
    if user_id not in user_data_store["users"]:
        user_data_store["users"][user_id] = {
            "name": update.effective_user.first_name or "",
            "username": update.effective_user.username or "",
            "first_seen": datetime.now().isoformat(),
            "msg_count": 0
        }
        stats["total_users"] += 1
        save_user_data()
        
        await context.bot.send_message(
            chat_id=OWNER_ID,
            text=f"🆕 Новый пользователь!\n👤 {user_data_store['users'][user_id]['name']}"
        )
    
    await update.message.reply_text(
        "👋 Привет! Напиши что-нибудь, я передам владельцу.\n"
        "Команды: /start /info /help"
    )

async def info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"📊 Статистика:\n👥 Пользователей: {stats['total_users']}\n💬 Сообщений: {stats['total_messages']}"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 Просто напиши сообщение — я передам его владельцу.\nОтвет придёт сюда же."
    )

async def forward_to_owner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    
    if user_id in blocked_users:
        await update.message.reply_text("❌ Вы заблокированы.")
        return
    
    user_chat_map[user_id] = update.effective_chat.id
    
    if user_id in user_data_store["users"]:
        user_data_store["users"][user_id]["msg_count"] += 1
    stats["total_messages"] += 1
    save_user_data()
    
    text = update.message.text or "Сообщение"
    username = update.effective_user.username or "без ника"
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️ Ответить", callback_data=f"reply_{user_id}"),
         InlineKeyboardButton("🚫 Блок", callback_data=f"block_{user_id}")]
    ])
    
    await context.bot.send_message(
        chat_id=OWNER_ID,
        text=f"📩 От: @{username}\n🆔 `{user_id}`\n\n{text}",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )
    
    await update.message.reply_text("✅ Отправлено!")

async def handle_reply_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user_id = data.split("_")[1]
    
    if data.startswith("reply_"):
        context.user_data["reply_to_user"] = user_id
        await query.edit_message_text("✍️ Напиши ответ. /cancel - отмена")
    
    elif data.startswith("block_"):
        if user_id in blocked_users:
            blocked_users.remove(user_id)
            user_data_store["blocked"] = list(blocked_users)
            await query.edit_message_text(f"✅ Разблокирован {user_id}")
        else:
            blocked_users.add(user_id)
            user_data_store["blocked"] = list(blocked_users)
            await query.edit_message_text(f"❌ Заблокирован {user_id}")
        save_user_data()

async def reply_to_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "reply_to_user" not in context.user_data:
        return
    
    user_id = context.user_data["reply_to_user"]
    chat_id = user_chat_map.get(user_id)
    
    if not chat_id:
        await update.message.reply_text("❌ Пользователь не найден")
        del context.user_data["reply_to_user"]
        return
    
    if user_id in blocked_users:
        await update.message.reply_text("⚠️ Пользователь заблокирован")
        return
    
    answer_text = update.message.text
    
    await context.bot.send_message(
        chat_id=chat_id,
        text=f"📨 Ответ:\n\n{answer_text}"
    )
    
    await update.message.reply_text(f"✅ Ответ отправлен")
    del context.user_data["reply_to_user"]

async def cancel_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "reply_to_user" in context.user_data:
        del context.user_data["reply_to_user"]
        await update.message.reply_text("✅ Отменено")
    else:
        await update.message.reply_text("Нет активного ответа")

async def stats_owner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return
    
    await update.message.reply_text(
        f"📊 Статистика\n\n👥 Пользователей: {stats['total_users']}\n💬 Сообщений: {stats['total_messages']}\n🚫 Заблокировано: {len(blocked_users)}"
    )

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return
    
    text = update.message.text.replace("/broadcast", "").strip()
    if not text:
        await update.message.reply_text("⚠️ /broadcast [текст]")
        return
    
    sent = 0
    for user_id, chat_id in user_chat_map.items():
        if user_id not in blocked_users:
            try:
                await context.bot.send_message(chat_id, f"📢 {text}")
                sent += 1
                await asyncio.sleep(0.05)
            except:
                pass
    
    await update.message.reply_text(f"✅ Отправлено {sent} пользователям")

def main():
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("info", info_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("stats", stats_owner))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CommandHandler("cancel", cancel_reply))
    
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.Chat(OWNER_ID), reply_to_user))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, forward_to_owner))
    app.add_handler(CallbackQueryHandler(handle_reply_button, pattern="(reply_|block_)"))
    
    print("✅ Бот запущен")
    app.run_polling()

if __name__ == "__main__":
    main()
