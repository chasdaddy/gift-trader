import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, CallbackQueryHandler, ContextTypes, filters

BOT_TOKEN = "PASTE_YOUR_BOT_TOKEN_HERE"

# =========================
# GLOBAL SETTINGS (Editable via Buttons)
# =========================

settings = {
    "min_price": 0.2,
    "max_price": 20.0,
    "below_floor_percent": 20,
    "rarity_keywords": ["rare", "limited", "legendary", "1/1"],

    # Marketplace fees in %
    "fees": {
        "getgems": 2.0,
        "portal": 2.5,
        "tonnel": 1.5,
        "mrkt": 2.0
    },

    # Floors per marketplace
    "floors": {
        "getgems": 10.0,
        "portal": 10.0,
        "tonnel": 10.0,
        "mrkt": 9.5
    }
}

MARKETS = ["getgems", "portal", "tonnel", "mrkt"]

# =========================
# UTILS
# =========================

def extract_price(text):
    m = re.search(r"(\d+(?:\.\d+)?)\s*ton", text.lower())
    return float(m.group(1)) if m else None

def extract_url(text):
    urls = re.findall(r"https?://\S+", text)
    return urls[0] if urls else None

def detect_market(text):
    for m in MARKETS:
        if m in text.lower():
            return m
    return None

def is_rare(text):
    return any(k in text.lower() for k in settings["rarity_keywords"])

def effective_price(price, market):
    fee = settings["fees"].get(market, 0)
    return price * (1 + fee / 100)

# =========================
# SETTINGS UI
# =========================

def settings_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔻 Min Price", callback_data="set_min"),
         InlineKeyboardButton("🔺 Max Price", callback_data="set_max")],
        [InlineKeyboardButton("📉 Below Floor %", callback_data="set_floor_pct")],
        [InlineKeyboardButton("💎 Rarity Keywords", callback_data="set_rare")],
        [InlineKeyboardButton("🏪 Fees", callback_data="set_fees")],
        [InlineKeyboardButton("📊 Floors", callback_data="set_floors")],
    ])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⚙️ Trading Bot Settings\nUse the buttons below to configure your strategy:",
        reply_markup=settings_keyboard()
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    action = query.data

    if action == "set_min":
        await query.message.reply_text("Send new MIN price in TON:")
        context.user_data["awaiting"] = "min"

    elif action == "set_max":
        await query.message.reply_text("Send new MAX price in TON:")
        context.user_data["awaiting"] = "max"

    elif action == "set_floor_pct":
        await query.message.reply_text("Send new BELOW FLOOR % (e.g. 20):")
        context.user_data["awaiting"] = "floor_pct"

    elif action == "set_rare":
        await query.message.reply_text("Send rarity keywords separated by commas:")
        context.user_data["awaiting"] = "rare"

    elif action == "set_fees":
        await query.message.reply_text(
            "Send fees as:\ngetgems=2, portal=2.5, tonnel=1.5, mrkt=2"
        )
        context.user_data["awaiting"] = "fees"

    elif action == "set_floors":
        await query.message.reply_text(
            "Send floors as:\ngetgems=10, portal=10, tonnel=10, mrkt=9.5"
        )
        context.user_data["awaiting"] = "floors"

async def settings_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "awaiting" not in context.user_data:
        return

    text = update.message.text.strip()
    key = context.user_data["awaiting"]

    try:
        if key == "min":
            settings["min_price"] = float(text)

        elif key == "max":
            settings["max_price"] = float(text)

        elif key == "floor_pct":
            settings["below_floor_percent"] = float(text)

        elif key == "rare":
            settings["rarity_keywords"] = [k.strip().lower() for k in text.split(",")]

        elif key == "fees":
            for pair in text.split(","):
                m, v = pair.split("=")
                settings["fees"][m.strip().lower()] = float(v)

        elif key == "floors":
            for pair in text.split(","):
                m, v = pair.split("=")
                settings["floors"][m.strip().lower()] = float(v)

        await update.message.reply_text("✅ Settings updated.", reply_markup=settings_keyboard())

    except Exception as e:
        await update.message.reply_text("❌ Invalid format. Try again.")

    context.user_data.pop("awaiting", None)

# =========================
# MARKET SCANNER
# =========================

async def scan_market(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    text = update.message.text
    market = detect_market(text)

    if not market:
        return

    price = extract_price(text)
    if not price:
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

    # Cross-sell arbitrage
    arbitrage_targets = []
    for m, floor in settings["floors"].items():
        if m == market:
            continue
        sell_after_fee = floor * (1 - settings["fees"].get(m, 0) / 100)
        profit = round(sell_after_fee - eff_buy, 3)
        if profit > 0:
            arbitrage_targets.append(f"{m.upper()} (+{profit} TON)")

    if not (below_floor or rare_flag or arbitrage_targets):
        return

    reason = []
    if below_floor:
        reason.append(f"📉 {discount}% below {market.upper()} floor")
    if rare_flag:
        reason.append("💎 Rare keyword detected")
    if arbitrage_targets:
        reason.append("🔁 Cross-sell: " + " | ".join(arbitrage_targets))

    message = f"""🔥 DEAL FOUND

🏪 Market: {market.upper()}
💰 Price: {price} TON
💸 After Fee: {round(eff_buy,3)} TON
📊 Floor ({market.upper()}): {own_floor} TON
🏷 Reason: {' | '.join(reason)}
"""

    if url:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🛒 BUY NOW", url=url)]
        ])
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=message,
            reply_markup=keyboard,
            disable_web_page_preview=True
        )
    else:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=message,
            disable_web_page_preview=True
        )

# =========================
# RUN
# =========================

app = ApplicationBuilder().token(BOT_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(button_handler))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, settings_input))
app.add_handler(MessageHandler(filters.TEXT, scan_market))

app.run_polling()
