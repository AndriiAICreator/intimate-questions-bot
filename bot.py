import os
import csv
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters
from dotenv import load_dotenv

load_dotenv()

# Конфігурація категорій питань
QUESTION_CATEGORIES = {
    'intimate': {
        'name': '🔥 Інтимні питання',
        'file': 'questions.csv',
        'description': 'Глибокі питання про інтимність та сексуальність'
    },
    'life': {
        'name': '🌟 Про життя',
        'file': 'life_questions.csv',
        'description': 'Філософські питання про щастя, мораль та сенс життя'
    },
    'cringe': {
        'name': '😅 Трохи крінжові питання',
        'file': 'cringe_questions.csv',
        'description': 'Абсурдні та кумедні ситуації для сміху'
    }
}

class QuestionManager:
    def __init__(self):
        self.questions_cache = {}
    
    def load_questions(self, category):
        """Завантажує питання для вказаної категорії"""
        if category in self.questions_cache:
            return self.questions_cache[category]
        
        filename = QUESTION_CATEGORIES[category]['file']
        questions = []
        
        try:
            with open(filename, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                questions = [dict(row) for row in reader]
                self.questions_cache[category] = questions
                print(f"✅ Завантажено {len(questions)} питань з категорії '{category}' ({filename})")
        except FileNotFoundError:
            print(f"❌ Файл {filename} не знайдено! Перевірте чи файл існує.")
            print(f"Поточна директорія: {os.getcwd()}")
            try:
                print(f"Файли в директорії: {os.listdir('.')}")
            except:
                print("Не можу отримати список файлів")
        except Exception as e:
            print(f"❌ Помилка завантаження {filename}: {e}")
        
        return questions
    
    def get_random_question(self, category, used_questions=None):
        """Отримує випадкове питання з категорії"""
        questions = self.load_questions(category)
        if not questions:
            return None
        
        if used_questions is None:
            used_questions = set()
        
        # Фільтруємо використані питання
        available = [q for q in questions if q['id'] not in used_questions]
        
        if not available:
            # Якщо всі питання використані, скидаємо список
            available = questions
            used_questions.clear()
        
        return random.choice(available)

# Глобальний менеджер питань
question_manager = QuestionManager()

# Зберігання активних ігор
games = {}

class Game:
    def __init__(self, game_id, category, creator_id, creator_name):
        self.game_id = game_id
        self.category = category
        self.creator_id = creator_id
        self.creator_name = creator_name
        self.players = {}  # {user_id: user_name}
        self.players[creator_id] = creator_name
        self.used_questions = set()
        self.current_question = None
        self.is_active = False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Стартове повідомлення з вибором дій"""
    keyboard = [
        [InlineKeyboardButton("🎯 Створити гру", callback_data="create_game")],
        [InlineKeyboardButton("🎮 Приєднатися до гри", callback_data="join_game")],
        [InlineKeyboardButton("ℹ️ Про бота", callback_data="about")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_text = """🎮 *Інтимні Питання для Пар*

Цей бот допоможе парам краще пізнати один одного через цікаві питання різних категорій.

Що бажаєте зробити?"""
    
    # Перевіряємо чи це callback query чи звичайне повідомлення
    if update.callback_query:
        await update.callback_query.edit_message_text(welcome_text, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='Markdown')

async def create_game_category_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показує вибір категорії для нової гри"""
    query = update.callback_query
    await query.answer()
    
    keyboard = []
    for cat_id, cat_info in QUESTION_CATEGORIES.items():
        keyboard.append([
            InlineKeyboardButton(
                cat_info['name'], 
                callback_data=f"category_{cat_id}"
            )
        ])
    
    keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="main_menu")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = """🎯 *Оберіть категорію питань:*

🔥 *Інтимні питання* - глибокі питання про сексуальність та інтимність
🌟 *Про життя* - філософські питання про щастя, мораль та сенс життя
😅 *Трохи крінжові питання* - абсурдні та кумедні ситуації для сміху

Кожна категорія містить 100 унікальних питань для різних настроїв!"""
    
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

async def create_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Створює нову гру обраної категорії"""
    query = update.callback_query
    await query.answer()
    
    # Отримуємо категорію з callback_data
    category = query.data.replace("category_", "")
    
    if category not in QUESTION_CATEGORIES:
        await query.edit_message_text("❌ Невідома категорія!")
        return
    
    # Генеруємо унікальний ID гри
    game_id = str(random.randint(1000, 9999))
    while game_id in games:
        game_id = str(random.randint(1000, 9999))
    
    # Створюємо гру
    creator_id = query.from_user.id
    creator_name = query.from_user.first_name or "Гравець"
    games[game_id] = Game(game_id, category, creator_id, creator_name)
    
    category_info = QUESTION_CATEGORIES[category]
    
    keyboard = [
        [InlineKeyboardButton("▶️ Почати гру", callback_data=f"start_game_{game_id}")],
        [InlineKeyboardButton("👥 Переглянути гравців", callback_data=f"view_players_{game_id}")],
        [InlineKeyboardButton("🚪 Закрити гру", callback_data=f"close_game_{game_id}")],
        [InlineKeyboardButton("⬅️ Головне меню", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = f"""✅ *Гру створено!*

🎯 *Категорія:* {category_info['name']}
📋 *Опис:* {category_info['description']}
🆔 *ID гри:* `{game_id}`
👤 *Гравці:* 1 (ви)

*Для приєднання партнера:*
Поділіться з ним командою: `/join {game_id}`

Або натисніть "Почати гру" якщо всі вже готові."""
    
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

async def join_game_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запитує ID гри для приєднання"""
    query = update.callback_query
    await query.answer()
    
    text = """🎮 *Приєднання до гри*

Введіть ID гри що отримали від партнера:

*Приклад:* `/join 1234`

Або натисніть кнопку нижче щоб повернутися."""
    
    keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data="main_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

async def join_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Приєднання до існуючої гри"""
    if not context.args:
        await update.message.reply_text("❌ Вкажіть ID гри: `/join 1234`", parse_mode='Markdown')
        return
    
    game_id = context.args[0]
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name or "Гравець"
    
    if game_id not in games:
        await update.message.reply_text("❌ Гра з таким ID не знайдена!")
        return
    
    game = games[game_id]
    
    if user_id in game.players:
        await update.message.reply_text("❌ Ви вже в цій грі!")
        return
    
    if game.is_active:
        await update.message.reply_text("❌ Ця гра вже активна!")
        return
    
    # Додаємо гравця
    game.players[user_id] = user_name
    category_info = QUESTION_CATEGORIES[game.category]
    
    keyboard = [
        [InlineKeyboardButton("▶️ Почати гру", callback_data=f"start_game_{game_id}")],
        [InlineKeyboardButton("👥 Переглянути гравців", callback_data=f"view_players_{game_id}")],
        [InlineKeyboardButton("🚪 Вийти з гри", callback_data=f"leave_game_{game_id}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = f"""✅ *Приєдналися до гри!*

🎯 *Категорія:* {category_info['name']}
🆔 *ID гри:* `{game_id}`
👥 *Гравців:* {len(game.players)}

Коли всі будуть готові, натисніть "Почати гру"."""
    
    await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')

async def view_players(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показує список гравців"""
    query = update.callback_query
    await query.answer()
    
    game_id = query.data.replace("view_players_", "")
    
    if game_id not in games:
        await query.edit_message_text("❌ Гра не знайдена!")
        return
    
    game = games[game_id]
    category_info = QUESTION_CATEGORIES[game.category]
    
    players_list = "\n".join([f"👤 {name}" for name in game.players.values()])
    
    text = f"""👥 *Гравці в грі*

🎯 *Категорія:* {category_info['name']}
🆔 *ID гри:* `{game_id}`

*Учасники ({len(game.players)}):*
{players_list}

*Статус:* {'🟢 Активна' if game.is_active else '🟡 Очікування'}"""
    
    keyboard = [
        [InlineKeyboardButton("▶️ Почати гру", callback_data=f"start_game_{game_id}")],
        [InlineKeyboardButton("⬅️ Назад", callback_data=f"game_menu_{game_id}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

async def game_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показує меню гри"""
    query = update.callback_query
    await query.answer()
    
    game_id = query.data.replace("game_menu_", "")
    
    if game_id not in games:
        await query.edit_message_text("❌ Гра не знайдена!")
        return
    
    game = games[game_id]
    category_info = QUESTION_CATEGORIES[game.category]
    user_id = query.from_user.id
    
    keyboard = []
    
    if game.is_active:
        keyboard.extend([
            [InlineKeyboardButton("➡️ Наступне питання", callback_data=f"next_question_{game_id}")],
            [InlineKeyboardButton("📊 Статистика", callback_data=f"game_stats_{game_id}")],
            [InlineKeyboardButton("🛑 Завершити гру", callback_data=f"end_game_{game_id}")]
        ])
    else:
        keyboard.extend([
            [InlineKeyboardButton("▶️ Почати гру", callback_data=f"start_game_{game_id}")],
            [InlineKeyboardButton("👥 Переглянути гравців", callback_data=f"view_players_{game_id}")]
        ])
    
    if user_id == game.creator_id:
        keyboard.append([InlineKeyboardButton("🚪 Закрити гру", callback_data=f"close_game_{game_id}")])
    else:
        keyboard.append([InlineKeyboardButton("🚪 Вийти з гри", callback_data=f"leave_game_{game_id}")])
    
    keyboard.append([InlineKeyboardButton("🏠 Головне меню", callback_data="main_menu")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = f"""🎮 *Гра: {category_info['name']}*

🆔 *ID:* `{game_id}`
👥 *Гравців:* {len(game.players)}
📝 *Питань переглянуто:* {len(game.used_questions)}
🎮 *Статус:* {'🟢 Активна' if game.is_active else '🟡 Очікування'}"""
    
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

async def start_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запускає гру та показує перше питання"""
    query = update.callback_query
    await query.answer()
    
    game_id = query.data.replace("start_game_", "")
    
    if game_id not in games:
        await query.edit_message_text("❌ Гра не знайдена!")
        return
    
    game = games[game_id]
    
    if len(game.players) < 1:  # Можна грати навіть одному
        await query.edit_message_text("❌ Приєднайтеся до гри для початку!")
        return
    
    # Активуємо гру
    game.is_active = True
    
    # Отримуємо перше питання
    question = question_manager.get_random_question(game.category, game.used_questions)
    
    if not question:
        await query.edit_message_text("❌ Не вдалося завантажити питання!")
        return
    
    game.current_question = question
    game.used_questions.add(question['id'])
    
    category_info = QUESTION_CATEGORIES[game.category]
    
    keyboard = [
        [InlineKeyboardButton("➡️ Наступне питання", callback_data=f"next_question_{game_id}")],
        [InlineKeyboardButton("📊 Статистика", callback_data=f"game_stats_{game_id}")],
        [InlineKeyboardButton("🛑 Завершити гру", callback_data=f"end_game_{game_id}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = f"""🎮 *Гра почалася!*

🎯 *Категорія:* {category_info['name']}
📝 *Питання #{len(game.used_questions)}:*

*{question['question']}*

💡 *Підказка:* {question['guidance']}"""
    
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

async def next_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показує наступне питання"""
    query = update.callback_query
    await query.answer()
    
    game_id = query.data.replace("next_question_", "")
    
    if game_id not in games:
        await query.edit_message_text("❌ Гра не знайдена!")
        return
    
    game = games[game_id]
    
    # Отримуємо нове питання
    question = question_manager.get_random_question(game.category, game.used_questions)
    
    if not question:
        await query.edit_message_text("❌ Питання закінчилися!")
        return
    
    game.current_question = question
    game.used_questions.add(question['id'])
    
    keyboard = [
        [InlineKeyboardButton("➡️ Наступне питання", callback_data=f"next_question_{game_id}")],
        [InlineKeyboardButton("📊 Статистика", callback_data=f"game_stats_{game_id}")],
        [InlineKeyboardButton("🛑 Завершити гру", callback_data=f"end_game_{game_id}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = f"""📝 *Питання #{len(game.used_questions)}:*

*{question['question']}*

💡 *Підказка:* {question['guidance']}"""
    
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обробник всіх callback кнопок"""
    query = update.callback_query
    await query.answer()  # Завжди відповідаємо на callback
    
    try:
        if query.data == "create_game":
            await create_game_category_selection(update, context)
        elif query.data.startswith("category_"):
            await create_game(update, context)
        elif query.data == "join_game":
            await join_game_input(update, context)
        elif query.data == "about":
            await show_about(update, context)
        elif query.data == "main_menu":
            await start(update, context)
        elif query.data.startswith("start_game_"):
            await start_game(update, context)
        elif query.data.startswith("next_question_"):
            await next_question(update, context)
        elif query.data.startswith("view_players_"):
            await view_players(update, context)
        elif query.data.startswith("game_menu_"):
            await game_menu(update, context)
        elif query.data.startswith("game_stats_"):
            await show_game_stats(update, context)
        elif query.data.startswith("end_game_"):
            await end_game(update, context)
        elif query.data.startswith("close_game_"):
            await close_game(update, context)
        elif query.data.startswith("leave_game_"):
            await leave_game(update, context)
        else:
            await query.edit_message_text("❌ Невідома команда!")
    except Exception as e:
        print(f"Error in button_handler: {e}")
        await query.edit_message_text("❌ Сталася помилка. Спробуйте ще раз.")

async def show_about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показує інформацію про бота"""
    query = update.callback_query
    
    text = """ℹ️ *Про бота*

Цей бот створений для пар що хочуть краще пізнати один одного через цікаві питання.

📊 *Категорії питань:*
🔥 *Інтимні питання* - 100 питань про сексуальність
🌟 *Про життя* - 100 філософських питань  
😅 *Трохи крінжові питання* - 100 кумедних питань

🎮 *Як грати:*
1. Створіть гру та оберіть категорію
2. Поділіться ID з партнером
3. Відповідайте на питання по черзі
4. Відкривайте один одного!"""
    
    keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data="main_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

async def show_game_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показує статистику гри"""
    query = update.callback_query
    game_id = query.data.replace("game_stats_", "")
    
    if game_id not in games:
        await query.edit_message_text("❌ Гра не знайдена!")
        return
    
    game = games[game_id]
    category_info = QUESTION_CATEGORIES[game.category]
    
    text = f"""📊 *Статистика гри*

🎯 *Категорія:* {category_info['name']}
🆔 *ID гри:* `{game_id}`
👥 *Гравці:* {len(game.players)}
📝 *Розглянуто питань:* {len(game.used_questions)}
🎮 *Статус:* {'Активна' if game.is_active else 'Очікування'}"""
    
    keyboard = [
        [InlineKeyboardButton("⬅️ Назад до гри", callback_data=f"game_menu_{game_id}")],
        [InlineKeyboardButton("🏠 Головне меню", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

async def end_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Завершує гру"""
    query = update.callback_query
    game_id = query.data.replace("end_game_", "")
    
    if game_id not in games:
        await query.edit_message_text("❌ Гра не знайдена!")
        return
    
    game = games[game_id]
    category_info = QUESTION_CATEGORIES[game.category]
    questions_count = len(game.used_questions)
    
    # Видаляємо гру
    del games[game_id]
    
    text = f"""🏁 *Гру завершено!*

Дякуємо за гру! Ви розглянули *{questions_count}* питань з категорії *{category_info['name']}*.

Сподіваємося ви краще пізнали один одного! 💕"""
    
    keyboard = [
        [InlineKeyboardButton("🎯 Нова гра", callback_data="create_game")],
        [InlineKeyboardButton("🏠 Головне меню", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

async def close_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Закриває гру (тільки створювач)"""
    query = update.callback_query
    game_id = query.data.replace("close_game_", "")
    
    if game_id not in games:
        await query.edit_message_text("❌ Гра не знайдена!")
        return
    
    game = games[game_id]
    
    if query.from_user.id != game.creator_id:
        await query.edit_message_text("❌ Тільки створювач може закрити гру!")
        return
    
    # Видаляємо гру
    del games[game_id]
    
    text = """🚪 *Гру закрито!*

Гра була видалена створювачем."""
    
    keyboard = [
        [InlineKeyboardButton("🎯 Створити нову гру", callback_data="create_game")],
        [InlineKeyboardButton("🏠 Головне меню", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

async def leave_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Вийти з гри"""
    query = update.callback_query
    game_id = query.data.replace("leave_game_", "")
    
    if game_id not in games:
        await query.edit_message_text("❌ Гра не знайдена!")
        return
    
    game = games[game_id]
    user_id = query.from_user.id
    
    if user_id in game.players:
        del game.players[user_id]
    
    text = f"""🚪 *Ви вийшли з гри*

ID гри: `{game_id}`
Гравців залишилося: {len(game.players)}"""
    
    keyboard = [
        [InlineKeyboardButton("🎯 Створити нову гру", callback_data="create_game")],
        [InlineKeyboardButton("🏠 Головне меню", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обробляє текстові повідомлення"""
    # Якщо користувач надіслав просто число - намагаємося приєднати до гри
    text = update.message.text.strip()
    
    if text.isdigit() and len(text) == 4:
        # Імітуємо команду /join
        context.args = [text]
        await join_game(update, context)
    else:
        await update.message.reply_text(
            "🤖 Не розумію команду. Використовуйте `/start` для початку або `/join XXXX` для приєднання до гри.",
            parse_mode='Markdown'
        )

def main():
    """Запуск бота"""
    TOKEN = os.getenv('BOT_TOKEN')
    
    if not TOKEN:
        print("❌ BOT_TOKEN не знайдено в змінних середовища!")
        return
    
    application = Application.builder().token(TOKEN).build()
    
    # Додаємо обробники
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("join", join_game))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
    
    print("🤖 Бот запущено з підтримкою категорій!")
    print("📊 Категорії:", ", ".join(QUESTION_CATEGORIES.keys()))
    
    # Перевіряємо наявність файлів
    for cat_id, cat_info in QUESTION_CATEGORIES.items():
        filename = cat_info['file']
        if os.path.exists(filename):
            print(f"✅ Знайдено файл: {filename}")
        else:
            print(f"❌ НЕ знайдено файл: {filename}")
    
    application.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
