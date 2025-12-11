import telebot
import json
import logging
import os
import math
import textwrap
from telebot import types

# --- КОНСТАНЫ С ВАШИМИ ДАННЫМИ ---
API_TOKEN = '8430418918:AAFljWxONqcsSnisTi1N7hjpr0afjxYg2Mc' 
ADMIN_IDS = [995375387,1081253267] # Замените на ваши ID администраторов
CHAPTERS_PER_GROUP = 10
CHAPTER_PAGE_SIZE = 850
# ----------------------------------

DATA_FILE = 'chapters.json'
PROGRESS_FILE = 'user_progress.json'
CONFIG_FILE = 'config.json'

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Инициализация бота
bot = telebot.TeleBot(API_TOKEN)
user_states = {} # Словарь для хранения состояний пользователей (FSM)

# --- Функции для работы с данными (JSON и Config) ---

def load_config():
    """Загружает конфигурацию (текст приветствия) из JSON файла."""
    if not os.path.exists(CONFIG_FILE): 
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump({"welcome_text": "👋 Привет! Привет Привет."}, f, ensure_ascii=False, indent=4)
        return {"welcome_text": "👋 Привет! Привет Привет."}
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {"welcome_text": "👋 Привет! Привет Привет."}

def save_config(config_data):
    """Сохраняет конфигурацию в JSON файл."""
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config_data, f, ensure_ascii=False, indent=4)

def load_chapters_data():
    """Загружает данные о частях и главах из JSON файла."""
    if not os.path.exists(DATA_FILE):
        json_data = {"parts": {}, "chapters": {}}
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, ensure_ascii=False)
        return json_data
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if 'parts' not in data: data['parts'] = {}
            if 'chapters' not in data: data['chapters'] = {}
            for chap_id in data['chapters']:
                if 'rated_by' not in data['chapters'][chap_id]:
                    data['chapters'][chap_id]['rated_by'] = []
            return data
    except json.JSONDecodeError:
        return {"parts": {}, "chapters": {}}

def save_chapters_data(data):
    """Сохраняет данные о главах и частях в JSON файл."""
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def load_user_progress(user_id):
    """Загружает прочитанные главы и текущую страницу для конкретного пользователя."""
    if not os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
            json.dump({}, f, ensure_ascii=False)
        return set(), {} # read_chapters_set, current_pages_dict
    try:
        with open(PROGRESS_FILE, 'r', encoding='utf-8') as f:
            progress_data = json.load(f)
            user_data = progress_data.get(str(user_id), {})
            if isinstance(user_data, list):
                return set(user_data), {} 
            return set(user_data.get('read', [])), user_data.get('pages', {})
    except json.JSONDecodeError:
        return set(), {}

def save_user_progress(user_id, read_chapters_set, current_pages_dict):
    """Сохраняет прочитанные главы и текущую страницу для пользователя."""
    with open(PROGRESS_FILE, 'r+', encoding='utf-8') as f:
        try:
            progress_data = json.load(f)
        except json.JSONDecodeError:
            progress_data = {}
        
        user_data_raw = progress_data.get(str(user_id))
        if isinstance(user_data_raw, list):
            user_data = {'read': user_data_raw, 'pages': {}}
        elif isinstance(user_data_raw, dict):
            user_data = user_data_raw
        else:
            user_data = {}

        user_data['read'] = list(read_chapters_set)
        user_data['pages'] = current_pages_dict
        progress_data[str(user_id)] = user_data
        
        f.seek(0)
        f.truncate()
        json.dump(progress_data, f, ensure_ascii=False, indent=4)

def get_user_read_page(user_id, chapter_id_str):
    """Получает последнюю прочитанную страницу для главы."""
    _, pages_dict = load_user_progress(user_id)
    return pages_dict.get(chapter_id_str, 0)

# --- Вспомогательные функции для состояний и длинных сообщений ---

def set_state(chat_id, state_name, data=None):
    user_states[chat_id] = {"state": state_name, "data": data or {}}

def get_state(chat_id):
    return user_states.get(chat_id, {}).get("state")

def get_state_data(chat_id):
    return user_states.get(chat_id, {}).get("data", {})

def clear_state(chat_id):
    if chat_id in user_states:
        del user_states[chat_id]

def send_long_message(chat_id, text, parse_mode=None):
    """Используется только для админки/приветствия, не для чтения глав."""
    if len(text) <= 4096:
        sent_message = bot.send_message(chat_id, text, parse_mode=parse_mode)
        return [sent_message.message_id]
    else:
        chunks = [text[i:i + 4000] for i in range(0, len(text), 4000)]
        message_ids = []
        for chunk in chunks:
            sent_message = bot.send_message(chat_id, chunk, parse_mode=parse_mode)
            message_ids.append(sent_message.message_id)
        return message_ids

def paginate_content(content, page_size):
    """
    Разбивает длинный текст на страницы, стараясь сохранять целостность абзацев
    и не превышать лимит Telegram на размер сообщения (4096 символов).
    """
    pages = []
    current_page = ""
    
    normalized_content = content.replace('\r\n', '\n')
    paragraphs = normalized_content.split('\n\n')
    
    for para in paragraphs:
        if not para.strip():
            continue
        if len(current_page) + len(para) + 2 < page_size:
            current_page += (para + '\n\n')
        else:
            if current_page:
                pages.append(current_page.strip())
            current_page = para + '\n\n'
    
    if current_page.strip():
        pages.append(current_page.strip())
        
    final_pages = []
    for page in pages:
        if len(page) > 4000:
            final_pages.extend(textwrap.wrap(page, 4000))
        else:
            final_pages.append(page)
    return final_pages

# --- Клавиатуры (Трехуровневая навигация) ---

# Уровень 1: Клавиатура выбора частей
def get_parts_keyboard(user_id):
    data = load_chapters_data()
    parts = data['parts']
    read_progress_set, _ = load_user_progress(user_id)
    markup = types.InlineKeyboardMarkup(row_width=1)
    
    if not parts:
        if user_id in ADMIN_IDS:
             markup.add(types.InlineKeyboardButton(text="🔑 Админ-панель", callback_data="open_admin_panel"))
        return markup 

    for part_name, chapter_ids in parts.items():
        all_read = all(str(chap_id) in read_progress_set for chap_id in chapter_ids)
        status_emoji = "✅" if all_read else "📖"
        button_text = f"{status_emoji} {part_name}"
        markup.add(types.InlineKeyboardButton(text=button_text, callback_data=f"show_groups_{part_name}"))
    
    if user_id in ADMIN_IDS:
        markup.add(types.InlineKeyboardButton(text="🔑 Админ-панель", callback_data="open_admin_panel"))

    return markup
    
# Уровень 2: Клавиатура выбора групп глав внутри части (по 10 шт)
def get_groups_keyboard(user_id, part_name):
    data = load_chapters_data()
    chapters_in_part = data['parts'].get(part_name, [])
    read_progress_set, _ = load_user_progress(user_id)
    markup = types.InlineKeyboardMarkup(row_width=1)

    if not chapters_in_part:
        markup.add(types.InlineKeyboardButton(text="◀️ Назад", callback_data="user_menu"))
        return markup

    total_chapters = len(chapters_in_part)
    total_groups = math.ceil(total_chapters / CHAPTERS_PER_GROUP)
    for group_index in range(total_groups):
        start_index = group_index * CHAPTERS_PER_GROUP
        end_index = min(start_index + CHAPTERS_PER_GROUP, total_chapters)
        
        group_ids = chapters_in_part[start_index:end_index]
        
        all_read = all(str(chap_id) in read_progress_set for chap_id in group_ids)
        
        start_num = start_index + 1
        end_num = end_index
        
        status_emoji = "✅" if all_read else "📖"
        button_text = f"{status_emoji} Главы {start_num}-{end_num}"

        markup.add(types.InlineKeyboardButton(text=button_text, callback_data=f"show_chapters_{part_name}_{group_index}"))

    back_to_parts_btn = types.InlineKeyboardButton(text="◀️ Назад", callback_data="user_menu")
    markup.add(back_to_parts_btn)
        
    return markup
    
# Уровень 3: Клавиатура со списком глав внутри конкретной группы
def get_chapters_in_group_keyboard(user_id, part_name, group_index_str):
    data = load_chapters_data()
    chapters_data = data['chapters']
    chapters_in_part = data['parts'].get(part_name, [])
    read_progress_set, _ = load_user_progress(user_id)
    markup = types.InlineKeyboardMarkup(row_width=1)
    
    group_index = int(group_index_str)
    start_index = group_index * CHAPTERS_PER_GROUP
    end_index = min(start_index + CHAPTERS_PER_GROUP, len(chapters_in_part))
    group_ids = chapters_in_part[start_index:end_index]

    for chap_id_str in group_ids:
        if chap_id_str in chapters_data:
            title = chapters_data[chap_id_str]['title']
            status_emoji = "✅" if chap_id_str in read_progress_set else "📖"
            # Используем полное название главы из JSON (например, "Глава 1")
            button_text = f"{status_emoji} {title}"
            markup.add(types.InlineKeyboardButton(text=button_text, callback_data=f"read_{chap_id_str}"))

    back_to_groups_btn = types.InlineKeyboardButton(text=f"◀️ Назад", callback_data=f"show_groups_{part_name}")
    markup.add(back_to_groups_btn)
        
    return markup

def get_admin_menu_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton(text="➕ Добавить новую часть", callback_data="admin_add_part"))
    markup.add(types.InlineKeyboardButton(text="✏️ Изменить название части", callback_data="admin_edit_part_name_start"))
    markup.add(types.InlineKeyboardButton(text="❌ Удалить часть", callback_data="admin_delete_part_start"))
    markup.add(types.InlineKeyboardButton(text="➕ Добавить главу", callback_data="admin_add_chapter_to_part_start"))
    markup.add(types.InlineKeyboardButton(text="✏️ Переименовать главу", callback_data=f"admin_rename_chapter_start"))
    markup.add(types.InlineKeyboardButton(text="❌ Удалить главу", callback_data=f"admin_delete_chapter_select_part"))
    markup.add(types.InlineKeyboardButton(text="⚙️ Изменить приветствие", callback_data=f"admin_edit_welcome_text"))
    markup.add(types.InlineKeyboardButton(text="⬅️ Назад", callback_data="user_menu"))
    return markup
def get_cancel_keyboard():
    # Эта клавиатура используется для Inline-кнопок отмены
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton(text="🚫 Отмена", callback_data="cancel"))
    return markup

def get_cancel_reply_keyboard():
    # Эта клавиатура используется для текстового ввода отмены (Reply-клавиатура)
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add("🚫 Отмена")
    return markup

def get_welcome_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton(text="📖 Перейти к главам", callback_data="user_menu"))
    return markup

# КЛАВИАТУРА ДЛЯ ПОСТРАНИЧНОГО ЧТЕНИЯ
def get_read_chapter_pagination_keyboard(chapter_id, current_page, total_pages):
    markup = types.InlineKeyboardMarkup(row_width=3)
    
    back_btn = types.InlineKeyboardButton(text="◀️ Назад", callback_data=f"paginate_{chapter_id}_{current_page - 1}")
    page_info_btn = types.InlineKeyboardButton(text=f"{current_page + 1}/{total_pages}", callback_data=f"select_page_{chapter_id}_{current_page}")
    next_btn = types.InlineKeyboardButton(text="Далее ▶️", callback_data=f"paginate_{chapter_id}_{current_page + 1}")
    
    if current_page == 0:
        back_btn = types.InlineKeyboardButton(text=" ", callback_data="placeholder")
    if current_page == total_pages - 1:
        next_btn = types.InlineKeyboardButton(text=" ", callback_data="placeholder")
    
    markup.add(back_btn, page_info_btn, next_btn)

    if current_page == total_pages - 1:
        data = load_chapters_data()
        chapters = data['chapters']
        if chapter_id in chapters:
            likes = chapters[chapter_id].get('likes', 0)
            dislikes = chapters[chapter_id].get('dislikes', 0)
            like_btn = types.InlineKeyboardButton(text=f"👍 ({likes})", callback_data=f"rate_like_{chapter_id}")
            dislike_btn = types.InlineKeyboardButton(text=f"👎 ({dislikes})", callback_data=f"rate_dislike_{chapter_id}")
            markup.add(like_btn, dislike_btn)
        
    back_to_list_btn = types.InlineKeyboardButton(text="📚 К списку глав", callback_data="back_to_chapter_list")
    markup.row(back_to_list_btn)
    
    return markup

# --- НОВЫЕ КЛАВИАТУРЫ АДМИНКИ (Пагинация для удаления/переименования) ---

# Уровень А1: Клавиатура выбора частей для удаления/переименования
def get_admin_parts_keyboard(action_prefix):
    data = load_chapters_data()
    parts = data['parts']
    markup = types.InlineKeyboardMarkup(row_width=1)
    if not parts:
        markup.add(types.InlineKeyboardButton(text="◀️ Назад в админку", callback_data="open_admin_panel"))
        return markup 
    for part_name in parts.keys():
        markup.add(types.InlineKeyboardButton(text=f"📚 {part_name}", callback_data=f"{action_prefix}{part_name}"))
    markup.add(types.InlineKeyboardButton(text="🚫 Отмена", callback_data="cancel"))
    return markup

# Уровень А2: Клавиатура выбора групп глав внутри части для удаления/переименования
def get_admin_groups_keyboard(part_name, action_prefix):
    data = load_chapters_data()
    chapters_in_part = data['parts'].get(part_name, [])
    markup = types.InlineKeyboardMarkup(row_width=1)

    if not chapters_in_part:
        back_callback = "admin_delete_chapter_select_part" if 'delete' in action_prefix else "admin_rename_chapter_start"
        markup.add(types.InlineKeyboardButton(text="◀️ Назад", callback_data=back_callback))
        return markup

    total_chapters = len(chapters_in_part)
    total_groups = math.ceil(total_chapters / CHAPTERS_PER_GROUP)

    for group_index in range(total_groups):
        start_index = group_index * CHAPTERS_PER_GROUP
        end_index = min(start_index + CHAPTERS_PER_GROUP, total_chapters)
        start_num = start_index + 1
        end_num = end_index
        button_text = f"Главы {start_num}-{end_num}"
        markup.add(types.InlineKeyboardButton(text=button_text, callback_data=f"{action_prefix}{part_name}_{group_index}"))

    back_to_parts_btn = types.InlineKeyboardButton(text="◀️ Назад к частям", callback_data="admin_delete_chapter_select_part" if 'delete' in action_prefix else "admin_rename_chapter_start")
    markup.add(back_to_parts_btn)
        
    return markup
    
# Уровень А3: Клавиатура со списком глав внутри конкретной группы для удаления/переименования
def get_admin_chapters_in_group_keyboard(part_name, group_index_str, action_prefix):
    data = load_chapters_data()
    chapters_data = data['chapters']
    chapters_in_part = data['parts'].get(part_name, [])
    markup = types.InlineKeyboardMarkup(row_width=1)
    
    group_index = int(group_index_str)
    start_index = group_index * CHAPTERS_PER_GROUP
    end_index = min(start_index + CHAPTERS_PER_GROUP, len(chapters_in_part))
    group_ids = chapters_in_part[start_index:end_index]
    for chap_id_str in group_ids:
        if chap_id_str in chapters_data:
            title = chapters_data[chap_id_str]['title']
            button_text = f"📖 {title}"
            markup.add(types.InlineKeyboardButton(text=button_text, callback_data=f"{action_prefix}{chap_id_str}"))

    back_to_groups_btn = types.InlineKeyboardButton(text=f"◀️ Назад", callback_data=f"admin_show_groups_delete_{part_name}" if 'delete' in action_prefix else f"admin_show_groups_rename_{part_name}")
    markup.add(back_to_groups_btn)
        
    return markup


# --- ОБРАБОТЧИКИ КОМАНД ---

@bot.message_handler(commands=['start'])
# ИСПРАВЛЕНИЕ: Функция теперь принимает ТОЛЬКО один аргумент 'message'.
def send_welcome_message(message):
    chat_id = message.chat.id
    user_id = message.from_user.id # Получаем user_id внутри функции
    config = load_config()
    welcome_text = config.get("welcome_text", "👋 Привет! Добро пожаловать.")
    
    # Мы используем send_long_message, чтобы показать полное приветствие, 
    # но оно не должно использоваться для глав.
    message_ids = send_long_message(chat_id, welcome_text, parse_mode="Markdown")
    
    if message_ids:
        bot.send_message(chat_id, "Выберите действие ниже:", reply_markup=get_welcome_keyboard())
    else:
        bot.send_message(chat_id, "Выберите действие ниже:", reply_markup=get_welcome_keyboard())


@bot.message_handler(commands=['admin'])
def admin_panel_command(message):
    if message.chat.id in ADMIN_IDS:
        bot.send_message(message.chat.id, "🔑 Открытие админ-панели...", reply_markup=types.ReplyKeyboardRemove())
        # Отправляем новое сообщение с админ-меню
        bot.send_message(message.chat.id, "🔑 Добро пожаловать в админ-панель. Выберите действие:", reply_markup=get_admin_menu_keyboard())
    else:
        bot.send_message(message.chat.id, "У вас нет прав администратора.")

@bot.callback_query_handler(func=lambda call: call.data == "open_admin_panel")
def open_admin_panel_callback(call):
    if call.from_user.id in ADMIN_IDS:
        bot.answer_callback_query(call.id)
        bot.edit_message_text("🔑 Добро пожаловать в админ-панель. Выберите действие:", call.message.chat.id, call.message.message_id, reply_markup=get_admin_menu_keyboard())

@bot.callback_query_handler(func=lambda call: call.data == "user_menu")
def back_to_user_menu_callback(call):
    bot.answer_callback_query(call.id)
    clear_state(call.message.chat.id)
    bot.edit_message_text("Выберите часть:", call.message.chat.id, call.message.message_id, reply_markup=get_parts_keyboard(call.from_user.id))
    
@bot.callback_query_handler(func=lambda call: call.data.startswith("show_groups_"))
def show_chapter_groups_callback(call):
    bot.answer_callback_query(call.id)
    part_name = call.data.replace("show_groups_", "")
    user_id = call.from_user.id
    
    bot.edit_message_text(
        f"Выберите главу:", 
        call.message.chat.id, 
        call.message.message_id, 
        reply_markup=get_groups_keyboard(user_id, part_name)
    )
    # При просмотре групп мы сохраняем только имя части
    set_state(call.message.chat.id, "VIEWING_GROUPS", data={'current_part_name': part_name})
    
@bot.callback_query_handler(func=lambda call: call.data.startswith("show_chapters_"))
def show_chapters_in_group_callback(call):
    bot.answer_callback_query(call.id)
    parts_data = call.data.replace("show_chapters_", "").split('_')
    group_index = parts_data[-1]
    part_name = "_".join(parts_data[:-1]) 
    user_id = call.from_user.id
    bot.edit_message_text(
        f"Выберите главу:",
        call.message.chat.id, 
        call.message.message_id, 
        reply_markup=get_chapters_in_group_keyboard(user_id, part_name, group_index)
    )
    # Сохраняем не только part_name, но и group_index, чтобы вернуться точно в этот список
    set_state(call.message.chat.id, "VIEWING_CHAPTERS_LIST", data={'current_part_name': part_name, 'current_group_index': group_index})


# --- ОБРАБОТЧИКИ НАВИГАЦИИ АДМИНКИ (Удаление/Переименование с пагинацией) ---

@bot.callback_query_handler(func=lambda call: call.data == "admin_delete_chapter_select_part")
def admin_delete_chapter_select_part_callback(call):
    bot.answer_callback_query(call.id)
    bot.edit_message_text("Выберите часть, из которой хотите удалить главу:", call.message.chat.id, call.message.message_id, reply_markup=get_admin_parts_keyboard("admin_show_groups_delete_"))

@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_show_groups_delete_"))
def admin_delete_show_groups_callback(call):
    bot.answer_callback_query(call.id)
    part_name = call.data.replace("admin_show_groups_delete_", "")
    bot.edit_message_text("Выберите группу глав:", call.message.chat.id, call.message.message_id, reply_markup=get_admin_groups_keyboard(part_name, "admin_show_chapters_delete_group_"))

@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_show_chapters_delete_group_"))
def admin_delete_show_chapters_callback(call):
    bot.answer_callback_query(call.id)
    parts_data = call.data.replace("admin_show_chapters_delete_group_", "").split('_')
    group_index = parts_data[-1]
    part_name = "_".join(parts_data[:-1])
    bot.edit_message_text("Выберите главу для **удаления** (показ по 10 шт.):", call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=get_admin_chapters_in_group_keyboard(part_name, group_index, "delete_chapter_"))

@bot.callback_query_handler(func=lambda call: call.data == "admin_rename_chapter_start")
def admin_rename_chapter_select_part_callback(call):
    bot.answer_callback_query(call.id)
    bot.edit_message_text("Выберите часть, в которой находится глава для переименования:", call.message.chat.id, call.message.message_id, reply_markup=get_admin_parts_keyboard("admin_show_groups_rename_"))

@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_show_groups_rename_"))
def admin_rename_show_groups_callback(call):
    bot.answer_callback_query(call.id)
    part_name = call.data.replace("admin_show_groups_rename_", "")
    bot.edit_message_text("Выберите группу глав:", call.message.chat.id, call.message.message_id, reply_markup=get_admin_groups_keyboard(part_name, "admin_show_chapters_rename_group_"))

@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_show_chapters_rename_group_"))
def admin_rename_show_chapters_callback(call):
    bot.answer_callback_query(call.id)
    parts_data = call.data.replace("admin_show_chapters_rename_group_", "").split('_')
    group_index = parts_data[-1]
    part_name = "_".join(parts_data[:-1])
    bot.edit_message_text("Выберите главу для **переименования**:", call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=get_admin_chapters_in_group_keyboard(part_name, group_index, "admin_rename_chapter_select_"))
# --- НОВЫЕ ОБРАБОТЧИКИ АДМИНКИ (Работа с частями через FSM) ---

@bot.callback_query_handler(func=lambda call: call.data == "admin_add_part")
def admin_add_part_start_callback(call):
    bot.answer_callback_query(call.id)
    if call.from_user.id not in ADMIN_IDS: return
    
    bot.edit_message_text("✏️ Введите название новой **части** (например, 'Том 1' или 'Часть 1'):", call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=get_cancel_keyboard())
    set_state(call.message.chat.id, "WAITING_FOR_NEW_PART_NAME")

@bot.callback_query_handler(func=lambda call: call.data == "admin_edit_part_name_start")
def admin_edit_part_name_select(call):
    bot.answer_callback_query(call.id)
    if call.from_user.id not in ADMIN_IDS: return
    
    data = load_chapters_data()
    parts = data['parts']
    if not parts:
        bot.answer_callback_query(call.id, "Нет доступных частей для редактирования.", show_alert=True)
        return

    markup = types.InlineKeyboardMarkup(row_width=1)
    for part_name in parts.keys():
        markup.add(types.InlineKeyboardButton(text=f"✏️ {part_name}", callback_data=f"select_edit_part_name_{part_name}"))
    markup.add(types.InlineKeyboardButton(text="🚫 Отмена", callback_data="cancel"))
    bot.edit_message_text("Выберите часть, название которой хотите изменить:", call.message.chat.id, call.message.message_id, reply_markup=markup)
@bot.callback_query_handler(func=lambda call: call.data.startswith("select_edit_part_name_"))
def admin_edit_part_name_input_start(call):
    bot.answer_callback_query(call.id)
    chat_id = call.message.chat.id
    old_part_name = call.data.replace("select_edit_part_name_", "") 
    
    set_state(chat_id, "WAITING_FOR_NEW_PART_NAME_EDIT", data={'old_part_name': old_part_name})
    bot.send_message(chat_id, f"Введите новое название для части '{old_part_name}':", reply_markup=get_cancel_reply_keyboard())
    bot.delete_message(chat_id, call.message.message_id)

# 6. Изменение приветствия - Шаг 1 (Начало FSM) - ЭТА ФУНКЦИЯ ДОБАВЛЕНА СЮДА
@bot.callback_query_handler(func=lambda call: call.data == "admin_edit_welcome_text")
def admin_edit_welcome_text_start(call):
    bot.answer_callback_query(call.id)
    chat_id = call.message.chat.id
    if chat_id not in ADMIN_IDS: return

    set_state(chat_id, "WAITING_FOR_NEW_WELCOME_TEXT")
    
    bot.send_message(chat_id, "✏️ Введите новый текст приветствия:", reply_markup=get_cancel_reply_keyboard())
    try:
        bot.delete_message(chat_id, call.message.message_id)
    except:
        pass


@bot.callback_query_handler(func=lambda call: call.data == "admin_add_chapter_to_part_start")
def admin_add_chapter_select_part(call):
    bot.answer_callback_query(call.id)
    if call.from_user.id not in ADMIN_IDS: return

    data = load_chapters_data()
    parts = data['parts']
    if not parts:
        bot.answer_callback_query(call.id, "Нет доступных частей. Сначала добавьте часть.", show_alert=True)
        return

    markup = types.InlineKeyboardMarkup(row_width=1)
    for part_name in parts.keys():
        markup.add(types.InlineKeyboardButton(text=f"➕ {part_name}", callback_data=f"select_part_for_chapter_{part_name}"))
    markup.add(types.InlineKeyboardButton(text="🚫 Отмена", callback_data="cancel"))
    bot.edit_message_text("Выберите часть, в которую хотите добавить главу:", call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("select_part_for_chapter_"))
def admin_add_chapter_enter_title(call):
    bot.answer_callback_query(call.id)
    chat_id = call.message.chat.id
    part_name = call.data.replace("select_part_for_chapter_", "")

    # Просим ввести название "Глава 1", "Глава 2" и т.д.
    set_state(chat_id, "WAITING_FOR_CHAPTER_TITLE_FOR_ADD", data={'target_part_name': part_name})
    bot.send_message(chat_id, f"Выбрана часть '{part_name}'. Введите **название** ✏️ новой главы (например, 'Глава 1: Начало'):", parse_mode="Markdown", reply_markup=get_cancel_reply_keyboard())
    bot.delete_message(chat_id, call.message.message_id)
    
@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_rename_chapter_select_"))
def admin_rename_chapter_select_chapter_callback(call):
    bot.answer_callback_query(call.id)
    chat_id = call.message.chat.id
    chapter_id = call.data.replace("admin_rename_chapter_select_", "")
    
    data = load_chapters_data()
    if chapter_id in data['chapters']:
        old_title = data['chapters'][chapter_id]['title']
        set_state(chat_id, "WAITING_FOR_NEW_CHAPTER_TITLE", data={'chapter_id': chapter_id, 'old_title': old_title})
        bot.send_message(chat_id, f"Введите новое название для главы '{old_title}' (ID: {chapter_id}):", reply_markup=get_cancel_reply_keyboard())
        bot.delete_message(chat_id, call.message.message_id)
    else:
        bot.send_message(chat_id, "Глава не найдена или произошла ошибка. Попробуйте снова.")


def handle_new_part_name_input_process(message):
    chat_id = message.chat.id
    part_name = message.text.strip()
    data = load_chapters_data()
    
    if part_name in data['parts']:
         bot.send_message(chat_id, "Такое название части уже существует. Попробуйте другое.", reply_markup=get_cancel_keyboard())
         return

    data['parts'][part_name] = []
    save_chapters_data(data)
    clear_state(chat_id)
    bot.send_message(chat_id, f"✅ Часть **'{part_name}'** успешно добавлена!", parse_mode="Markdown", reply_markup=types.ReplyKeyboardRemove())
    bot.send_message(chat_id, "Выберите следующее действие:", reply_markup=get_admin_menu_keyboard())

def handle_new_part_name_edit_input_process(message):
    chat_id = message.chat.id
    new_part_name = message.text.strip()
    user_data = get_state_data(chat_id)
    old_part_name = user_data.get('old_part_name')
    if not old_part_name:
        clear_state(chat_id)
        bot.send_message(chat_id, "Произошла ошибка состояния. Попробуйте снова.", reply_markup=types.ReplyKeyboardRemove())
        bot.send_message(chat_id, "Возврат в админ-панель:", reply_markup=get_admin_menu_keyboard())
        return

    data = load_chapters_data()

    if new_part_name in data['parts']:
        bot.send_message(chat_id, "Такое название уже существует. Попробуйте другое.", reply_markup=get_cancel_reply_keyboard())
        return
        
    data['parts'][new_part_name] = data['parts'].pop(old_part_name)
    save_chapters_data(data)

    clear_state(chat_id)
    bot.send_message(chat_id, f"✅ Название части успешно обновлено на '{new_part_name}'.", reply_markup=types.ReplyKeyboardRemove())
    bot.send_message(chat_id, "Выберите следующее действие в админ-панели:", reply_markup=get_admin_menu_keyboard())
    
def handle_add_title_input_process(message):
    chat_id = message.chat.id
    title = message.text
    data = get_state_data(chat_id)
    
    if not title.strip():
        bot.send_message(chat_id, "Название не может быть пустым. Введите название главы или нажмите 'Отмена':", reply_markup=get_cancel_reply_keyboard())
        return
        
    data['new_title'] = title
    set_state(chat_id, "WAITING_FOR_CONTENT_FILE_FOR_ADD", data=data) 
    bot.send_message(chat_id, f"Название '{title}' принято ✅. Теперь **отправьте содержание как текстовый файл (.txt)** 📝, или введите текст (текст может быть очень длинным).", parse_mode="Markdown", reply_markup=get_cancel_reply_keyboard())

@bot.message_handler(content_types=['text', 'document'], func=lambda message: get_state(message.chat.id) == "WAITING_FOR_CONTENT_FILE_FOR_ADD")
def handle_add_content_input(message):
    chat_id = message.chat.id
    
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
    else:
        return

    if not content.strip():
        bot.send_message(chat_id, "Не удалось получить текст. Попробуйте еще раз.", reply_markup=get_cancel_reply_keyboard())
        return

    user_data = get_state_data(chat_id)
    title = user_data['new_title']
    target_part_name = user_data['target_part_name']
    
    data = load_chapters_data()
    
    if not data['chapters']:
        new_chapter_id = 1
    else:
        max_id = max(int(k) for k in data['chapters'].keys())
        new_chapter_id = max_id + 1
    new_chapter_id_str = str(new_chapter_id)
    
    data['chapters'][new_chapter_id_str] = {"title": title, "content": content, "likes": 0, "dislikes": 0, "rated_by": []}
    if target_part_name in data['parts']:
        data['parts'][target_part_name].append(new_chapter_id_str)
    
    save_chapters_data(data)

    bot.send_message(chat_id, f"🎉 Глава {new_chapter_id_str} ('{title}') успешно **добавлена** в часть '{target_part_name}'!", parse_mode="Markdown", reply_markup=types.ReplyKeyboardRemove())
    clear_state(chat_id)
    bot.send_message(chat_id, "Выберите следующее действие в админ-панели 👇:", reply_markup=get_admin_menu_keyboard())
# 6. Переименование главы - Шаг 4 (Сохранение нового названия)
def handle_new_chapter_title_input_process(message):
    chat_id = message.chat.id
    new_title = message.text.strip()
    user_data = get_state_data(chat_id)
    chapter_id = user_data.get('chapter_id')
    old_title = user_data.get('old_title')
    
    if not chapter_id:
        bot.send_message(chat_id, "Произошла ошибка состояния. Попробуйте снова.", reply_markup=types.ReplyKeyboardRemove())
        clear_state(chat_id)
        bot.send_message(chat_id, "Возврат в админ-панель:", reply_markup=get_admin_menu_keyboard())
        return

    data = load_chapters_data()
    if chapter_id in data['chapters']:
        data['chapters'][chapter_id]['title'] = new_title
        save_chapters_data(data)

        clear_state(chat_id)
        bot.send_message(chat_id, f"✅ Название главы ID {chapter_id} успешно обновлено с '{old_title}' на **'{new_title}'**.", parse_mode="Markdown", reply_markup=types.ReplyKeyboardRemove())
        bot.send_message(chat_id, "Выберите следующее действие в админ-панели:", reply_markup=get_admin_menu_keyboard())
    else:
        bot.send_message(chat_id, "Произошла ошибка: глава не найдена. Попробуйте снова.")
        clear_state(chat_id)
        bot.send_message(chat_id, "Возврат в админ-панель:", reply_markup=get_admin_menu_keyboard())
# --- FSM: ИЗМЕНЕНИЕ ПРИВЕТСТВИЯ ---

def handle_new_welcome_text_input_process(message):
    chat_id = message.chat.id
    new_text = message.text
    
    if not new_text.strip():
        bot.send_message(chat_id, "Текст приветствия не может быть пустым. Введите текст или нажмите 'Отмена':", reply_markup=get_cancel_reply_keyboard())
        return

    config = load_config()
    config["welcome_text"] = new_text
    save_config(config)

    clear_state(chat_id)
    bot.send_message(chat_id, f"✅ Текст приветствия успешно обновлен.", reply_markup=types.ReplyKeyboardRemove())
    # ИСПРАВЛЕНО: передаем только один аргумент, как требует новая сигнатура send_welcome_message
    send_welcome_message(message) 

# --- ОБЩИЙ ОБРАБОТЧИК ТЕКСТОВЫХ СООБЩЕНИЙ ДЛЯ FSM И ОТМЕНЫ ---
@bot.message_handler(content_types=['text'])
def handle_text_messages(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    current_state = get_state(chat_id)

    # Мы полагаемся на независимый обработчик handle_text_cancel для обработки кнопки "🚫 Отмена"

    is_admin_state = current_state in [
        "WAITING_FOR_NEW_PART_NAME", "WAITING_FOR_NEW_PART_NAME_EDIT", 
        "WAITING_FOR_CHAPTER_TITLE_FOR_ADD", "WAITING_FOR_CONTENT_FILE_FOR_ADD", 
        "WAITING_FOR_NEW_CHAPTER_TITLE", "WAITING_FOR_NEW_WELCOME_TEXT"
    ]

    if is_admin_state and user_id not in ADMIN_IDS:
        bot.send_message(chat_id, "У вас нет прав для выполнения этого действия.")
        clear_state(chat_id)
        return

    # Обработка состояний FSM
    if current_state == "WAITING_FOR_NEW_PART_NAME":
        handle_new_part_name_input_process(message)
    elif current_state == "WAITING_FOR_NEW_PART_NAME_EDIT":
        handle_new_part_name_edit_input_process(message)
    elif current_state == "WAITING_FOR_CHAPTER_TITLE_FOR_ADD":
        handle_add_title_input_process(message)
    elif current_state == "WAITING_FOR_NEW_CHAPTER_TITLE":
        handle_new_chapter_title_input_process(message)
    elif current_state == "WAITING_FOR_NEW_WELCOME_TEXT":
        handle_new_welcome_text_input_process(message)
    elif current_state == "WAITING_FOR_CONTENT_FILE_FOR_ADD":
         # Этот обработчик теперь использует декоратор message_handler выше
         handle_add_content_input(message)
    else:
        # Если нет активного FSM состояния, просто показываем меню
        # ИСПРАВЛЕНО: передаем только один аргумент message
        send_welcome_message(message)

        
# 4. Удаление главы - Логика выбора и подтверждения
@bot.callback_query_handler(func=lambda call: call.data.startswith("delete_chapter_"))
def handle_confirm_delete_chapter(call):
    bot.answer_callback_query(call.id)
    chat_id = call.message.chat.id
    chapter_id_to_delete = call.data.replace("delete_chapter_", "")
    
    logging.info(f"[DELETE] Admin {chat_id} attempting to delete chapter ID: {chapter_id_to_delete}")
    
    data = load_chapters_data()
    chapters = data['chapters']
    parts = data['parts']

    if chapter_id_to_delete in chapters:
        # ИСПРАВЛЕНА ОШИБКА: Добавлена закрывающая скобка и кавычка
        logging.info(f"[DELETE] Chapter {chapter_id_to_delete} found, proceeding with deletion.")
        title = chapters[chapter_id_to_delete]['title']
        
        del data['chapters'][chapter_id_to_delete]
        
        found = False
        for part_name in parts:
            if chapter_id_to_delete in parts[part_name]:
                parts[part_name].remove(chapter_id_to_delete)
                found = True
                logging.info(f"[DELETE] Removed chapter {chapter_id_to_delete} from part '{part_name}'.")
                break
        
        save_chapters_data(data)
        
        try:
            with open(PROGRESS_FILE, 'r+', encoding='utf-8') as f:
                progress_data = json.load(f)
                for user_id_str in progress_data:
                    user_data = progress_data.get(user_id_str)
                    if isinstance(user_data, list):
                        user_data = {'read': user_data, 'pages': {}}
                    elif not isinstance(user_data, dict):
                         continue

                    if chapter_id_to_delete in user_data.get('read', []):
                        user_data['read'].remove(chapter_id_to_delete)
                    if chapter_id_to_delete in user_data.get('pages', {}):
                         del user_data['pages'][chapter_id_to_delete]
                    
                    progress_data[user_id_str] = user_data 
                         
                f.seek(0)
                f.truncate()
                json.dump(progress_data, f, ensure_ascii=False, indent=4)
        except json.JSONDecodeError:
            logging.error("Error updating user progress during chapter deletion.")
            
        bot.send_message(chat_id, f"🗑️ Глава '{title}' (ID {chapter_id_to_delete}) успешно удалена.", reply_markup=types.ReplyKeyboardRemove())
        bot.send_message(chat_id, "Выберите следующее действие в админ-панели:", reply_markup=get_admin_menu_keyboard())
    else:
        logging.warning(f"[DELETE] Chapter {chapter_id_to_delete} NOT FOUND in data['chapters']!")
        bot.answer_callback_query(call.id, "Глава не найдена.", show_alert=True)
        bot.send_message(chat_id, "Возврат в админ-панель:", reply_markup=get_admin_menu_keyboard())

# --- FSM: УДАЛЕНИЕ ЧАСТИ ---

@bot.callback_query_handler(func=lambda call: call.data == "admin_delete_part_start")
def admin_delete_part_select(call):
    bot.answer_callback_query(call.id)
    if call.from_user.id not in ADMIN_IDS: return
    
    data = load_chapters_data()
    parts = data['parts']
    if not parts:
        bot.answer_callback_query(call.id, "Нет доступных частей для удаления.", show_alert=True)
        return

    markup = types.InlineKeyboardMarkup(row_width=1)
    for part_name in parts.keys():
        markup.add(types.InlineKeyboardButton(text=f"❌ {part_name}", callback_data=f"delete_part_{part_name}"))
    markup.add(types.InlineKeyboardButton(text="🚫 Отмена", callback_data="cancel"))
    bot.edit_message_text("Выберите **часть** для безвозвратного удаления:", call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("delete_part_"))
def handle_confirm_delete_part(call):
    bot.answer_callback_query(call.id)
    chat_id = call.message.chat.id
    part_name = call.data.replace("delete_part_", "")
    
    logging.info(f"[DELETE PART] Admin {chat_id} attempting to delete part name: '{part_name}'")

    data = load_chapters_data()
    if part_name in data['parts']:
        logging.info(f"[DELETE PART] Part '{part_name}' found, proceeding with deletion.")

        chapters_to_delete = data['parts'][part_name]
        
        for chap_id in chapters_to_delete:
            if chap_id in data['chapters']:
                del data['chapters'][chap_id]
                logging.info(f"[DELETE PART] Also removed associated chapter ID: {chap_id}")
        
        del data['parts'][part_name]
        
        save_chapters_data(data)

        try:
            with open(PROGRESS_FILE, 'r+', encoding='utf-8') as f:
                progress_data = json.load(f)
                for user_id_str in progress_data:
                    user_data = progress_data.get(user_id_str)
                    if isinstance(user_data, list):
                        user_data = {'read': user_data, 'pages': {}}
                    elif not isinstance(user_data, dict):
                         continue
                        
                    current_read_progress = set(user_data.get('read', []))
                    current_pages = user_data.get('pages', {})

                    ids_to_remove = set(chapters_to_delete)
                    
                    user_data['read'] = list(current_read_progress - ids_to_remove)
                    user_data['pages'] = {cid: page for cid, page in current_pages.items() if cid not in ids_to_remove}

                    progress_data[user_id_str] = user_data
                    
                f.seek(0)
                f.truncate()
                json.dump(progress_data, f, ensure_ascii=False, indent=4)
        except json.JSONDecodeError:
            logging.error("Error updating user progress during part deletion.")
        bot.send_message(chat_id, f"🗑️ Часть '{part_name}' и все входящие в нее главы **безвозвратно удалены**.", parse_mode="Markdown", reply_markup=types.ReplyKeyboardRemove())
        bot.send_message(chat_id, "Выберите следующее действие в админ-панели:", reply_markup=get_admin_menu_keyboard())
    else:
        logging.warning(f"[DELETE PART] Part '{part_name}' NOT FOUND!")
        bot.answer_callback_query(call.id, "Часть не найдена.", show_alert=True)
        bot.send_message(chat_id, "Возврат в админ-панель:", reply_markup=get_admin_menu_keyboard())
# --- ОБРАБОТЧИКИ ПОЛЬЗОВАТЕЛЬСКОЙ ЧАСТИ (ПОСТРАНИЧНОЕ ЧТЕНИЕ) ---

# ОБНОВЛЕННАЯ ФУНКЦИЯ send_chapter_page (С ИСПРАВЛЕНИЯМИ ДЛЯ FSM)
def send_chapter_page(chat_id, user_id, chapter_id_str, page_index, message_id=None, navigation_data=None):
    """Отправляет конкретную страницу главы."""
    data = load_chapters_data()
    if chapter_id_str not in data['chapters']:
        if message_id:
             try: bot.delete_message(chat_id, message_id)
             except: pass
             bot.send_message(chat_id, "Глава не найдена. Возврат в меню.", reply_markup=get_parts_keyboard(user_id))
        return

    chapter_data = data['chapters'][chapter_id_str]
    content = chapter_data['content']
    pages = paginate_content(content, CHAPTER_PAGE_SIZE) 
    total_pages = len(pages)

    if not (0 <= page_index < total_pages):
        bot.answer_callback_query(user_id, "Это первая или последняя страница.")
        return

    page_text = pages[page_index]
    title = chapter_data['title']
    
    # !!! ИСПРАВЛЕНИЕ #1: Сохраняем все навигационные данные в FSM !!!
    state_data_to_save = {
        'chapter_id': chapter_id_str, 
        'page': page_index, 
        'total_pages': total_pages, 
        'current_message_id': message_id
    }
    if navigation_data:
        state_data_to_save.update(navigation_data)
        
    set_state(chat_id, "READING_CHAPTER", data=state_data_to_save)
    
    read_progress_set, pages_dict = load_user_progress(user_id)
    pages_dict[chapter_id_str] = page_index
    save_user_progress(user_id, read_progress_set, pages_dict)

    keyboard = get_read_chapter_pagination_keyboard(chapter_id_str, page_index, total_pages)
    
    # Добавляем заголовок к каждой странице
    full_text = f"**{title}**\n\n{page_text}"

    if message_id:
        try:
            # Пытаемся отредактировать сообщение, если message_id известен
            bot.edit_message_text(
                full_text,
                chat_id,
                message_id,
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
        except telebot.apihelper.ApiTelegramException as e:
            if "message is not modified" not in str(e):
                logging.error(f"Failed to edit message text: {e}")
                # Если редактирование не удалось по другой причине, отправляем новое сообщение
                sent_message = bot.send_message(chat_id, full_text, reply_markup=keyboard, parse_mode="Markdown")
                # Обновляем message_id в состоянии FSM
                user_states[chat_id]['data']['current_message_id'] = sent_message.message_id
    else:
        # Если message_id не был передан (первый вход в главу), отправляем новое сообщение
        sent_message = bot.send_message(chat_id, full_text, reply_markup=keyboard, parse_mode="Markdown")
        # Обновляем message_id в состоянии FSM
        user_states[chat_id]['data']['current_message_id'] = sent_message.message_id

    if page_index == total_pages - 1:
        read_progress_set, pages_dict = load_user_progress(user_id)
        if chapter_id_str not in read_progress_set:
            read_progress_set.add(chapter_id_str)
            save_user_progress(user_id, read_progress_set, pages_dict)
            logging.info(f"User {user_id} marked chapter {chapter_id_str} as read upon finishing the last page.")
@bot.callback_query_handler(func=lambda call: call.data.startswith("read_"))
def read_chapter_callback(call):
    bot.answer_callback_query(call.id)
    chat_id = call.message.chat.id
    user_id = call.from_user.id
    chapter_id_str = call.data.replace("read_", "")
    
    start_page = get_user_read_page(user_id, chapter_id_str)

    # !!! ИСПРАВЛЕНИЕ #2: Передаем текущие навигационные данные в функцию чтения !!!
    # state_data содержит 'current_part_name' и 'current_group_index' из предыдущего состояния
    current_nav_data = get_state_data(chat_id) 
    
    # Передаем message_id текущего сообщения, чтобы его можно было отредактировать под чтение
    send_chapter_page(chat_id, user_id, chapter_id_str, start_page, call.message.message_id, navigation_data=current_nav_data)


@bot.callback_query_handler(func=lambda call: call.data.startswith("paginate_"))
def handle_pagination(call):
    chat_id = call.message.chat.id
    user_id = call.from_user.id
    parts = call.data.replace("paginate_", "").split('_')
    requested_page = int(parts[-1])
    chapter_id_str = "_".join(parts[:-1]) 
    
    # При пагинации мы знаем ID сообщения из callback.message.message_id. 
    # Также берем данные навигации из текущего состояния FSM (они там уже есть)
    current_nav_data = get_state_data(chat_id)

    send_chapter_page(chat_id, user_id, chapter_id_str, requested_page, call.message.message_id, navigation_data=current_nav_data)


# ИСПРАВЛЕННАЯ ФУНКЦИЯ back_to_chapter_list_callback
@bot.callback_query_handler(func=lambda call: call.data == "back_to_chapter_list")
def back_to_chapter_list_callback(call):
    bot.answer_callback_query(call.id)
    chat_id = call.message.chat.id
    user_id = call.from_user.id
    message_id = call.message.message_id
    
    state_data = get_state_data(chat_id)
    # Эти данные теперь гарантированно есть в состоянии 'READING_CHAPTER' благодаря исправлениям 1 и 2
    current_part_name = state_data.get('current_part_name')
    current_group_index = state_data.get('current_group_index')

    clear_state(chat_id) 

    if current_part_name and current_group_index is not None:
        # Возвращаемся к конкретному списку глав в группе через редактирование сообщения
        try:
            bot.edit_message_text(
                f"Выберите главу в части '{current_part_name}':",
                chat_id,
                message_id,
                reply_markup=get_chapters_in_group_keyboard(user_id, current_part_name, current_group_index)
            )
            # Важно: восстанавливаем состояние, чтобы следующие действия были корректны
            set_state(chat_id, "VIEWING_CHAPTERS_LIST", data={'current_part_name': current_part_name, 'current_group_index': current_group_index})
        except telebot.apihelper.ApiTelegramException as e:
            logging.error(f"Failed to edit message on back navigation to chapter list: {e}")
            # Если редактирование не сработало (например, сообщение слишком старое), отправляем новое сообщение
            bot.send_message(chat_id, f"Выберите главу в части '{current_part_name}':", reply_markup=get_chapters_in_group_keyboard(user_id, current_part_name, current_group_index))


    elif current_part_name:
         # Если индекс группы потерян, возвращаемся хотя бы к списку групп
         try:
            bot.edit_message_text(
                f"Выберите группу глав в части '{current_part_name}':",
                chat_id,
                message_id,
                reply_markup=get_groups_keyboard(user_id, current_part_name)
            )
            set_state(chat_id, "VIEWING_GROUPS", data={'current_part_name': current_part_name})
         except:
             bot.send_message(chat_id, f"Выберите группу глав в части '{current_part_name}':", reply_markup=get_groups_keyboard(user_id, current_part_name))


    else:
        # Если вся информация потеряна, отправляем новое сообщение в главное меню
        bot.send_message(chat_id, "Информация о предыдущем меню потеряна. Возврат в главное меню:", reply_markup=get_parts_keyboard(call.from_user.id))


@bot.callback_query_handler(func=lambda call: call.data.startswith("select_page_"))
def select_page_menu_callback(call):
    chat_id = call.message.chat.id
    
    parts = call.data.replace("select_page_", "").split('_')
    current_page = int(parts[-1])
    chapter_id = "_".join(parts[:-1])

    state_data = get_state_data(chat_id)
    total_pages = state_data.get('total_pages', 1)

    markup = types.InlineKeyboardMarkup(row_width=6)
    page_buttons = []
    for i in range(total_pages):
        btn_text = f"🔹{i+1}🔹" if i == current_page else str(i+1)
        page_buttons.append(types.InlineKeyboardButton(text=btn_text, callback_data=f"paginate_{chapter_id}_{i}"))
        
    markup.add(*page_buttons)
    markup.row(types.InlineKeyboardButton(text="◀️ Назад к чтению", callback_data=f"paginate_{chapter_id}_{current_page}"))
    
    try:
        bot.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=markup)
    except telebot.apihelper.ApiTelegramException as e:
        if "message is not modified" not in str(e):
            logging.error(f"Failed to show page selection menu: {e}")


@bot.callback_query_handler(func=lambda call: call.data.startswith("rate_"))
def handle_rating(call):
    user_id = call.from_user.id
    # ИСПРАВЛЕНИЕ ОШИБКИ: Правильное извлечение action и chapter_id
    parts = call.data.split('_', 2) 
    action = parts[1] # <-- ИСПРАВЛЕНО
    chapter_id = parts[2] # <-- ИСПРАВЛЕНО
    data = load_chapters_data()
    chapters = data['chapters']

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
        
        save_chapters_data(data)

        state_data = get_state_data(call.message.chat.id)
        if state_data.get('chapter_id') == chapter_id and state_data.get('page') is not None:
            current_page = state_data['page']
            total_pages = state_data['total_pages']
            try:
                bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=get_read_chapter_pagination_keyboard(chapter_id, current_page, total_pages))
            except telebot.apihelper.ApiTelegramException as e:
                if "message is not modified" not in str(e):
                    logging.error(f"Failed to edit message markup after rating: {e}")
    else:
        bot.answer_callback_query(call.id, "Глава не найдена. 😕", show_alert=True)

# --- НЕЗАВИСИМЫЕ ОБРАБОТЧИКИ ДЛЯ КНОПКИ "ОТМЕНА" (Гарантированное решение) ---

def process_cancellation(chat_id, message_id=None, is_text=False):
    """Центральная логика отмены для обоих обработчиков."""
    current_state = get_state(chat_id)
    
    if current_state:
        clear_state(chat_id)

    if is_text:
        bot.send_message(chat_id, "🚫 Действие отменено.", reply_markup=types.ReplyKeyboardRemove())
    else:
        if message_id:
            try:
                bot.edit_message_reply_markup(chat_id, message_id, reply_markup=None)
            except telebot.apihelper.ApiTelegramException:
                pass
        # Сообщение об отмене отправляем как новое
        bot.send_message(chat_id, "🚫 Действие отменено.")

    # Мы гарантируем возврат в меню, даже если FSM состояние было потеряно
    if chat_id in ADMIN_IDS:
        # Всегда возвращаем админа в админ-панель
        bot.send_message(chat_id, "Возврат в админ-панель:", reply_markup=get_admin_menu_keyboard())
    else:
        # Всегда возвращаем пользователя в главное меню
        # ИСПРАВЛЕНО: передаем только один аргумент message
        send_welcome_message(chat_id)


# 1. Обработчик текстового сообщения "🚫 Отмена" (Reply-клавиатура)
@bot.message_handler(content_types=['text'], func=lambda message: message.text == "🚫 Отмена")
def handle_text_cancel(message):
    process_cancellation(message.chat.id, message.message_id, is_text=True)

# 2. Обработчик Inline-кнопки с callback_data="cancel"
@bot.callback_query_handler(func=lambda call: call.data == "cancel")
def handle_callback_cancel(call):
    bot.answer_callback_query(call.id, "Действие отменено.")
    process_cancellation(call.message.chat.id, call.message.message_id, is_text=False)
    
# --- КОНЕЦ НЕЗАВИСИМЫХ ОБРАБОТЧИКОВ ---


# --- Запуск бота ---
if __name__ == '__main__':
    logging.info("Bot is starting up and polling...")
    load_config() 
    load_chapters_data()
    
    if not os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
            json.dump({}, f, ensure_ascii=False)
            
    bot.infinity_polling()
