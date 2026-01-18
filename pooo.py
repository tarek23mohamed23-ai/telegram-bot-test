#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import logging
import tempfile
import shutil
from typing import Dict, List, Tuple
from pathlib import Path

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)
from telegram.constants import ParseMode

# ==================== إعدادات البوت ====================
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"  # ضع توكن البوت هنا
ADMIN_ID = 123456789  # ضع معرف المدير هنا

# ==================== إعداد السجل ====================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ==================== حالات المحادثة ====================
(
    MAIN_MENU,
    FONT_BUILDER_MENU,
    WAITING_SVG,
    WAITING_MAPPING,
    THANK_MESSAGE,
) = range(5)

# ==================== رسائل البوت ====================
WELCOME_MESSAGE = """
<b>✨ مرحباً بك في بوت تركيب الخطوط ✨</b>

هذا البوت يساعدك على تحويل المخطوطات إلى خط TTF حقيقي!

اضغط على الزر أدناه للبدء 👇
"""

FONT_BUILDER_MESSAGE = """
<b>🎨 قائمة تركيب الخط</b>

قم بإضافة المخطوطات الخاصة بك (من 1 إلى 400 مخطوطة)

<i>ملاحظة: يجب أن تكون المخطوطات بصيغة SVG منزوعة الخلفية</i>
"""

SVG_REQUEST_MESSAGE = """
<b>📤 أرسل ملف المخطوطة</b>

الرجاء إرسال ملف المخطوطة بصيغة <code>SVG</code> منزوع الخلفية
"""

MAPPING_REQUEST_MESSAGE = """
<b>🔤 أدخل الترقيم للمخطوطة</b>

يمكنك استخدام:
• حروف عربية
• حروف انجليزية
• أرقام عربية أو انجليزية
• رموز
• أكثر من حرف

مثال: <code>أ</code> أو <code>abc</code> أو <code>123</code>
"""

BUILDING_FONT_MESSAGE = """
<b>⚙️ جاري تركيب الخط...</b>

الرجاء الانتظار...
"""

FONT_READY_MESSAGE = """
<b>✅ تم تركيب الخط بنجاح!</b>

يتم الآن إرسال ملف الخط...
"""

THANK_YOU_REQUEST = """
<b>💚 شكراً لاستخدامك البوت!</b>

إذا أعجبك البوت، يمكنك إرسال رسالة شكر لمطور البوت 🌟
"""

THANK_YOU_RECEIVED = """
<b>✨ شكراً لك!</b>

تم إرسال رسالتك للمطور بنجاح 💚

سيتم العودة للقائمة الرئيسية...
"""


# ==================== دوال مساعدة ====================
def get_main_keyboard() -> InlineKeyboardMarkup:
    """إنشاء لوحة مفاتيح القائمة الرئيسية"""
    keyboard = [
        [InlineKeyboardButton("✨ تركيب خط", callback_data="build_font")]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_font_builder_keyboard(glyphs_count: int = 0) -> InlineKeyboardMarkup:
    """إنشاء لوحة مفاتيح قائمة تركيب الخط"""
    keyboard = [
        [InlineKeyboardButton("➕ اضف مخطوطة", callback_data="add_glyph")],
    ]
    
    if glyphs_count > 0:
        keyboard.append([InlineKeyboardButton(f"🍂 تم الانتهاء ({glyphs_count} مخطوطة)", callback_data="finish_font")])
    
    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main")])
    
    return InlineKeyboardMarkup(keyboard)


def get_cancel_keyboard() -> InlineKeyboardMarkup:
    """إنشاء لوحة مفاتيح الإلغاء"""
    keyboard = [
        [InlineKeyboardButton("❌ إلغاء", callback_data="cancel_add")]
    ]
    return InlineKeyboardMarkup(keyboard)


async def download_svg_file(file, user_id: int) -> str:
    """تحميل ملف SVG وحفظه مؤقتاً"""
    try:
        # إنشاء مجلد مؤقت للمستخدم
        user_dir = Path(tempfile.gettempdir()) / f"font_builder_{user_id}"
        user_dir.mkdir(exist_ok=True)
        
        # حفظ الملف
        file_path = user_dir / f"{file.file_id}.svg"
        await file.download_to_drive(file_path)
        
        return str(file_path)
    except Exception as e:
        logger.error(f"Error downloading SVG file: {e}")
        return None


def create_font_from_glyphs(glyphs_data: List[Tuple[str, str]], user_id: int) -> str:
    """إنشاء خط TTF من المخطوطات"""
    try:
        import fontforge
        
        # إنشاء خط جديد
        font = fontforge.font()
        font.fontname = "TMFont"
        font.familyname = "TM FONT"
        font.fullname = "TM FONT"
        font.encoding = "UnicodeFull"
        
        # إعدادات الخط
        font.ascent = 800
        font.descent = 200
        font.em = 1000
        
        # إضافة المخطوطات
        for svg_path, mapping in glyphs_data:
            if not os.path.exists(svg_path):
                logger.warning(f"SVG file not found: {svg_path}")
                continue
            
            # تحديد نقطة Unicode للحرف
            if len(mapping) == 1:
                codepoint = ord(mapping)
            else:
                # في حالة أكثر من حرف، استخدم أول حرف
                codepoint = ord(mapping[0])
            
            try:
                # إنشاء الحرف في الخط
                glyph = font.createChar(codepoint)
                
                # استيراد المخطوطة SVG
                glyph.importOutlines(svg_path)
                
                # ضبط عرض الحرف
                glyph.width = 600
                
                # إذا كان الترقيم أكثر من حرف، أضف ligature
                if len(mapping) > 1:
                    glyph.glyphname = mapping
                    
            except Exception as e:
                logger.error(f"Error processing glyph {mapping}: {e}")
                continue
        
        # حفظ الخط
        output_dir = Path(tempfile.gettempdir()) / f"font_builder_{user_id}"
        output_dir.mkdir(exist_ok=True)
        output_path = output_dir / "TM_FONT.ttf"
        
        font.generate(str(output_path))
        font.close()
        
        return str(output_path)
        
    except ImportError:
        logger.error("FontForge is not installed!")
        return None
    except Exception as e:
        logger.error(f"Error creating font: {e}")
        return None


def cleanup_user_data(user_id: int):
    """تنظيف البيانات المؤقتة للمستخدم"""
    try:
        user_dir = Path(tempfile.gettempdir()) / f"font_builder_{user_id}"
        if user_dir.exists():
            shutil.rmtree(user_dir)
    except Exception as e:
        logger.error(f"Error cleaning up user data: {e}")


# ==================== معالجات الأوامر ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """معالج أمر البدء"""
    user = update.effective_user
    
    # تنظيف البيانات السابقة
    context.user_data.clear()
    cleanup_user_data(user.id)
    
    await update.message.reply_text(
        WELCOME_MESSAGE,
        reply_markup=get_main_keyboard(),
        parse_mode=ParseMode.HTML
    )
    
    return MAIN_MENU


async def main_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """معالج القائمة الرئيسية"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "build_font":
        # إعادة تعيين البيانات
        context.user_data["glyphs"] = []
        
        await query.edit_message_text(
            FONT_BUILDER_MESSAGE,
            reply_markup=get_font_builder_keyboard(0),
            parse_mode=ParseMode.HTML
        )
        return FONT_BUILDER_MENU
    
    return MAIN_MENU


async def font_builder_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """معالج قائمة تركيب الخط"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "add_glyph":
        # التحقق من عدد المخطوطات
        glyphs_count = len(context.user_data.get("glyphs", []))
        
        if glyphs_count >= 400:
            await query.answer("❌ لقد وصلت للحد الأقصى (400 مخطوطة)", show_alert=True)
            return FONT_BUILDER_MENU
        
        await query.edit_message_text(
            SVG_REQUEST_MESSAGE,
            reply_markup=get_cancel_keyboard(),
            parse_mode=ParseMode.HTML
        )
        return WAITING_SVG
    
    elif query.data == "finish_font":
        glyphs = context.user_data.get("glyphs", [])
        
        if not glyphs:
            await query.answer("❌ يجب إضافة مخطوطة واحدة على الأقل", show_alert=True)
            return FONT_BUILDER_MENU
        
        await query.edit_message_text(
            BUILDING_FONT_MESSAGE,
            parse_mode=ParseMode.HTML
        )
        
        # إنشاء الخط
        user_id = update.effective_user.id
        font_path = create_font_from_glyphs(glyphs, user_id)
        
        if font_path and os.path.exists(font_path):
            await query.message.reply_text(
                FONT_READY_MESSAGE,
                parse_mode=ParseMode.HTML
            )
            
            # إرسال الخط
            with open(font_path, 'rb') as font_file:
                await query.message.reply_document(
                    document=font_file,
                    filename="TM_FONT.ttf",
                    caption="<b>✨ خطك جاهز!</b>",
                    parse_mode=ParseMode.HTML
                )
            
            # تنظيف البيانات
            cleanup_user_data(user_id)
            context.user_data["glyphs"] = []
            
            # طلب رسالة الشكر
            await query.message.reply_text(
                THANK_YOU_REQUEST,
                parse_mode=ParseMode.HTML
            )
            return THANK_MESSAGE
        else:
            await query.message.reply_text(
                "<b>❌ حدث خطأ أثناء تركيب الخط</b>\n\nالرجاء المحاولة مرة أخرى",
                reply_markup=get_main_keyboard(),
                parse_mode=ParseMode.HTML
            )
            return MAIN_MENU
    
    elif query.data == "back_to_main":
        await query.edit_message_text(
            WELCOME_MESSAGE,
            reply_markup=get_main_keyboard(),
            parse_mode=ParseMode.HTML
        )
        return MAIN_MENU
    
    return FONT_BUILDER_MENU


async def receive_svg(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """استقبال ملف SVG"""
    message = update.message
    
    if not message.document:
        await message.reply_text(
            "<b>❌ خطأ</b>\n\nالرجاء إرسال ملف SVG",
            reply_markup=get_cancel_keyboard(),
            parse_mode=ParseMode.HTML
        )
        return WAITING_SVG
    
    # التحقق من نوع الملف
    file_name = message.document.file_name.lower()
    if not file_name.endswith('.svg'):
        await message.reply_text(
            "<b>❌ خطأ</b>\n\nالملف يجب أن يكون بصيغة SVG",
            reply_markup=get_cancel_keyboard(),
            parse_mode=ParseMode.HTML
        )
        return WAITING_SVG
    
    # تحميل الملف
    file = await message.document.get_file()
    user_id = update.effective_user.id
    svg_path = await download_svg_file(file, user_id)
    
    if svg_path:
        context.user_data["current_svg"] = svg_path
        
        await message.reply_text(
            MAPPING_REQUEST_MESSAGE,
            reply_markup=get_cancel_keyboard(),
            parse_mode=ParseMode.HTML
        )
        return WAITING_MAPPING
    else:
        await message.reply_text(
            "<b>❌ فشل تحميل الملف</b>\n\nالرجاء المحاولة مرة أخرى",
            reply_markup=get_cancel_keyboard(),
            parse_mode=ParseMode.HTML
        )
        return WAITING_SVG


async def receive_mapping(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """استقبال الترقيم للمخطوطة"""
    message = update.message
    mapping = message.text.strip()
    
    if not mapping:
        await message.reply_text(
            "<b>❌ خطأ</b>\n\nالرجاء إدخال الترقيم",
            reply_markup=get_cancel_keyboard(),
            parse_mode=ParseMode.HTML
        )
        return WAITING_MAPPING
    
    # حفظ المخطوطة
    svg_path = context.user_data.get("current_svg")
    if not svg_path:
        await message.reply_text(
            "<b>❌ خطأ</b>\n\nلم يتم العثور على المخطوطة",
            parse_mode=ParseMode.HTML
        )
        return FONT_BUILDER_MENU
    
    if "glyphs" not in context.user_data:
        context.user_data["glyphs"] = []
    
    context.user_data["glyphs"].append((svg_path, mapping))
    glyphs_count = len(context.user_data["glyphs"])
    
    del context.user_data["current_svg"]
    
    await message.reply_text(
        f"<b>✅ تمت إضافة المخطوطة بنجاح!</b>\n\n"
        f"عدد المخطوطات: <b>{glyphs_count}</b>\n"
        f"الترقيم: <code>{mapping}</code>",
        reply_markup=get_font_builder_keyboard(glyphs_count),
        parse_mode=ParseMode.HTML
    )
    
    return FONT_BUILDER_MENU


async def cancel_add_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """إلغاء إضافة مخطوطة"""
    query = update.callback_query
    await query.answer()
    
    # حذف المخطوطة المؤقتة إن وجدت
    if "current_svg" in context.user_data:
        del context.user_data["current_svg"]
    
    glyphs_count = len(context.user_data.get("glyphs", []))
    
    await query.edit_message_text(
        FONT_BUILDER_MESSAGE,
        reply_markup=get_font_builder_keyboard(glyphs_count),
        parse_mode=ParseMode.HTML
    )
    
    return FONT_BUILDER_MENU


async def receive_thank_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """استقبال رسالة الشكر وإرسالها للمطور"""
    message = update.message
    user = update.effective_user
    thank_text = message.text
    
    # إرسال الرسالة للمطور
    try:
        admin_message = (
            f"<b>💚 رسالة شكر جديدة!</b>\n\n"
            f"من: {user.mention_html()}\n"
            f"المعرف: <code>{user.id}</code>\n\n"
            f"<i>{thank_text}</i>"
        )
        
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=admin_message,
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        logger.error(f"Error sending thank message to admin: {e}")
    
    # الرد على المستخدم
    await message.reply_text(
        THANK_YOU_RECEIVED,
        parse_mode=ParseMode.HTML
    )
    
    # العودة للقائمة الرئيسية
    await message.reply_text(
        WELCOME_MESSAGE,
        reply_markup=get_main_keyboard(),
        parse_mode=ParseMode.HTML
    )
    
    return MAIN_MENU


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """إلغاء المحادثة"""
    user = update.effective_user
    cleanup_user_data(user.id)
    context.user_data.clear()
    
    await update.message.reply_text(
        "<b>❌ تم الإلغاء</b>\n\nللعودة للقائمة الرئيسية، اضغط /start",
        parse_mode=ParseMode.HTML
    )
    
    return ConversationHandler.END


# ==================== الدالة الرئيسية ====================
def main():
    """بدء تشغيل البوت"""
    
    if not BOT_TOKEN or BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        logger.error("Please set BOT_TOKEN in the code!")
        return
    
    if ADMIN_ID == 123456789:
        logger.warning("Please set ADMIN_ID in the code!")
    
    # إنشاء التطبيق
    application = Application.builder().token(BOT_TOKEN).build()
    
    # إنشاء معالج المحادثة
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
        ],
        states={
            MAIN_MENU: [
                CallbackQueryHandler(main_menu_handler),
            ],
            FONT_BUILDER_MENU: [
                CallbackQueryHandler(font_builder_menu_handler),
            ],
            WAITING_SVG: [
                MessageHandler(filters.Document.ALL, receive_svg),
                CallbackQueryHandler(cancel_add_handler, pattern="^cancel_add$"),
            ],
            WAITING_MAPPING: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_mapping),
                CallbackQueryHandler(cancel_add_handler, pattern="^cancel_add$"),
            ],
            THANK_MESSAGE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_thank_message),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_command),
        ],
        per_user=True,
        per_chat=True,
    )
    
    # إضافة المعالجات
    application.add_handler(conv_handler)
    
    # بدء البوت
    logger.info("Bot started successfully!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
