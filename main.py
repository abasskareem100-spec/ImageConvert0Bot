import os
import logging
import tempfile
from io import BytesIO
from PIL import Image
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Bot token from environment variable
TOKEN = os.getenv("TELEGRAM_TOKEN")
if not TOKEN:
    raise ValueError("No TELEGRAM_TOKEN found in environment variables!")

# Supported formats
SUPPORTED_FORMATS = {
    "PNG": "PNG",
    "JPG": "JPEG",
    "JPEG": "JPEG",
    "WEBP": "WEBP",
    "BMP": "BMP",
    "GIF": "GIF",
    "ICO": "ICO",
    "TIFF": "TIFF",
    "PDF": "PDF"
}

# Start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a welcome message when the command /start is issued."""
    user = update.effective_user
    welcome_message = (
        f"🎨 Hello {user.first_name}!\n\n"
        "I'm **ImageConvert0Bot**, your personal image converter.\n\n"
        "Here's what I can do:\n"
        "• Convert images between PNG, JPG, WEBP, BMP, GIF, ICO, TIFF, and PDF\n"
        "• Convert multiple images at once\n"
        "• High quality conversion\n\n"
        "📤 **How to use:**\n"
        "1. Send me an image (or multiple images)\n"
        "2. Choose your desired output format\n"
        "3. I'll convert and send it back!\n\n"
        "Use /help for more commands."
    )
    await update.message.reply_text(welcome_message)

# Help command
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a help message when the command /help is issued."""
    help_text = (
        "🆘 **Help & Commands:**\n\n"
        "/start - Start the bot and see welcome message\n"
        "/help - Show this help message\n"
        "/formats - Show all supported formats\n"
        "/convert - Convert the replied image\n"
        "/cancel - Cancel current operation\n\n"
        "📸 **Supported formats:**\n"
        "PNG, JPG, JPEG, WEBP, BMP, GIF, ICO, TIFF, PDF\n\n"
        "💡 **Tips:**\n"
        "• Send multiple images at once\n"
        "• Use high quality images for best results\n"
        "• I'll auto-detect the current format"
    )
    await update.message.reply_text(help_text)

# Formats command
async def formats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show all supported formats."""
    formats_list = "📋 **Supported Formats:**\n\n"
    for fmt in SUPPORTED_FORMATS.keys():
        formats_list += f"• {fmt}\n"
    formats_list += "\nSend an image and I'll ask which format you want!"
    await update.message.reply_text(formats_list)

# Cancel command
async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel current operation."""
    context.user_data.clear()
    await update.message.reply_text("✅ Operation cancelled. Send me an image to start again!")

# Handle photos
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming photos."""
    photo = update.message.photo[-1]  # Get the highest quality
    file = await photo.get_file()
    await process_file(update, context, file)

# Handle documents (for images sent as files)
async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming documents (images)."""
    document = update.message.document
    if document.mime_type and document.mime_type.startswith('image/'):
        file = await document.get_file()
        await process_file(update, context, file)
    else:
        await update.message.reply_text("❌ Please send an image file (PNG, JPG, WEBP, etc.)")

async def process_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process the image file and show format selection."""
    try:
        # Store file in context for later use
        context.user_data['file'] = update.message.photo[-1] if update.message.photo else update.message.document
        
        # Create inline keyboard with format options
        keyboard = []
        row = []
        for idx, fmt in enumerate(SUPPORTED_FORMATS.keys()):
            row.append(InlineKeyboardButton(fmt, callback_data=f"convert_{fmt}"))
            if (idx + 1) % 3 == 0:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "🔄 **Choose your output format:**",
            reply_markup=reply_markup
        )
    except Exception as e:
        logger.error(f"Error processing file: {e}")
        await update.message.reply_text("❌ Error processing your image. Please try again.")

# Handle format selection callback
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the format selection button press."""
    query = update.callback_query
    await query.answer()
    
    # Get the selected format
    selected_format = query.data.replace("convert_", "")
    await query.edit_message_text(f"⏳ Converting to **{selected_format}**... Please wait.")
    
    try:
        # Get the file from context
        if 'file' not in context.user_data:
            await query.edit_message_text("❌ No image found. Please send an image first.")
            return
        
        # Download the image
        file_obj = context.user_data['file']
        if hasattr(file_obj, 'file_id'):
            file = await file_obj.get_file()
        else:
            file = file_obj
        
        # Download to temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as temp_input:
            await file.download_to_drive(temp_input.name)
            temp_input_path = temp_input.name
        
        # Open and convert the image
        with Image.open(temp_input_path) as img:
            # Convert to RGB if necessary (for JPEG)
            if selected_format in ["JPEG", "JPG"] and img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            
            # Save to temp output
            with tempfile.NamedTemporaryFile(delete=False, suffix=f'.{selected_format.lower()}') as temp_output:
                output_path = temp_output.name
                
                # Save with appropriate parameters
                save_kwargs = {}
                if selected_format == "JPEG":
                    save_kwargs['quality'] = 95
                elif selected_format == "PNG":
                    save_kwargs['compress_level'] = 6
                elif selected_format == "WEBP":
                    save_kwargs['quality'] = 90
                
                img.save(output_path, format=selected_format, **save_kwargs)
        
        # Send the converted file
        with open(output_path, 'rb') as f:
            if selected_format in ["PDF"]:
                await query.message.reply_document(
                    document=f,
                    filename=f"converted.{selected_format.lower()}",
                    caption=f"✅ Converted to **{selected_format}** successfully!"
                )
            else:
                await query.message.reply_photo(
                    photo=f,
                    caption=f"✅ Converted to **{selected_format}** successfully!"
                )
        
        # Clean up temp files
        os.unlink(temp_input_path)
        os.unlink(output_path)
        context.user_data.clear()
        
    except Exception as e:
        logger.error(f"Error during conversion: {e}")
        await query.edit_message_text(f"❌ Error converting image: {str(e)}\nPlease try again with a different format.")

# Error handler
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Log errors."""
    logger.error(f"Update {update} caused error {context.error}")

def main():
    """Start the bot."""
    # Create the Application
    application = Application.builder().token(TOKEN).build()
    
    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("formats", formats_command))
    application.add_handler(CommandHandler("cancel", cancel_command))
    
    # Add message handlers
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(MessageHandler(filters.Document.IMAGE, handle_document))
    
    # Add callback query handler
    application.add_handler(CallbackQueryHandler(button_callback, pattern="^convert_"))
    
    # Add error handler
    application.add_error_handler(error_handler)
    
    # Start the bot (using polling for Railway)
    logger.info("Starting bot...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
