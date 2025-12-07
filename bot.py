import telebot
import json
import logging
import os
import math
import textwrap # Добавлен модуль для более удобного переноса текста
from telebot import types

# --- КОНСТАНЫ С ВАШИМИ ДАННЫМИ ---
API_TOKEN = '8430418918:AAFljWxONqcsSnisTi1N7hjpr0afjxYg2Mc' 
ADMIN_IDS = [995375387,1081253267] # Замените на ваши ID администраторов
CHAPTERS_PER_GROUP = 10
CHAPTER_PAGE_SIZE = 850 # Уменьшил размер страницы для надежности
# ----------------------------------

DATA_FILE = 'chapters.json'
PROGRESS_FILE = 'user_progress.json'
CONFIG_FILE = 'config.json'

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Инициализация бота
bot = telebot.TeleBot(API_TOKEN)
user_states = {}

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
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump({"parts": {}, "chapters": {}}, f, ensure_ascii=False)
        return {"parts": {}, "chapters": {}}
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if 'parts' not in data: data['parts'] = {}
            if 'chapters' not in data: data['chapters'] = {}
            return data
    except json.JSONDecodeError:
        return {"parts": {}, "chapters": {}}

def save_chapters_data(data):
    """Сохраняет данные о главах и частях в JSON файл."""
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def load_user_progress(user_id):
    """Загружает прочитанные главы для конкретного пользователя."""
    if not os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
            json.dump({}, f, ensure_ascii=False)
        return set()
    try:
        with open(PROGRESS_FILE, 'r', encoding='utf-8') as f:
            progress_data = json.load(f)
            return set(progress_data.get(str(user_id), []))
    except json.JSONDecodeError:
        return set()

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
# --- Вспомогательные функции для состояний и длинных сообщений ---

def set_state(chat_id, state_name, data=None):
    user_states[chat_id] = {"state": state_name, "data": data or {}}
    # logging.info(f"Chat {chat_id} state set to: {state_name}")

def get_state(chat_id):
    return user_states.get(chat_id, {}).get("state")

def get_state_data(chat_id):
    return user_states.get(chat_id, {}).get("data", {})

def clear_state(chat_id):
    if chat_id in user_states:
        # logging.info(f"Chat {chat_id} state cleared.")
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
    
    # Сначала заменяем все переносы строк на один стандартный, чтобы textwrap работал предсказуемо
    normalized_content = content.replace('\r\n', '\n')
    
    # Разбиваем на абзацы
    paragraphs = normalized_content.split('\n\n')
    
    for para in paragraphs:
        if not para.strip():
            continue
            
        # Проверяем, поместится ли абзац на текущую страницу
        if len(current_page) + len(para) + 2 < page_size:
            current_page += (para + '\n\n')
        else:
            # Если не помещается, сохраняем текущую страницу и начинаем новую с этого абзаца
            if current_page:
                pages.append(current_page.strip())
            current_page = para + '\n\n'
    
    # Добавляем последнюю страницу
    if current_page.strip():
        pages.append(current_page.strip())
        
    # Страховка: если абзац сам по себе больше чем page_size (что маловероятно),
    # разбиваем его простым textwrap.wrap
    final_pages = []
    for page in pages:
        if len(page) > 4000: # Используем лимит API как верхний потолок
            final_pages.extend(textwrap.wrap(page, 4000))
        else:
            final_pages.append(page)
            
    return final_pages

# --- Клавиатуры (Трехуровневая навигация) ---

# Уровень 1: Клавиатура выбора частей
def get_parts_keyboard(user_id):
    data = load_chapters_data()
    parts = data['parts']
    read_progress = load_user_progress(user_id)
    markup = types.InlineKeyboardMarkup()
    
    if not parts:
        if user_id in ADMIN_IDS:
             markup.add(types.InlineKeyboardButton(text="🔑 Админ-панель", callback_data="open_admin_panel"))
        return markup 

    for part_name, chapter_ids in parts.items():
        all_read = all(str(chap_id) in read_progress for chap_id in chapter_ids)
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
    read_progress = load_user_progress(user_id)
    markup = types.InlineKeyboardMarkup()

    if not chapters_in_part:
        markup.add(types.InlineKeyboardButton(text="◀️ Назад", callback_data="user_menu"))
        return markup

    # Группируем ID глав по 10 штук
    total_chapters = len(chapters_in_part)
    total_groups = math.ceil(total_chapters / CHAPTERS_PER_GROUP)

    for group_index in range(total_groups):
        start_index = group_index * CHAPTERS_PER_GROUP
        end_index = min(start_index + CHAPTERS_PER_GROUP, total_chapters)
        
        group_ids = chapters_in_part[start_index:end_index]
        
        # Проверяем прогресс чтения для всей группы
        all_read = all(str(chap_id) in read_progress for chap_id in group_ids)
        
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
    read_progress = load_user_progress(user_id)
    markup = types.InlineKeyboardMarkup()
    
    group_index = int(group_index_str)
    start_index = group_index * CHAPTERS_PER_GROUP
    end_index = min(start_index + CHAPTERS_PER_GROUP, len(chapters_in_part))
    
    # Получаем ID глав для этой конкретной группы
    group_ids = chapters_in_part[start_index:end_index]

    for chap_id_str in group_ids:
        if chap_id_str in chapters_data:
            title = chapters_data[chap_id_str]['title']
            status_emoji = "✅" if chap_id_str in read_progress else "📖"
            # Используется только название из JSON, без добавления "Глава X:"
            button_text = f"{status_emoji} {title}"
            markup.add(types.InlineKeyboardButton(text=button_text, callback_data=f"read_{chap_id_str}"))

    # Кнопка назад к выбору групп
    back_to_groups_btn = types.InlineKeyboardButton(text=f"◀️ Назад", callback_data=f"show_groups_{part_name}")
    markup.add(back_to_groups_btn)
        
    return markup

def get_admin_menu_keyboard():
    markup = types.InlineKeyboardMarkup()
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
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(text="🚫 Отмена", callback_data="cancel"))
    return markup

def get_cancel_reply_keyboard():
    # Клавиатура ответа для FSM
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add("🚫 Отмена")
    return markup

def get_welcome_keyboard():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(text="📖 Перейти к главам", callback_data="user_menu"))
    return markup

# КЛАВИАТУРА ДЛЯ ПОСТРАНИЧНОГО ЧТЕНИЯ
def get_read_chapter_pagination_keyboard(chapter_id, current_page, total_pages):
    markup = types.InlineKeyboardMarkup(row_width=3)
    
    back_btn = types.InlineKeyboardButton(text="◀️ Назад", callback_data=f"paginate_{chapter_id}_{current_page - 1}")
    page_info_btn = types.InlineKeyboardButton(text=f"{current_page + 1}/{total_pages}", callback_data="page_info_placeholder")
    next_btn = types.InlineKeyboardButton(text="Далее ▶️", callback_data=f"paginate_{chapter_id}_{current_page + 1}")
    
    # Логика отключения кнопок, если это первая или последняя страница
    if current_page == 0:
        back_btn = types.InlineKeyboardButton(text=" ", callback_data="placeholder")
    if current_page == total_pages - 1:
        next_btn = types.InlineKeyboardButton(text=" ", callback_data="placeholder")
    
    markup.add(back_btn, page_info_btn, next_btn)

    # Добавляем кнопки оценок только на последней странице
    if current_page == total_pages - 1:
        data = load_chapters_data()
        chapters = data['chapters']
        # Убеждаемся, что глава существует в данных перед попыткой доступа
        if chapter_id in chapters:
            likes = chapters[chapter_id].get('likes', 0)
            dislikes = chapters[chapter_id].get('dislikes', 0)
            like_btn = types.InlineKeyboardButton(text=f"👍 ({likes})", callback_data=f"rate_like_{chapter_id}")
            dislike_btn = types.InlineKeyboardButton(text=f"👎 ({dislikes})", callback_data=f"rate_dislike_{chapter_id}")
            markup.add(like_btn, dislike_btn)
        
    # Кнопка возврата к списку глав в самом конце (добавлена на все страницы для удобства)
    back_to_list_btn = types.InlineKeyboardButton(text="📚 К списку глав", callback_data="back_to_chapter_list")
    markup.add(back_to_list_btn)
    
    return markup

# --- НОВЫЕ КЛАВИАТУРЫ АДМИНКИ (Пагинация для удаления/переименования) ---

# Уровень А1: Клавиатура выбора частей для удаления/переименования
def get_admin_parts_keyboard(action_prefix):
    # action_prefix может быть 'admin_show_groups_delete_' или 'admin_show_groups_rename_'
    data = load_chapters_data()
    parts = data['parts']
    markup = types.InlineKeyboardMarkup()
    if not parts:
        markup.add(types.InlineKeyboardButton(text="◀️ Назад в админку", callback_data="open_admin_panel"))
        return markup 
    for part_name in parts.keys():
        markup.add(types.InlineKeyboardButton(text=f"📚 {part_name}", callback_data=f"{action_prefix}{part_name}"))
    markup.add(types.InlineKeyboardButton(text="🚫 Отмена", callback_data="cancel"))
    return markup

# Уровень А2: Клавиатура выбора групп глав внутри части для удаления/переименования
def get_admin_groups_keyboard(part_name, action_prefix):
    # action_prefix может быть 'admin_show_chapters_delete_group_' или 'admin_show_chapters_rename_group_'
    data = load_chapters_data()
    chapters_in_part = data['parts'].get(part_name, [])
    markup = types.InlineKeyboardMarkup()

    if not chapters_in_part:
        # Улучшенная логика "Назад"
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
    # action_prefix теперь ТОЛЬКО 'delete_chapter_' или 'admin_rename_chapter_select_'
    data = load_chapters_data()
    chapters_data = data['chapters']
    chapters_in_part = data['parts'].get(part_name, [])
    markup = types.InlineKeyboardMarkup()
    
    group_index = int(group_index_str)
    start_index = group_index * CHAPTERS_PER_GROUP
    end_index = min(start_index + CHAPTERS_PER_GROUP, len(chapters_in_part))
    group_ids = chapters_in_part[start_index:end_index]

    for chap_id_str in group_ids:
        if chap_id_str in chapters_data:
            title = chapters_data[chap_id_str]['title']
            # callback_data: delete_chapter_CHAPTER_ID или admin_rename_chapter_select_CHAPTER_ID
            markup.add(types.InlineKeyboardButton(text=f"{chap_id_str}: {title}", callback_data=f"{action_prefix}{chap_id_str}"))

    # Кнопка назад к выбору групп
    # Определяем правильный callback для кнопки "Назад" в зависимости от префикса действия
    if 'delete' in action_prefix:
        back_callback = f"admin_show_groups_delete_{part_name}"
    elif 'rename' in action_prefix:
        back_callback = f"admin_show_groups_rename_{part_name}"
    else:
        back_callback = "open_admin_panel" # Fallback

    back_to_groups_btn = types.InlineKeyboardButton(text=f"◀️ Назад к группам", callback_data=back_callback)
    markup.add(back_to_groups_btn)
        
    return markup

# --- Основные обработчики команд и сообщений (Обновленные) ---

def cancel_handler_callback_message(message):
    # Универсальный обработчик отмены через текстовое сообщение
    chat_id = message.chat.id
    current_state = get_state(chat_id)
    if current_state:
        clear_state(chat_id)
        bot.send_message(chat_id, "🚫 Действие отменено.", reply_markup=types.ReplyKeyboardRemove())
        if chat_id in ADMIN_IDS:
             bot.send_message(chat_id, "Возврат в админ-панель:", reply_markup=get_admin_menu_keyboard())
        else:
             send_welcome_message(chat_id, chat_id)
    
def send_welcome_message(chat_id, user_id):
    clear_state(chat_id)
    config = load_config()
    welcome_text = config.get("welcome_text", "👋 Привет!")
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

# ОБНОВЛЕНО: user_menu показывает ЧАСТИ
@bot.callback_query_handler(func=lambda call: call.data == "user_menu")
def back_to_user_menu_callback(call):
    bot.answer_callback_query(call.id)
    clear_state(call.message.chat.id)
    bot.edit_message_text("Выберите часть:", call.message.chat.id, call.message.message_id, reply_markup=get_parts_keyboard(call.from_user.id))
# ОБРАБОТЧИК: Открытие групп внутри части (Уровень 2)
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
    # Сохраняем текущую часть в состояние для удобства навигации
    set_state(call.message.chat.id, "VIEWING_GROUPS", data={'current_part_name': part_name})
# ОБРАБОТЧИК: Открытие списка глав внутри группы (Уровень 3)
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
    # Сохраняем текущую часть в состояние для удобства навигации
    # Обновляем состояние, чтобы при возврате из чтения главы знать куда вернуться
    set_state(call.message.chat.id, "VIEWING_CHAPTERS_LIST", data={'current_part_name': part_name, 'current_group_index': group_index})


# --- ОБРАБОТЧИКИ НАВИГАЦИИ АДМИНКИ (Удаление/Переименование с пагинацией) ---

# Удаление: Шаг 1.1: Выбор части
@bot.callback_query_handler(func=lambda call: call.data == "admin_delete_chapter_select_part")
def admin_delete_chapter_select_part_callback(call):
    bot.answer_callback_query(call.id)
    bot.edit_message_text("Выберите часть, из которой хотите удалить главу:", call.message.chat.id, call.message.message_id, reply_markup=get_admin_parts_keyboard("admin_show_groups_delete_"))

# Удаление: Шаг 1.2: Выбор группы глав в части
@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_show_groups_delete_"))
def admin_delete_show_groups_callback(call):
    bot.answer_callback_query(call.id)
    part_name = call.data.replace("admin_show_groups_delete_", "")
    bot.edit_message_text("Выберите группу глав:", call.message.chat.id, call.message.message_id, reply_markup=get_admin_groups_keyboard(part_name, "admin_show_chapters_delete_group_"))

# Удаление: Шаг 1.3: Выбор конкретной главы в группе (с пагинацией)
@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_show_chapters_delete_group_"))
def admin_delete_show_chapters_callback(call):
    bot.answer_callback_query(call.id)
    parts_data = call.data.replace("admin_show_chapters_delete_group_", "").split('_')
    group_index = parts_data[-1]
    part_name = "_".join(parts_data[:-1])
    # ИСПРАВЛЕНО ЗДЕСЬ: Префикс изменен на "delete_chapter_"
    bot.edit_message_text("Выберите главу для **удаления** (показ по 10 шт.):", call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=get_admin_chapters_in_group_keyboard(part_name, group_index, "delete_chapter_"))

# Переименование: Шаг 1.1: Выбор части (Начало FSM)
@bot.callback_query_handler(func=lambda call: call.data == "admin_rename_chapter_start")
def admin_rename_chapter_select_part_callback(call):
    bot.answer_callback_query(call.id)
    bot.edit_message_text("Выберите часть, в которой находится глава для переименования:", call.message.chat.id, call.message.message_id, reply_markup=get_admin_parts_keyboard("admin_show_groups_rename_"))

# Переименование: Шаг 1.2: Выбор группы глав в части
@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_show_groups_rename_"))
def admin_rename_show_groups_callback(call):
    bot.answer_callback_query(call.id)
    part_name = call.data.replace("admin_show_groups_rename_", "")
    bot.edit_message_text("Выберите группу глав:", call.message.chat.id, call.message.message_id, reply_markup=get_admin_groups_keyboard(part_name, "admin_show_chapters_rename_group_"))

# Переименование: Шаг 1.3: Выбор конкретной главы в группе
@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_show_chapters_rename_group_"))
def admin_rename_show_chapters_callback(call):
    bot.answer_callback_query(call.id)
    parts_data = call.data.replace("admin_show_chapters_rename_group_", "").split('_')
    group_index = parts_data[-1]
    part_name = "_".join(parts_data[:-1])
    bot.edit_message_text("Выберите главу для **переименования**:", call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=get_admin_chapters_in_group_keyboard(part_name, group_index, "admin_rename_chapter_select_"))
# НОВЫЕ ОБРАБОТЧИКИ АДМИНКИ (Работа с частями)

# 1. Добавление новой части - ШАГ 1 (Имя)
@bot.callback_query_handler(func=lambda call: call.data == "admin_add_part")
def admin_add_part_start_callback(call):
    bot.answer_callback_query(call.id)
    if call.from_user.id not in ADMIN_IDS: return
    
    bot.edit_message_text("✏️ Введите название новой **части** (например, 'Том 1' или 'Часть 1'):", call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=get_cancel_keyboard())
    set_state(call.message.chat.id, "WAITING_FOR_NEW_PART_NAME")

# 1. Добавление новой части - ШАГ 2 (Сохранение)
@bot.message_handler(func=lambda message: get_state(message.chat.id) == "WAITING_FOR_NEW_PART_NAME")
def handle_new_part_name_input(message):
    chat_id = message.chat.id
    if message.text in ["🚫 Отмена", "/cancel"]: 
        return cancel_handler_callback_message(message)
    
    part_name = message.text.strip()
    data = load_chapters_data()
    
    if part_name in data['parts']:
         bot.send_message(chat_id, "Такое название части уже существует. Попробуйте другое.", reply_markup=get_cancel_keyboard())
         return

    data['parts'][part_name] = [] # Инициализируем пустым списком ID глав
    save_chapters_data(data)
    clear_state(chat_id)
    bot.send_message(chat_id, f"✅ Часть **'{part_name}'** успешно добавлена!", parse_mode="Markdown", reply_markup=types.ReplyKeyboardRemove())
    bot.send_message(chat_id, "Выберите следующее действие:", reply_markup=get_admin_menu_keyboard())


# 2. Изменение названия части - ШАГ 1 (Выбор части)
@bot.callback_query_handler(func=lambda call: call.data == "admin_edit_part_name_start")
def admin_edit_part_name_select(call):
    bot.answer_callback_query(call.id)
    if call.from_user.id not in ADMIN_IDS: return
    
    data = load_chapters_data()
    parts = data['parts']
    if not parts:
        bot.answer_callback_query(call.id, "Нет доступных частей для редактирования.", show_alert=True)
        return

    markup = types.InlineKeyboardMarkup()
    for part_name in parts.keys():
        markup.add(types.InlineKeyboardButton(text=f"✏️ {part_name}", callback_data=f"select_edit_part_name_{part_name}"))
    markup.add(types.InlineKeyboardButton(text="🚫 Отмена", callback_data="cancel"))
    bot.edit_message_text("Выберите часть, название которой хотите изменить:", call.message.chat.id, call.message.message_id, reply_markup=markup)

# 2. Изменение названия части - ШАГ 2 (Ввод нового имени)
@bot.callback_query_handler(func=lambda call: call.data.startswith("select_edit_part_name_"))
def admin_edit_part_name_input_start(call):
    bot.answer_callback_query(call.id)
    chat_id = call.message.chat.id
    old_part_name = call.data.replace("select_edit_part_name_", "") 
    
    set_state(chat_id, "WAITING_FOR_NEW_PART_NAME_EDIT", data={'old_part_name': old_part_name})
    bot.send_message(chat_id, f"Введите новое название для части '{old_part_name}':", reply_markup=get_cancel_reply_keyboard())
    bot.delete_message(chat_id, call.message.message_id)

# 2. Изменение названия части - ШАГ 3 (Сохранение нового имени)
@bot.message_handler(func=lambda message: get_state(message.chat.id) == "WAITING_FOR_NEW_PART_NAME_EDIT")
def handle_new_part_name_edit_input(message):
    chat_id = message.chat.id
    if message.text == "🚫 Отмена": return cancel_handler_callback_message(message)

    new_part_name = message.text.strip()
    user_data = get_state_data(chat_id)
    old_part_name = user_data['old_part_name']
    
    data = load_chapters_data()

    if new_part_name in data['parts']:
        bot.send_message(chat_id, "Такое название уже существует. Попробуйте другое.", reply_markup=get_cancel_reply_keyboard())
        return
        
    data['parts'][new_part_name] = data['parts'].pop(old_part_name)
    save_chapters_data(data)

    clear_state(chat_id)
    bot.send_message(chat_id, f"✅ Название части успешно обновлено на '{new_part_name}'.", reply_markup=types.ReplyKeyboardRemove())
    bot.send_message(chat_id, "Выберите следующее действие в админ-панели:", reply_markup=get_admin_menu_keyboard())
# 3. Добавление главы в существующую часть - ШАГ 1 (Выбор части)
@bot.callback_query_handler(func=lambda call: call.data == "admin_add_chapter_to_part_start")
def admin_add_chapter_select_part(call):
    bot.answer_callback_query(call.id)
    if call.from_user.id not in ADMIN_IDS: return

    data = load_chapters_data()
    parts = data['parts']
    if not parts:
        bot.answer_callback_query(call.id, "Нет доступных частей. Сначала добавьте часть.", show_alert=True)
        return

    markup = types.InlineKeyboardMarkup()
    for part_name in parts.keys():
        markup.add(types.InlineKeyboardButton(text=f"➕ {part_name}", callback_data=f"select_part_for_chapter_{part_name}"))
    markup.add(types.InlineKeyboardButton(text="🚫 Отмена", callback_data="cancel"))
    bot.edit_message_text("Выберите часть, в которую хотите добавить главу:", call.message.chat.id, call.message.message_id, reply_markup=markup)

# 3. Добавление главы в существующую часть - ШАГ 2 (Ввод ID главы)
@bot.callback_query_handler(func=lambda call: call.data.startswith("select_part_for_chapter_"))
def admin_add_chapter_enter_id(call):
    bot.answer_callback_query(call.id)
    chat_id = call.message.chat.id
    part_name = call.data.replace("select_part_for_chapter_", "")

    set_state(chat_id, "WAITING_FOR_CHAPTER_ID_FOR_ADD", data={'target_part_name': part_name})
    bot.send_message(chat_id, f"Выбрана часть '{part_name}'. Введите **уникальный ID** 🔢 новой главы (например, '150'):", parse_mode="Markdown", reply_markup=get_cancel_reply_keyboard())
    bot.delete_message(chat_id, call.message.message_id)
# 3. Добавление главы - ШАГ 3 (Title)
@bot.message_handler(func=lambda message: get_state(message.chat.id) == "WAITING_FOR_CHAPTER_ID_FOR_ADD")
def handle_add_chapter_id_input(message):
    chat_id = message.chat.id
    if message.text == "🚫 Отмена": return cancel_handler_callback_message(message)
    chapter_id = message.text.strip()
    
    if not chapter_id.isdigit():
        bot.send_message(chat_id, "ID должен быть числом 🔢. Попробуйте снова.", reply_markup=get_cancel_reply_keyboard())
        return
    
    data = load_chapters_data()
    if chapter_id in data['chapters']:
         bot.send_message(chat_id, "Такой ID уже существует. Выберите другой.", reply_markup=get_cancel_reply_keyboard())
         return

    user_data = get_state_data(chat_id)
    user_data['current_chapter_id'] = chapter_id
    set_state(chat_id, "WAITING_FOR_TITLE_FOR_ADD", data=user_data)
    bot.send_message(chat_id, f"ID {chapter_id} принят. Теперь введите **название** ✏️ новой главы:", parse_mode="Markdown", reply_markup=get_cancel_reply_keyboard())

# 3. Добавление главы - ШАГ 4 (Content - Ожидание файла/текста)
@bot.message_handler(func=lambda message: get_state(message.chat.id) == "WAITING_FOR_TITLE_FOR_ADD")
def handle_add_title_input(message):
    chat_id = message.chat.id
    if message.text == "🚫 Отмена": return cancel_handler_callback_message(message)
    title = message.text
    data = get_state_data(chat_id)
    data['new_title'] = title
    set_state(chat_id, "WAITING_FOR_CONTENT_FILE_FOR_ADD", data=data) 
    bot.send_message(chat_id, f"Название принято ✅. Теперь **отправьте содержание как текстовый файл (.txt)** 📝, или введите текст (текст может быть очень длинным).", parse_mode="Markdown", reply_markup=get_cancel_reply_keyboard())

# 3. Добавление главы - ШАГ 5 (Сохранение файла/текста и привязка к части)
@bot.message_handler(content_types=['text', 'document'], func=lambda message: get_state(message.chat.id) == "WAITING_FOR_CONTENT_FILE_FOR_ADD")
def handle_add_content_input(message):
    chat_id = message.chat.id
    if message.content_type == 'text' and message.text == "🚫 Отмена":
        # Используем универсальный обработчик отмены
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
    target_part_name = user_data['target_part_name']
    
    data = load_chapters_data()
    # Добавляем главу в общий список глав
    data['chapters'][chapter_id] = {"title": title, "content": content, "likes": 0, "dislikes": 0, "rated_by": []}
    # Привязываем ID главы к нужной части
    if target_part_name in data['parts']:
        data['parts'][target_part_name].append(chapter_id)
    
    save_chapters_data(data)

    bot.send_message(chat_id, f"🎉 Глава {chapter_id} ('{title}') успешно **добавлена** в часть '{target_part_name}'!", parse_mode="Markdown", reply_markup=types.ReplyKeyboardRemove())
    clear_state(chat_id)
    bot.send_message(chat_id, "Выберите следующее действие в админ-панели 👇:", reply_markup=get_admin_menu_keyboard())

# 4. Удаление главы - Логика выбора и подтверждения (ИСПРАВЛЕНО: Префикс изменен на delete_chapter_)

@bot.callback_query_handler(func=lambda call: call.data.startswith("delete_chapter_"))
def handle_confirm_delete_chapter(call):
    bot.answer_callback_query(call.id)
    chat_id = call.message.chat.id
    chapter_id = call.data.replace("delete_chapter_", "")
    
    # --- ЛОГИРОВАНИЕ ДЛЯ ОТЛАДКИ ---
    logging.info(f"[DELETE] Admin {chat_id} attempting to delete chapter ID: {chapter_id}")
    
    data = load_chapters_data()
    chapters = data['chapters']
    parts = data['parts']

    if chapter_id in chapters:
        logging.info(f"[DELETE] Chapter {chapter_id} found, proceeding with deletion.")
        title = chapters[chapter_id]['title']
        
        # Удаляем главу из списка chapters
        del data['chapters'][chapter_id]
        
        # Удаляем ID главы из соответствующего списка в parts
        for part_name in parts:
            if chapter_id in parts[part_name]:
                parts[part_name].remove(chapter_id)
                logging.info(f"[DELETE] Removed chapter {chapter_id} from part '{part_name}'.")
                break
        
        save_chapters_data(data)
        
        bot.send_message(chat_id, f"🗑️ Глава '{title}' (ID {chapter_id}) успешно удалена.", reply_markup=types.ReplyKeyboardRemove())
        bot.send_message(chat_id, "Выберите следующее действие в админ-панели:", reply_markup=get_admin_menu_keyboard())
    else:
        logging.warning(f"[DELETE] Chapter {chapter_id} NOT FOUND in data['chapters']!")
        bot.answer_callback_query(call.id, "Глава не найдена.", show_alert=True)
        bot.send_message(chat_id, "Возврат в админ-панель:", reply_markup=get_admin_menu_keyboard())
# --- FSM: УДАЛЕНИЕ ЧАСТИ (ИСПРАВЛЕН ПРЕФИКС КОЛБЭКА) ---

# 5. Удаление части - Шаг 1 (Выбор части)
@bot.callback_query_handler(func=lambda call: call.data == "admin_delete_part_start")
def admin_delete_part_select(call):
    bot.answer_callback_query(call.id)
    if call.from_user.id not in ADMIN_IDS: return
    
    data = load_chapters_data()
    parts = data['parts']
    if not parts:
        bot.answer_callback_query(call.id, "Нет доступных частей для удаления.", show_alert=True)
        return

    markup = types.InlineKeyboardMarkup()
    for part_name in parts.keys():
        # ИСПРАВЛЕНО ЗДЕСЬ: Новый уникальный префикс callback_data для части - delete_part_
        markup.add(types.InlineKeyboardButton(text=f"❌ {part_name}", callback_data=f"delete_part_{part_name}"))
    markup.add(types.InlineKeyboardButton(text="🚫 Отмена", callback_data="cancel"))
    bot.edit_message_text("Выберите **часть** для безвозвратного удаления:", call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)

# 5. Удаление части - Шаг 2 (Подтверждение и удаление)
# НОВЫЙ ОБРАБОТЧИК ДЛЯ УДАЛЕНИЯ ЧАСТИ (использует delete_part_)
@bot.callback_query_handler(func=lambda call: call.data.startswith("delete_part_"))
def handle_confirm_delete_part(call):
    bot.answer_callback_query(call.id)
    chat_id = call.message.chat.id
    # Используем новый префикс для замены
    part_name = call.data.replace("delete_part_", "")
    
    # --- ЛОГИРОВАНИЕ ДЛЯ ОТЛАДКИ УДАЛЕНИЯ ЧАСТИ ---
    logging.info(f"[DELETE PART] Admin {chat_id} attempting to delete part name: '{part_name}'")

    data = load_chapters_data()
    if part_name in data['parts']:
        logging.info(f"[DELETE PART] Part '{part_name}' found, proceeding with deletion.")

        chapters_to_delete = data['parts'][part_name]
        
        # 1. Удаляем все главы, которые были внутри этой части
        for chap_id in chapters_to_delete:
            if chap_id in data['chapters']:
                del data['chapters'][chap_id]
                logging.info(f"[DELETE PART] Also removed associated chapter ID: {chap_id}")
        
        # 2. Удаляем саму часть
        del data['parts'][part_name]
        
        save_chapters_data(data)
        
        bot.send_message(chat_id, f"🗑️ Часть '{part_name}' и все входящие в нее главы **безвозвратно удалены**.", parse_mode="Markdown", reply_markup=types.ReplyKeyboardRemove())
        bot.send_message(chat_id, "Выберите следующее действие в админ-панели:", reply_markup=get_admin_menu_keyboard())
    else:
        logging.warning(f"[DELETE PART] Part '{part_name}' NOT FOUND!")
        bot.answer_callback_query(call.id, "Часть не найдена.", show_alert=True)
        bot.send_message(chat_id, "Возврат в админ-панель:", reply_markup=get_admin_menu_keyboard())


# --- FSM: ПЕРЕИМЕНОВАНИЕ ГЛАВЫ ---

# 6. Переименование главы - Шаг 3 (Ввод нового названия)
@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_rename_chapter_select_"))
def admin_rename_chapter_enter_new_title(call):
    bot.answer_callback_query(call.id)
    chat_id = call.message.chat.id
    chapter_id = call.data.replace("admin_rename_chapter_select_", "")

    data = load_chapters_data()
    if chapter_id not in data['chapters']:
        bot.send_message(chat_id, "Глава не найдена.")
        return cancel_handler_callback_message(call.message)

    current_title = data['chapters'][chapter_id]['title']
    
    set_state(chat_id, "WAITING_FOR_NEW_CHAPTER_TITLE", data={'chapter_id': chapter_id, 'old_title': current_title})
    bot.send_message(chat_id, f"Текущее название: **'{current_title}'**. Введите новое название для главы ID {chapter_id}:", parse_mode="Markdown", reply_markup=get_cancel_reply_keyboard())
    bot.delete_message(chat_id, call.message.message_id)

# 6. Переименование главы - Шаг 4 (Сохранение нового названия)
@bot.message_handler(func=lambda message: get_state(message.chat.id) == "WAITING_FOR_NEW_CHAPTER_TITLE")
def handle_new_chapter_title_input(message):
    chat_id = message.chat.id
    if message.text == "🚫 Отмена": return cancel_handler_callback_message(message)
    
    new_title = message.text.strip()
    user_data = get_state_data(chat_id)
    chapter_id = user_data['chapter_id']
    old_title = user_data['old_title']

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

@bot.callback_query_handler(func=lambda call: call.data == "admin_edit_welcome_text")
def admin_edit_welcome_text_start(call):
    bot.answer_callback_query(call.id)
    if call.from_user.id not in ADMIN_IDS: return

    config = load_config()
    current_text = config.get("welcome_text", "Текст не установлен.")

    set_state(call.message.chat.id, "WAITING_FOR_NEW_WELCOME_TEXT")
    bot.send_message(call.message.chat.id, f"Текущий текст приветствия:\n\n{current_text}\n\nВведите новый текст приветствия (поддерживает Markdown):", reply_markup=get_cancel_reply_keyboard(), parse_mode="Markdown")
    bot.delete_message(call.message.chat.id, call.message.message_id)

@bot.message_handler(func=lambda message: get_state(message.chat.id) == "WAITING_FOR_NEW_WELCOME_TEXT")
def handle_new_welcome_text_input(message):
    chat_id = message.chat.id
    if message.text == "🚫 Отмена": return cancel_handler_callback_message(message)
    
    new_text = message.text
    config = load_config()
    config["welcome_text"] = new_text
    save_config(config)

    clear_state(chat_id)
    bot.send_message(chat_id, f"✅ Текст приветствия успешно обновлен.", reply_markup=types.ReplyKeyboardRemove())
    bot.send_message(chat_id, "Выберите следующее действие в админ-панели:", reply_markup=get_admin_menu_keyboard())


# --- ОБРАБОТЧИКИ ПОЛЬЗОВАТЕЛЬСКОЙ ЧАСТИ (ПОСТРАНИЧНОЕ ЧТЕНИЕ) ---

def send_chapter_page(chat_id, user_id, chapter_id_str, page_index, message_id=None):
    """Отправляет конкретную страницу главы."""
    data = load_chapters_data()
    if chapter_id_str not in data['chapters']:
        # Если глава не найдена, отправляем пользователя в меню, не редактируя сообщение
        if message_id:
             bot.send_message(chat_id, "Глава не найдена. Возврат в меню.", reply_markup=get_parts_keyboard(user_id))
             try: bot.delete_message(chat_id, message_id)
             except: pass
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
    
    # Сохраняем текущее состояние страницы для пользователя
    set_state(chat_id, "READING_CHAPTER", data={'chapter_id': chapter_id_str, 'page': page_index, 'total_pages': total_pages, 'current_message_id': message_id})

    keyboard = get_read_chapter_pagination_keyboard(chapter_id_str, page_index, total_pages)
    # Форматируем заголовок только для первой страницы или если страница одна
    if total_pages == 1 or page_index == 0:
         full_text = f"**{title}**\n\n{page_text}"
    else:
         full_text = page_text # После первой страницы отправляем только контент

    # Логика отправки/редактирования сообщения
    if message_id:
        try:
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
            bot.answer_callback_query(user_id, "Сообщение не изменено.")
    else:
        # Отправляем новое сообщение (при первом открытии главы)
        sent_message = bot.send_message(chat_id, full_text, reply_markup=keyboard, parse_mode="Markdown")
        # Сохраняем ID нового сообщения в состояние для будущих правок
        user_states[chat_id]['data']['current_message_id'] = sent_message.message_id


    # Если это последняя страница, отмечаем главу как прочитанную
    if page_index == total_pages - 1:
        read_progress = load_user_progress(user_id)
        if chapter_id_str not in read_progress:
            read_progress.add(chapter_id_str)
            save_user_progress(user_id, read_progress)
            logging.info(f"User {user_id} marked chapter {chapter_id_str} as read upon finishing the last page.")


@bot.callback_query_handler(func=lambda call: call.data.startswith("read_"))
def read_chapter_callback(call):
    bot.answer_callback_query(call.id)
    chat_id = call.message.chat.id
    user_id = call.from_user.id
    chapter_id_str = call.data.replace("read_", "")
    
    # Запускаем отображение с первой страницы (index 0)
    # ID сообщения не передаем, т.к. создаем новое, а старое (список глав) удаляем
    send_chapter_page(chat_id, user_id, chapter_id_str, 0)
    
    # Удаляем предыдущее сообщение со списком глав, чтобы не дублировать интерфейс
    try:
        bot.delete_message(chat_id, call.message.message_id)
    except Exception as e:
        logging.info(f"Could not delete chapter list message: {e}")


@bot.callback_query_handler(func=lambda call: call.data.startswith("paginate_"))
def handle_pagination(call):
    bot.answer_callback_query(call.id)
    chat_id = call.message.chat.id
    user_id = call.from_user.id
    # callback_data format: paginate_CHAPTER_ID_PAGE_INDEX
    parts = call.data.replace("paginate_", "").split('_')
    requested_page = int(parts[-1])
    chapter_id_str = "_".join(parts[:-1]) # Собираем обратно ID, если он содержал подчеркивания

    # Отправляем запрошенную страницу, редактируя текущее сообщение
    send_chapter_page(chat_id, user_id, chapter_id_str, requested_page, call.message.message_id)


@bot.callback_query_handler(func=lambda call: call.data == "back_to_chapter_list")
def back_to_chapter_list_callback(call):
    bot.answer_callback_query(call.id)
    chat_id = call.message.chat.id
    
    # Пытаемся получить информацию о текущей части/группе из состояния
    state_data = get_state_data(chat_id)
    current_part_name = state_data.get('current_part_name')
    
    clear_state(chat_id) # Очищаем состояние чтения главы

    if current_part_name:
        # Если состояние найдено, возвращаемся к списку групп для этой части
        user_id = call.from_user.id
        # Отправляем новое сообщение с клавиатурой групп
        bot.send_message(
            chat_id, 
            "Выберите главу:", 
            reply_markup=get_groups_keyboard(user_id, current_part_name)
        )
    else:
        # Если состояние потеряно (например, бот перезапустился), отправляем в основное меню
        bot.send_message(chat_id, "Информация о предыдущем меню потеряна. Возврат в главное меню:", reply_markup=get_parts_keyboard(call.from_user.id))

    # Удаляем сообщение с пагинацией/лайками, чтобы не засорять чат
    try:
        bot.delete_message(chat_id, call.message.message_id)
    except Exception as e:
        logging.error(f"Failed to delete message on back navigation: {e}")


@bot.callback_query_handler(func=lambda call: call.data.startswith("rate_"))
def handle_rating(call):
    user_id = call.from_user.id
    action, chapter_id = call.data.replace("rate_", "").split('_', 1)
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
        
        save_chapters_data(data) # Сохраняем обновленные данные

        # Обновляем кнопки с новыми счетчиками на текущей (последней) странице
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

# --- Запуск бота ---
if __name__ == '__main__':
    logging.info("Bot is starting up and polling...")
    # Убеждаемся, что файлы существуют при старте
    load_config() # Инициализация файла конфига
    load_chapters_data()
    
    if not os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
            json.dump({}, f, ensure_ascii=False)
            
    bot.infinity_polling()
