import asyncio
import enum
import logging
import os
import platform
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import aiohttp
import anyio
import async_timeout
import pymorphy2
import pytest
from aiohttp import ClientResponseError

import adapters
from adapters.exceptions import ArticleNotFound
import text_tools
import contextmanagers

logger = logging.getLogger(__name__)


class ProcessingStatus(enum.Enum):
    OK = 'OK'
    FETCH_ERROR = 'FETCH_ERROR'
    PARSING_ERROR = 'PARSING_ERROR'
    TIMEOUT = 'TIMEOUT'


async def fetch(session: aiohttp.ClientSession, url: str, timeout: float = 3) -> str:
    async with async_timeout.timeout(timeout):
        async with session.get(url) as response:
            response.raise_for_status()
            return await response.text()


async def process_article(
    session: aiohttp.ClientSession,
    morph: pymorphy2.MorphAnalyzer,
    charged_words: list[str],
    url: str,
    results: list[dict[str, Any]],
    fetch_timeout: float = 3,
    morph_timeout: float = 3,
) -> None:
    result = {'url': url, 'words': None, 'jaundice_rate': None, 'status': ProcessingStatus.FETCH_ERROR.value}

    try:
        hostname = urlsplit(url).hostname
        if hostname != 'inosmi.ru':
            raise ArticleNotFound
        html = await fetch(session, url, fetch_timeout)
        clean_text = adapters.SANITIZERS['inosmi_ru'](html, plaintext=True)
        with contextmanagers.fix_execution_time_in_log(logger):
            article_words = await text_tools.split_by_words(morph, clean_text, morph_timeout)
    except ClientResponseError:
        results.append(result)
        return
    except ArticleNotFound:
        result['status'] = ProcessingStatus.PARSING_ERROR.value
        results.append(result)
        return
    except (asyncio.TimeoutError, TimeoutError):
        result['status'] = ProcessingStatus.TIMEOUT.value
        results.append(result)
        return
    result['words'] = len(article_words)
    jaundice_rate = text_tools.calculate_jaundice_rate(article_words, charged_words)
    result['jaundice_rate'] = jaundice_rate
    result['status'] = ProcessingStatus.OK.value
    results.append(result)
    return


def get_charged_words(charged_dict_path):
    charged_words = []

    charged_words_files = os.listdir(charged_dict_path)

    if not charged_words_files:
        return charged_words

    for charged_words_file in charged_words_files:
        with open(os.path.join(charged_dict_path, charged_words_file), encoding='UTF8') as f:
            for word in f:
                word = word.strip()
                if word:
                    charged_words.append(word)
    return charged_words


@pytest.fixture
def event_loop():
    """Create an instance of the default event loop for each test case."""
    # from https://github.com/pytest-dev/pytest-asyncio/issues/371
    policy = asyncio.WindowsSelectorEventLoopPolicy()
    res = policy.new_event_loop()
    asyncio.set_event_loop(res)
    res._close = res.close
    res.close = lambda: None

    yield res

    res._close()


@pytest.mark.asyncio
async def test_process_article():
    morph = pymorphy2.MorphAnalyzer()
    try:
        charged_words = get_charged_words('data/charged_dict')
    except FileNotFoundError:
        charged_words = []
    async with aiohttp.ClientSession() as session:
        # ok
        results = []
        url = 'https://inosmi.ru/20230206/ssha-260376601.html'
        await process_article(session, morph, charged_words, url, results)
        result = results[0]
        assert result['url'] == url
        assert result['jaundice_rate'] >= 0
        assert result['jaundice_rate'] <= 100
        assert result['status'] == ProcessingStatus.OK.value

        # page not exist
        results = []
        url = 'https://inosmi.ru/20230206/siriya-26598.html'
        await process_article(session, morph, charged_words, url, results)
        result = results[0]
        assert result['url'] == url
        assert result['jaundice_rate'] is None
        assert result['words'] is None
        assert result['status'] == ProcessingStatus.FETCH_ERROR.value

        # article not found
        results = []
        url = 'https://mail.ru'
        await process_article(session, morph, charged_words, url, results)
        result = results[0]
        assert result['url'] == url
        assert result['jaundice_rate'] is None
        assert result['words'] is None
        assert result['status'] == ProcessingStatus.PARSING_ERROR.value

        # request timeout
        results = []
        url = 'https://inosmi.ru/20230206/siriya-260386598.html'
        await process_article(session, morph, charged_words, url, results, fetch_timeout=0.001)
        result = results[0]
        assert result['url'] == url
        assert result['jaundice_rate'] is None
        assert result['words'] is None
        assert result['status'] == ProcessingStatus.TIMEOUT.value

        # morph timeout
        results = []
        url = 'https://inosmi.ru/20230206/siriya-260386598.html'
        await process_article(session, morph, charged_words, url, results, morph_timeout=0.001)
        result = results[0]
        assert result['url'] == url
        assert result['jaundice_rate'] is None
        assert result['words'] is None
        assert result['status'] == ProcessingStatus.TIMEOUT.value


async def process_articles_bulk(urls: list[str], charged_dict_path: Path = 'data/charged_dict') -> list[dict[str, Any]]:
    morph = pymorphy2.MorphAnalyzer()

    try:
        charged_words = get_charged_words(charged_dict_path)
    except FileNotFoundError:
        charged_words = []

    results = []
    async with aiohttp.ClientSession() as session:
        async with anyio.create_task_group() as tg:
            for url in urls:
                tg.start_soon(process_article, session, morph, charged_words, url, results)

    return results


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)

    urls = [
        'https://inosmi.ru/20230206/ssha-260376601.html',
        'https://inosmi.ru/20230206/sholts-260387982.html',
        'https://inosmi.ru/20230206/evrokomissiya-260381212.html',
        'https://inosmi.ru/20230206/bennet-260382733.html',
        'https://inosmi.ru/20230206/basketbolist-260378360.html',
        'https://inosmi.ru/20230206/-guterresh-260387030.html',
        'https://inosmi.ru/20230206/siriya-260386598.html',
        'https://inosmi.ru/20230206/siriya-26598.html',  # not exist
        'https://mail.ru',  # wrong site
    ]

    if platform.system() == 'Windows':
        # without this it will always RuntimeError in the end of function
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(process_articles_bulk(urls))
