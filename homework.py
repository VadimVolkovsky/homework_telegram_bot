import logging
import os
import sys
import time
from pprint import pprint

import requests
import telegram
from dotenv import load_dotenv

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


class TelegramBotHandler(logging.Handler):
    """Хэндлер для отправки логов в телеграмм."""

    def __init__(self, bot):
        """Добавилась переменная bot."""
        super().__init__()
        self.bot = bot

    def emit(self, record: logging.LogRecord):
        """Устанавливаем ограничение на отправку сообщений.
        Если сообщение уровня ERROR/CRITICAL уже было отправлено в телеграм,
        повторная отправка не производится.
        """
        global LAST_ERROR
        if (record.levelno >= logging.ERROR
           and LAST_ERROR != record.message):
            send_message(self.bot, self.format(record))
        LAST_ERROR = record.message


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    bot.send_message(
        chat_id=TELEGRAM_CHAT_ID,
        text=message
    )


def get_api_answer(current_timestamp):
    """Делает запрос к единственному эндпоинту API-сервиса.
    В качестве параметра функция получает временную метку.
    В случае успешного запроса должна вернуть ответ API,
    преобразовав его из формата JSON к типам данных Python.
    """
    timestamp = current_timestamp or int(time.time())
    headers = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}
    params = {'from_date': timestamp}
    response = requests.get(ENDPOINT, headers=headers, params=params)
    if response.status_code == 200:
        pprint(response.json())
        return response.json()
    else:
        message = f'ENDPOINT недоступен. Код ответа API:{response.status_code}'
        logging.error(message)
        raise Exception(message)


def check_response(response):
    """Проверяет ответ API на корректность.
    В качестве параметра функция получает ответ API,
    приведенный к типам данных Python.
    Если ответ API соответствует ожиданиям,
    то функция должна вернуть список домашних работ (он может быть и пустым),
    доступный в ответе API по ключу 'homeworks'.
    """
    try:
        homeworks_list = response['homeworks']
    except KeyError as error:
        logging.error(f'Вернулся пустой словарь {error}')
        raise KeyError
    if not isinstance(homeworks_list, list):
        logging.error('Домашки приходят не в виде списка')
        raise TypeError
    return homeworks_list


def parse_status(homework):
    """Извлекает из информации о конкретной домашней работе статус этой работы.
    В качестве параметра функция получает
    только один элемент из списка домашних работ.
    В случае успеха, функция возвращает подготовленную
    для отправки в Telegram строку,
    содержащую один из вердиктов словаря HOMEWORK_STATUSES.
    """
    try:
        homework_name = homework['homework_name']
    except KeyError as error:
        message = f'отсутствие ключа `homework_name` в ответе от API - {error}'
        logging.error(message)
        raise KeyError(message)

    try:
        homework_status = homework['status']
    except KeyError as error:
        message = f'отсутствие ключа "homework_status" в ответе от API-{error}'
        logging.error(message)
        raise KeyError(message)

    try:
        homework_status == 'approved' or 'reviewing' or 'rejected'
        verdict = HOMEWORK_STATUSES.get(homework_status)
        logging.info('Изменился статус проверки работы')
    except KeyError as error:
        message = f'отсутствие ожидаемых ключей в ответе API - {error}'
        logging.error(message)
        raise KeyError
    if homework_status == 'unknown':
        message = 'Недокументированный статус домашки '
        logging.error(message)
        raise TypeError(message)
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверяет доступность переменных окружения.
    Переменные необходимы для работы программы.
    Если отсутствует хотя бы одна переменная окружения —
    функция должна вернуть False, иначе — True.
    """
    if all((PRACTICUM_TOKEN, TELEGRAM_CHAT_ID, TELEGRAM_TOKEN)):
        return True
    else:
        return False


def main():
    """Основная логика работы бота."""
    _log_format = '%(asctime)s - %(levelname)s - %(message)s'
    logging.basicConfig(
        level=logging.INFO,
        format=_log_format,
        handlers=[logging.StreamHandler(sys.stdout)]
    )

    if not check_tokens():
        logging.critical('Отсутствует необходимый токен(ы)')
        return
    global bot
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    logger_tg = logging.getLogger()
    handler_tg = TelegramBotHandler(bot)
    logger_tg.addHandler(handler_tg)
    logging.info('Бот запущен')
    current_timestamp = ''

    while True:
        try:
            response = get_api_answer(current_timestamp)
            homework_list = check_response(response)
            homework = homework_list[0]
            message = parse_status(homework)
            send_message(bot, message)
            current_timestamp = response.get('current_date')
            logging.info('Сообщение успешно отправлено в телеграм')
            time.sleep(RETRY_TIME)
        except IndexError:
            logging.info('Обновлений не найдено')
            current_timestamp = response.get('current_date')
            time.sleep(RETRY_TIME)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            print(message)
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
