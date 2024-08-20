import logging
import pydantic

logger = logging.getLogger(__name__)

_SECRETS_SINGLETON_MAP: dict[str, pydantic.SecretStr] = dict()


def put_secret(secret_key: str, secret_value: pydantic.SecretStr | str):
    if secret_key in _SECRETS_SINGLETON_MAP:
        logger.warning(f'Overwriting existing secret {secret_key}!')

    # We will box the secret value here, if passed in as a string.
    if isinstance(secret_value, str):
        secret_value = pydantic.SecretStr(secret_value=secret_value)
    _SECRETS_SINGLETON_MAP[secret_key] = secret_value


def get_secret(secret_key: str) -> pydantic.SecretStr:
    if secret_key not in _SECRETS_SINGLETON_MAP or _SECRETS_SINGLETON_MAP[secret_key] is None:
        logger.warning(f'Secret {secret_key} has been requested but does not exist!')
    return _SECRETS_SINGLETON_MAP[secret_key]
