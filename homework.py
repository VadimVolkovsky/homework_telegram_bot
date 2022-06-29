import logging
import os
import sys
import time

import exceptions
import requests
import telegram
from dotenv import load_dotenv

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

token_dict = {
    'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
    'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
    'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID
}

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {token_dict["PRACTICUM_TOKEN"]}'}


HOMEWORK_VERDICTS = {
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
        LAST_ERROR = None
        if (record.levelno >= logging.ERROR
           and LAST_ERROR != record.message):
            send_message(self.bot, self.format(record))
        LAST_ERROR = record.message


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(
            chat_id=token_dict["TELEGRAM_CHAT_ID"],
            text=message
        )
        logging.info('Сообщение успешно отправлено в Telegram')
    except Exception as error:
        raise exceptions.ChatNotFoundException(error)


def get_api_answer(current_timestamp):
    """Делает запрос к единственному эндпоинту API-сервиса.
    В качестве параметра функция получает временную метку.
    В случае успешного запроса должна вернуть ответ API,
    преобразовав его из формата JSON к типам данных Python.
    """
    timestamp = current_timestamp or int(time.time())
    headers = {'Authorization': f'OAuth {token_dict["PRACTICUM_TOKEN"]}'}
    params = {'from_date': timestamp}
    response = requests.get(ENDPOINT, headers=headers, params=params)
    if response.status_code != 200:
        raise exceptions.EndPointIsNotAvailiable(response.status_code)
    return response.json()


def check_response(response):
    """Проверяет ответ API на корректность.
    В качестве параметра функция получает ответ API,
    приведенный к типам данных Python.
    Если ответ API соответствует ожиданиям,
    то функция должна вернуть список домашних работ (он может быть и пустым),
    доступный в ответе API по ключу 'homeworks'.
    """
    if not isinstance(response, dict):
        raise TypeError('переменная response не соответствует типу dict')
    homeworks_list = response['homeworks']
    if not isinstance(homeworks_list, list):
        raise TypeError('домашки приходят не в виде списка')
    return homeworks_list


def parse_status(homework):
    """Извлекает из информации о конкретной домашней работе статус этой работы.
    В качестве параметра функция получает
    только один элемент из списка домашних работ.
    В случае успеха, функция возвращает подготовленную
    для отправки в Telegram строку,
    содержащую один из вердиктов словаря HOMEWORK_STATUSES.
    """
    if not isinstance(homework, dict):
        raise TypeError('переменная homework не соответствует типу dict')
    homework_name = homework['homework_name']
    homework_status = homework['status']

    if homework_status not in (HOMEWORK_VERDICTS):
        raise KeyError('Отсутствие ожидаемых ключей в ответе API')
    verdict = HOMEWORK_VERDICTS.get(homework_status)
    logging.info('Изменился статус проверки работы')

    if homework_status == 'unknown':
        raise TypeError('Недокументированный статус домашки')
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверяет доступность переменных окружения.
    Переменные необходимы для работы программы.
    Если отсутствует хотя бы одна переменная окружения —
    функция должна вернуть False, иначе — True.
    """
    if all((PRACTICUM_TOKEN, TELEGRAM_CHAT_ID, TELEGRAM_TOKEN)):
        return bool


# flake8: noqa: C901
def main():
    """Основная логика работы бота."""
    _log_format = '%(asctime)s - %(levelname)s - %(message)s'
    logging.basicConfig(
        level=logging.INFO,
        format=_log_format,
        handlers=[logging.StreamHandler(sys.stdout)]
    )

    if not check_tokens():
        for key, token in token_dict.items():
            if not token:
                message = f'Токен {key} потерялся'
                logging.error(message)
                raise exceptions.TokenNotFoundException(message)


    bot = telegram.Bot(token=token_dict["TELEGRAM_TOKEN"])
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
        except IndexError:
            logging.info('Обновлений не найдено')
            current_timestamp = response.get('current_date')
        except TypeError as error:
            message = f'Неверный тип данных: {error}'
            logging.error(message)
        except KeyError as error:
            message = f'Ошибка доступа по ключу: {error}'
            logging.error(message)
        except exceptions.ChatNotFoundException as error:
            message = f'Не удалось отправить сообщение в Telegram - {error}'
            logging.error(message)
        except exceptions.EndPointIsNotAvailiable as error:
            message = f'ENDPOINT недоступен. Код ответа API: {error}'
            logging.error(message)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(message)
        finally:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
