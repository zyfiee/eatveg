import os
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")

FILTER_OPTIONS = {
    "all": "🥗 All Veg-Friendly",
    "pure_veg": "🌱 Pure Vegetarian",
    "vegan": "🥦 Vegan-Friendly",
    "indian": "🍛 Indian",
    "chinese": "🥢 Chinese",
    "western": "🍽️ Western",
}

# ---------- /start ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[KeyboardButton("📍 Share My Location", request_location=True)]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text(
        "👋 Welcome to *SG Veggie Finder*!\n\n"
        "I'll find vegetarian and veg-friendly places near you.\n\n"
        "Tap the button below to share your location 👇",
        parse_mode="Markdown",
        reply_markup=reply_markup,
    )

# ---------- /help ----------
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🌿 *How to use SG Veggie Finder:*\n\n"
        "1. Tap 📍 Share My Location\n"
        "2. I'll show you nearby veg-friendly places\n"
        "3. Use the filter buttons to narrow by type\n"
        "4. Tap any result to see it on the map\n\n"
        "Commands:\n"
        "/start - Restart the bot\n"
        "/help - Show this message",
        parse_mode="Markdown",
    )

# ---------- Location handler ----------
async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lat = update.message.location.latitude
    lon = update.message.location.longitude

    # Save location for filter reuse
    context.user_data["lat"] = lat
    context.user_data["lon"] = lon

    await update.message.reply_text("🔍 Searching nearby vegetarian places...")

    # Show filter keyboard
    keyboard = [
        [
            InlineKeyboardButton("🥗 All Veg-Friendly", callback_data="filter:all"),
            InlineKeyboardButton("🌱 Pure Veg", callback_data="filter:pure_veg"),
        ],
        [
            InlineKeyboardButton("🥦 Vegan", callback_data="filter:vegan"),
            InlineKeyboardButton("🍛 Indian", callback_data="filter:indian"),
        ],
        [
            InlineKeyboardButton("🥢 Chinese", callback_data="filter:chinese"),
            InlineKeyboardButton("🍽️ Western", callback_data="filter:western"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Choose a filter:", reply_markup=reply_markup)

    # Default: search all veg-friendly
    await search_and_send(update, context, lat, lon, filter_type="all")

# ---------- Filter button handler ----------
async def handle_filter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    filter_type = query.data.split(":")[1]
    lat = context.user_data.get("lat")
    lon = context.user_data.get("lon")

    if not lat or not lon:
        await query.message.reply_text("Please share your location first using /start")
        return

    label = FILTER_OPTIONS.get(filter_type, "All Veg-Friendly")
    await query.message.reply_text(f"🔍 Filtering by: *{label}*...", parse_mode="Markdown")
    await search_and_send(query, context, lat, lon, filter_type=filter_type)

# ---------- Core search function ----------
async def search_and_send(update_or_query, context, lat, lon, filter_type="all"):
    keyword_map = {
        "all": "vegetarian restaurant",
        "pure_veg": "pure vegetarian restaurant",
        "vegan": "vegan restaurant",
        "indian": "vegetarian indian restaurant",
        "chinese": "vegetarian chinese restaurant",
        "western": "vegetarian western restaurant",
    }
    keyword = keyword_map.get(filter_type, "vegetarian restaurant")

    url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
    params = {
        "location": f"{lat},{lon}",
        "radius": 1500,  # 1.5km radius
        "keyword": keyword,
        "key": GOOGLE_API_KEY,
    }

    response = requests.get(url, params=params)
    data = response.json()
    places = data.get("results", [])

    if not places:
        msg = "😔 No places found nearby. Try a different filter or a wider area."
        if hasattr(update_or_query, "message"):
            await update_or_query.message.reply_text(msg)
        else:
            await update_or_query.message.reply_text(msg)
        return

    # Send summary list (top 5)
    top_places = places[:5]
    lines = [f"🌿 *Top {len(top_places)} Veg-Friendly Places Nearby:*\n"]
    for i, place in enumerate(top_places, 1):
        name = place.get("name", "Unknown")
        rating = place.get("rating", "N/A")
        total = place.get("user_ratings_total", 0)
        address = place.get("vicinity", "")
        open_now = place.get("opening_hours", {}).get("open_now")
        status = "🟢 Open" if open_now is True else ("🔴 Closed" if open_now is False else "")
        stars = "⭐" * round(float(rating)) if rating != "N/A" else ""
        lines.append(
            f"*{i}. {name}*\n"
            f"   {stars} {rating} ({total} reviews) {status}\n"
            f"   📍 {address}\n"
        )

    # Use the right reply method
    if hasattr(update_or_query, "message"):
    reply_target = update_or_query.message
else:
    reply_target = update_or_query
    
    await reply_target.reply_text("\n".join(lines), parse_mode="Markdown")

    # Send each place as a map pin
    for place in top_places:
        name = place.get("name", "Place")
        address = place.get("vicinity", "")
        geo = place.get("geometry", {}).get("location", {})
        place_lat = geo.get("lat")
        place_lon = geo.get("lng")
        if place_lat and place_lon:
            await reply_target.reply_venue(
                latitude=place_lat,
                longitude=place_lon,
                title=name,
                address=address,
            )

# ---------- Run the bot ----------
if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.LOCATION, handle_location))
    app.add_handler(CallbackQueryHandler(handle_filter, pattern="^filter:"))
    print("Bot is running...")
    app.run_polling()
