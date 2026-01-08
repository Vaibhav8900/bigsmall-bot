import logging
import json
import os
BOT_TOKEN = os.getenv('8547761539:AAG-4WYMBmlYw8YdWgDMVaBOhfJEUehRfsU') 
import pandas as pd
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# --- CONFIG ---
BOT_TOKEN = "8547761539:AAG-4WYMBmlYw8YdWgDMVaBOhfJEUehRfsU"
DATA_FILE = "bigsmall_data.json"
STATS_FILE = "stats.json"

# Enable logging to catch errors
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class BigSmallBot:
    def __init__(self):
        self.data = self.load_data()
        self.stats = self.load_stats()
        self.pending_bet = None 

    def load_data(self):
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, 'r') as f:
                    return json.load(f)
            except: return []
        return []

    def save_data(self):
        with open(DATA_FILE, 'w') as f:
            json.dump(self.data, f)

    def load_stats(self):
        if os.path.exists(STATS_FILE):
            try:
                with open(STATS_FILE, 'r') as f:
                    data = json.load(f)
                    # Ensure all keys exist
                    for key in ["wins", "losses", "bankroll", "unit"]:
                        if key not in data: data[key] = 0
                    return data
            except: pass
        return {"wins": 0, "losses": 0, "bankroll": 15000, "unit": 150}

    def save_stats(self):
        with open(STATS_FILE, 'w') as f:
            json.dump(self.stats, f)

    def is_big(self, num):
        # Uses the whole number but checks the last digit logic
        last_digit = int(str(num)[-1])
        return last_digit >= 5

    def analyze_pattern(self):
        if len(self.data) < 3:
            return "WAIT", "Need 3+ game rounds"
        
        # Get outcomes for last 5 entries
        bs = ['B' if self.is_big(r) else 'S' for r in self.data[-5:]]
        
        # Pattern 1: Anti-Dragon (Skip if 3+ same in a row)
        if len(bs) >= 3 and (bs[-3:] == ['B','B','B'] or bs[-3:] == ['S','S','S']):
            return "SKIP", "Streak detected (3+)"
        
        # Pattern 2: 2-Same Reversal
        elif len(bs) >= 2 and bs[-1] == bs[-2]:
            opp = 'S' if bs[-1] == 'B' else 'B'
            return opp, f"Reversal after {bs[-1]}{bs[-1]}"
        
        # Pattern 3: Continue Trend
        elif len(bs) >= 2 and bs[-1] != bs[-2]:
            return bs[-1], "Trend Continuation"
            
        return "WAIT", "Pattern unclear"

bot_logic = BigSmallBot()

# --- HANDLERS ---

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log Errors caused by Updates."""
    logger.error(f"Update {update} caused error {context.error}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📊 Stats", callback_data='stats'), 
         InlineKeyboardButton("💰 Bankroll", callback_data='bankroll')],
        [InlineKeyboardButton("📈 Export", callback_data='export'),
         InlineKeyboardButton("🔄 Reset", callback_data='reset')]
    ]
    await update.message.reply_text(
        f"🎯 **Big/Small Bot Active**\n\n"
        f"• Send full numbers (e.g. 77214)\n"
        f"• Tracks last digit automatically\n"
        f"• Standard Unit: ₹{bot_logic.stats['unit']}\n\n"
        "Ready for first number!",
        reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown'
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "".join(filter(str.isdigit, update.message.text))
    
    if not text:
        # Ignore if it's just text like "WIN" (handled by other handler)
        return

    bot_logic.data.append(text)
    bot_logic.save_data()
    
    prediction, reason = bot_logic.analyze_pattern()
    
    if prediction == "SKIP":
        res = f"⚠️ **SKIP**\n`{reason}`"
    elif prediction == "WAIT":
        res = f"⏳ **WAIT**\n`{reason}`"
    else:
        bot_logic.pending_bet = bot_logic.stats['unit']
        side = "🔴 BIG" if prediction == "B" else "🟢 SMALL"
        res = (f"🚀 **SIGNAL**\n\n"
               f"🎯 **BET: {side}**\n"
               f"💰 Amount: ₹{bot_logic.pending_bet}\n"
               f"📊 Strategy: `{reason}`")

    await update.message.reply_text(res, parse_mode='Markdown')

async def track_result(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message.text.upper()
    if not bot_logic.pending_bet:
        await update.message.reply_text("No active bet. Send a number first!")
        return

    if "WIN" in msg:
        profit = bot_logic.pending_bet * 0.96
        bot_logic.stats['wins'] += 1
        bot_logic.stats['bankroll'] += profit
        await update.message.reply_text(f"✅ **WIN! +₹{profit:.2f}**")
    elif "LOSS" in msg:
        bot_logic.stats['losses'] += 1
        bot_logic.stats['bankroll'] -= bot_logic.pending_bet
        await update.message.reply_text(f"❌ **LOSS! -₹{bot_logic.pending_bet}**")
    
    bot_logic.pending_bet = None
    bot_logic.save_stats()

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    # Using try-except for the answer_callback_query to handle "Query too old"
    try:
        await query.answer()
    except:
        pass
    
    if query.data == 'stats':
        total = bot_logic.stats['wins'] + bot_logic.stats['losses']
        wr = (bot_logic.stats['wins'] / total * 100) if total > 0 else 0
        text = (f"📊 **LIVE STATS**\n"
                f"Wins: {bot_logic.stats['wins']}\n"
                f"Losses: {bot_logic.stats['losses']}\n"
                f"Win Rate: {wr:.1f}%\n"
                f"Current Bankroll: ₹{bot_logic.stats['bankroll']:.2f}")
        await query.message.reply_text(text, parse_mode='Markdown')
    
    elif query.data == 'reset':
        bot_logic.data = []
        bot_logic.save_data()
        await query.message.reply_text("🔄 History Cleared.")

def main():
    # Set high timeouts for Pydroid 3 / Mobile Networks
    app = Application.builder().token(BOT_TOKEN).connect_timeout(30).read_timeout(30).build()
    
    app.add_error_handler(error_handler)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.Regex(r'(?i)(WIN|LOSS)'), track_result))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("🤖 Bot is starting...")
    # drop_pending_updates ignores messages sent while the bot was offline
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
