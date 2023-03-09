import pymorphy2
from aiohttp import web

import articles_processor


def get_morph():
    global morph
    try:
        return morph
    except NameError:
        morph = pymorphy2.MorphAnalyzer()
        return morph


async def process_articles(request: web.Request):
    max_urls_in_query = 10
    urls = request.rel_url.query.get('urls', '').split(',')
    if len(urls) > max_urls_in_query:
        return web.json_response({"error": "too many urls in request, should be 10 or less"}, status=400)
    morph = get_morph()
    results = await articles_processor.process_articles_bulk(morph, urls)
    return web.json_response({'urls': results})


if __name__ == '__main__':
    app = web.Application()
    app.add_routes([
        web.get('/', process_articles),
    ])
    web.run_app(app)
