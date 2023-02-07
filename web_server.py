from aiohttp import web

import articles_processor


async def process_articles(request: web.Request):
    max_urls_in_query = 10
    urls = request.rel_url.query.get('urls', '').split(',')
    if len(urls) > max_urls_in_query:
        return web.json_response({"error": "too many urls in request, should be 10 or less"}, status=400)
    results = await articles_processor.process_articles_bulk(urls)
    return web.json_response({'urls': results})


app = web.Application()
app.add_routes([
    web.get('/', process_articles),
])

if __name__ == '__main__':
    web.run_app(app)
