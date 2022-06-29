class TokenNotFoundException(Exception):
    """Обработка исключения при отсуствии хотя бы одного из токенов."""

    pass


class ChatNotFoundException(Exception):
    """Обработка исключения при неверном chat_id."""

    pass


class EndPointIsNotAvailiable(Exception):
    """Обработка исключения при недоступности ENDPOINT API."""

    pass
