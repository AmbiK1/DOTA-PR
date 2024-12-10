import telebot
import requests
from telebot import types
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import time
import os

BOT_TOKEN = '7412710420:AAHNCea4_fq6e83x79rPL4sW06Vla0LnHJE'
bot = telebot.TeleBot(BOT_TOKEN)


@bot.message_handler(commands=['start'])
def start(message):
    welcome_text = (
        f"👋 Привет, {message.from_user.first_name}!\n\n"
        "Я бот, который поможет тебе с информацией по Dota 2.\n"
        "Чтобы узнать, что я умею, нажми /help"
    )
    bot.reply_to(message, welcome_text)


@bot.message_handler(commands=['help'])
def help(message):
    help_text = (
        "🔍 Список доступных команд:\n\n"
        "/guide - Получить гайд по предметам для любого героя\n"
        "/win - Показать топ-10 героев по винрейту\n"
        "/help - Показать список команд\n"
        "/support - Написать в техподдержку\n\n"
        "По всем вопросам обращайтесь в техподдержку!"
    )
    bot.reply_to(message, help_text)


@bot.message_handler(commands=['support'])
def support(message):
    # Отправляем инструкцию пользователю
    bot.reply_to(message,
                 "Опишите вашу проблему или предложение в следующем сообщении.\n"
                 "Я перешлю его команде поддержки."
                 )
    # Регистрируем следующий шаг
    bot.register_next_step_handler(message, process_support_message)


def process_support_message(message):
    try:
        # Формируем сообщение для поддержки
        support_message = (
            f"📩 Новое сообщение в поддержку\n\n"
            f"От: {message.from_user.first_name} ({message.from_user.id})\n"
            f"Username: @{message.from_user.username}\n\n"
            f"Сообщение:\n{message.text}"
        )

        # Отправляем сообщение администратору
        bot.send_message("@SashaAmb", support_message)

        # Подтверждаем пользователю
        bot.reply_to(message,
                     "✅ Ваше сообщение отправлено в техподдержку!\n"
                     "Мы рассмотрим его в ближайшее время."
                     )

    except Exception as e:
        bot.reply_to(message,
                     "❌ Произошла ошибка при отправке сообщения.\n"
                     "Пожалуйста, попробуйте позже или напишите напрямую @SashaAmb"
                     )


@bot.message_handler(commands=['guide'])
def hero_guide(message):
    try:
        url = 'https://api.opendota.com/api/heroStats'
        response = requests.get(url)
        heroes_data = response.json()

        # Создаем клавиатуру с кнопками героев
        markup = types.InlineKeyboardMarkup(row_width=3)
        buttons = []
        for hero in heroes_data:
            button = types.InlineKeyboardButton(
                text=hero['localized_name'],
                callback_data=f"hero_{hero['id']}"
            )
            buttons.append(button)

        markup.add(*buttons)
        bot.reply_to(message, "Выберите героя для просмотра гайда:", reply_markup=markup)

    except Exception as e:
        bot.reply_to(message, f"Произошла ошибка при получении списка героев: {str(e)}")


@bot.callback_query_handler(func=lambda call: call.data.startswith('hero_'))
def handle_hero_selection(call):
    try:
        hero_id = call.data.split('_')[1]
        guide_url = f"https://www.opendota.com/heroes/{hero_id}/items"

        # Отправляем сообщение о начале загрузки
        bot.answer_callback_query(call.id)
        status_message = bot.send_message(call.message.chat.id, "Загружаю гайд, пожалуйста подождите...")

        # Настройка Chrome в безголовом режиме
        chrome_options = Options()
        chrome_options.add_argument("--headless")  # Запуск в фоновом режиме
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--window-size=1920,1080")

        # Инициализация драйвера
        driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=chrome_options
        )

        # Загрузка страницы
        driver.get(guide_url)
        # Ждем загрузки контента
        time.sleep(5)

        # Создаем папку для скриншотов, если её нет
        if not os.path.exists("screenshots"):
            os.makedirs("screenshots")

        # Делаем скриншот
        screenshot_path = f"screenshots/hero_{hero_id}.png"
        driver.save_screenshot(screenshot_path)
        driver.quit()

        # Отправляем скриншот
        with open(screenshot_path, 'rb') as photo:
            bot.send_photo(
                call.message.chat.id,
                photo,
                caption=f"Гайд по предметам для выбранного героя\nСсылка: {guide_url}"
            )

        # Удаляем скриншот после отправки
        os.remove(screenshot_path)

        # Удаляем сообщение о загрузке
        bot.delete_message(call.message.chat.id, status_message.message_id)

    except Exception as e:
        bot.send_message(
            call.message.chat.id,
            f"Произошла ошибка при получении гайда: {str(e)}\n"
            f"Вы можете посмотреть гайд по ссылке: {guide_url}"
        )


@bot.message_handler(commands=['win'])
def get_top_winrate_heroes(message):
    try:
        # Получаем данные с публичной страницы статистики героев
        url = 'https://api.opendota.com/api/heroStats'
        response = requests.get(url)
        heroes_data = response.json()

        # Создаем список героев с их винрейтом из публичных матчей
        heroes_list = []
        for hero in heroes_data:
            if hero['1_pick'] > 0:  # Используем статистику из публичных матчей
                winrate = (hero['1_win'] / hero['1_pick']) * 100
                heroes_list.append({
                    'name': hero['localized_name'],
                    'winrate': winrate,
                    'matches': hero['1_pick'],
                    'wins': hero['1_win']
                })

        # Сортируем по винрейту
        sorted_heroes = sorted(heroes_list, key=lambda x: x['winrate'], reverse=True)

        # Формируем сообщение с топ-10 героями
        reply_message = "🏆 Топ 10 героев по винрейту в публичных матчах:\n\n"
        for i, hero in enumerate(sorted_heroes[:10], 1):
            reply_message += (f"{i}. {hero['name']}\n"
                              f"   Винрейт: {hero['winrate']:.2f}%\n"
                              f"   Победы: {hero['wins']:,}\n"
                              f"   Всего игр: {hero['matches']:,}\n\n")

        reply_message += "\nДанные взяты с OpenDota Public Matches"
        bot.reply_to(message, reply_message)

    except Exception as e:
        bot.reply_to(message, f"Произошла ошибка при получении данных: {str(e)}")


bot.polling(none_stop=True)