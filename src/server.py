import aiohttp
import aiohttp.web # Maybe only needed on Windows?
import asyncio
import backup_maker


async def handle_upload(request):
    data = await request.post()
    file = data['file'].file.read()
    filename = data['file'].filename

    try:
        resp = backup_maker.build_new_file(file)
    except backup_maker.BadFile:
        return aiohttp.web.HTTPBadRequest()

    response = aiohttp.web.Response(body=resp)
    response.headers['Content-Disposition'] = f'attachment; filename="NoQsb_{filename}"'
    response.headers['Access-Control-Allow-Origin'] = '*'
    return response


app = aiohttp.web.Application(client_max_size=5e7) # Max size is 50MB
app.add_routes([aiohttp.web.post('/api/upload-backup', handle_upload)])


async def main():
    runner = aiohttp.web.AppRunner(app)
    await runner.setup()
    site = aiohttp.web.TCPSite(runner, '127.0.0.1', 8008)
    await site.start()

    while True: # lol
        await asyncio.sleep(3600)


if __name__ == '__main__':
    asyncio.run(main())
