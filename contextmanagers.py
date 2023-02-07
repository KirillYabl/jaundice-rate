import contextlib
import time


@contextlib.contextmanager
def fix_execution_time_in_log(logger):
    stime = time.monotonic()
    try:
        yield
    finally:
        execution_time = time.monotonic() - stime
        logger.info(f'Анализ закончен за {execution_time} сек')
