import os
import logging
import random
import psycopg2
import asyncio
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

# TON Configuration - REPLACE WITH YOUR WALLET ADDRESS
TON_WALLET_ADDRESS = os.environ.get('TON_WALLET_ADDRESS', 'UQDn-7fmd-goYxycJZuKBBkaBM2Hd8XJEVOqQyE_22892mXs')

# Database connection
def get_db_connection():
    try:
        database_url = os.environ.get('DATABASE_URL')
        if not database_url:
            logger.error("DATABASE_URL not found in environment variables")
            return None
        
        conn = psycopg2.connect(database_url)
        return conn
    except Exception as e:
        logger.error(f"Database connection error: {e}")
        return None

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
            wallet_connected BOOLEAN DEFAULT FALSE,
            wallet_address TEXT
        )
        ''')
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            wallet_connected BOOLEAN DEFAULT FALSE,
            wallet_address TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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

# Generate unique ticket ID
def generate_ticket_id():
    return f"TONLOTO_{random.randint(100000, 999999)}_{int(datetime.now().timestamp())}"

# Check if user exists, create if not
def ensure_user_exists(user_id, username):
    try:
        conn = get_db_connection()
        if conn is None:
            return False
            
        cursor = conn.cursor()
        cursor.execute('''
        INSERT INTO users (user_id, username) 
        VALUES (%s, %s)
        ON CONFLICT (user_id) DO UPDATE SET username = EXCLUDED.username
        ''', (user_id, username or 'Unknown'))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Error ensuring user exists: {e}")
        return False

# Check TON payment (simplified for testing)
async def check_ton_payment(ticket_id, user_id):
    try:
        # Simulate payment verification
        await asyncio.sleep(2)
        
        # For testing, simulate success
        return True
        
    except Exception as e:
        logger.error(f"Payment check error: {e}")
        return False

# Check if user has wallet connected
def check_wallet_connection(user_id):
    try:
        conn = get_db_connection()
        if conn is None:
            return False
            
        cursor = conn.cursor()
        cursor.execute('SELECT wallet_connected FROM users WHERE user_id = %s', (user_id,))
        result = cursor.fetchone()
        conn.close()
        
        return result[0] if result else False
    except Exception as e:
        logger.error(f"Error checking wallet connection: {e}")
        return False

# Start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    # Ensure user exists in database
    ensure_user_exists(user.id, user.username)
    
    wallet_connected = check_wallet_connection(user.id)
    
    if wallet_connected:
        keyboard = [
            [InlineKeyboardButton("💰 Buy Ticket", callback_data='buy_ticket')],
            [InlineKeyboardButton("🎫 My Tickets", callback_data='my_tickets')],
            [InlineKeyboardButton("🔗 Wallet Settings", callback_data='connect_wallet')]
        ]
        wallet_status = "✅ Your wallet is connected!"
    else:
        keyboard = [
            [InlineKeyboardButton("💰 Buy Ticket", callback_data='buy_ticket')],
            [InlineKeyboardButton("🎫 My Tickets", callback_data='my_tickets')],
            [InlineKeyboardButton("🔗 Connect Wallet", callback_data='connect_wallet')]
        ]
        wallet_status = "🔗 Connect your wallet to purchase tickets easily"
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    logger.info(f"Received /start from user {user.id} ({user.username})")
    
    welcome_text = f"Hi {user.mention_html()}! Welcome to TON Lottery! 🎰\n\n"
    welcome_text += "🎫 Buy lottery tickets for 1 TON each\n"
    welcome_text += "💰 80% of all ticket sales go to the prize pool!\n"
    welcome_text += "🏆 Weekly draws every Saturday at 20:00 UTC\n\n"
    welcome_text += wallet_status
    
    await update.message.reply_html(welcome_text, reply_markup=reply_markup)

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
    elif query.data == 'wallet_connected':
        await wallet_connected(update, context)
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

# Start callback for back button
async def start_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    
    wallet_connected = check_wallet_connection(user.id)
    
    if wallet_connected:
        keyboard = [
            [InlineKeyboardButton("💰 Buy Ticket", callback_data='buy_ticket')],
            [InlineKeyboardButton("🎫 My Tickets", callback_data='my_tickets')],
            [InlineKeyboardButton("🔗 Wallet Settings", callback_data='connect_wallet')]
        ]
        wallet_status = "✅ Your wallet is connected!"
    else:
        keyboard = [
            [InlineKeyboardButton("💰 Buy Ticket", callback_data='buy_ticket')],
            [InlineKeyboardButton("🎫 My Tickets", callback_data='my_tickets')],
            [InlineKeyboardButton("🔗 Connect Wallet", callback_data='connect_wallet')]
        ]
        wallet_status = "🔗 Connect your wallet to purchase tickets easily"
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_text = f"Hi {user.mention_html()}! Welcome to TON Lottery! 🎰\n\n"
    welcome_text += wallet_status
    
    await query.edit_message_text(welcome_text, reply_markup=reply_markup, parse_mode='HTML')

# Connect wallet handler
async def connect_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    
    keyboard = [
        [InlineKeyboardButton("📱 Connect Tonkeeper", callback_data='connect_tonkeeper')],
        [InlineKeyboardButton("📲 Connect Tonhub", callback_data='connect_tonhub')],
        [InlineKeyboardButton("⬅️ Back", callback_data='back_to_main')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "🔗 Connect your TON wallet:\n\n"
        "Select your wallet provider to connect. After connecting your wallet, "
        "you'll be able to purchase tickets more easily!\n\n"
        "💡 You can still buy tickets without connecting a wallet by sending TON manually.",
        reply_markup=reply_markup
    )

# Connect to Tonkeeper
async def connect_tonkeeper(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    
    # Generate a simple connection explanation
    connection_guide = (
        "📱 **Connecting Tonkeeper:**\n\n"
        "1. **Open Tonkeeper** on your phone\n"
        "2. **Tap the Scan button** in the app\n"
        "3. **Scan this QR code** (when we implement it)\n"
        "4. **Confirm the connection** in your wallet\n\n"
        "🔒 **Your wallet remains secure** - we only request basic access\n\n"
        "For now, we're simulating the connection process. "
        "Click 'I'm Connected' below to proceed."
    )
    
    keyboard = [
        [InlineKeyboardButton("✅ I'm Connected", callback_data='wallet_connected')],
        [InlineKeyboardButton("⬅️ Back", callback_data='connect_wallet')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(connection_guide, reply_markup=reply_markup, parse_mode='Markdown')

# Connect to Tonhub
async def connect_tonhub(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    
    # Generate a simple connection explanation
    connection_guide = (
        "📲 **Connecting Tonhub:**\n\n"
        "1. **Open Tonhub** on your phone\n"
        "2. **Go to Settings** → **Connected Apps**\n"
        "3. **Tap 'Connect New App'**\n"
        "4. **Scan this QR code** (when we implement it)\n"
        "5. **Confirm the connection** in your wallet\n\n"
        "🔒 **Your wallet remains secure** - we only request basic access\n\n"
        "For now, we're simulating the connection process. "
        "Click 'I'm Connected' below to proceed."
    )
    
    keyboard = [
        [InlineKeyboardButton("✅ I'm Connected", callback_data='wallet_connected')],
        [InlineKeyboardButton("⬅️ Back", callback_data='connect_wallet')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(connection_guide, reply_markup=reply_markup, parse_mode='Markdown')

# Handle wallet connected callback
async def wallet_connected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    
    # Save wallet connection to database
    try:
        conn = get_db_connection()
        if conn is None:
            await query.edit_message_text("❌ Database error. Please try again.")
            return
            
        cursor = conn.cursor()
        cursor.execute('''
        UPDATE users SET wallet_connected = TRUE 
        WHERE user_id = %s
        ''', (user.id,))
        conn.commit()
        conn.close()
        
        logger.info(f"User {user.id} wallet connection recorded")
        
    except Exception as e:
        logger.error(f"Error saving wallet connection: {e}")
        await query.edit_message_text("❌ Error saving connection. Please try again.")
        return
    
    keyboard = [
        [InlineKeyboardButton("💰 Buy Ticket", callback_data='buy_ticket')],
        [InlineKeyboardButton("🎫 My Tickets", callback_data='my_tickets')],
        [InlineKeyboardButton("🔗 Wallet Settings", callback_data='connect_wallet')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    success_message = (
        "✅ **Wallet Connected Successfully!**\n\n"
        "Your TON wallet is now connected to your account.\n\n"
        "🎉 **What you can do now:**\n"
        "• Purchase lottery tickets seamlessly\n"
        "• View your transaction history\n"
        "• Participate in weekly draws\n\n"
        "💰 **Next step:** Buy your first lottery ticket!"
    )
    
    await query.edit_message_text(success_message, reply_markup=reply_markup, parse_mode='Markdown')

# Buy ticket flow
async def buy_ticket(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    
    # Generate ticket numbers
    numbers, bonus = generate_numbers()
    ticket_id = generate_ticket_id()
    
    # Store in context for confirmation
    context.user_data['pending_ticket'] = {
        'numbers': numbers,
        'bonus': bonus,
        'ticket_id': ticket_id
    }
    
    # Save to database with pending status
    try:
        conn = get_db_connection()
        if conn is None:
            await query.edit_message_text("❌ Database connection error. Please try again.")
            return
            
        cursor = conn.cursor()
        cursor.execute('''
        INSERT INTO tickets (user_id, username, numbers, bonus_number, ticket_id, purchased_at)
        VALUES (%s, %s, %s, %s, %s, %s)
        ''', (
            user.id, 
            user.username or 'Unknown', 
            ','.join(map(str, numbers)), 
            bonus, 
            ticket_id,
            datetime.now()
        ))
        conn.commit()
        conn.close()
        
        logger.info(f"Ticket {ticket_id} created for user {user.id}")
        
    except Exception as e:
        logger.error(f"Database error in buy_ticket: {e}")
        await query.edit_message_text("❌ Error creating ticket. Please try again later.")
        return
    
    keyboard = [
        [InlineKeyboardButton("✅ Confirm Purchase", callback_data=f'confirm_{ticket_id}')],
        [InlineKeyboardButton("❌ Cancel", callback_data='back_to_main')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    ticket_message = (
        f"🎫 **Your Lottery Ticket**\n\n"
        f"🔢 **Numbers:** {', '.join(map(str, numbers))}\n"
        f"⭐ **Bonus:** {bonus}\n\n"
        f"📋 **Ticket ID:** {ticket_id}\n"
        f"💰 **Price:** 1 TON\n\n"
        f"✅ **Confirm purchase?**"
    )
    
    await query.edit_message_text(ticket_message, reply_markup=reply_markup, parse_mode='Markdown')

# Confirm purchase
async def confirm_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE, ticket_id):
    query = update.callback_query
    user = query.from_user
    
    keyboard = [
        [InlineKeyboardButton("💳 I've Paid", callback_data=f'pay_{ticket_id}')],
        [InlineKeyboardButton("🔍 Check Payment", callback_data=f'check_{ticket_id}')],
        [InlineKeyboardButton("⬅️ Back", callback_data='back_to_main')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    payment_instructions = (
        f"💳 **Payment Instructions**\n\n"
        f"Please send exactly **1 TON** to:\n"
        f"`{TON_WALLET_ADDRESS}`\n\n"
        f"📋 **Important Details:**\n"
        f"• Amount: **1 TON** (exactly)\n"
        f"• Network: **TON Blockchain**\n"
        f"• Memo: **{ticket_id}** (include this!)\n"
        f"• User ID: `{user.id}`\n\n"
        f"⏱️ **After sending**, click 'I've Paid' below.\n"
        f"🔄 Payment confirmation takes 2-3 minutes."
    )
    
    await query.edit_message_text(payment_instructions, parse_mode='Markdown', reply_markup=reply_markup)

# Process payment
async def process_payment(update: Update, context: ContextTypes.DEFAULT_TYPE, ticket_id):
    query = update.callback_query
    user = query.from_user
    await query.answer()
    
    # Show waiting message
    await query.edit_message_text(
        "🔍 **Checking for payment...**\n\n"
        "Please wait while we verify your transaction on the blockchain...\n"
        "This usually takes 2-3 minutes.",
        parse_mode='Markdown'
    )
    
    # Check if payment was received
    payment_received = await check_ton_payment(ticket_id, user.id)
    
    if payment_received:
        # Update database
        try:
            conn = get_db_connection()
            if conn is None:
                await query.edit_message_text("❌ Database error. Please contact support.")
                return
                
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
                
                success_message = (
                    f"✅ **Payment Confirmed!**\n\n"
                    f"🎫 **Your Lottery Ticket:**\n"
                    f"Numbers: {', '.join(numbers)}\n"
                    f"Bonus: {bonus}\n\n"
                    f"📋 **Ticket ID:** {ticket_id}\n\n"
                    f"🎉 **Good luck!** The draw will be on Saturday at 20:00 UTC.\n\n"
                    f"💰 **Prize pool:** 80% of all ticket sales!\n"
                    f"🏆 **To win:** Match all 6 numbers + bonus"
                )
                
                await query.edit_message_text(success_message, parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Database error in process_payment: {e}")
            await query.edit_message_text("❌ Error updating payment status. Please contact support.")
    else:
        keyboard = [
            [InlineKeyboardButton("🔍 Check Again", callback_data=f'check_{ticket_id}')],
            [InlineKeyboardButton("💳 Try Payment Again", callback_data=f'pay_{ticket_id}')],
            [InlineKeyboardButton("⬅️ Back", callback_data='back_to_main')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        error_message = (
            f"❌ **Payment Not Received Yet**\n\n"
            f"Please verify:\n"
            f"1. ✅ Sent exactly **1 TON**\n"
            f"2. ✅ Used address: `{TON_WALLET_ADDRESS}`\n"
            f"3. ✅ Included memo: `{ticket_id}`\n"
            f"4. ⏱️ Wait 2-3 minutes for blockchain confirmation\n\n"
            f"Click 'Check Again' after waiting."
        )
        
        await query.edit_message_text(error_message, parse_mode='Markdown', reply_markup=reply_markup)

# Check payment status
async def check_payment_status(update: Update, context: ContextTypes.DEFAULT_TYPE, ticket_id):
    query = update.callback_query
    user = query.from_user
    await query.answer()
    
    await query.edit_message_text(
        "🔍 **Checking for payment...**\n\n"
        "Please wait while we verify your transaction...",
        parse_mode='Markdown'
    )
    
    payment_received = await check_ton_payment(ticket_id, user.id)
    
    if payment_received:
        await process_payment(update, context, ticket_id)
    else:
        keyboard = [
            [InlineKeyboardButton("🔍 Check Again", callback_data=f'check_{ticket_id}')],
            [InlineKeyboardButton("💳 Try Payment Again", callback_data=f'pay_{ticket_id}')],
            [InlineKeyboardButton("⬅️ Back", callback_data='back_to_main')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "❌ **Payment Not Confirmed Yet**\n\n"
            "Please wait a few more minutes for blockchain confirmation.\n"
            "If you've sent the payment, it should be confirmed soon.",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

# View user's tickets
async def my_tickets(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    await query.answer()
    
    try:
        conn = get_db_connection()
        if conn is None:
            await query.message.reply_text("❌ Database error. Please try again.")
            return
            
        cursor = conn.cursor()
        cursor.execute('''
        SELECT ticket_id, numbers, bonus_number, purchased_at, payment_status 
        FROM tickets WHERE user_id = %s ORDER BY purchased_at DESC
        ''', (user.id,))
        
        tickets = cursor.fetchall()
        conn.close()
        
        if not tickets:
            await query.message.reply_text("You don't have any tickets yet. Buy your first ticket!")
            return
        
        message = "🎫 **Your Tickets**\n\n"
        for ticket in tickets:
            status = "✅ Paid" if ticket[4] == 'paid' else "⏳ Pending"
            message += (
                f"📋 **ID:** {ticket[0]}\n"
                f"🔢 **Numbers:** {ticket[1]} + {ticket[2]}\n"
                f"📅 **Purchased:** {ticket[3].strftime('%Y-%m-%d %H:%M')}\n"
                f"📊 **Status:** {status}\n\n"
            )
        
        keyboard = [[InlineKeyboardButton("⬅️ Back", callback_data='back_to_main')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.message.reply_text(message, reply_markup=reply_markup, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Error fetching tickets: {e}")
        await query.message.reply_text("❌ Error retrieving your tickets. Please try again.")

# Error handler
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(msg="Exception while handling an update:", exc_info=context.error)

# Main function - SIMPLIFIED FOR RAILWAY (ONLY POLLING)
def main():
    # Get token from environment variable
    token = os.environ.get('TELEGRAM_BOT_TOKEN')
    if not token:
        logger.error("No TELEGRAM_BOT_TOKEN found in environment variables")
        return
    
    # Check if TON wallet address is set
    if TON_WALLET_ADDRESS == 'YOUR_TON_WALLET_ADDRESS_HERE':
        logger.error("Please set your TON_WALLET_ADDRESS in environment variables")
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
    
    # Use polling only (simpler and more reliable)
    logger.info("Starting bot with polling...")
    application.run_polling()

if __name__ == '__main__':
    main()
