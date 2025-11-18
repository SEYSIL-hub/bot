import telebot
from telebot import types
import json
import os
import traceback 
from flask import Flask, request # Импортируем Flask и request (для хостингов типа PythonAnywhere)

# --- КОНФИГУРАЦИЯ ---

# Используем токен напрямую (для хостингов, где нет env vars, например PythonAnywhere)
# !!! Вставьте ВАШ актуальный токен сюда, если он изменился !!!
API_TOKEN = '8430418918:AAFljWxONqcsSnisTi1N7hjpr0afjxYg2Mc' 
print("INFO: Using hardcoded API Token.")

bot = telebot.TeleBot(API_TOKEN)
ADMIN_IDS = [] # Пустой список администраторов

DB_FILE = 'chapters_db.json'

# --- ФУНКЦИИ РАБОТЫ С "БАЗОЙ ДАННЫХ" ---

def load_chapters_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    else:
        print(f"INFO: {DB_FILE} not found, initializing default DB.")
        return {
            'chapter1': {"title": "Глава 1: Начало", "text": "Текст Главы 1."},
            'chapter2': {"title": "Глава 2: Продолжение", "text": "Текст Главы 2."},
            'chapter3': {"title": "Глава 3: Финал", "text": "Текст Главы 3."}
        }

def save_chapters_db(db):
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(db, f, ensure_ascii=False, indent=4)

chapters_db = load_chapters_db()

# --- СОСТОЯНИЯ ПОЛЬЗОВАТЕЛЕЙ (Расширенный FSM) ---

class AdminState:
    WAITING_FOR_NEW_TEXT = 1
    WAITING_FOR_NEW_TITLE = 2
    WAITING_FOR_NEW_CHAPTER_ID = 3

user_states = {}

def set_user_state(user_id, state, data=None):
    user_states[user_id] = {"state": state, "data": data}

def get_user_state(user_id):
    return user_states.get(user_id, {"state": None, "data": None})

def clear_user_state(user_id):
    if user_id in user_states:
        del user_states[user_id]

# --- УТИЛИТЫ ---
def is_admin(user_id):
    return user_id in ADMIN_IDS

# --- КЛАВИАТУРЫ (ПЕРЕМЕЩЕНЫ ВЫШЕ, ЧТОБЫ ИЗБЕЖАТЬ NameError) ---

def get_main_menu_keyboard() -> types.InlineKeyboardMarkup:
    markup = types.InlineKeyboardMarkup()
    for chapter_id, data in chapters_db.items():
        markup.add(types.InlineKeyboardButton(data["title"], callback_data=f"view_{chapter_id}"))
    return markup

def get_chapter_keyboard(chapter_id: str, user_id: int) -> types.InlineKeyboardMarkup:
    markup = types.InlineKeyboardMarkup()
    if is_admin(user_id):
        markup.add(types.InlineKeyboardButton("✍️ Изменить текст", callback_data=f"edit_text_{chapter_id}"))
        markup.add(types.InlineKeyboardButton("✏️ Изменить название", callback_data=f"edit_title_{chapter_id}"))
    markup.add(types.InlineKeyboardButton("◀️ Назад в меню", callback_data="main_menu"))
    return markup

def get_admin_keyboard() -> types.InlineKeyboardMarkup:
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("➕ Добавить новую главу", callback_data="admin_add_chapter"))
    markup.add(types.InlineKeyboardButton("➖ Удалить главу", callback_data=f"admin_delete_chapter_select"))
    markup.add(types.InlineKeyboardButton("📊 Посмотреть все (Debug)", callback_data="admin_view_all_chapters"))
    markup.add(types.InlineKeyboardButton("◀️ Вернуться в основное меню", callback_data="main_menu"))
    return markup

def get_cancel_keyboard() -> types.InlineKeyboardMarkup:
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("❌ Отмена", callback_data="cancel_action"))
    return markup


# --- ОБРАБОТЧИКИ КОМАНД И НАВИГАЦИИ (Теперь могут вызывать функции клавиатур без ошибок) ---

@bot.message_handler(commands=['start'])
def send_welcome(message: types.Message):
    print(f"INFO: Получена команда /start от пользователя {message.chat.id}")
    # Функция get_main_menu_keyboard() теперь определена выше
    bot.send_message(message.chat.id, "Привет! Используйте меню ниже для навигации по главам.", reply_markup=get_main_menu_keyboard())
    print("INFO: Сообщение с меню отправлено.")

@bot.message_handler(commands=['admin'])
def admin_panel_command(message: types.Message):
    if is_admin(message.chat.id):
        bot.send_message(message.chat.id, "🔐 *Админ-панель:* Выберите действие.", reply_markup=get_admin_keyboard(), parse_mode="Markdown")
    else:
        bot.send_message(message.chat.id, "Извините, у вас нет доступа к этой команде.")

@bot.callback_query_handler(func=lambda call: call.data == "main_menu")
def show_main_menu(call: types.CallbackQuery):
    bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text="Используйте меню ниже для навигации по главам.", reply_markup=get_main_menu_keyboard())
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data.startswith("view_"))
def view_chapter(call: types.CallbackQuery):
    chapter_id = call.data.replace("view_", "")
    data = chapters_db.get(chapter_id)
    if data:
        text = f"*{data['title']}*:\n\n{data['text']}"
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=text, reply_markup=get_chapter_keyboard(chapter_id, call.message.chat.id), parse_mode="Markdown")
    else:
        bot.send_message(call.message.chat.id, "Глава не найдена.")
    bot.answer_callback_query(call.id)

# ... (остальные обработчики callback_query и message_handler) ...

@bot.message_handler(func=lambda message: True)
def echo_all(message):
    bot.send_message(message.chat.id, "Я не понимаю эту команду. Пожалуйста, используйте /start или кнопки меню.")


# --- ОБРАБОТЧИК ДЛЯ PYTHONANYWHERE (WEBHOOK) ИЛИ LONG POLLING ---

# Если вы используете PythonAnywhere/Яндекс, нужен этот блок:
application = Flask(__name__)

@application.route('/', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return 'ok', 200
    else:
        return 'wrong request', 400

# Если вы используете мобильное приложение/Amvera, удалите блок выше и используйте этот:
# if __name__ == "__main__":
#     print("Bot is starting via Long Polling...")
#     try:
#         bot.infinity_polling(timeout=10)
#     except Exception as e:
#         print(f"An error occurred during polling: {e}")
#         traceback.print_exc()
