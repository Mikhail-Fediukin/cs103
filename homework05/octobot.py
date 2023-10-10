import json
from datetime import datetime

import re
import gspread  # type: ignore
import pandas as pd
import telebot  # type: ignore
import validators  # type: ignore

bot = telebot.TeleBot("6200114256:AAHS-nbYfRRyUu9TS7fkJqjlXqBt2y6EiPE")


def connect_table(message):
    url = message.text
    sheet_id = url.split("/")[5]
    try:
        with open("tables.json") as json_file:
            tables = json.load(json_file)
        title = len(tables) + 1
        tables[title] = {"url": url, "id": sheet_id}
    except FileNotFoundError:
        tables = {0: {"url": url, "id": sheet_id}}
    with open("tables.json", "w") as json_file:
        json.dump(tables, json_file)
    bot.send_message(message.chat.id, "Google-таблица подключена!")
    start(message)


def access_current_sheet():
    try:
        with open("tables.json") as json_file:
            tables = json.load(json_file)
        sheet_id = tables[max(tables)]["id"]
        gc = gspread.service_account(filename="credentials.json")
        sh = gc.open_by_key(sheet_id)
        sheet = sh.sheet1
        ws_values = sheet.get_all_values()
        df = pd.DataFrame.from_records(ws_values[1:], columns=ws_values[0])
        return sheet, tables[max(tables)]["url"], df
    except FileNotFoundError:
        return None


def convert_date(date):
    the_day = re.split(r'[,./!_-]', date)
    return datetime(int(the_day[2]), int(the_day[1]), int(the_day[0]))


def start(message):
    start_markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    if not access_current_sheet():
        start_markup.row("Подключить Google-таблицу")
    else:
        start_markup.row("Посмотреть дедлайны на этой неделе")
        start_markup.row("Редактировать дедлайны")
        start_markup.row("Редактировать таблицу")
        start_markup.row("That will be all")

    info = bot.send_message(message.chat.id, "Выбери действие:", reply_markup=start_markup)
    bot.register_next_step_handler(info, choose_action)


def choose_action(message):
    if message.text == "That will be all":
        bot.send_message(
            message.chat.id,
            "Скорейшего окончания сессии!\nДля возобновления работы напиши /start",
        )

    elif message.text == "Подключить Google-таблицу":
        info = bot.send_message(message.chat.id, "Отправь ссылку на Google-таблицу")
        bot.register_next_step_handler(info, connect_table)

    elif message.text == "Посмотреть дедлайны на этой неделе":
        frame = access_current_sheet()[2]
        deadlines = 0
        for i in range(frame.shape[0]):
            for j in range(2, frame.shape[1]):
                cell_data = frame.iat[i, j]
                if cell_data:
                    on_week = convert_date(cell_data) - datetime.now()
                    if 0 < on_week.days < 7:
                        deadlines += 1
                        bot.send_message(
                            message.chat.id,
                            f"{ frame.iat[i, 0] }. Работа №{ j - 1 }\nДедлайн <b>{ frame.iat[i, j] }</b>",
                            parse_mode="HTML",
                        )
        if deadlines == 0:
            bot.send_message(message.chat.id, "Дедлайнов на ближайшей неделе нет")
        start(message)

    elif message.text == "Редактировать дедлайны":
        markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        markup.row("Добавить новый дедлайн")
        markup.row("Редактировать существующий дедлайн")
        markup.row("Вернуться в начало")
        bot.send_message(message.chat.id, "Выбери действие", reply_markup=markup)
        bot.register_next_step_handler(message, choose_subject)

    elif message.text == "Редактировать таблицу":
        markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        markup.row("Добавить новую дисциплину")
        markup.row("Изменить информацию о дисциплине")
        markup.row("Удалить дисциплину")
        markup.row("Удалить все дисциплины")
        markup.row("Вернуться в начало")
        info = bot.send_message(message.chat.id, "Выбери действие", reply_markup=markup)
        bot.register_next_step_handler(info, choose_subject_action)


def choose_subject_action(message):
    if message.text == "Вернуться в начало":
        start(message)

    elif message.text == "Добавить новую дисциплину":
        info = bot.send_message(message.chat.id, "Введи название дисциплины, которую желаешь добавить")
        bot.register_next_step_handler(info, add_new_subject)

    elif message.text == "Изменить информацию о дисциплине":
        markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        markup.row("Изменить название дисциплины")
        markup.row("Изменить ссылку на таблицу с баллами по дисциплине")
        info = bot.send_message(message.chat.id, "Выбери действие", reply_markup=markup)
        bot.register_next_step_handler(info, choose_subject)

    elif message.text == "Удалить дисциплину":
        choose_subject(message)

    """elif message.text == "Удалить все дисциплины":
        markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        markup.row("Да, удалить ВСЕ")
        markup.row("Нет, вернуться")
        info = bot.send_message(message.chat.id, "Точно удалить ВСЕ?", reply_markup=markup)
        bot.register_next_step_handler(info, choose_removal_option)"""


def choose_deadline_action(message, action):
    global ROW, COL
    cell = access_current_sheet()[0].find(message.text)
    ROW, COL = cell.row, cell.col
    info = bot.send_message(message.chat.id, "Введи номер работы")
    bot.register_next_step_handler(info, update_subject_deadline, action)


def choose_subject(message):
    if message.text == "Вернуться в начало":
        start(message)
    else:
        markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        data = access_current_sheet()
        for i in range(data[2].shape[0]):
            markup.row(data[2].at[i, "Subject"])
        info = bot.send_message(message.chat.id, "Выбери дисциплину", reply_markup=markup)
        if message.text == "Изменить название дисциплины":
            bot.register_next_step_handler(info, update_subject_title)
        elif message.text == "Изменить ссылку на таблицу с баллами по дисциплине":
            bot.register_next_step_handler(info, update_subject_url)
        elif message.text == "Удалить дисциплину":
            bot.register_next_step_handler(info, delete_subject)
        elif message.text == "Добавить новый дедлайн" or message.text == "Редактировать существующий дедлайн":
            bot.register_next_step_handler(info, choose_deadline_action, message.text)


def update_subject_deadline(message, action):
    global COL
    if not message.text.isdigit():
        info = bot.send_message(
            message.chat.id,
            "Error. Для номера работы используй только цифры",
        )
        bot.register_next_step_handler(info, update_subject_deadline, action)
        return
    data = access_current_sheet()
    if action == "Редактировать дедлайн" and int(message.text) > data[2].shape[1] - 2:
        info = bot.send_message(
            message.chat.id,
            "Работа не найдена. Попробуй еще раз",
        )
        bot.register_next_step_handler(info, update_subject_deadline, action)
        return
    cur_date = data[0].cell(ROW, COL + int(message.text) + 1).value
    if cur_date:
        info = bot.send_message(
            message.chat.id,
            f"Дедлайн данной работы: <b>{ cur_date }</b>." f"\nВведи новую дату дедлайна в формате\nDD/MM/YYYY",
            parse_mode="HTML",
        )
    elif action == "Редактировать дедлайн":
        info = bot.send_message(
            message.chat.id,
            "Работа не найдена. Попробуй еще раз",
        )
        bot.register_next_step_handler(info, update_subject_deadline, action)
        return
    else:
        info = bot.send_message(message.chat.id, "Введи дату дедлайна в формате\nDD/MM/YYYY")
    COL += int(message.text) + 1
    bot.register_next_step_handler(info, update_cell_datetime)


def add_new_subject(message):
    access_current_sheet()[0].append_row([message.text])
    info = bot.send_message(message.chat.id, "Введи ссылку на таблицу с баллами по данной дисциплине")
    bot.register_next_step_handler(info, add_new_subject_url)


def add_new_subject_url(message):
    text = "https:///" + message.text if (len(message.text) > 3 and message.text[:4] == "www.") else message.text
    if not validators.url(text):
        new = bot.send_message(message.chat.id, "Cсылка не работает:(\nПопробуй еще раз.")
        bot.register_next_step_handler(new, add_new_subject_url)
        return
    data = access_current_sheet()
    data[0].update_cell(data[2].shape[0] + 1, 2, text)
    bot.send_message(message.chat.id, "Дисциплина добавлена")
    start(message)


def update_subject_title(message):
    cell = access_current_sheet()[0].find(message.text)
    global ROW, COL
    ROW, COL = cell.row, cell.col
    info = bot.send_message(message.chat.id, "Введи новое название")
    bot.register_next_step_handler(info, update_cell_data, info.text)


def update_subject_url(message):
    cell = access_current_sheet()[0].find(message.text)
    global ROW, COL
    ROW, COL = cell.row, cell.col + 1
    info = bot.send_message(message.chat.id, "Введи новую ссылку")
    bot.register_next_step_handler(info, update_cell_data, info.text)


def update_cell_data(message, action):
    if action == "Введи новую ссылку" or action == "Cсылка не работает:(\nПопробуй еще раз.":
        text = "https://" + message.text if (len(message.text) > 3 and message.text[:4] == "www.") else message.text
        if not validators.url(text):
            info = bot.send_message(message.chat.id, "Cсылка не работает:(\nПопробуй еще раз.")
            bot.register_next_step_handler(info, update_cell_data, info.text)
            return
        message.text = text
    global ROW, COL
    access_current_sheet()[0].update_cell(ROW, COL, message.text)
    bot.send_message(message.chat.id, "Готово!")
    start(message)


def update_cell_datetime(message):
    try:
        today = datetime.now()
        date = convert_date(message.text)
        on_sometime = date - today
        if on_sometime.days // 365 > 2 or date < today:
            info = bot.send_message(
                message.chat.id,
                "Дедлайн вносится максимум на ближайшие 2 года от настоящего момента.\nПопробуй ещё раз",
            )
            bot.register_next_step_handler(info, update_cell_datetime)
            return
    except Exception:
        info = bot.send_message(
            message.chat.id,
            "Error. Дата должна соответствовать форматy DD/MM/YYYY "
            "и иметь адекватные временные рамки.\nПопробуй ещё раз",
        )
        bot.register_next_step_handler(info, update_cell_datetime)
        return

    global ROW, COL
    access_current_sheet()[0].update_cell(ROW, COL, message.text)
    bot.send_message(message.chat.id, "Готово!")
    start(message)


def delete_subject(message):
    cell = access_current_sheet()[0].find(message.text)
    access_current_sheet()[0].delete_rows(cell.row)
    bot.send_message(message.chat.id, "Готово! Одним меньше!")
    start(message)


def choose_removal_option(message):
    if message.text == "Да, удалить ВСЕ":
        clear_subject_list(message)

    elif message.text == "Нет, вернуться":
        bot.send_message(message.chat.id, "Хорошо. Возможно через полгода...")
        start(message)


def clear_subject_list(message):
    access_current_sheet()[0].clear()
    bot.send_message(message.chat.id, "Готово! Кажется, это начало новой жизни без долгов.")
    start(message)


def is_valid_date(date: str, divider: str) -> bool:
    try:
        the_day = re.split(r'[,./!_-]', date)
        datetime(int(the_day[2]), int(the_day[1]), int(the_day[0]))
    except ValueError:
        return False


def is_valid_url(url: str = "") -> bool:
    return validators.url(url)


@bot.message_handler(commands=["start"])
def greetings(message):
    bot.send_message(
        message.chat.id,
        "Решительно приветствую!\nСо мной ты достигнешь всех намеченных целей!",
    )
    start(message)


ROW, COL = None, None
bot.infinity_polling()
