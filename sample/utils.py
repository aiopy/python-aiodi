from logging import Logger, Formatter, StreamHandler, getLogger, NOTSET
from typing import Union


def get_simple_logger(
        name: str,
        level: Union[str, int] = NOTSET,
        fmt: str = '[%(asctime)s] - %(name)s - %(levelname)s - %(message)s',
) -> Logger:
    logger = getLogger(name)
    logger.setLevel(level)
    handler = StreamHandler()
    handler.setLevel(level)
    formatter = Formatter(fmt)
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger