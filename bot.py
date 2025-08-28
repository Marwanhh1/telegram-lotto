import os
import logging
import random
import psycopg2
import requests
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# TON Configuration - ADD YOUR WALLET ADDRESS HERE
TON_WALLET_ADDRESS = "UQDn-7fmd-goYxycJZuKBBkaBM2Hd8XJEVOqQyE_22892mXs"  # Replace with your actual TON wallet address
TON_API_URL = "https://toncenter.com/api/v2/"  # TON blockchain API

# Database connection
def get_db_connection():
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        logger.error("DATABASE_URL not found in environment variables")
        return None
    return psycopg2.connect(database_url)

# Initialize database
def init_db():
    try:
        conn = get_db_connection()
        if conn is None:
            logger.error("Could not connect to database")
            return
            
        cursor = conn.cursor()
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS tickets (
            id SERIAL PRIMARY KEY,
            user_id INTEGER,
            username TEXT,
            numbers TEXT,
            bonus_number INTEGER,
            ticket_id TEXT UNIQUE,
            purchased_at TIMESTAMP,
            payment_status TEXT DEFAULT 'pending',
            payment_hash TEXT,
            payment_amount FLOAT,
            payment_address TEXT
        )
        ''')
        conn.commit()
        conn.close()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing database: {e}")

# Generate lottery numbers
def generate_numbers():
    numbers = sorted(random.sample(range(1, 43), 6))
    bonus = random.randint(1, 42)
    return numbers, bonus

# Check TON payment using TON Center API
async def check_ton_payment(ticket_id, user_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT payment_address FROM tickets WHERE ticket_id = %s AND user_id = %s', 
                      (ticket_id, user_id))
        result = cursor.fetchone()
        conn.close()
        
        if not result:
            return False
            
        # In a real implementation, you would check blockchain for the transaction
        # This is a simplified version that simulates payment verification
        # For real implementation, use: https://toncenter.com/api/v2/#/accounts/account_get_events
        
        # Simulate payment check - replace with actual blockchain query
        await asyncio.sleep(2)  # Simulate API call delay
        return True  # Simulate successful payment
        
    except Exception as e:
        logger.error(f"Payment check error: {e}")
        return False

# Generate unique payment address (for tracking)
def generate_payment_address(user_id, ticket_id):
    # In a real implementation, you might use sub-wallets or memo codes
    # For simplicity, we'll use the main wallet address with tracking data
    return TON_WALLET_ADDRESS

# Start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    keyboard = [
        [InlineKeyboardButton("💰 Buy Ticket", callback_data='buy_ticket')],
        [InlineKeyboardButton("🎫 My Tickets", callback_data='my_tickets')],
        [InlineKeyboardButton("🔗 Connect Wallet", callback_data='connect_wallet')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    logger.info(f"Received /start from user {user.id} ({user.username})")
    
    await update.message.reply_html(
        f"Hi {user.mention_html()}! Welcome to TON Lottery!\n\n"
        "Get your lottery ticket for 1 TON and win big!",
        reply_markup=reply_markup
    )

# Handle button callbacks
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    logger.info(f"Received callback: {query.data}")
    
    if query.data == 'buy_ticket':
        await buy_ticket(update, context)
    elif query.data == 'my_tickets':
        await my_tickets(update, context)
    elif query.data == 'connect_wallet':
        await connect_wallet(update, context)
    elif query.data == 'connect_tonkeeper':
        await connect_tonkeeper(update, context)
    elif query.data == 'connect_tonhub':
        await connect_tonhub(update, context)
    elif query.data.startswith('confirm_'):
        ticket_id = query.data.replace('confirm_', '')
        await confirm_purchase(update, context, ticket_id)
    elif query.data.startswith('pay_'):
        ticket_id = query.data.replace('pay_', '')
        await process_payment(update, context, ticket_id)
    elif query.data.startswith('check_'):
        ticket_id = query.data.replace('check_', '')
        await check_payment_status(update, context, ticket_id)
    elif query.data == 'back_to_main':
        await start_callback(update, context)

# Confirm purchase
async def confirm_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE, ticket_id):
    query = update.callback_query
    user = query.from_user
    
    # Generate unique payment address for tracking
    payment_address = generate_payment_address(user.id, ticket_id)
    
    # Save payment address to database
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
        UPDATE tickets SET payment_address = %s 
        WHERE ticket_id = %s AND user_id = %s
        ''', (payment_address, ticket_id, user.id))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Database error: {e}")
        await query.edit_message_text("❌ Error processing request. Please try again.")
        return
    
    keyboard = [
        [InlineKeyboardButton("💳 I've Paid", callback_data=f'pay_{ticket_id}')],
        [InlineKeyboardButton("🔍 Check Payment", callback_data=f'check_{ticket_id}')],
        [InlineKeyboardButton("⬅️ Back", callback_data='back_to_main')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"💳 Please send exactly 1 TON to:\n\n"
        f"`{payment_address}`\n\n"
        f"**Important:**\n"
        f"• Send exactly 1 TON\n"
        f"• Network: TON Blockchain\n"
        f"• After sending, click 'I've Paid'\n\n"
        f"Ticket ID: `{ticket_id}`\n"
        f"User ID: `{user.id}`",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

# Process payment
async def process_payment(update: Update, context: ContextTypes.DEFAULT_TYPE, ticket_id):
    query = update.callback_query
    user = query.from_user
    
    # Check if payment was received
    payment_received = await check_ton_payment(ticket_id, user.id)
    
    if payment_received:
        # Update database
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('''
            UPDATE tickets SET payment_status = 'paid' 
            WHERE ticket_id = %s AND user_id = %s
            ''', (ticket_id, user.id))
            conn.commit()
            
            # Get ticket details
            cursor.execute('SELECT numbers, bonus_number FROM tickets WHERE ticket_id = %s', (ticket_id,))
            ticket = cursor.fetchone()
            conn.close()
            
            if ticket:
                numbers = ticket[0].split(',')
                bonus = ticket[1]
                
                await query.edit_message_text(
                    f"✅ Payment confirmed!\n\n"
                    f"🎫 Your lottery ticket:\n"
                    f"Main: {', '.join(numbers)}\n"
                    f"Bonus: {bonus}\n\n"
                    f"Ticket ID: {ticket_id}\n\n"
                    f"Good luck! The draw will be on Saturday at 20:00 UTC."
                )
        except Exception as e:
            logger.error(f"Database error: {e}")
            await query.edit_message_text("❌ Error updating payment status. Please contact support.")
    else:
        keyboard = [
            [InlineKeyboardButton("🔍 Check Again", callback_data=f'check_{ticket_id}')],
            [InlineKeyboardButton("💳 Try Payment Again", callback_data=f'pay_{ticket_id}')],
            [InlineKeyboardButton("⬅️ Back", callback_data='back_to_main')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"❌ Payment not received yet.\n\n"
            f"Please make sure you:\n"
            f"1. Sent exactly 1 TON\n"
            f"2. Used the correct address\n"
            f"3. Wait for blockchain confirmation (2-3 minutes)\n\n"
            f"Click 'Check Again' after waiting a few minutes.",
            reply_markup=reply_markup
        )

# Check payment status
async def check_payment_status(update: Update, context: ContextTypes.DEFAULT_TYPE, ticket_id):
    query = update.callback_query
    user = query.from_user
    await query.answer()
    
    payment_received = await check_ton_payment(ticket_id, user.id)
    
    if payment_received:
        await process_payment(update, context, ticket_id)
    else:
        await query.message.reply_text(
            "Payment not confirmed yet. Please wait a few minutes and try again."
        )

# ... (keep the rest of your functions the same) ...

# Main function
def main():
    # Get token from environment variable
    token = os.environ.get('TELEGRAM_BOT_TOKEN')
    if not token:
        logger.error("No TELEGRAM_BOT_TOKEN found in environment variables")
        return
    
    # Initialize database
    init_db()
    
    # Create Application
    application = Application.builder().token(token).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    
    # Error handler
    application.add_error_handler(error_handler)
    
    # Use polling (simpler for development)
    logger.info("Starting polling...")
    application.run_polling()

if __name__ == '__main__':
    main()
