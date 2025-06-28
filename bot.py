import os
import csv
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
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
            print(f"Файли в директорії: {os.listdir('.')}")
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
    def __init__(self, game_id, category, creator_id):
        self.game_id = game_id
        self.category = category
        self.creator_id = creator_id
        self.players = {creator_id}
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
    
    welcome_text = """
🎮 **Інтимні Питання для Пар**

Цей бот допоможе парам краще пізнати один одного через цікаві питання різних категорій.

Що бажаєте зробити?
"""
    
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
    
    text = """
🎯 **Оберіть категорію питань:**

🔥 **Інтимні питання** - глибокі питання про сексуальність та інтимність
🌟 **Про життя** - філософські питання про щастя, мораль та сенс життя
😅 **Трохи крінжові питання** - абсурдні та кумедні ситуації для сміху

Кожна категорія містить 100 унікальних питань для різних настроїв!
"""
    
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
    games[game_id] = Game(game_id, category, creator_id)
    
    category_info = QUESTION_CATEGORIES[category]
    
    keyboard = [
        [InlineKeyboardButton("▶️ Почати гру", callback_data=f"start_game_{game_id}")],
        [InlineKeyboardButton("🚪 Закрити гру", callback_data=f"close_game_{game_id}")],
        [InlineKeyboardButton("⬅️ Головне меню", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = f"""
✅ **Гру створено!**

🎯 **Категорія:** {category_info['name']}
📋 **Опис:** {category_info['description']}
🆔 **ID гри:** `{game_id}`
👤 **Гравці:** 1 (ви)

Поділіться ID з партнером, щоб він міг приєднатися:
/join {game_id}

Або натисніть "Почати гру" якщо всі вже готові.
"""
    
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

async def join_game_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запитує ID гри для приєднання"""
    query = update.callback_query
    await query.answer()
    
    text = """
🎮 **Приєднання до гри**

Введіть ID гри, що отримали від партнера:

Приклад: `/join 1234`

Або натисніть кнопку нижче щоб повернутися.
"""
    
    keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data="main_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

async def join_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Приєднання до існуючої гри"""
    if not context.args:
        await update.message.reply_text("❌ Вкажіть ID гри: /join 1234")
        return
    
    game_id = context.args[0]
    user_id = update.effective_user.id
    
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
    game.players.add(user_id)
    category_info = QUESTION_CATEGORIES[game.category]
    
    keyboard = [
        [InlineKeyboardButton("▶️ Почати гру", callback_data=f"start_game_{game_id}")],
        [InlineKeyboardButton("🚪 Вийти з гри", callback_data=f"leave_game_{game_id}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = f"""
✅ **Приєдналися до гри!**

🎯 **Категорія:** {category_info['name']}
🆔 **ID гри:** `{game_id}`
👥 **Гравців:** {len(game.players)}

Коли всі будуть готові, натисніть "Почати гру".
"""
    
    await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')

async def start_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запускає гру та показує перше питання"""
    query = update.callback_query
    await query.answer()
    
    game_id = query.data.replace("start_game_", "")
    
    if game_id not in games:
        await query.edit_message_text("❌ Гра не знайдена!")
        return
    
    game = games[game_id]
    
    if len(game.players) < 2:
        await query.edit_message_text("❌ Потрібно мінімум 2 гравці для початку!")
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
    
    text = f"""
🎮 **Гра почалася!**

🎯 **Категорія:** {category_info['name']}
📝 **Питання #{len(game.used_questions)}:**

**{question['question']}**

💡 **Підказка:** {question['guidance']}
"""
    
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
    
    text = f"""
📝 **Питання #{len(game.used_questions)}:**

**{question['question']}**

💡 **Підказка:** {question['guidance']}
"""
    
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обробник всіх callback кнопок"""
    query = update.callback_query
    await query.answer()  # Завжди відповідаємо на callback
    
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

async def show_about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показує інформацію про бота"""
    query = update.callback_query
    
    text = """
ℹ️ **Про бота**

Цей бот створений для пар що хочуть краще пізнати один одного через цікаві питання.

📊 **Категорії питань:**
🔥 **Інтимні питання** - 100 питань про сексуальність
🌟 **Про життя** - 100 філософських питань  
😅 **Трохи крінжові питання** - 100 кумедних питань

🎮 **Як грати:**
1. Створіть гру та оберіть категорію
2. Поділіться ID з партнером
3. Відповідайте на питання по черзі
4. Відкривайте один одного!

Розробник: @ваш_username
"""
    
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
    
    text = f"""
📊 **Статистика гри**

🎯 **Категорія:** {category_info['name']}
🆔 **ID гри:** `{game_id}`
👥 **Гравці:** {len(game.players)}
📝 **Розглянуто питань:** {len(game.used_questions)}
🎮 **Статус:** {'Активна' if game.is_active else 'Очікування'}
"""
    
    keyboard = [
        [InlineKeyboardButton("⬅️ Назад до гри", callback_data=f"start_game_{game_id}")],
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
    
    # Видаляємо гру
    del games[game_id]
    
    text = f"""
🏁 **Гру завершено!**

Дякуємо за гру! Ви розглянули **{len(game.used_questions)}** питань з категорії **{category_info['name']}**.

Сподіваємося ви краще пізнали один одного! 💕
"""
    
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
    
    text = "🚪 **Гру закрито!**\n\nГра була видалена створювачем."
    
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
        game.players.remove(user_id)
    
    text = f"""
🚪 **Ви вийшли з гри**

ID гри: `{game_id}`
Гравців залишилося: {len(game.players)}
"""
    
    keyboard = [
        [InlineKeyboardButton("🎯 Створити нову гру", callback_data="create_game")],
        [InlineKeyboardButton("🏠 Головне меню", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

def main():
    """Запуск бота"""
    TOKEN = os.getenv('BOT_TOKEN')
    
    if not TOKEN:
        print("❌ BOT_TOKEN не знайдено в .env файлі!")
        return
    
    application = Application.builder().token(TOKEN).build()
    
    # Додаємо обробники
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("join", join_game))
    application.add_handler(CallbackQueryHandler(button_handler))
    
    print("🤖 Бот запущено з підтримкою категорій!")
    application.run_polling()

if __name__ == '__main__':
    main()
