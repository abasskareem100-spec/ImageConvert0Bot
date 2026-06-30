import os
import logging
import tempfile
from PIL import Image
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Bot token from environment variable
TOKEN = os.getenv("TELEGRAM_TOKEN")
if not TOKEN:
    raise ValueError("No TELEGRAM_TOKEN found in environment variables!")

# Supported formats
SUPPORTED_FORMATS = ["PNG", "JPG", "WEBP", "BMP", "GIF", "ICO", "TIFF"]

# Start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    welcome_message = (
        f"🎨 Hello {user.first_name}!\n\n"
        "I'm **ImageConvert0Bot**, your personal image converter.\n\n"
        "📤 **How to use:**\n"
        "1. Send me an image\n"
        "2. Choose your desired output format\n"
        "3. I'll convert and send it back!\n\n"
        "Use /help for more commands."
    )
    await update.message.reply_text(welcome_message)

# Help command
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "🆘 **Help & Commands:**\n\n"
        "/start - Start the bot\n"
        "/help - Show this help\n"
        "/formats - Show all supported formats\n"
        "/cancel - Cancel current operation\n\n"
        "📸 **Supported formats:**\n"
        "PNG, JPG, WEBP, BMP, GIF, ICO, TIFF"
    )
    await update.message.reply_text(help_text)

# Formats command
async def formats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    formats_list = "📋 **Supported Formats:**\n\n"
    for fmt in SUPPORTED_FORMATS:
        formats_list += f"• {fmt}\n"
    await update.message.reply_text(formats_list)

# Cancel command
async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("✅ Cancelled. Send me an image to start again!")

# Handle photos
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo = update.message.photo[-1]
    context.user_data['file_id'] = photo.file_id
    await show_format_buttons(update, context)

# Handle documents
async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    document = update.message.document
    if document.mime_type and document.mime_type.startswith('image/'):
        context.user_data['file_id'] = document.file_id
        await show_format_buttons(update, context)
    else:
        await update.message.reply_text("❌ Please send an image file.")

async def show_format_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = []
    row = []
    for idx, fmt in enumerate(SUPPORTED_FORMATS):
        row.append(InlineKeyboardButton(fmt, callback_data=fmt))
        if len(row) == 3:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "🔄 **Choose output format:**",
        reply_markup=reply_markup
    )

# Handle format selection
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    selected_format = query.data
    await query.edit_message_text(f"⏳ Converting to **{selected_format}**...")
    
    try:
        if 'file_id' not in context.user_data:
            await query.edit_message_text("❌ No image found. Send an image first.")
            return
        
        # Create temp directory
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = os.path.join(temp_dir, 'input.jpg')
            output_path = os.path.join(temp_dir, f'output.{selected_format.lower()}')
            
            # Download image
            file = await context.bot.get_file(context.user_data['file_id'])
            await file.download_to_drive(input_path)
            
            # Convert
            with Image.open(input_path) as img:
                # Handle GIF specially
                if selected_format == "GIF":
                    img.save(output_path, format='GIF', save_all=True)
                else:
                    # Convert to RGB for JPG
                    if selected_format in ["JPG", "JPEG"] and img.mode in ("RGBA", "P"):
                        img = img.convert("RGB")
                    
                    # Save
                    save_kwargs = {}
                    if selected_format == "JPG":
                        selected_format = "JPEG"
                        save_kwargs['quality'] = 95
                    elif selected_format == "PNG":
                        save_kwargs['compress_level'] = 6
                    elif selected_format == "WEBP":
                        save_kwargs['quality'] = 90
                    
                    img.save(output_path, format=selected_format, **save_kwargs)
            
            # Send result
            with open(output_path, 'rb') as f:
                await query.message.reply_document(
                    document=f,
                    filename=f"converted.{selected_format.lower()}",
                    caption=f"✅ Converted to **{selected_format}** successfully!"
                )
            
            context.user_data.clear()
            
    except Exception as e:
        logger.error(f"Conversion error: {e}")
        await query.edit_message_text(f"❌ Error: {str(e)}")

# Error handler
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Error: {context.error}")

def main():
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("formats", formats_command))
    app.add_handler(CommandHandler("cancel", cancel_command))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.Document.IMAGE, handle_document))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_error_handler(error_handler)
    
    logger.info("Bot is starting...")
    app.run_polling()

if __name__ == "__main__":
    main()
