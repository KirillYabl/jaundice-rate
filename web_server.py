from aiohttp import web

import articles_processor


async def process_articles(request: web.Request):
    urls = request.rel_url.query.get('urls', '').split(',')
    results = await articles_processor.process_articles_bulk(urls)
    return web.json_response({'urls': results})


app = web.Application()
app.add_routes([
    web.get('/', process_articles),
])

if __name__ == '__main__':
    web.run_app(app)
