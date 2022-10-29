class NotSendException(Exception):
    """Исключение не для пересылки в Telegram."""
    pass


class ResponseError(Exception):
    """Отсутствует подключение к API."""


class EmptyResponseError(NotSendException):
    """Пустой запрос"""
    pass


class HTTPStatusError(Exception):
    """Пришел статус отличный от 200."""
    pass


class TelegramError(NotSendException):
    """Сообщение не отправлено в Telegram."""
