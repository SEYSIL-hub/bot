import telebot
import json
import logging
from telebot import types
import os

# --- КОНСТАНТЫ С ВАШИМИ ДАННЫМИ ---
# Убедитесь, что переменная окружения TG_TOKEN установлена в вашей системе
API_TOKEN = os.environ.get('TG_TOKEN') 
ADMIN_IDS = [995375387, 1081253267]
# ----------------------------------

DATA_FILE = 'chapters.json'
CONFIG_FILE = 'config.json'

logging.basicConfig(level=logging.INFO)

# Инициализация бота
bot = telebot.TeleBot(API_TOKEN)
user_states = {}

# --- Функции для работы с данными (JSON) ---

def load_chapters():
    """Загружает главы из JSON файла (простая структура словаря)."""
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump({}, f, ensure_ascii=False)
        return {}
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {}

def save_chapters(chapters):
    """Сохраняет главы в JSON файл."""
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(chapters, f, ensure_ascii=False, indent=4)

def load_config():
    """Загружает конфигурацию (приветствие) из JSON файла."""
    if not os.path.exists(CONFIG_FILE):
        config_data = {"welcome_message": "👋 Привет! Это ваш бот для чтения глав."}
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, ensure_ascii=False, indent=4)
        return config_data
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {"welcome_message": "👋 Привет! Это ваш бот для чтения глав."}

def save_config(config):
    """Сохраняет конфигурацию в JSON файл."""
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=4)

# --- Вспомогательные функции для состояний ---

def set_state(chat_id, state_name, data=None):
    user_states[chat_id] = {"state": state_name, "data": data or {}}

def get_state(chat_id):
    return user_states.get(chat_id, {}).get("state")

def get_state_data(chat_id):
    return user_states.get(chat_id, {}).get("data", {})

def clear_state(chat_id):
    if chat_id in user_states:
        del user_states[chat_id]

# --- Функция для отправки длинных сообщений (работает при чтении) ---

def send_long_message(chat_id, text, parse_mode=None):
    """Автоматически разбивает и отправляет текст частями."""
    if len(text) <= 4096:
        bot.send_message(chat_id, text, parse_mode=parse_mode)
    else:
        # ИСПРАВЛЕННАЯ СТРОКА 1
        chunks = [text[i:i + 4000] for i in range(0, len(text), 4000)]
        for chunk in chunks:
            bot.send_message(chat_id, chunk, parse_mode=parse_mode)

# --- Клавиатуры ---

def get_main_menu_keyboard(user_id):
    chapters = load_chapters()
    markup = types.InlineKeyboardMarkup()
    
    sorted_chapter_ids = sorted(chapters.keys(), key=int)

    for chap_id in sorted_chapter_ids:
        button_text = f"📖 {chapters[chap_id]['title']}"
        markup.add(types.InlineKeyboardButton(text=button_text, callback_data=f"read_{chap_id}"))

    if user_id in ADMIN_IDS:
        markup.add(types.InlineKeyboardButton(text="🔑 Админ-панель", callback_data="open_admin_panel"))

    return markup

def get_admin_menu_keyboard():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(text="✏️ Изменить приветствие", callback_data="admin_edit_welcome"))
    markup.add(types.InlineKeyboardButton(text="➕ Добавить главу", callback_data="admin_add"))
    markup.add(types.InlineKeyboardButton(text="✏️ Изменить название главы", callback_data="admin_edit_title"))
    markup.add(types.InlineKeyboardButton(text="📝 Изменить содержание", callback_data="admin_edit_content"))
    markup.add(types.InlineKeyboardButton(text="❌ Удалить главу", callback_data="admin_delete"))
    markup.add(types.InlineKeyboardButton(text="⬅️ Назад в меню глав", callback_data="user_menu"))
    return markup

def get_cancel_keyboard():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(text="🚫 Отмена", callback_data="cancel"))
    return markup

def get_cancel_reply_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add("🚫 Отмена")
    return markup

def get_welcome_keyboard():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(text="📖 Перейти к главам", callback_data="user_menu"))
    return markup

def get_read_chapter_keyboard(chapter_id):
    chapters = load_chapters()
    likes = chapters[chapter_id].get('likes', 0)
    dislikes = chapters[chapter_id].get('dislikes', 0)

    markup = types.InlineKeyboardMarkup(row_width=2)
    like_btn = types.InlineKeyboardButton(text=f"👍 Понравилось ({likes})", callback_data=f"rate_like_{chapter_id}")
    dislike_btn = types.InlineKeyboardButton(text=f"👎 Не понравилось ({dislikes})", callback_data=f"rate_dislike_{chapter_id}")
    back_btn = types.InlineKeyboardButton(text="◀️ Назад к меню", callback_data="user_menu")
    
    markup.add(like_btn, dislike_btn)
    markup.add(back_btn)
    return markup

# Дополнительный обработчик отмены для ReplyKeyboard
def cancel_handler_callback_message(message):
    clear_state(message.chat.id)
    bot.send_message(message.chat.id, "Возврат в админ-панель:", reply_markup=get_admin_menu_keyboard())


# --- Основные обработчики команд и сообщений ---

def send_welcome_message(chat_id, user_id):
    clear_state(chat_id)
    config = load_config()
    welcome_text = config.get("welcome_message", "Привет!")
    bot.send_message(
        chat_id,
        welcome_text,
        reply_markup=get_welcome_keyboard()
    )

@bot.message_handler(commands=['start'])
def send_welcome(message):
    send_welcome_message(message.chat.id, message.from_user.id)

@bot.callback_query_handler(func=lambda call: call.data == "open_admin_panel")
def open_admin_panel_callback(call):
    bot.answer_callback_query(call.id)
    if call.from_user.id in ADMIN_IDS:
        bot.edit_message_text("🔑 Добро пожаловать в админ-панель. Выберите действие:", call.message.chat.id, call.message.message_id, reply_markup=get_admin_menu_keyboard())

@bot.callback_query_handler(func=lambda call: call.data == "user_menu")
def back_to_user_menu_callback(call):
    bot.answer_callback_query(call.id)
    clear_state(call.message.chat.id)
    bot.edit_message_text("Выберите главу из меню:", call.message.chat.id, call.message.message_id, reply_markup=get_main_menu_keyboard(call.from_user.id))

@bot.callback_query_handler(func=lambda call: call.data.startswith("read_"))
def read_chapter_callback(call):
    bot.answer_callback_query(call.id, text="Загрузка главы...")

    chapter_id = call.data.replace("read_", "")
    chapters = load_chapters()
    if chapter_id in chapters:
        chapter = chapters[chapter_id]
        
        send_long_message(call.message.chat.id, f"**{chapter['title']}**\n\n{chapter['content']}", parse_mode="Markdown")
        
        bot.send_message(call.message.chat.id, "--- Конец главы ---", reply_markup=get_read_chapter_keyboard(chapter_id))
        bot.delete_message(call.message.chat.id, call.message.message_id)
    else:
        bot.answer_callback_query(call.id, "Глава не найдена. 😕", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data == "cancel")
def cancel_handler_callback(call):
    bot.answer_callback_query(call.id)

    clear_state(call.message.chat.id)
    bot.send_message(call.message.chat.id, "↩️ Действие отменено.", reply_markup=types.ReplyKeyboardRemove())
    bot.send_message(call.message.chat.id, "Выберите следующее действие в админ-панели:", reply_markup=get_admin_menu_keyboard())


# --- ОБРАБОТЧИКИ FSM (Админ-панель) ---

# Редактирование приветственного сообщения - ШАГ 1
@bot.callback_query_handler(func=lambda call: call.data == "admin_edit_welcome")
def admin_edit_welcome_start(call):
    bot.answer_callback_query(call.id)
    
    if call.from_user.id not in ADMIN_IDS: return
    config = load_config()
    current_welcome = config.get("welcome_message", "")
    bot.edit_message_text(f"✏️ Введите новое приветственное сообщение (Текущее: \n\n{current_welcome}):", call.message.chat.id, call.message.message_id, reply_markup=get_cancel_keyboard())
    set_state(call.message.chat.id, "WAITING_FOR_NEW_WELCOME_MESSAGE")


# Редактирование приветственного сообщения - ШАГ 2
@bot.message_handler(func=lambda message: get_state(message.chat.id) == "WAITING_FOR_NEW_WELCOME_MESSAGE")
def handle_new_welcome_message(message):
    chat_id = message.chat.id
    if message.text == "🚫 Отмена": return cancel_handler_callback_message(message)
    
    new_welcome_message = message.text
    config = load_config()
    config["welcome_message"] = new_welcome_message
    save_config(config)

    clear_state(chat_id)
    bot.send_message(chat_id, f"✅ Приветственное сообщение успешно обновлено.", reply_markup=types.ReplyKeyboardRemove())
    bot.send_message(chat_id, "Выберите следующее действие в админ-панели:", reply_markup=get_admin_menu_keyboard())


# 1. Добавление новой главы - ШАГ 1 (ID)
@bot.callback_query_handler(func=lambda call: call.data == "admin_add")
def admin_add_chapter_start_callback(call):
    bot.answer_callback_query(call.id)

    if call.from_user.id not in ADMIN_IDS: return
    bot.edit_message_text("🔢 Введите ID новой главы (например, '3'):", call.message.chat.id, call.message.message_id, reply_markup=get_cancel_keyboard())
    set_state(call.message.chat.id, "WAITING_FOR_CHAPTER_ID_FOR_ADD")


# 1. Добавление новой главы - ШАГ 2 (Title)
@bot.message_handler(func=lambda message: get_state(message.chat.id) == "WAITING_FOR_CHAPTER_ID_FOR_ADD")
def handle_add_chapter_id_input(message):
    chat_id = message.chat.id
    if message.text == "🚫 Отмена": return cancel_handler_callback_message(message)
    chapter_id = message.text.strip()
    
    if not chapter_id.isdigit():
        bot.send_message(chat_id, "ID должен быть числом 🔢. Попробуйте снова.", reply_markup=get_cancel_reply_keyboard())
        return
    chapters = load_chapters()
    if chapter_id in chapters:
         bot.send_message(chat_id, "Такой ID уже существует. Выберите другой или нажмите Отмена.", reply_markup=get_cancel_reply_keyboard())
         return

    set_state(chat_id, "WAITING_FOR_TITLE_FOR_ADD", data={'current_chapter_id': chapter_id})
    bot.send_message(chat_id, f"ID {chapter_id} принят. Теперь введите **название** ✏️ новой главы:", parse_mode="Markdown", reply_markup=get_cancel_reply_keyboard())

# 1. Добавление новой главы - ШАГ 3 (Content - Ожидание файла/текста)
@bot.message_handler(func=lambda message: get_state(message.chat.id) == "WAITING_FOR_TITLE_FOR_ADD")
def handle_add_title_input(message):
    chat_id = message.chat.id
    if message.text == "🚫 Отмена": return cancel_handler_callback_message(message)
    title = message.text
    data = get_state_data(chat_id)
    data['new_title'] = title
    set_state(chat_id, "WAITING_FOR_CONTENT_FILE_FOR_ADD", data=data) 
    bot.send_message(chat_id, f"Название принято ✅. Теперь **отправьте содержание как текстовый файл (.txt)** 📝, или введите текст (текст может быть очень длинным). При использовании файла, убедитесь, что его размер не превышает лимиты Telegram (обычно до 20 МБ).", parse_mode="Markdown", reply_markup=get_cancel_reply_keyboard())


# 1. Добавление новой главы - ШАГ 4 (Сохранение файла/текста)
# ИСПРАВЛЕННАЯ СТРОКА 2
@bot.message_handler(content_types=['text', 'document'], func=lambda message: get_state(message.chat.id) == "WAITING_FOR_CONTENT_FILE_FOR_ADD")
def handle_add_content_input(message):
    chat_id = message.chat.id
    if message.content_type == 'text' and message.text == "🚫 Отмена":
        bot.send_message(chat_id, "Отмена.", reply_markup=types.ReplyKeyboardRemove())
        return cancel_handler_callback_message(message)
    
    content = ""
    if message.content_type == 'text':
        content = message.text
    elif message.content_type == 'document':
        if not message.document.file_name.endswith('.txt'):
             bot.send_message(chat_id, "Пожалуйста, отправьте файл в формате .txt или введите текст.", reply_markup=get_cancel_reply_keyboard())
             return
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        try:
            content = downloaded_file.decode('utf-8')
        except UnicodeDecodeError:
            bot.send_message(chat_id, "Не удалось прочитать файл в формате UTF-8. Попробуйте другой файл.", reply_markup=get_cancel_reply_keyboard())
            return

    if not content:
        bot.send_message(chat_id, "Не удалось получить текст. Попробуйте еще раз.", reply_markup=get_cancel_reply_keyboard())
        return

    user_data = get_state_data(chat_id)
    chapter_id = user_data['current_chapter_id']
    title = user_data['new_title']
    chapters = load_chapters()
    # Добавляем начальные значения для лайков и дизлайков
    chapters[chapter_id] = {"title": title, "content": content, "likes": 0, "dislikes": 0, "rated_by": []}
    save_chapters(chapters)

    bot.send_message(chat_id, f"🎉 Глава {chapter_id} ('{title}') успешно **добавлена**!", reply_markup=types.ReplyKeyboardRemove())
    clear_state(chat_id)
    bot.send_message(chat_id, "Выберите следующее действие в админ-панели 👇:", reply_markup=get_admin_menu_keyboard())

# 2. Изменение ТОЛЬКО названия главы
@bot.callback_query_handler(func=lambda call: call.data == "admin_edit_title")
def admin_edit_title_start_callback(call):
    bot.answer_callback_query(call.id)

    if call.from_user.id not in ADMIN_IDS: return
    chapters = load_chapters()
    markup = types.InlineKeyboardMarkup()
    if not chapters:
        bot.answer_callback_query(call.id, "Нет доступных глав для редактирования.", show_alert=True)
        return
    for chap_id, chap_data in chapters.items():
        markup.add(types.InlineKeyboardButton(text=f"ID {chap_id}: {chap_data['title']}", callback_data=f"select_edit_title_{chap_id}"))
    markup.add(types.InlineKeyboardButton(text="🚫 Отмена", callback_data="cancel"))
    bot.edit_message_text("✏️ Выберите главу, название которой хотите изменить:", call.message.chat.id, call.message.message_id, reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith("select_edit_title_"))
def handle_select_chapter_for_title_edit(call):
    bot.answer_callback_query(call.id)

    chat_id = call.message.chat.id
    chapter_id = call.data.replace("select_edit_title_", "")
    chapters = load_chapters()
    if chapter_id in chapters:
        set_state(chat_id, "WAITING_FOR_NEW_TITLE_EDIT", data={'current_chapter_id': chapter_id})
        bot.send_message(chat_id, f"Глава найдена. Введите новое название для главы ID {chapter_id}:", reply_markup=get_cancel_reply_keyboard())
        bot.delete_message(chat_id, call.message.message_id)
    else:
        bot.answer_callback_query(call.id, "Глава не найдена.", show_alert=True)


@bot.message_handler(func=lambda message: get_state(message.chat.id) == "WAITING_FOR_NEW_TITLE_EDIT")
def handle_new_title_input(message):
    if message.text == "🚫 Отмена": return cancel_handler_callback_message(message)
    chat_id = message.chat.id
    new_title = message.text
    user_data = get_state_data(chat_id)
    chapter_id = user_data['current_chapter_id']
    chapters = load_chapters()
    chapters[chapter_id]['title'] = new_title
    save_chapters(chapters)
    bot.send_message(chat_id, f"✅ Название главы ID {chapter_id} успешно обновлено на '{new_title}'.", reply_markup=types.ReplyKeyboardRemove())
    clear_state(chat_id)
    bot.send_message(chat_id, "Выберите следующее действие в админ-панели:", reply_markup=get_admin_menu_keyboard())

# 3. Изменение ТОЛЬКО содержания главы - ***ЖДЕМ ФАЙЛ/ТЕКСТ***
@bot.callback_query_handler(func=lambda call: call.data == "admin_edit_content")
def admin_edit_content_start_callback(call):
    bot.answer_callback_query(call.id)

    if call.from_user.id not in ADMIN_IDS: return
    chapters = load_chapters()
    markup = types.InlineKeyboardMarkup()
    if not chapters:
        bot.answer_callback_query(call.id, "Нет доступных глав для редактирования.", show_alert=True)
        return
    for chap_id, chap_data in chapters.items():
        markup.add(types.InlineKeyboardButton(text=f"ID {chap_id}: {chap_data['title']}", callback_data=f"select_edit_content_{chap_id}"))
    markup.add(types.InlineKeyboardButton(text="🚫 Отмена", callback_data="cancel"))
    bot.edit_message_text("📝 Выберите главу, содержание которой хотите изменить:", call.message.chat.id, call.message.message_id, reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith("select_edit_content_"))
def handle_edit_content_id_input(call):
    bot.answer_callback_query(call.id)

    chat_id = call.message.chat.id
    chapter_id = call.data.replace("select_edit_content_", "")
    chapters = load_chapters()
    if chapter_id in chapters:
        set_state(chat_id, "WAITING_FOR_NEW_CONTENT_FILE_EDIT", data={'current_chapter_id': chapter_id}) 
        bot.send_message(chat_id, f"Глава найдена. Отправьте новое содержание для главы ID {chapter_id} **текстовым файлом (.txt)**, или введите текст (можно длинный):", reply_markup=get_cancel_reply_keyboard())
        bot.delete_message(chat_id, call.message.message_id)
    else:
        bot.answer_callback_query(call.id, "Глава не найдена.", show_alert=True)

# ИСПРАВЛЕННАЯ СТРОКА 3
@bot.message_handler(content_types=['text', 'document'], func=lambda message: get_state(message.chat.id) == "WAITING_FOR_NEW_CONTENT_FILE_EDIT")
def handle_new_content_input_edit(message):
    chat_id = message.chat.id
    if message.content_type == 'text' and message.text == "🚫 Отмена": 
        bot.send_message(chat_id, "Отмена.", reply_markup=types.ReplyKeyboardRemove())
        return cancel_handler_callback_message(message)
    
    content = ""
    if message.content_type == 'text':
        content = message.text
    elif message.content_type == 'document':
        if not message.document.file_name.endswith('.txt'):
             bot.send_message(chat_id, "Пожалуйста, отправьте файл в формате .txt или введите текст.", reply_markup=get_cancel_reply_keyboard())
             return
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        try:
            content = downloaded_file.decode('utf-8')
        except UnicodeDecodeError:
            bot.send_message(chat_id, "Не удалось прочитать файл в формате UTF-8.", reply_markup=get_cancel_reply_keyboard())
            return

    if not content:
        bot.send_message(chat_id, "Не удалось получить текст. Попробуйте еще раз.", reply_markup=get_cancel_reply_keyboard())
        return

    user_data = get_state_data(chat_id)
    chapter_id = user_data['current_chapter_id']
    chapters = load_chapters()
    chapters[chapter_id]['content'] = content
    save_chapters(chapters)
    bot.send_message(chat_id, f"✅ Содержание главы ID {chapter_id} успешно обновлено.", reply_markup=types.ReplyKeyboardRemove())
    clear_state(chat_id)
    bot.send_message(chat_id, "Выберите следующее действие в админ-панели:", reply_markup=get_admin_menu_keyboard())


# 4. Удаление главы
@bot.callback_query_handler(func=lambda call: call.data == "admin_delete")
def admin_delete_chapter_start_callback(call):
    bot.answer_callback_query(call.id)

    if call.from_user.id not in ADMIN_IDS: return
    chapters = load_chapters()
    markup = types.InlineKeyboardMarkup()
    if not chapters:
        bot.answer_callback_query(call.id, "Нет доступных глав для удаления.", show_alert=True)
        return
    
    for chap_id, chap_data in chapters.items():
        markup.add(types.InlineKeyboardButton(text=f"❌ ID {chap_id}: {chap_data['title']}", callback_data=f"confirm_delete_{chap_id}"))
    
    markup.add(types.InlineKeyboardButton(text="🚫 Отмена", callback_data="cancel"))
    bot.edit_message_text("❌ Выберите главу для удаления:", call.message.chat.id, call.message.message_id, reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith("confirm_delete_"))
def handle_confirm_delete_chapter(call):
    bot.answer_callback_query(call.id)

    chat_id = call.message.chat.id
    chapter_id = call.data.replace("confirm_delete_", "")

    chapters = load_chapters()
    if chapter_id in chapters:
        title = chapters[chapter_id]['title']
        del chapters[chapter_id]
        save_chapters(chapters)
        
        bot.send_message(chat_id, f"🗑️ Глава ID {chapter_id} ('{title}') успешно удалена.", reply_markup=types.ReplyKeyboardRemove())
        bot.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None) 
        bot.send_message(chat_id, "Выберите следующее действие в админ-панели:", reply_markup=get_admin_menu_keyboard())
    else:
        bot.answer_callback_query(call.id, "Глава не найдена.", show_alert=True)
        bot.send_message(chat_id, "Возврат в админ-панель:", reply_markup=get_admin_menu_keyboard())


# --- Обработка системы оценок ---

@bot.callback_query_handler(func=lambda call: call.data.startswith("rate_"))
def handle_rating(call):
    user_id = call.from_user.id
    action, chapter_id = call.data.replace("rate_", "").split('_', 1)
    chapters = load_chapters()

    if chapter_id in chapters:
        chapter = chapters[chapter_id]
        rated_by = set(chapter.get('rated_by', []))

        if user_id in rated_by:
            bot.answer_callback_query(call.id, "Вы уже оценили эту главу.", show_alert=True)
            return

        rated_by.add(user_id)
        chapter['rated_by'] = list(rated_by)

        if action == 'like':
            chapter['likes'] = chapter.get('likes', 0) + 1
            bot.answer_callback_query(call.id, "👍 Спасибо за вашу оценку!")
        elif action == 'dislike':
            chapter['dislikes'] = chapter.get('dislikes', 0) + 1
            bot.answer_callback_query(call.id, "👎 Ваша оценка учтена.")
        
        save_chapters(chapters)

        # Обновляем кнопки с новыми счетчиками
        try:
            bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=get_read_chapter_keyboard(chapter_id))
        except telebot.apihelper.ApiTelegramException as e:
            if "message is not modified" not in str(e):
                logging.error(f"Failed to edit message markup: {e}")

    else:
        bot.answer_callback_query(call.id, "Глава не найдена. 😕", show_alert=True)

# --- Запуск бота ---
if __name__ == '__main__':
    logging.info("Bot is polling...")
    # Убеждаемся, что файлы существуют при старте
    load_chapters()
    load_config()
    bot.infinity_polling()
