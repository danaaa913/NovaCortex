"""Telegram handlers and application entry point (``main``)."""

import logging

from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, ConversationHandler, filters

from novacortex.agent import YarmoukAgent
from novacortex.config import TELEGRAM_TOKEN, require_secrets
from novacortex.db import init_db, save_user
from novacortex.logging_setup import configure_logging
from novacortex.memory import memory_system
from novacortex.rag.indexing import load_data_from_json

logger = logging.getLogger(__name__)

# ==================== TELEGRAM HANDLERS ====================
CHOOSING_LEVEL, ASKING_ID = range(2)
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    reply_keyboard = [['بكالوريوس', 'ماجستير', 'دكتوراه']]
    await update.message.reply_text(
        f"أهلاً {user.first_name}. اختر مستواك الدراسي:",
        reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True)
    )
    return CHOOSING_LEVEL
async def level_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    level = update.message.text
    context.user_data['study_level'] = level
    await update.message.reply_text(
        "ما هو رقمك الجامعي؟ (أو اكتب 'زائر')",
        reply_markup=ReplyKeyboardRemove()
    )
    return ASKING_ID
async def id_provided(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uni_id = update.message.text
    user = update.effective_user
    study_level = context.user_data.get('study_level', 'بكالوريوس')
    save_user(telegram_id=user.id, username=user.username, first_name=user.first_name,
              role="student" if uni_id.isdigit() else "visitor", uni_id=uni_id, study_level=study_level)
    await update.message.reply_text("تم التسجيل. يمكنك السؤال الآن.")
    return ConversationHandler.END
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    question = update.message.text
    user_id = update.effective_user.id
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    agent = context.bot_data.get('agent')
    if not agent:
        agent = YarmoukAgent()
        context.bot_data['agent'] = agent
    result = await agent.ask(question, user_id)
    await update.message.reply_text(result["response"])
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("تم الإلغاء.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END
async def clear_memory_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    memory_system.clear_memory(update.effective_user.id)
    await update.message.reply_text("تم المسح.")
# ==================== MAIN ====================
def main():
    configure_logging()
    require_secrets()
    init_db()
    if not load_data_from_json():
        logger.error("Failed to load data!")
        return
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            CHOOSING_LEVEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, level_chosen)],
            ASKING_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, id_provided)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )
    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("clear", clear_memory_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("NovaCortex v14.0 — Competition Edition is running...")
    application.run_polling()
