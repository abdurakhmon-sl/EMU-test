import telebot
from telebot import types, apihelper
import pandas as pd
import random
import json
import os
from datetime import datetime, timedelta

# --- ПРОКСИ (обязательно для PythonAnywhere) ---
apihelper.proxy = {'https': 'http://proxy.server:3128'}

# --- КОНФИГУРАЦИЯ ---
BOT_TOKEN = '8564473279:AAGg6OGNITMQ059IO7Ar83JgCNI3BWo0CW4'
ADMIN_ID = 1825865550
SPECIAL_SUBJECTS = [
    "Тест 2", "Тест 3", "Тест 6",
    "Биофизика (тест 4)", "Биофизика",
    "Латинский язык", "Информатика",
    "Преклиническая", "Анатомия 1",
    "Анатомия 2", "Анатомия 3",
    "Стом ведение"
]

STATS_FILE  = 'stats.json'
USERS_FILE  = 'allowed_users.json'
LOGS_FILE   = 'attempts.json'
DATA_FILE   = 'data.xlsx'

bot = telebot.TeleBot(BOT_TOKEN)
users_db = {}
user_temp_selection = {}

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
def load_json(filename):
    if not os.path.exists(filename):
        return [] if filename in (USERS_FILE, LOGS_FILE) else {}
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return [] if filename in (USERS_FILE, LOGS_FILE) else {}

def save_json(filename, data):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def load_questions():
    try:
        if not os.path.exists(DATA_FILE):
            return []
        df = pd.read_excel(DATA_FILE, keep_default_na=False)
        return df.map(str).to_dict('records')   # исправлено: applymap → map
    except Exception as e:
        print(f"Ошибка загрузки вопросов: {e}")
        return []

def get_tashkent_time():
    return (datetime.utcnow() + timedelta(hours=5)).strftime("%d.%m %H:%M")

def is_allowed(uid):
    if uid == ADMIN_ID:
        return True
    allowed = load_json(USERS_FILE)
    return uid in allowed

def record_mistake(user_id, question_text):
    stats = load_json(STATS_FILE)
    uid = str(user_id)
    if uid not in stats:
        stats[uid] = {}
    stats[uid][question_text] = stats[uid].get(question_text, 0) + 1
    save_json(STATS_FILE, stats)

all_questions = load_questions()

# --- МЕНЮ ---
def get_main_menu(user_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    subjects = sorted(list(set(
        q['subject'] for q in all_questions if q['subject'].strip()
    )))
    markup.add(*[types.KeyboardButton(s) for s in subjects])
    markup.row(types.KeyboardButton("🏆 Рейтинг"), types.KeyboardButton("👤 Мой профиль"))
    if user_id == ADMIN_ID:
        markup.row(types.KeyboardButton("⚙️ Админка"))
    return markup

# --- СТАРТ ---
@bot.message_handler(commands=['start'])
def start_cmd(message):
    uid = message.chat.id
    if is_allowed(uid):
        bot.send_message(uid, "👋 Выберите предмет:", reply_markup=get_main_menu(uid))
    else:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📨 Отправить запрос", callback_data="req_access"))
        bot.send_message(uid, "🔒 Доступ закрыт. Отправьте запрос администратору.", reply_markup=markup)

# --- ЗАПРОС ДОСТУПА ---
@bot.callback_query_handler(func=lambda call: call.data == "req_access")
def req_acc(call):
    uid = call.message.chat.id
    bot.edit_message_text("📨 Запрос отправлен!", uid, call.message.message_id)
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("✅ Пустить", callback_data=f"allow_{uid}"),
        types.InlineKeyboardButton("🚫 Отказать", callback_data=f"deny_{uid}")
    )
    name = call.from_user.first_name or "Без имени"
    username = f" (@{call.from_user.username})" if call.from_user.username else ""
    bot.send_message(ADMIN_ID, f"👤 Запрос от {name}{username}\nID: {uid}", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith(('allow_', 'deny_')))
def admin_dec(call):
    if call.message.chat.id != ADMIN_ID:
        return
    action, tid = call.data.split('_', 1)
    tid = int(tid)
    if action == 'allow':
        users = load_json(USERS_FILE)
        if tid not in users:
            users.append(tid)
        save_json(USERS_FILE, users)
        try:
            bot.send_message(tid, "🎉 Доступ открыт! Нажмите /start")
        except:
            pass
        bot.answer_callback_query(call.id, "✅ Пользователь добавлен")
    else:
        bot.answer_callback_query(call.id, "🚫 Отказано")
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except:
        pass

# --- РЕЙТИНГ ---
@bot.message_handler(func=lambda m: m.text == "🏆 Рейтинг")
def rating_list(message):
    if not is_allowed(message.chat.id):
        return
    subjects = sorted(list(set(
        q['subject'] for q in all_questions if q['subject'].strip()
    )))
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(*[
        types.InlineKeyboardButton(s, callback_data=f"sh_rat_{i}")
        for i, s in enumerate(subjects)
    ])
    bot.send_message(message.chat.id, "📊 Выберите предмет:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('sh_rat_'))
def sh_rat(call):
    idx = int(call.data.split('_')[2])
    subjects = sorted(list(set(
        q['subject'] for q in all_questions if q['subject'].strip()
    )))
    if idx >= len(subjects):
        return
    sub = subjects[idx]
    logs = load_json(LOGS_FILE)
    u_stats = {}
    for l in logs:
        if l.get('user_id') == ADMIN_ID or l.get('subject') != sub:
            continue
        uid = l['user_id']
        if uid not in u_stats:
            u_stats[uid] = {'s': 0, 'c': 0, 'n': l.get('username', 'Студент')}
        u_stats[uid]['s'] += l['score']
        u_stats[uid]['c'] += 1

    leaders = sorted(
        [{'n': v['n'], 'a': int(v['s'] / v['c']), 't': v['c']} for v in u_stats.values()],
        key=lambda x: x['a'], reverse=True
    )
    if not leaders:
        text = f"🏆 {sub}\n\nПока нет результатов."
    else:
        text = f"🏆 ТОП-10: {sub}\n\n"
        for i, u in enumerate(leaders[:10], 1):
            text += f"{i}. {u['n']} — {u['a']}% ({u['t']} тестов)\n"
    try:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id)
    except:
        bot.send_message(call.message.chat.id, text)

# --- ПРОФИЛЬ ---
@bot.message_handler(func=lambda m: m.text in ["👤 Мой профиль", "/profile"])
def profile(message):
    if not is_allowed(message.chat.id):
        return
    logs = load_json(LOGS_FILE)
    u_logs = [l for l in logs if l.get('user_id') == message.chat.id]
    if not u_logs:
        bot.send_message(message.chat.id, "📭 История пуста.")
        return
    avg = int(sum(l['score'] for l in u_logs) / len(u_logs))
    msg = (f"👤 {message.from_user.first_name}\n"
           f"📊 Средний балл: {avg}%\n"
           f"📝 Всего тестов: {len(u_logs)}\n\n"
           f"🕒 Последние 10:\n")
    for l in u_logs[-10:][::-1]:
        subj = l.get('subject', '')[:15]
        msg += f"• {l.get('date','')} | {subj} — {l['score']}%\n"
    bot.send_message(message.chat.id, msg)

# --- АДМИНКА ---
@bot.message_handler(func=lambda m: m.text == "⚙️ Админка" and m.chat.id == ADMIN_ID)
def adm(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("📢 Объявление", "📋 Последние 10 попыток", "💾 Скачать базу", "🏠 Главное меню")
    bot.send_message(ADMIN_ID, "⚙️ Админка:", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "📋 Последние 10 попыток" and m.chat.id == ADMIN_ID)
def admin_history(message):
    logs = load_json(LOGS_FILE)
    if not logs:
        bot.send_message(ADMIN_ID, "Логов пока нет.")
        return
    msg = "🕒 ПОСЛЕДНИЕ 10 (UZB время):\n\n"
    for l in logs[-10:][::-1]:
        icon = {"exam": "🎓", "practice": "🏋️", "mistakes": "🚑"}.get(l.get('mode_key'), "📝")
        msg += (f"👤 {l.get('username','?')}\n"
                f"📅 {l.get('date','')} | {icon} {l.get('mode_display','ТЕСТ')}\n"
                f"📊 {l['score']}% | {l.get('subject','')}\n\n")
    bot.send_message(ADMIN_ID, msg)

@bot.message_handler(func=lambda m: m.text == "📢 Объявление" and m.chat.id == ADMIN_ID)
def announce(message):
    msg = bot.send_message(ADMIN_ID, "✍️ Напишите текст объявления:")
    bot.register_next_step_handler(msg, send_announce)

def send_announce(message):
    users = load_json(USERS_FILE)
    ok, fail = 0, 0
    for uid in users:
        try:
            bot.send_message(uid, f"📢 ОБЪЯВЛЕНИЕ:\n\n{message.text}")
            ok += 1
        except:
            fail += 1
    bot.send_message(ADMIN_ID, f"✅ Отправлено: {ok}\n❌ Не доставлено: {fail}",
                     reply_markup=get_main_menu(ADMIN_ID))

@bot.message_handler(content_types=['document'])
def up_db(message):
    if message.chat.id != ADMIN_ID:
        return
    if message.document.file_name == 'data.xlsx':
        file_info = bot.get_file(message.document.file_id)
        with open(DATA_FILE, 'wb') as f:
            f.write(bot.download_file(file_info.file_path))
        global all_questions
        all_questions = load_questions()
        bot.send_message(ADMIN_ID, f"✅ База обновлена! Загружено вопросов: {len(all_questions)}")

# --- ВЫБОР ПРЕДМЕТА ---
@bot.message_handler(func=lambda m: m.text in list(set(
    q['subject'] for q in all_questions if q['subject'].strip()
)))
def set_mode(message):
    if not is_allowed(message.chat.id):
        return
    user_temp_selection[message.chat.id] = message.text
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("🎓 Экзамен", "🏋️ Тренировка", "🚑 Ошибки")
    markup.add("🏠 Главное меню")
    bot.send_message(message.chat.id,
                     f"📚 Предмет: *{message.text}*\nВыберите режим:",
                     parse_mode="Markdown",
                     reply_markup=markup)

# --- СТАРТ ТЕСТА ---
@bot.message_handler(func=lambda m: m.text in ["🎓 Экзамен", "🏋️ Тренировка", "🚑 Ошибки"])
def start_test(message):
    uid = message.chat.id
    if not is_allowed(uid):
        return
    subject = user_temp_selection.get(uid)
    if not subject:
        bot.send_message(uid, "⚠️ Сначала выберите предмет.", reply_markup=get_main_menu(uid))
        return

    mode = ('exam'     if "Экзамен"   in message.text else
            'mistakes' if "Ошибки"    in message.text else
            'practice')

    all_sub_qs = [q for q in all_questions if q['subject'] == subject]

    if mode == 'mistakes':
        user_errs = load_json(STATS_FILE).get(str(uid), {})
        final_qs = [q for q in all_sub_qs if q['question'] in user_errs]
        if not final_qs:
            bot.send_message(uid, "🎉 У вас нет ошибок по этому предмету!",
                             reply_markup=get_main_menu(uid))
            return
    else:
        limit = 20 if subject in SPECIAL_SUBJECTS else 25
        final_qs = random.sample(all_sub_qs, min(limit, len(all_sub_qs)))

    points = 5 if subject in SPECIAL_SUBJECTS or len(final_qs) == 20 else 4
    mode_name = {"exam": "🎓 ЭКЗАМЕН", "practice": "🏋️ ТРЕНИРОВКА", "mistakes": "🚑 ОШИБКИ"}[mode]

    users_db[uid] = {
        'qs': final_qs, 'idx': 0, 'score': 0,
        'mode': mode, 'mode_name': mode_name,
        'sub': subject, 'results': [], 'pval': points
    }
    bot.send_message(uid,
                     f"🚀 {mode_name}\n📚 {subject}\n❓ Вопросов: {len(final_qs)}",
                     reply_markup=types.ReplyKeyboardRemove())
    send_q(uid)

# --- ОТПРАВКА ВОПРОСА ---
def send_q(uid):
    d = users_db.get(uid)
    if not d:
        return
    if d['idx'] >= len(d['qs']):
        finish(uid)
        return
    q = d['qs'][d['idx']]
    opts = [o for o in [q.get('option_1',''), q.get('option_2',''),
                         q.get('option_3',''), q.get('option_4','')]
            if str(o).strip() and str(o).lower() != 'nan']
    random.shuffle(opts)
    d['lopts'] = opts

    txt = f"❓ Вопрос {d['idx']+1}/{len(d['qs'])}\n\n{q['question']}\n\n"
    for i, o in enumerate(opts, 1):
        txt += f"{i}. {o}\n"

    kb = types.InlineKeyboardMarkup(row_width=4)
    kb.add(*[types.InlineKeyboardButton(str(i), callback_data=f"a_{i-1}")
             for i in range(1, len(opts)+1)])
    bot.send_message(uid, txt, reply_markup=kb)

# --- ПРОВЕРКА ОТВЕТА ---
@bot.callback_query_handler(func=lambda call: call.data.startswith('a_'))
def check_a(call):
    uid = call.message.chat.id
    d = users_db.get(uid)
    if not d:
        bot.answer_callback_query(call.id, "Тест не найден. Начните заново.")
        return

    try:
        bot.edit_message_reply_markup(uid, call.message.message_id, reply_markup=None)
    except:
        pass

    idx = int(call.data.split('_')[1])
    if idx >= len(d.get('lopts', [])):
        return

    ans = d['lopts'][idx]
    q = d['qs'][d['idx']]
    correct = str(q.get('correct_option', '')).strip()
    is_ok = str(ans).strip() == correct

    if is_ok:
        d['score'] += d['pval']
        d['results'].append(f"✅ {q['question']}")
    else:
        record_mistake(uid, q['question'])
        d['results'].append(f"❌ {q['question']}\n   └ Правильно: {correct}")

    if d['mode'] == 'practice':
        bot.send_message(uid, "✅ Верно!" if is_ok else f"❌ Ошибка!\nПравильный ответ: {correct}")

    d['idx'] += 1
    send_q(uid)

# --- ЗАВЕРШЕНИЕ ТЕСТА ---
def finish(uid):
    d = users_db.get(uid)
    if not d:
        return

    logs = load_json(LOGS_FILE)
    try:
        username = bot.get_chat(uid).first_name or "Студент"
    except:
        username = "Студент"

    logs.append({
        'date': get_tashkent_time(),
        'user_id': uid,
        'username': username,
        'subject': d['sub'],
        'score': d['score'],
        'total': len(d['qs']),
        'mode_key': d['mode'],
        'mode_display': d['mode_name']
    })
    save_json(LOGS_FILE, logs)

    bot.send_message(uid, f"🏁 {d['mode_name']} завершён!\n📊 Результат: {d['score']}%")

    # Отправляем отчёт по 5 вопросов за раз
    res_txt = "📝 ОТЧЁТ:\n\n"
    for i, line in enumerate(d['results'], 1):
        res_txt += f"{i}. {line}\n\n"
        if i % 5 == 0:
            bot.send_message(uid, res_txt)
            res_txt = ""
    if res_txt.strip():
        bot.send_message(uid, res_txt)

    del users_db[uid]

    # Запрашиваем отзыв
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("➡️ Пропустить")
    msg = bot.send_message(uid,
                           "✍️ Напишите пожелание или отзыв администратору\n(или нажмите «Пропустить»):",
                           reply_markup=markup)
    bot.register_next_step_handler(msg, process_feedback)

def process_feedback(message):
    uid = message.chat.id
    if message.text and message.text not in ["➡️ Пропустить", "/start"]:
        uname = f" (@{message.from_user.username})" if message.from_user.username else ""
        try:
            bot.send_message(ADMIN_ID,
                             f"📩 Отзыв от {message.from_user.first_name}{uname}:\n\n«{message.text}»")
        except:
            pass
        bot.send_message(uid, "✅ Спасибо! Сообщение отправлено.")

    bot.send_message(uid, "🏠 Главное меню:", reply_markup=get_main_menu(uid))

# --- ГЛАВНОЕ МЕНЮ (кнопка) ---
@bot.message_handler(func=lambda m: m.text == "🏠 Главное меню")
def back_m(message):
    if not is_allowed(message.chat.id):
        return
    bot.send_message(message.chat.id, "🏠 Главное меню:", reply_markup=get_main_menu(message.chat.id))

# --- ЗАПУСК ---
if __name__ == "__main__":
    print(f"Бот v25.0 запущен... Загружено вопросов: {len(all_questions)}")
    try:
        bot.delete_my_commands()
    except:
        pass
    bot.infinity_polling(timeout=30, long_polling_timeout=25)