import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv
from exceptions import (EmptyResponseError, HTTPStatusError, NotSendException,
                        ResponseError, TelegramError)

load_dotenv()


PRACTICUM_TOKEN = os.getenv("YP_TOKEN")
TELEGRAM_TOKEN = os.getenv("TG_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TG_CHAT_ID")

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s, %(levelname)s, %(message)s, %(name)s',
    handlers=[logging.FileHandler('main.log', 'w', 'utf-8'),
              logging.StreamHandler(sys.stdout)]
)


def send_message(bot, message):
    """Отправка сообщения в Telegram чат."""
    try:
        logging.info('Отправляем сообщение в Telegram.')
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    except TelegramError:
        raise TelegramError(f'Сбои при отправке сообщения в Telegram: '
                            f'{message}')
    else:
        logging.info(f'Сообщение успешно отправлено: {message}')


def get_api_answer(current_timestamp):
    """Получить ответ от сервера практикума по API."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
        logging.info(f'Отправляем запрос к API. endpoint: {ENDPOINT},'
                     f'headers: {HEADERS}, params: {params}')
        if response.status_code != HTTPStatus.OK:
            raise HTTPStatusError(f'Пришел отличный от 200 статус: '
                                f'{response.status_code}. '
                                f'Причина: {response.reason}. '
                                f'Текст ответа: {response.text}, '
                                f'с параметрами: {params}')
        return response.json()
    except ResponseError as error:
        raise ResponseError(
            f'Проблема с подключением к API. endpoint: {ENDPOINT}, '
            f'headers: {HEADERS}, '
            f'params: {params}. '
            f'Ошибка: {error}')


def check_response(response: dict):
    """Проверка корректности ответа API."""
    logging.info('Начинаем проверку корректности ответа API.')
    if not isinstance(response, dict):
        raise TypeError(f'Ответ пришел не с типом данных dict: {response}')

    if 'homeworks' not in response or 'current_date' not in response:
        raise EmptyResponseError(f'Пришел пустой ответ: {response}')
    homeworks = response.get('homeworks')
    if not isinstance(homeworks, list):
        raise KeyError(
            f'Домашки не являются типом данных list: {response}')

    logging.info('Ответ API пришел в нужном формате')
    return homeworks


def parse_status(homework: dict):
    """Проверить статус работы в ответе сервера."""
    if 'homework_name' not in homework:
        raise KeyError(f'Ключ "homework_name" отсутствует в {homework}')
    homework_name = homework['homework_name']
    homework_status = homework['status']
    reviewer_comment = homework['reviewer_comment']
    if homework_status not in HOMEWORK_STATUSES:
        logging.error('Статус не обнаружен в списке')
        raise ValueError('Статус не обнаружен в списке')
    logging.info('Получен статус домашки')
    verdict = HOMEWORK_STATUSES[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверка доступности переменных окружения."""
    return all((PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID))


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        not_enough_tokens = ('Отсутствует одна из переменных окружения: '
                             'PRACTICUM_TOKEN, TELEGRAM_TOKEN, '
                             'TELEGRAM_CHAT_ID')
        logging.critical(not_enough_tokens)
        sys.exit(not_enough_tokens)

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time()) - 60*60*24*50
    current_report = {
        'lesson_name': '',
        'name': '',
        'output': '',
        'reviewer_comment': '',
    }
    prev_report = current_report.copy()
    while True:
        try:
            response = get_api_answer(current_timestamp)
            current_timestamp = response.get('current_date', current_timestamp)
            homework = check_response(response)
            if homework:
                last_homework = homework[0]
                current_report['lesson_name'] = last_homework.get('lesson_name')
                current_report['name'] = last_homework.get('homework_name')
                current_report['output'] = parse_status(last_homework)
                if last_homework.get('status') != 'reviewing':
                    current_report['reviewer_comment'] = last_homework.get(
                        'reviewer_comment')
                else:
                    current_report['reviewer_comment'] = ''

                message = (f'Модуль: {current_report["lesson_name"]}\n'
                           f'Домашка: {current_report["name"]}\n\n'
                           f'Вердикт: {current_report["output"]}\n\n'
                           f'Комментарий ревьюера: '
                           f'{current_report["reviewer_comment"]}')
            else:
                message = 'Домашки нет, проверять нечего.'
                current_report['output'] = message

            if current_report != prev_report:
                send_message(bot, message)
                prev_report = current_report.copy()
            else:
                logging.debug('Изменений нет.')

        except NotSendException as error:
            logging.exception(error)

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.exception(message)
            current_report['output'] = message
            if current_report != prev_report:
                send_message(bot, message)
                prev_report = current_report.copy()

        finally:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
