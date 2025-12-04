import telebot
import json
import logging
import os
import math
from telebot import types

# --- КОНСТАНТЫ С ВАШИМИ ДАННЫМИ ---
# Убедитесь, что переменная окружения TG_TOKEN установлена в вашей системе
API_TOKEN = '8430418918:AAFljWxONqcsSnisTi1N7hjpr0afjxYg2Mc' 
ADMIN_IDS = [995375387, 1081253267] # <-- Вставьте сюда ваш ID администратора, например: [995375387, 1081253267]
# Новая константа для размера блока глав (50 глав на страницу)
CHAPTERS_PER_PAGE = 20
# ----------------------------------

DATA_FILE = 'chapters.json'
CONFIG_FILE = 'config.json'
# Новый файл для хранения прогресса пользователей
PROGRESS_FILE = 'user_progress.json'

logging.basicConfig(level=logging.INFO)

# Инициализация бота
bot = telebot.TeleBot(API_TOKEN)
user_states = {}

# --- Функции для работы с данными (JSON) ---

def load_chapters():
    """Загружает главы из JSON файла."""
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
    """Загружает конфигурацию (приветствие, названия кнопок) из JSON файла."""
    if not os.path.exists(CONFIG_FILE):
        config_data = {
            "welcome_message": "👋 Привет! Это ваш бот для чтения глав.",
            "pagination_button_text": "Главы {start}-{end}" # Шаблон названия кнопки пагинации
        }
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, ensure_ascii=False, indent=4)
        return config_data
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {
            "welcome_message": "👋 Привет! Это ваш бот для чтения глав.",
            "pagination_button_text": "Главы {start}-{end}"
        }

def save_config(config):
    """Сохраняет конфигурацию в JSON файл."""
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=4)

# НОВАЯ ФУНКЦИЯ: Работа с прогрессом пользователя
def load_user_progress(user_id):
    """Загружает прочитанные главы для конкретного пользователя."""
    if not os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
            json.dump({}, f, ensure_ascii=False)
        return set()
    try:
        with open(PROGRESS_FILE, 'r', encoding='utf-8') as f:
            progress_data = json.load(f)
            # Возвращаем set прочитанных глав для данного user_id
            return set(progress_data.get(str(user_id), []))
    except json.JSONDecodeError:
        return set()

# НОВАЯ ФУНКЦИЯ: Сохранение прогресса пользователя
def save_user_progress(user_id, read_chapters_set):
    """Сохраняет прочитанные главы для пользователя."""
    with open(PROGRESS_FILE, 'r+', encoding='utf-8') as f:
        try:
            progress_data = json.load(f)
        except json.JSONDecodeError:
            progress_data = {}
        
        progress_data[str(user_id)] = list(read_chapters_set)
        
        f.seek(0)
        f.truncate()
        json.dump(progress_data, f, ensure_ascii=False, indent=4)

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

# --- Функция для отправки длинных сообщений ---

def send_long_message(chat_id, text, parse_mode=None):
    """Автоматически разбивает и отправляет текст частями."""
    if len(text) <= 4096:
        bot.send_message(chat_id, text, parse_mode=parse_mode)
    else:
        chunks = [text[i:i + 4000] for i in range(0, len(text), 4000)]
        for chunk in chunks:
            bot.send_message(chat_id, chunk, parse_mode=parse_mode)
# --- Клавиатуры (Обновленные функции) ---

# НОВАЯ ФУНКЦИЯ: Клавиатура для выбора блока глав
def get_chapter_blocks_keyboard(user_id):
    chapters = load_chapters()
    config = load_config()
    read_progress = load_user_progress(user_id)
    markup = types.InlineKeyboardMarkup()
    
    sorted_chapter_ids = sorted([int(c_id) for c_id in chapters.keys()])
    if not sorted_chapter_ids:
        # Если глав нет, возвращаем пустое меню или сообщение
        if user_id in ADMIN_IDS:
             markup.add(types.InlineKeyboardButton(text="🔑 Админ-панель", callback_data="open_admin_panel"))
        return markup 

    total_chapters = len(sorted_chapter_ids)
    total_pages = math.ceil(total_chapters / CHAPTERS_PER_PAGE)

    for page in range(total_pages):
        start_index = page * CHAPTERS_PER_PAGE
        end_index = min(start_index + CHAPTERS_PER_PAGE, total_chapters)
        
        block_ids = sorted_chapter_ids[start_index:end_index]
        
        start_id = block_ids[0]
        end_id = block_ids[-1]
        
        # --- Логика отметки прочтения ---
        # Проверяем, все ли главы в блоке прочитаны пользователем
        all_read = all(str(chap_id) in read_progress for chap_id in block_ids)
        
        # Используем шаблон названия кнопки из конфига
        button_text_template = config.get("pagination_button_text", "Главы {start}-{end}")
        button_text = button_text_template.format(start=start_id, end=end_id)

        if all_read:
            button_text = f"✅ {button_text}"
        else:
            button_text = f"📖 {button_text}"

        markup.add(types.InlineKeyboardButton(text=button_text, callback_data=f"show_block_{page+1}"))
    
    if user_id in ADMIN_IDS:
        markup.add(types.InlineKeyboardButton(text="🔑 Админ-панель", callback_data="open_admin_panel"))

    return markup


# НОВАЯ ФУНКЦИЯ: Клавиатура со списком глав внутри блока
def get_main_menu_keyboard(user_id, page=1):
    chapters = load_chapters()
    read_progress = load_user_progress(user_id)
    markup = types.InlineKeyboardMarkup()
    
    sorted_chapter_ids = sorted([int(c_id) for c_id in chapters.keys()])
    
    start_index = (page - 1) * CHAPTERS_PER_PAGE
    end_index = min(start_index + CHAPTERS_PER_PAGE, len(sorted_chapter_ids))
    
    if start_index >= len(sorted_chapter_ids):
        return get_chapter_blocks_keyboard(user_id)

    for i in range(start_index, end_index):
        chap_id_int = sorted_chapter_ids[i]
        chap_id_str = str(chap_id_int)
        
        title = chapters[chap_id_str]['title']
        
        # Добавляем эмодзи, если прочитано
        status_emoji = "✅" if chap_id_str in read_progress else "📖"
        
        button_text = f"{status_emoji} ID {chap_id_str}: {title}"
        markup.add(types.InlineKeyboardButton(text=button_text, callback_data=f"read_{chap_id_str}"))

    # Добавляем кнопки навигации (назад к блокам)
    back_to_blocks_btn = types.InlineKeyboardButton(text="◀️ Назад к блокам глав", callback_data="user_menu")
    markup.add(back_to_blocks_btn)

    if user_id in ADMIN_IDS:
        markup.add(types.InlineKeyboardButton(text="🔑 Админ-панель", callback_data="open_admin_panel"))
        
    return markup


def get_admin_menu_keyboard():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(text="✏️ Изменить приветствие", callback_data="admin_edit_welcome"))
    # Новая кнопка админки
    markup.add(types.InlineKeyboardButton(text="🏷️ Изменить название кнопок пагинации", callback_data="admin_edit_pagination_text"))
    markup.add(types.InlineKeyboardButton(text="➕ Добавить главу", callback_data="admin_add"))
    markup.add(types.InlineKeyboardButton(text="✏️ Изменить название главы", callback_data=f"admin_edit_title"))
    markup.add(types.InlineKeyboardButton(text="📝 Изменить содержание", callback_data=f"admin_edit_content"))
    markup.add(types.InlineKeyboardButton(text="❌ Удалить главу", callback_data=f"admin_delete"))
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
    # Проверка на случай удаления главы пока пользователь её читает
    if chapter_id not in chapters:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton(text="◀️ Назад к меню", callback_data="user_menu"))
        return markup
        
    likes = chapters[chapter_id].get('likes', 0)
    dislikes = chapters[chapter_id].get('dislikes', 0)

    markup = types.InlineKeyboardMarkup(row_width=2)
    like_btn = types.InlineKeyboardButton(text=f"👍 ({likes})", callback_data=f"rate_like_{chapter_id}")
    dislike_btn = types.InlineKeyboardButton(text=f"👎 ({dislikes})", callback_data=f"rate_dislike_{chapter_id}")
    # Кнопка возврата к блокам глав
    back_btn = types.InlineKeyboardButton(text="◀️ К списку глав", callback_data="back_to_chapter_list")
    
    markup.add(like_btn, dislike_btn)
    markup.add(back_btn)
    return markup

def cancel_handler_callback_message(message):
    clear_state(message.chat.id)
    bot.send_message(message.chat.id, "Возврат в админ-панель:", reply_markup=types.ReplyKeyboardRemove())
    bot.send_message(message.chat.id, "Выберите действие:", reply_markup=get_admin_menu_keyboard())
# --- Основные обработчики команд и сообщений (Обновленные) ---

def send_welcome_message(chat_id, user_id):
    clear_state(chat_id)
    config = load_config()
    welcome_text = config.get("welcome_message", "Привет!")
    bot.send_message(
        chat_id,
        welcome_text,
        reply_markup=get_welcome_keyboard()
    )

@bot.message_handler(commands=['start', 'menu'])
def send_welcome(message):
    send_welcome_message(message.chat.id, message.from_user.id)

@bot.callback_query_handler(func=lambda call: call.data == "open_admin_panel")
def open_admin_panel_callback(call):
    bot.answer_callback_query(call.id)
    if call.from_user.id in ADMIN_IDS:
        bot.edit_message_text("🔑 Добро пожаловать в админ-панель. Выберите действие:", call.message.chat.id, call.message.message_id, reply_markup=get_admin_menu_keyboard())

# ОБНОВЛЕНО: user_menu теперь показывает БЛОКИ глав
@bot.callback_query_handler(func=lambda call: call.data == "user_menu")
def back_to_user_menu_callback(call):
    bot.answer_callback_query(call.id)
    clear_state(call.message.chat.id)
    bot.edit_message_text("Выберите блок глав из меню:", call.message.chat.id, call.message.message_id, reply_markup=get_chapter_blocks_keyboard(call.from_user.id))

# НОВЫЙ ОБРАБОТЧИК: Открытие конкретного блока глав
@bot.callback_query_handler(func=lambda call: call.data.startswith("show_block_"))
def show_chapter_block_callback(call):
    bot.answer_callback_query(call.id)
    page_number = int(call.data.replace("show_block_", ""))
    user_id = call.from_user.id
    
    bot.edit_message_text(
        f"Список глав (Блок {page_number}):", 
        call.message.chat.id, 
        call.message.message_id, 
        reply_markup=get_main_menu_keyboard(user_id, page=page_number)
    )

# НОВЫЙ ОБРАБОТЧИК: Возврат из чтения главы к списку глав
@bot.callback_query_handler(func=lambda call: call.data == "back_to_chapter_list")
def back_to_chapter_list_callback(call):
    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, "Выберите блок глав из меню:", reply_markup=get_chapter_blocks_keyboard(call.from_user.id))
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except:
        pass


# ОБНОВЛЕНО: read_chapter_callback теперь отмечает главу как прочитанную
@bot.callback_query_handler(func=lambda call: call.data.startswith("read_"))
def read_chapter_callback(call):
    bot.answer_callback_query(call.id, text="Загрузка главы...")

    chapter_id = call.data.replace("read_", "")
    chapters = load_chapters()
    user_id = call.from_user.id

    if chapter_id in chapters:
        chapter = chapters[chapter_id]
        
        # --- НОВАЯ ЛОГИКА: Отметить главу как прочитанную ---
        read_progress = load_user_progress(user_id)
        if chapter_id not in read_progress:
            read_progress.add(chapter_id)
            save_user_progress(user_id, read_progress)
            logging.info(f"User {user_id} marked chapter {chapter_id} as read.")
        # ----------------------------------------------------

        send_long_message(call.message.chat.id, f"**{chapter['title']}**\n\n{chapter['content']}", parse_mode="Markdown")
        
        bot.send_message(call.message.chat.id, "--- Конец главы ---", reply_markup=get_read_chapter_keyboard(chapter_id))
        
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass
            
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

# НОВЫЕ ОБРАБОТЧИКИ: Изменение текста кнопок пагинации
@bot.callback_query_handler(func=lambda call: call.data == "admin_edit_pagination_text")
def admin_edit_pagination_text_start(call):
    bot.answer_callback_query(call.id)
    if call.from_user.id not in ADMIN_IDS: return
    config = load_config()
    current_template = config.get("pagination_button_text", "Главы {start}-{end}")
    
    msg_text = (
        f"✏️ Введите новый шаблон для кнопок пагинации.\n\n"
        f"**Важно:** Используйте `{'{start}'}` и `{'{end}'}` как заполнители для первого и последнего номера главы в блоке.\n\n"
        f"Пример: `Главы с {'{start}'} по {'{end}'}` даст 'Главы с 1 по 50'.\n\n"
        f"Текущий шаблон: `{current_template}`"
    )
    
    bot.edit_message_text(msg_text, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=get_cancel_keyboard())
    set_state(call.message.chat.id, "WAITING_FOR_PAGINATION_TEMPLATE")

@bot.message_handler(func=lambda message: get_state(message.chat.id) == "WAITING_FOR_PAGINATION_TEMPLATE")
def handle_new_pagination_template(message):
    chat_id = message.chat.id
    if message.text == "🚫 Отмена": return cancel_handler_callback_message(message)
    
    new_template = message.text
    
    if '{start}' not in new_template or '{end}' not in new_template:
        bot.send_message(chat_id, "🚫 Ошибка: Шаблон должен содержать `{'{start}'}` и `{'{end}'}`. Попробуйте еще раз.", parse_mode="Markdown", reply_markup=get_cancel_reply_keyboard())
        return

    config = load_config()
    config["pagination_button_text"] = new_template
    save_config(config)

    clear_state(chat_id)
    bot.send_message(chat_id, f"✅ Шаблон кнопок пагинации успешно обновлен на `{new_template}`.", parse_mode="Markdown", reply_markup=types.ReplyKeyboardRemove())
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
    bot.send_message(chat_id, f"Название принято ✅. Теперь **отправьте содержание как текстовый файл (.txt)** 📝, или введите текст (текст может быть очень длинным).", parse_mode="Markdown", reply_markup=get_cancel_reply_keyboard())


# 1. Добавление новой главы - ШАГ 4 (Сохранение файла/текста)
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
@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_edit_title"))
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
@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_edit_content"))
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
@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_delete"))
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
        # bot.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None) 
        bot.send_message(chat_id, "Выберите следующее действие в админ-панели:", reply_markup=get_admin_menu_keyboard())
    else:
        bot.answer_callback_query(call.id, "Глава не найдена.", show_alert=True)
        bot.send_message(chat_id, "Возврат в админ-панель:", reply_markup=get_admin_menu_keyboard())


# --- Обработка системы оценок (без изменений) ---

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
    # Убеждаемся, что файл прогресса тоже инициализирован при старте
    if not os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
            json.dump({}, f, ensure_ascii=False)
            
    bot.infinity_polling()
