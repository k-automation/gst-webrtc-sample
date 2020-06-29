import asyncio
from threading import Thread
# import asyncio_glib
# asyncio.set_event_loop_policy(asyncio_glib.GLibEventLoopPolicy())  # noqa

import json
import logging

from aiohttp import web
from tv_client import TvClient, GstThread


gst_thread = GstThread()
gst_thread.start()

logging.basicConfig(level=logging.DEBUG,
                    format='%(relativeCreated)6d %(threadName)s %(message)s')


async def azip(*gens):
    tasks = dict((asyncio.create_task(g.__anext__(), name='azip-anext'), g)
                 for g in gens)
    while True:
        if len(tasks) == 0:
            return
        for t in tasks.keys():
            if t.cancelled():
                import pdb
                pdb.set_trace()
        done, _ = await asyncio.wait(tasks.keys(), return_when=asyncio.FIRST_COMPLETED)
        for dd in done:
            gen = tasks[dd]
            del tasks[dd]
            if dd.cancelled():
                logging.error("azip: task: %s cancelled", dd)
                continue
            if dd.exception() is None:
                task = asyncio.create_task(
                    gen.__anext__(), name='azip-anext-' + gen.__name__)
                tasks[task] = gen
                yield dd.result()
            elif not isinstance(dd.exception(), StopAsyncIteration):
                logging.error("azip: Exception %s", dd.exception())
                yield dd.result()


async def handle_websocket_client(request):
    RECEIVE = 0
    SEND = 1
    client = TvClient(asyncio.get_running_loop(), gst_thread.gst_loop)

    ws = web.WebSocketResponse()
    await ws.prepare(request)

    async def mark_receive(websocket):
        async for message in websocket:
            yield (RECEIVE, message)
        logging.info("Websocket disconnected")
        yield (RECEIVE, None)

    async def mark_send(tvclient):
        while True:
            msg = await client.sendQueue.get()
            if msg is None:
                logging.info("Closing send queue")
                break
            yield (SEND, msg)

    async for t, message in azip(mark_receive(ws), mark_send(client)):
        if t == RECEIVE:
            logging.debug("receive %s", message)
            if message is None:
                logging.info("Stop tv client")
                client.stop()
                continue
            data = message.json()
            logging.debug("receive %s", data)
            if data["action"] == "connect":
                client.setIp(data["ip"])
            elif data["action"] == "set-description":
                client.setRemoteDescription(data["desc"])
            elif data["action"] == "ice-candidate":
                client.addIceCandidate(
                    data["candidate"]["mline"], data["candidate"]["candidate"])
        else:
            logging.debug("send %s", message)
            await ws.send_json(message)
    logging.info("Client left")


async def shielded_handle_websocket_client(request):
    return await asyncio.shield(handle_websocket_client(request))

app = web.Application()

app.router.add_get('/ws', shielded_handle_websocket_client)
app.router.add_static('/', path='./static/', name='static')

web.run_app(app)
