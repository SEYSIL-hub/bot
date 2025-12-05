import telebot
import json
import logging
import os
import math
from telebot import types

# --- КОНСТАНТЫ С ВАШИМИ ДАННЫМИ ---
# Убедитесь, что переменная окружения TG_TOKEN установлена в вашей системе
API_TOKEN = '8430418918:AAFljWxONqcsSnisTi1N7hjpr0afjxYg2Mc' 
ADMIN_IDS = [995375387,1081253267] # Замените на ваши ID администраторов
# Размер группы глав (второй уровень меню)
CHAPTERS_PER_GROUP = 10
# ----------------------------------

DATA_FILE = 'chapters.json'
PROGRESS_FILE = 'user_progress.json'

logging.basicConfig(level=logging.INFO)

# Инициализация бота
bot = telebot.TeleBot(API_TOKEN)
# user_states будет хранить текущую выбранную часть/группу для навигации
user_states = {}

# --- Функции для работы с данными (JSON) ---

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

def get_state(chat_id):
    return user_states.get(chat_id, {}).get("state")

def get_state_data(chat_id):
    return user_states.get(chat_id, {}).get("data", {})

def clear_state(chat_id):
    if chat_id in user_states:
        del user_states[chat_id]

def send_long_message(chat_id, text, parse_mode=None):
    """Автоматически разбивает и отправляет текст частями."""
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

# Уровень 2: Клавиатура выбора групп глав внутри части (по 20 шт)
def get_groups_keyboard(user_id, part_name):
    data = load_chapters_data()
    chapters_in_part = data['parts'].get(part_name, [])
    read_progress = load_user_progress(user_id)
    markup = types.InlineKeyboardMarkup()

    if not chapters_in_part:
        markup.add(types.InlineKeyboardButton(text="◀️ Назад", callback_data="user_menu"))
        return markup

    # Группируем ID глав по 20 штук
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

        # callback_data: show_chapters_ЧастьНазвание_ИндексГруппы
        markup.add(types.InlineKeyboardButton(text=button_text, callback_data=f"show_chapters_{part_name}_{group_index}"))

    # Добавляем кнопки навигации (назад к частям)
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
    # Новые кнопки админки для управления частями/главами
    markup.add(types.InlineKeyboardButton(text="➕ Добавить новую часть", callback_data="admin_add_part"))
    markup.add(types.InlineKeyboardButton(text="✏️ Изменить название части", callback_data="admin_edit_part_name_start"))
    markup.add(types.InlineKeyboardButton(text="➕ Добавить главу", callback_data="admin_add_chapter_to_part_start"))
    markup.add(types.InlineKeyboardButton(text="❌ Удалить главу", callback_data=f"admin_delete_chapter_start"))
    markup.add(types.InlineKeyboardButton(text="⬅️ Назад", callback_data="user_menu"))
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
    data = load_chapters_data()
    chapters = data['chapters']
    if chapter_id not in chapters:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton(text="◀️ Назад", callback_data="user_menu"))
        return markup
        
    likes = chapters[chapter_id].get('likes', 0)
    dislikes = chapters[chapter_id].get('dislikes', 0)

    markup = types.InlineKeyboardMarkup(row_width=2)
    like_btn = types.InlineKeyboardButton(text=f"👍 ({likes})", callback_data=f"rate_like_{chapter_id}")
    dislike_btn = types.InlineKeyboardButton(text=f"👎 ({dislikes})", callback_data=f"rate_dislike_{chapter_id}")
    # Кнопка возврата к списку глав
    back_btn = types.InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_chapter_list")
    
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
    welcome_text = "👋 Привет! Это ваш бот для чтения глав."
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
     # Сохраняем текущую часть и группу в состояние для удобства навигации
    set_state(call.message.chat.id, "VIEWING_CHAPTERS", data={'current_part_name': part_name, 'current_group_index': group_index, 'content_message_ids': []})


# ОБРАБОТЧИК: Возврат из чтения главы к списку глав (теперь работает корректно)
@bot.callback_query_handler(func=lambda call: call.data == "back_to_chapter_list")
def back_to_chapter_list_callback(call):
    bot.answer_callback_query(call.id)
    chat_id = call.message.chat.id
    user_data = get_state_data(chat_id)
    current_part_name = user_data.get('current_part_name')
    current_group_index = user_data.get('current_group_index')
    content_message_ids = user_data.get('content_message_ids', [])

    # 1. Удаляем все сообщения с контентом главы
    for msg_id in content_message_ids:
        try:
            bot.delete_message(chat_id, msg_id)
        except Exception as e:
            logging.error(f"Failed to delete content message {msg_id}: {e}")
    
    # 2. Очищаем список ID сообщений из состояния
    user_data['content_message_ids'] = []
    set_state(chat_id, "VIEWING_CHAPTERS", data=user_data) # Обновляем состояние

    if current_part_name and current_group_index is not None:
        # 3. Редактируем сообщение с кнопками "назад" обратно в список глав
        try:
            bot.edit_message_text(
                f"Выберите главу:", 
                chat_id,
                call.message.message_id, # ID сообщения, к которому прикреплена кнопка "назад"
                reply_markup=get_chapters_in_group_keyboard(call.from_user.id, current_part_name, current_group_index)
            )
        except telebot.apihelper.ApiTelegramException as e:
            logging.error(f"Failed to edit message back to list: {e}")
            bot.send_message(chat_id, "Произошла ошибка при возврате к списку. Попробуйте снова через меню.", reply_markup=get_welcome_keyboard())
    else:
        bot.send_message(chat_id, "К сожалению, ваше предыдущее местоположение потеряно. Возврат в меню.")
        back_to_user_menu_callback(call)
        
        
# ОБРАБОТЧИК: read_chapter_callback теперь использует отдельное сообщение для кнопок
@bot.callback_query_handler(func=lambda call: call.data.startswith("read_"))
def read_chapter_callback(call):
    bot.answer_callback_query(call.id, text="Загрузка главы...")

    chapter_id = call.data.replace("read_", "")
    data = load_chapters_data()
    chapters = data['chapters']
    user_id = call.from_user.id
    chat_id = call.message.chat.id

    if chapter_id in chapters:
        chapter = chapters[chapter_id]
        
        # --- ЛОГИКА: Отметить главу как прочитанную ---
        read_progress = load_user_progress(user_id)
        if chapter_id not in read_progress:
            read_progress.add(chapter_id)
            save_user_progress(user_id, read_progress)
            logging.info(f"User {user_id} marked chapter {chapter_id} as read.")
        # ----------------------------------------------------
        
        # 1. Удаляем предыдущее сообщение со списком глав
        try:
            bot.delete_message(chat_id, call.message.message_id)
        except Exception as e:
            logging.error(f"Could not delete message: {e}")

        # 2. Отправляем контент главы (возможно, несколькими частями) и сохраняем их ID
        full_text = f"**{chapter['title']}**\n\n{chapter['content']}"
        sent_ids = send_long_message(chat_id, full_text, parse_mode="Markdown")
        
        # Обновляем состояние пользователя с ID отправленных сообщений с контентом
        user_data = get_state_data(chat_id)
        user_data['content_message_ids'] = sent_ids
        set_state(chat_id, "VIEWING_CHAPTERS", data=user_data)

        # 3. Отправляем ОТДЕЛЬНОЕ сообщение с кнопками навигации
        bot.send_message(chat_id, "Оцените главу", reply_markup=get_read_chapter_keyboard(chapter_id))


    else:
        bot.answer_callback_query(call.id, "Глава не найдена. 😕", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data == "cancel")
def cancel_handler_callback(call):
    bot.answer_callback_query(call.id)
    clear_state(call.message.chat.id)
    bot.edit_message_text("↩️ Действие отменено. Выберите следующее действие в админ-панели:", call.message.chat.id, call.message.message_id, reply_markup=get_admin_menu_keyboard())

# --- ОБРАБОТЧИКИ FSM (Админ-панель: Управление частями и главами) ---
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
        callback_name = part_name.replace(" ", "_")
        markup.add(types.InlineKeyboardButton(text=f"✏️ {part_name}", callback_data=f"select_edit_part_name_{callback_name}"))
    markup.add(types.InlineKeyboardButton(text="🚫 Отмена", callback_data="cancel"))
    bot.edit_message_text("Выберите часть, название которой хотите изменить:", call.message.chat.id, call.message.message_id, reply_markup=markup)

# 2. Изменение названия части - ШАГ 2 (Ввод нового имени)
@bot.callback_query_handler(func=lambda call: call.data.startswith("select_edit_part_name_"))
def admin_edit_part_name_input_start(call):
    bot.answer_callback_query(call.id)
    chat_id = call.message.chat.id
    old_part_name = call.data.replace("select_edit_part_name_", "").replace("_", " ")
    
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
        callback_name = part_name.replace(" ", "_")
        markup.add(types.InlineKeyboardButton(text=f"➕ {part_name}", callback_data=f"select_part_for_chapter_{callback_name}"))
    markup.add(types.InlineKeyboardButton(text="🚫 Отмена", callback_data="cancel"))
    bot.edit_message_text("Выберите часть, в которую хотите добавить главу:", call.message.chat.id, call.message.message_id, reply_markup=markup)


# 3. Добавление главы в существующую часть - ШАГ 2 (Ввод ID главы)
@bot.callback_query_handler(func=lambda call: call.data.startswith("select_part_for_chapter_"))
def admin_add_chapter_enter_id(call):
    bot.answer_callback_query(call.id)
    chat_id = call.message.chat.id
    part_name = call.data.replace("select_part_for_chapter_", "").replace("_", " ")

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
    target_part_name = user_data['target_part_name'] # Получаем имя части из FSM
    
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


# 4. Удаление главы - Логика выбора и подтверждения (Адаптировано)

@bot.callback_query_handler(func=lambda call: call.data == "admin_delete_chapter_start")
def admin_delete_chapter_start_callback(call):
    bot.answer_callback_query(call.id)
    if call.from_user.id not in ADMIN_IDS: return
    
    data = load_chapters_data()
    chapters = data['chapters']
    if not chapters:
        bot.answer_callback_query(call.id, "Нет доступных глав для удаления.", show_alert=True)
        return

    markup = types.InlineKeyboardMarkup()
    for chap_id, chap_data in chapters.items():
        # Используем только название главы в кнопке выбора для удаления
        markup.add(types.InlineKeyboardButton(text=f"❌ {chap_data['title']}", callback_data=f"confirm_delete_{chap_id}"))
    
    markup.add(types.InlineKeyboardButton(text="🚫 Отмена", callback_data="cancel"))
    bot.edit_message_text("❌ Выберите главу для удаления:", call.message.chat.id, call.message.message_id, reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith("confirm_delete_"))
def handle_confirm_delete_chapter(call):
    bot.answer_callback_query(call.id)
    chat_id = call.message.chat.id
    chapter_id = call.data.replace("confirm_delete_", "")
    
    data = load_chapters_data()
    chapters = data['chapters']
    parts = data['parts']

    if chapter_id in chapters:
        title = chapters[chapter_id]['title']
        
        # Удаляем главу из списка chapters
        del data['chapters'][chapter_id]
        
        # Удаляем ID главы из соответствующего списка в parts
        for part_name in parts:
            if chapter_id in parts[part_name]:
                parts[part_name].remove(chapter_id)
                break
        
        save_chapters_data(data)
        
        bot.send_message(chat_id, f"🗑️ Глава '{title}' (ID {chapter_id}) успешно удалена.", reply_markup=types.ReplyKeyboardRemove())
        bot.send_message(chat_id, "Выберите следующее действие в админ-панели:", reply_markup=get_admin_menu_keyboard())
    else:
        bot.answer_callback_query(call.id, "Глава не найдена.", show_alert=True)
        bot.send_message(chat_id, "Возврат в админ-панель:", reply_markup=get_admin_menu_keyboard())
# --- Обработка системы оценок (без изменений) ---

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
    load_chapters_data()
    
    if not os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
            json.dump({}, f, ensure_ascii=False)
            
    bot.infinity_polling()
