from dotenv import load_dotenv
import os

load_dotenv()  # loads .env from your laptop
BOT_TOKEN = os.getenv("BOT_TOKEN")
import os
import re
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, CallbackQueryHandler, ContextTypes, filters

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Initial settings
settings = {
    "min_price": 0.2,
    "max_price": 20.0,
    "below_floor_percent": 20,
    "rarity_keywords": ["rare", "limited", "legendary", "1/1"],

    # Marketplace fees (%)
    "fees": {
        "getgems": 5.0,
        "portal": 5.0,
        "tonnel": 7.0,
        "mrkt": 0.0
    },

    # Floors per marketplace (editable)
    "floors": {
        "getgems": 10.0,
        "portal": 10.0,
        "tonnel": 10.0,
        "mrkt": 9.5
    }
}

MARKETS = ["getgems", "portal", "tonnel", "mrkt"]

def extract_price(text: str):
    m = re.search(r"(\d+(?:\.\d+)?)\s*ton", text.lower())
    return float(m.group(1)) if m else None

def extract_url(text: str):
    urls = re.findall(r"https?://\S+", text)
    return urls[0] if urls else None

def detect_market(text: str):
    for m in MARKETS:
        if m in text.lower():
            return m
    return None

def is_rare(text: str):
    return any(k in text.lower() for k in settings["rarity_keywords"])

def effective_price(price, market):
    fee = settings["fees"].get(market, 0)
    return price * (1 + fee / 100)

# Settings UI
def settings_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔻 Min Price", callback_data="set_min"),
         InlineKeyboardButton("🔺 Max Price", callback_data="set_max")],
        [InlineKeyboardButton("📉 Below Floor %", callback_data="set_floor_pct")],
        [InlineKeyboardButton("💎 Rarity Keywords", callback_data="set_rare")],
        [InlineKeyboardButton("🏪 Fees", callback_data="set_fees")],
        [InlineKeyboardButton("📊 Floors", callback_data="set_floors")]
    ])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⚙️ Bot Settings (configure by buttons):",
        reply_markup=settings_keyboard()
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    action = query.data
    await query.message.reply_text(f"Send new value for {action.strip('set_')}:")
    context.user_data["awaiting"] = action

async def settings_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "awaiting" not in context.user_data:
        return
    key = context.user_data["awaiting"]
    text = update.message.text.strip()

    try:
        if key == "set_min":
            settings["min_price"] = float(text)
        elif key == "set_max":
            settings["max_price"] = float(text)
        elif key == "set_floor_pct":
            settings["below_floor_percent"] = float(text)
        elif key == "set_rare":
            settings["rarity_keywords"] = [k.strip().lower() for k in text.split(",")]
        elif key == "set_fees":
            for pair in text.split(","):
                m, v = pair.split("=")
                settings["fees"][m.strip().lower()] = float(v)
        elif key == "set_floors":
            for pair in text.split(","):
                m, v = pair.split("=")
                settings["floors"][m.strip().lower()] = float(v)

        await update.message.reply_text("✅ Updated.", reply_markup=settings_keyboard())
    except:
        await update.message.reply_text("❌ Invalid format.")

    context.user_data.pop("awaiting", None)

# Scanner
async def scan_market(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    text = update.message.text
    market = detect_market(text)
    if not market:
        return

    price = extract_price(text)
    if price is None:
        return

    if price < settings["min_price"] or price > settings["max_price"]:
        return

    url = extract_url(text)
    rare_flag = is_rare(text)

    eff_buy = effective_price(price, market)
    own_floor = settings["floors"].get(market)

    below_floor = False
    discount = None
    if own_floor:
        discount = round((1 - (price / own_floor)) * 100, 2)
        if discount >= settings["below_floor_percent"]:
            below_floor = True

    arbitrage_targets = []
    for m, floor_v in settings["floors"].items():
        if m == market:
            continue
        eff_sell = floor_v * (1 - settings["fees"].get(m, 0) / 100)
        profit = round(eff_sell - eff_buy, 4)
        if profit > 0:
            arbitrage_targets.append(f"{m.upper()} (+{profit} TON)")

    if not (below_floor or rare_flag or arbitrage_targets):
        return

    reason = []
    if below_floor:
        reason.append(f"📉 {discount}% below {market.upper()} floor")
    if rare_flag:
        reason.append("💎 Rare detected")
    if arbitrage_targets:
        reason.append("🔁 Cross-sell: " + " | ".join(arbitrage_targets))

    msg = f"🔥 DEAL FOUND\n\n🏪 {market.upper()}  Price: {price} TON  After Fee: {eff_buy:.3f} TON\n📊 Floor: {own_floor} TON\n🏷 {' | '.join(reason)}"

    if url:
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🛒 BUY NOW", url=url)]])
        await context.bot.send_message(update.effective_chat.id, msg, reply_markup=kb)
    else:
        await context.bot.send_message(update.effective_chat.id, msg)

app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(button_handler))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, settings_input))
app.add_handler(MessageHandler(filters.TEXT, scan_market))
app.run_polling()
