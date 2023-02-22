import asyncio
import time

import pymorphy2
import string

import pytest


def _clean_word(word: str) -> str:
    word = word.replace('«', '').replace('»', '').replace('…', '')
    # FIXME какие еще знаки пунктуации часто встречаются ?
    word = word.strip(string.punctuation)
    return word


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


async def split_by_words(morph: pymorphy2.MorphAnalyzer, text: str, timeout: float = 3) -> list[str]:
    """Учитывает знаки пунктуации, регистр и словоформы, выкидывает предлоги."""
    words = []
    stime = time.monotonic()
    for word in text.split():
        execution_time = time.monotonic() - stime
        if execution_time > timeout:
            raise TimeoutError
        cleaned_word = _clean_word(word)
        normalized_word = morph.parse(cleaned_word)[0].normal_form
        if len(normalized_word) > 2 or normalized_word == 'не':
            words.append(normalized_word)
        await asyncio.sleep(0)
    return words

@pytest.mark.asyncio
async def test_split_by_words() -> None:
    # Экземпляры MorphAnalyzer занимают 10-15Мб RAM т.к. загружают в память много данных
    # Старайтесь организовать свой код так, чтоб создавать экземпляр MorphAnalyzer заранее и в единственном числе
    morph = pymorphy2.MorphAnalyzer()

    result = await split_by_words(morph, 'Во-первых, он хочет, чтобы')
    assert result == ['во-первых', 'хотеть', 'чтобы']

    result = await split_by_words(morph, '«Удивительно, но это стало началом!»')
    assert result == ['удивительно', 'это', 'стать', 'начало']

    with pytest.raises(TimeoutError):
        text = 'Во-первых, он хочет, чтобы, «Удивительно, но это стало началом!»'
        text *= 10_000
        result = await split_by_words(morph, text)


def calculate_jaundice_rate(article_words: list[str], charged_words: list[str]) -> float:
    """Расчитывает желтушность текста, принимает список "заряженных" слов и ищет их внутри article_words."""

    if not article_words:
        return 0.0

    found_charged_words = [word for word in article_words if word in set(charged_words)]

    score = len(found_charged_words) / len(article_words) * 100

    return round(score, 2)


def test_calculate_jaundice_rate() -> None:
    assert -0.01 < calculate_jaundice_rate([], []) < 0.01
    assert 33.0 < calculate_jaundice_rate(['все', 'аутсайдер', 'побег'], ['аутсайдер', 'банкротство']) < 34.0
