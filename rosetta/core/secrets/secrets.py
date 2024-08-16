import logging

logger = logging.getLogger(__name__)

_SECRETS_SINGLETON_MAP: dict[str, str] = dict()


def put_secret(secret_key: str, secret_value: str):
    if secret_key in _SECRETS_SINGLETON_MAP:
        logger.warning(f'Overwriting existing secret {secret_key}!')
    _SECRETS_SINGLETON_MAP[secret_key] = secret_value


def get_secret(secret_key: str) -> str:
    return _SECRETS_SINGLETON_MAP[secret_key]
