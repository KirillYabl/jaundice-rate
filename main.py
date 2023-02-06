import asyncio
import enum
import os
import platform

import aiohttp
import anyio
import pymorphy2
from aiohttp import ClientResponseError

import adapters
import text_tools


class ProcessingStatus(enum.Enum):
    OK = 'OK'
    FETCH_ERROR = 'FETCH_ERROR'


async def fetch(session, url):
    async with session.get(url) as response:
        response.raise_for_status()
        return await response.text()


async def process_article(session, morph, charged_words, url, results):
    result = {'url': url, 'words': None, 'jaundice_rate': None, 'status': ProcessingStatus.FETCH_ERROR}
    try:
        html = await fetch(session, url)
        result['status'] = ProcessingStatus.OK
    except ClientResponseError:
        results.append(result)
        return
    clean_text = adapters.SANITIZERS['inosmi_ru'](html, plaintext=True)
    article_words = text_tools.split_by_words(morph, clean_text)
    result['words'] = len(article_words)
    jaundice_rate = text_tools.calculate_jaundice_rate(article_words, charged_words)
    result['jaundice_rate'] = jaundice_rate
    results.append(result)
    return


async def main():
    morph = pymorphy2.MorphAnalyzer()
    charged_words = []
    charged_dict_path = 'data/charged_dict'
    charged_words_files = os.listdir(charged_dict_path)
    for charged_words_file in charged_words_files:
        with open(os.path.join(charged_dict_path, charged_words_file), encoding='UTF8') as f:
            for word in f:
                word = word.strip()
                if word:
                    charged_words.append(word)
    urls = [
        'https://inosmi.ru/20230206/ssha-260376601.html',
        'https://inosmi.ru/20230206/sholts-260387982.html',
        'https://inosmi.ru/20230206/evrokomissiya-260381212.html',
        'https://inosmi.ru/20230206/bennet-260382733.html',
        'https://inosmi.ru/20230206/basketbolist-260378360.html',
        'https://inosmi.ru/20230206/-guterresh-260387030.html',
        'https://inosmi.ru/20230206/siriya-260386598.html',
        'https://inosmi.ru/20230206/siriya-26598.html',
    ]
    results = []
    async with aiohttp.ClientSession() as session:
        async with anyio.create_task_group() as tg:
            for url in urls:
                tg.start_soon(process_article, session, morph, charged_words, url, results)
    for result in results:
        print(result)


if platform.system() == 'Windows':
    # without this it will always RuntimeError in the end of function
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

asyncio.run(main())
