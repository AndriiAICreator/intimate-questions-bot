import os
import csv
import random
import asyncio
from typing import Dict, List, Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv

# Завантажити змінні середовища
load_dotenv()

# Глобальні змінні для зберігання даних
games: Dict[str, dict] = {}
all_questions: Dict[str, List[dict]] = {}
all_prizes: Dict[str, List[str]] = {}

# Конфігурація категорій питань
QUESTION_CATEGORIES = {
    'intimate': {
        'name': '🔥 Інтимні питання',
        'file': 'questions.csv',
        'prize_file': 'winner_prizes_intim.csv'
    },
    'life': {
        'name': '🌟 Про життя',
        'file': 'life_questions.csv',
        'prize_file': 'winner_prizes_life.csv'
    },
    'cringe': {
        'name': '😅 Трохи крінжові питання',
        'file': 'cringe_questions.csv',
        'prize_file': 'winner_prizes_krin.csv'
    }
}

# Імена особливих користувачів (обов'язково в нижньому регістрі!)
SPECIAL_USERNAMES = {"apofickk"} # <-- Замініть на реальні імена без символу @

class GameStates:
    WAITING_FOR_PLAYERS = "waiting"
    IN_PROGRESS = "playing"
    VOTING = "voting"
    FINISHED = "finished"

def load_questions():
    """Завантажити питання з усіх файлів категорій"""
    global all_questions
    total_loaded = 0
    for category_key, details in QUESTION_CATEGORIES.items():
        try:
            with open(details['file'], 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                category_questions = list(reader)
                all_questions[category_key] = category_questions
                print(f"✅ Завантажено {len(category_questions)} питань з категорії '{details['name']}' ({details['file']})")
                total_loaded += len(category_questions)
        except FileNotFoundError:
            print(f"❌ Файл {details['file']} не знайдено!")
            all_questions[category_key] = []
        except Exception as e:
            print(f"❌ Помилка завантаження питань з {details['file']}: {e}")
            all_questions[category_key] = []
    print(f"📊 Всього завантажено: {total_loaded} питань.")


def generate_game_code() -> str:
    """Генерувати унікальний код гри"""
    return ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', k=6))


def load_prizes():
    """Завантажити призи для переможців з файлів категорій"""
    global all_prizes
    print("\nЗавантаження призів для переможців...")
    for category_key, details in QUESTION_CATEGORIES.items():
        prize_file = details.get('prize_file')
        if not prize_file:
            continue
        try:
            with open(prize_file, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                # Припускаємо, що колонка з призом називається 'prize'
                prizes = [row['prize'] for row in reader]
                all_prizes[category_key] = prizes
                print(f"✅ Завантажено {len(prizes)} призів для категорії '{details['name']}'")
        except FileNotFoundError:
            print(f"❌ Файл призів {prize_file} не знайдено!")
            all_prizes[category_key] = []
        except Exception as e:
            print(f"❌ Помилка завантаження призів з {prize_file}: {e}")
            all_prizes[category_key] = []


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start - головне меню"""
    keyboard = [
        [InlineKeyboardButton("🎮 Створити гру", callback_data='create_game')],
        [InlineKeyboardButton("🚪 Приєднатися до гри", callback_data='join_game')],
        [InlineKeyboardButton("ℹ️ Як грати?", callback_data='rules')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_text = (
        "🔥 *Intimate Questions Game* 🔥\n\n"
        "Гра для компаній, які хочуть краще пізнати один одного!\n\n"
        "🎯 *Як це працює:*\n"
        "• Один створює кімнату з кодом\n"
        "• Інші приєднуються за кодом\n"
        "• Бот задає питання всім одночасно\n"
        "• Після обговорення голосуєте один за одного\n"
        "• Переможець визначається за балами!\n\n"
        "Що бажаєш зробити?"
    )
    
    await update.message.reply_text(
        welcome_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def create_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показати меню вибору категорії для нової гри"""
    query = update.callback_query
    await query.answer()

    keyboard = []
    for key, details in QUESTION_CATEGORIES.items():
        keyboard.append([InlineKeyboardButton(details['name'], callback_data=f'create_cat_{key}')])
    
    keyboard.append([InlineKeyboardButton("🔙 Назад до меню", callback_data='back_to_menu')])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        "✨ *Вибір категорії гри*\n\n"
        "Будь ласка, оберіть категорію питань для вашої нової гри:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def create_game_with_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Створити нову гру з обраною категорією"""
    query = update.callback_query
    await query.answer()

    category_key = query.data.split('_')[-1]
    if category_key not in QUESTION_CATEGORIES:
        await query.edit_message_text("❌ Помилка: Невідома категорія.")
        return

    game_code = generate_game_code()
    user_id = query.from_user.id
    user_name = query.from_user.first_name or "Гравець"

    # Створити нову гру
    games[game_code] = {
        'code': game_code,
        'creator_id': user_id,
        'state': GameStates.WAITING_FOR_PLAYERS,
        'players': [{'id': user_id, 'name': user_name}],
        'scores': {user_id: 0},
        'category': category_key,
        'current_question': None,
        'used_questions': [],
        'votes': {},
        'round_number': 0
    }

    keyboard = [
        [InlineKeyboardButton("▶️ Почати гру", callback_data=f'start_game_{game_code}')],
        [InlineKeyboardButton("👥 Переглянути гравців", callback_data=f'show_players_{game_code}')],
        [InlineKeyboardButton("❌ Скасувати гру", callback_data=f'cancel_game_{game_code}')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    category_name = QUESTION_CATEGORIES[category_key]['name']
    
    # Формуємо текст повідомлення
    created_text = (
        f"🎮 *Гру створено!*\n\n"
        f"🔑 *Код кімнати:* `{game_code}`\n"
        f"📚 *Категорія:* {category_name}\n\n"
        f"👤 *Створив:* {user_name}\n"
        f"👥 *Гравців:* 1\n\n"
        f"📋 Поділіться цим кодом з друзями!\n"
        f"Мінімум потрібно 2 гравці для початку гри."
    )

    # Перевіряємо, чи є творець у списку особливих
    if user_id in SPECIAL_USER_IDS:
        special_message = "\n\n✨ *Бачу, головний на місці!* ✨\nГарної гри, бос!"
        created_text += special_message

    await query.edit_message_text(
        created_text,
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

    
async def join_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Приєднатися до гри"""
    query = update.callback_query
    await query.answer()
    
    # Додати кнопку скасування
    keyboard = [
        [InlineKeyboardButton("❌ Скасувати", callback_data='back_to_menu')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "🚪 *Приєднання до гри*\n\n"
        "Введіть код кімнати (6 символів):",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )
    
    # Зберегти стан очікування коду
    context.user_data['waiting_for_code'] = True

async def handle_join_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обробити введений код кімнати"""
    if not context.user_data.get('waiting_for_code'):
        return
    
    code = update.message.text.strip().upper()
    user_id = update.message.from_user.id
    user_name = update.message.from_user.first_name or "Гравець"
    
    # Перевірити чи існує гра
    if code not in games:
        keyboard = [
            [InlineKeyboardButton("🏠 Головне меню", callback_data='back_to_menu')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "❌ Гра з таким кодом не знайдена!\n"
            "Перевірте код і спробуйте ще раз.",
            reply_markup=reply_markup
        )
        context.user_data['waiting_for_code'] = False
        return
    
    game = games[code]
    
    # Перевірити чи користувач вже в грі
    if any(player['id'] == user_id for player in game['players']):
        keyboard = [
            [InlineKeyboardButton("👥 Переглянути гравців", callback_data=f'show_players_{code}')],
            [InlineKeyboardButton("🏠 Головне меню", callback_data='back_to_menu')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)


    # Перевіряємо, чи є гравець у списку особливих
    if user_id in SPECIAL_USER_IDS:
        special_message = "\n\n✨ *О, бачу тут свої люди!* ✨\nВдалої гри!"
        join_text += special_message



        
        await update.message.reply_text(
            f"⚠️ Ви вже приєдналися до гри {code}!",
            reply_markup=reply_markup
        )
        context.user_data['waiting_for_code'] = False
        return
    
    # Перевірити стан гри
    if game['state'] != GameStates.WAITING_FOR_PLAYERS:
        keyboard = [
            [InlineKeyboardButton("🏠 Головне меню", callback_data='back_to_menu')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "❌ Ця гра вже почалася або завершилася!",
            reply_markup=reply_markup
        )
        context.user_data['waiting_for_code'] = False
        return
    
    # Додати гравця
    game['players'].append({'id': user_id, 'name': user_name})
    game['scores'][user_id] = 0
    
    context.user_data['waiting_for_code'] = False
    
    keyboard = [
        [InlineKeyboardButton("👥 Переглянути гравців", callback_data=f'show_players_{code}')],
        [InlineKeyboardButton("🔄 Назад до меню", callback_data='back_to_menu')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"✅ *Успішно приєдналися до гри!*\n\n"
        f"🔑 *Код:* `{code}`\n"
        f"👥 *Гравців:* {len(game['players'])}\n\n"
        f"Очікуйте поки створювач почне гру.",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def show_players(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показати список гравців"""
    query = update.callback_query
    await query.answer()
    
    game_code = query.data.split('_')[-1]
    
    if game_code not in games:
        await query.edit_message_text("❌ Гра не знайдена!")
        return
    
    game = games[game_code]
    players_list = "\n".join([f"• {player['name']}" for player in game['players']])
    
    keyboard = []
    if game['state'] == GameStates.WAITING_FOR_PLAYERS:
        if query.from_user.id == game['creator_id'] and len(game['players']) >= 2:
            keyboard.append([InlineKeyboardButton("▶️ Почати гру", callback_data=f'start_game_{game_code}')])
        keyboard.append([InlineKeyboardButton("🔄 Оновити", callback_data=f'show_players_{game_code}')])
    
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data='back_to_menu')])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"👥 *Гравці в кімнаті {game_code}:*\n\n"
        f"{players_list}\n\n"
        f"📊 *Всього гравців:* {len(game['players'])}",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def start_game_round(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Почати гру або новий раунд"""
    query = update.callback_query
    await query.answer()
    
    game_code = query.data.split('_')[-1]
    
    if game_code not in games:
        await query.edit_message_text("❌ Гра не знайдена!")
        return
    
    game = games[game_code]
    
    # Перевірити права
    if query.from_user.id != game['creator_id']:
        await query.answer("❌ Тільки створювач може керувати грою!", show_alert=True)
        return
    
    # Перевірити кількість гравців
    if len(game['players']) < 2:
        await query.answer("❌ Потрібно мінімум 2 гравці!", show_alert=True)
        return
    
    # Отримати нове питання з правильної категорії
    category_key = game['category']
    question_pool = all_questions.get(category_key, [])
    
    available_questions = [q for q in question_pool if q['id'] not in game['used_questions']]
    
    if not available_questions:
        # Якщо питання в цій категорії закінчилися
        await finish_game(update, context, game_code)
        return
    
    current_question = random.choice(available_questions)
    game['used_questions'].append(current_question['id'])
    game['current_question'] = current_question
    game['state'] = GameStates.IN_PROGRESS
    game['round_number'] += 1
    game['votes'] = {}
    
    # Надіслати питання всім гравцям
    question_text = (
        f"🎯 *Раунд {game['round_number']}*\n\n"
        f"📝 *Питання:*\n{current_question['question']}\n\n"
        f"💡 *Підказки для обговорення:*\n{current_question['guidance']}\n\n"
        f"⏰ Обговоріть питання та натисніть 'Готовий голосувати' коли закінчите!"
    )
    
    keyboard = [
        [InlineKeyboardButton("✅ Готовий голосувати", callback_data=f'ready_vote_{game_code}')],
        [InlineKeyboardButton("⏭️ Пропустити питання", callback_data=f'skip_question_{game_code}')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Надіслати всім гравцям
    for player in game['players']:
        try:
            await context.bot.send_message(
                chat_id=player['id'],
                text=question_text,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
        except Exception as e:
            print(f"Не вдалося надіслати повідомлення гравцю {player['name']}: {e}")

async def ready_to_vote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Гравець готовий голосувати"""
    query = update.callback_query
    await query.answer()
    
    game_code = query.data.split('_')[-1]
    user_id = query.from_user.id
    
    if game_code not in games:
        await query.edit_message_text("❌ Гра не знайдена!")
        return
    
    game = games[game_code]
    
    if game['state'] != GameStates.IN_PROGRESS:
        await query.answer("❌ Зараз не час для голосування!", show_alert=True)
        return
    
    # Перевірити чи гравець в грі
    if not any(player['id'] == user_id for player in game['players']):
        await query.answer("❌ Ви не в цій грі!", show_alert=True)
        return
    
    # Показати варіанти голосування (всі гравці крім себе)
    keyboard = []
    for player in game['players']:
        if player['id'] != user_id:  # Не можна голосувати за себе
            keyboard.append([InlineKeyboardButton(
                f"🗳️ {player['name']}", 
                callback_data=f'vote_{game_code}_{player["id"]}'
            )])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"🗳️ *Голосування*\n\n"
        f"Виберіть гравця, якому хочете віддати свій бал за цей раунд:\n\n"
        f"💡 *Пам'ятайте:* Не можна голосувати за себе!",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def vote_for_player(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Проголосувати за гравця"""
    query = update.callback_query
    await query.answer()
    
    data_parts = query.data.split('_')
    game_code = data_parts[1]
    voted_for_id = int(data_parts[2])
    voter_id = query.from_user.id
    
    if game_code not in games:
        await query.edit_message_text("❌ Гра не знайдена!")
        return
    
    game = games[game_code]
    
    # Записати голос
    game['votes'][voter_id] = voted_for_id
    
    # Знайти ім'я гравця за якого проголосували
    voted_player_name = next(
        (player['name'] for player in game['players'] if player['id'] == voted_for_id),
        "Невідомий гравець"
    )
    
    await query.edit_message_text(
        f"✅ *Ваш голос зараховано!*\n\n"
        f"Ви проголосували за: *{voted_player_name}*\n\n"
        f"Очікуйте поки всі гравці проголосують..."
    )
    
    # Перевірити чи всі проголосували
    if len(game['votes']) == len(game['players']):
        await process_round_results(context, game_code)

async def process_round_results(context: ContextTypes.DEFAULT_TYPE, game_code: str):
    """Обробити результати раунду"""
    game = games[game_code]
    
    # Підрахувати бали
    round_scores = {}
    for player in game['players']:
        round_scores[player['id']] = 0
    
    for voter_id, voted_for_id in game['votes'].items():
        if voted_for_id in round_scores:
            round_scores[voted_for_id] += 1
    
    # Додати до загальної суми
    for player_id, points in round_scores.items():
        game['scores'][player_id] += points
    
    # Повідомлення про завершення раунду (БЕЗ результатів)
    completion_text = f"✅ *Раунд {game['round_number']} завершено!*\n\n"
    completion_text += f"Всі гравці проголосували. Готові до наступного питання?"
    
    # Кнопки для продовження
    keyboard = [
        [InlineKeyboardButton("▶️ Наступне питання", callback_data=f'start_game_{game_code}')],
        [InlineKeyboardButton("🏁 Завершити гру", callback_data=f'finish_game_{game_code}')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Надіслати повідомлення про завершення всім гравцям
    for player in game['players']:
        try:
            await context.bot.send_message(
                chat_id=player['id'],
                text=completion_text,
                parse_mode='Markdown',
                reply_markup=reply_markup if player['id'] == game['creator_id'] else None
            )
        except Exception as e:
            print(f"Не вдалося надіслати повідомлення гравцю {player['id']}: {e}")

async def skip_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Пропустити поточне питання"""
    query = update.callback_query
    await query.answer()
    
    game_code = query.data.split('_')[-1]
    
    if game_code not in games:
        await query.edit_message_text("❌ Гра не знайдена!")
        return
    
    game = games[game_code]
    
    # Тільки створювач може пропускати
    if query.from_user.id != game['creator_id']:
        await query.answer("❌ Тільки створювач може пропускати питання!", show_alert=True)
        return
    
    # Почати новий раунд
    await start_game_round(update, context)

async def finish_game(update: Update, context: ContextTypes.DEFAULT_TYPE, game_code: str = None):
    """Завершити гру та показати результати з призом для переможця"""
    if not game_code:
        query = update.callback_query
        await query.answer()
        game_code = query.data.split('_')[-1]
    
    if game_code not in games:
        if hasattr(update, 'callback_query'):
            await update.callback_query.edit_message_text("❌ Гра не знайдена!")
        return
    
    game = games[game_code]
    game['state'] = GameStates.FINISHED
    
    # Підрахувати фінальні результати
    final_results = sorted(game['scores'].items(), key=lambda x: x[1], reverse=True)
    
    results_text = f"🎉 *ФІНАЛЬНІ РЕЗУЛЬТАТИ ГРИ {game_code}*\n\n"
    winner_name = "Ніхто"
    
    if final_results:
        winner_id = final_results[0][0]
        winner_name = next((player['name'] for player in game['players'] if player['id'] == winner_id), "Невідомий")

    for i, (player_id, score) in enumerate(final_results):
        player_name = next(player['name'] for player in game['players'] if player['id'] == player_id)
        medal = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else "🏅"
        results_text += f"{medal} {i+1}. {player_name}: {score} балів\n"
    
    results_text += f"\n🎯 Всього було {game['round_number']} раундів."

    # --- Логіка додавання призу ---
    category_key = game.get('category')
    prizes_for_category = all_prizes.get(category_key, [])
    
    if prizes_for_category:
        random_prize = random.choice(prizes_for_category)
        prize_text = (
            f"\n\n🏆 *Приз для переможця, {winner_name}!* 🏆\n\n"
            f"_{random_prize}_"
        )
        results_text += prize_text
    # --- Кінець логіки призу ---

    results_text += f"\n\n🎮 Дякуємо за гру!"
    
    keyboard = [
        [InlineKeyboardButton("🔄 Нова гра", callback_data='create_game')],
        [InlineKeyboardButton("🏠 Головне меню", callback_data='back_to_menu')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Надіслати фінальні результати всім
    for player in game['players']:
        try:
            await context.bot.send_message(
                chat_id=player['id'],
                text=results_text,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
        except Exception as e:
            print(f"Не вдалося надіслати фінальні результати гравцю {player['id']}: {e}")
    
    # Видалити гру з пам'яті
    if game_code in games:
        del games[game_code]

async def show_rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показати правила гри"""
    query = update.callback_query
    await query.answer()
    
    rules_text = (
        "📖 *ПРАВИЛА ГРИ*\n\n"
        "🎯 *Мета:* Отримати найбільше балів за рахунок цікавих відповідей\n\n"
        "🎮 *Як грати:*\n"
        "1. Створіть кімнату, обравши категорію, або приєднайтесь за кодом\n"
        "2. Потрібно мінімум 2 гравці\n"
        "3. Бот надсилає питання всім одночасно\n"
        "4. Обговорюйте відповіді разом\n"
        "5. Потім кожен голосує за найкращу відповідь\n"
        "6. Не можна голосувати за себе!\n"
        "7. Гравець з найбільшою кількістю балів перемагає\n\n"
        "💡 *Поради:*\n"
        "• Будьте відвертими та щирими\n"
        "• Слухайте один одного\n"
        "• Не соромтеся ділитися думками\n"
        "• Пам'ятайте: це гра для дорослих!"
    )
    
    keyboard = [
        [InlineKeyboardButton("🔙 Назад до меню", callback_data='back_to_menu')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        rules_text,
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def back_to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Повернутися до головного меню"""
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("🎮 Створити гру", callback_data='create_game')],
        [InlineKeyboardButton("🚪 Приєднатися до гри", callback_data='join_game')],
        [InlineKeyboardButton("ℹ️ Як грати?", callback_data='rules')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "🔥 *Intimate Questions Game* 🔥\n\n"
        "Що бажаєте зробити?",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def cancel_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Скасувати гру"""
    query = update.callback_query
    await query.answer()
    
    game_code = query.data.split('_')[-1]
    
    if game_code in games:
        game = games[game_code]
        if query.from_user.id == game['creator_id']:
            del games[game_code]
            
            # Додати кнопку повернення до меню
            keyboard = [
                [InlineKeyboardButton("🏠 Головне меню", callback_data='back_to_menu')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                f"❌ Гру {game_code} скасовано!",
                reply_markup=reply_markup
            )
        else:
            await query.answer("❌ Тільки створювач може скасувати гру!", show_alert=True)
    else:
        # Додати кнопку повернення до меню навіть якщо гра не знайдена
        keyboard = [
            [InlineKeyboardButton("🏠 Головне меню", callback_data='back_to_menu')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "❌ Гра не знайдена!",
            reply_markup=reply_markup
        )

def main():
    """Головна функція запуску бота"""
    # Завантажити питання
    load_questions()
    load_prizes()
    
    # Отримати токен з environment
    token = os.getenv('BOT_TOKEN')
    if not token:
        print("❌ BOT_TOKEN не знайдено в .env файлі")
        return
    
    # Створити додаток
    application = Application.builder().token(token).build()
    
    # Додати обробники команд
    application.add_handler(CommandHandler("start", start))
    
    # Додати обробники callback_query
    application.add_handler(CallbackQueryHandler(create_game, pattern='create_game'))
    application.add_handler(CallbackQueryHandler(create_game_with_category, pattern=r'create_cat_\w+'))
    application.add_handler(CallbackQueryHandler(join_game, pattern='join_game'))
    application.add_handler(CallbackQueryHandler(show_players, pattern=r'show_players_\w+'))
    application.add_handler(CallbackQueryHandler(start_game_round, pattern=r'start_game_\w+'))
    application.add_handler(CallbackQueryHandler(ready_to_vote, pattern=r'ready_vote_\w+'))
    application.add_handler(CallbackQueryHandler(vote_for_player, pattern=r'vote_\w+_\d+'))
    application.add_handler(CallbackQueryHandler(skip_question, pattern=r'skip_question_\w+'))
    application.add_handler(CallbackQueryHandler(finish_game, pattern=r'finish_game_\w+'))
    application.add_handler(CallbackQueryHandler(show_rules, pattern='rules'))
    application.add_handler(CallbackQueryHandler(back_to_menu, pattern='back_to_menu'))
    application.add_handler(CallbackQueryHandler(cancel_game, pattern=r'cancel_game_\w+'))
    
    # Додати обробник текстових повідомлень для кодів кімнат
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_join_code))
    
    print("🚀 Бот запущено!")
    # print(f"📊 Завантажено {len(questions)} питань")
    print("💬 Надішліть /start боту для початку гри")
    
    # Запустити бота
    application.run_polling()

if __name__ == '__main__':
    main()
