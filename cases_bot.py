import os
import sqlite3
import random
from datetime import date
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

TOKEN = os.getenv("BOT_TOKEN")
DB = "cases.db"

CASES = {
    "zombie": ("🧟 Зомби", 10, ["Рука зомби", "Зуб зомби", "Голова зомби", "Кость зомби", "Золотая голова зомби"], [3, 5, 8, 15, 25]),
    "skeleton": ("💀 Скелет", 25, ["Череп", "Ребро", "Рука скелета", "Золотой череп", "Корона скелета"], [8, 12, 20, 40, 75]),
    "vampire": ("🧛 Вампир", 50, ["Клык вампира", "Плащ вампира", "Кровавый кристалл", "Вампирская маска", "Корона вампира"], [15, 25, 40, 100, 200]),
    "demon": ("😈 Демон", 100, ["Рог демона", "Демонический глаз", "Крыло демона", "Огненный меч", "Корона демона"], [30, 50, 80, 200, 400]),
    "dragon": ("🐉 Дракон", 200, ["Драконья чешуя", "Драконий коготь", "Драконье яйцо", "Драконье сердце", "Золотой дракон"], [60, 100, 160, 400, 800]),
    "legend": ("👑 Легендарный", 400, ["Золотой амулет", "Королевский меч", "Легендарный щит", "Золотая корона", "Королевский трон"], [120, 200, 320, 800, 1500]),
    "space": ("🌌 Космический", 800, ["Звёздный камень", "Лунный кристалл", "Планета", "Чёрная звезда", "Галактика"], [240, 400, 650, 1600, 3500]),
    "god": ("⚡ Божественный", 1500, ["Световой шар", "Крылья ангела", "Божественный меч", "Золотой ангел", "Сфера бога"], [450, 750, 1200, 3000, 7000])
}

def connect():
    return sqlite3.connect(DB)

def setup():
    with connect() as db:
        db.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT, balance INTEGER DEFAULT 100, daily TEXT)")
        db.execute("CREATE TABLE IF NOT EXISTS items (id INTEGER, item TEXT, amount INTEGER DEFAULT 1, PRIMARY KEY(id,item))")

def get_user(uid, name):
    with connect() as db:
        db.execute("INSERT OR IGNORE INTO users(id,name) VALUES(?,?)", (uid, name))
        db.execute("UPDATE users SET name=? WHERE id=?", (name, uid))
        return db.execute("SELECT balance FROM users WHERE id=?", (uid,)).fetchone()[0]

def menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎁 Кейсы", callback_data="cases")],
        [InlineKeyboardButton("💰 Баланс", callback_data="balance"),
         InlineKeyboardButton("🎒 Инвентарь", callback_data="inventory")],
        [InlineKeyboardButton("🎁 Ежедневный бонус", callback_data="daily")],
        [InlineKeyboardButton("🏆 Топ игроков", callback_data="top")]
    ])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.first_name)
    await update.message.reply_text(
        "🎉 Добро пожаловать в КЕЙСЫ!\nУ тебя есть 100 ⭐ для игры.",
        reply_markup=menu()
    )

async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    name = q.from_user.first_name
    balance = get_user(uid, name)

    if q.data == "cases":
        keyboard = [[InlineKeyboardButton(f"{v[0]} — {v[1]} ⭐", callback_data="open_" + k)] for k, v in CASES.items()]
        keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="home")])
        await q.edit_message_text("🎁 Выбери кейс:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif q.data.startswith("open_"):
        key = q.data[5:]
        title, price, prizes, values = CASES[key]
        if balance < price:
            await q.edit_message_text(f"❌ Не хватает звёзд!\nНужно: {price} ⭐\nУ тебя: {balance} ⭐", reply_markup=menu())
            return
        prize, value = random.choice(list(zip(prizes, values)))
        with connect() as db:
            db.execute("UPDATE users SET balance=balance-? WHERE id=?", (price, uid))
            db.execute("""INSERT INTO items(id,item,amount) VALUES(?,?,1)
                          ON CONFLICT(id,item) DO UPDATE SET amount=amount+1""", (uid, prize))
            db.execute("UPDATE users SET balance=balance+? WHERE id=?", (value, uid))
            new_balance = db.execute("SELECT balance FROM users WHERE id=?", (uid,)).fetchone()[0]
        await q.edit_message_text(
            f"🎁 Кейс: {title}\n\n🏆 Выпало: {prize}\n💎 Стоимость: {value} ⭐\n\n💰 Баланс: {new_balance} ⭐",
            reply_markup=menu()
        )

    elif q.data == "balance":
        await q.edit_message_text(f"💰 Твой баланс: {balance} ⭐", reply_markup=menu())

    elif q.data == "inventory":
        with connect() as db:
            rows = db.execute("SELECT item,amount FROM items WHERE id=? ORDER BY item", (uid,)).fetchall()
        message = "🎒 Твой инвентарь:\n\n"
        message += "\n".join(f"• {item} × {amount}" for item, amount in rows) if rows else "Пока пусто."
        await q.edit_message_text(message, reply_markup=menu())

    elif q.data == "daily":
        today = str(date.today())
        with connect() as db:
            last = db.execute("SELECT daily FROM users WHERE id=?", (uid,)).fetchone()[0]
            if last == today:
                await q.edit_message_text("⏳ Ты уже получил бонус сегодня!", reply_markup=menu())
                return
            db.execute("UPDATE users SET balance=balance+25,daily=? WHERE id=?", (today, uid))
            balance += 25
        await q.edit_message_text(f"🎁 Ты получил 25 ⭐!\n💰 Баланс: {balance} ⭐", reply_markup=menu())

    elif q.data == "top":
        with connect() as db:
            rows = db.execute("SELECT name,balance FROM users ORDER BY balance DESC LIMIT 10").fetchall()
        message = "🏆 ТОП ИГРОКОВ\n\n"
        message += "\n".join(f"{i+1}. {n} — {b} ⭐" for i, (n, b) in enumerate(rows))
        await q.edit_message_text(message, reply_markup=menu())

    elif q.data == "home":
        await q.edit_message_text("🎉 Главное меню КЕЙСЫ:", reply_markup=menu())

def main():
    if not TOKEN:
        raise RuntimeError("Не задан BOT_TOKEN")
    setup()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(buttons))
    app.run_polling()

if __name__ == "__main__":
    main()