import asyncio


async def azip(*gens):
    tasks = dict((asyncio.Task(g.__anext__()), g) for g in gens)
    while True:
        if len(tasks) == 0:
            return
        done, _ = await asyncio.wait(tasks.keys(), return_when=asyncio.FIRST_COMPLETED)
        for dd in done:
            gen = tasks[dd]
            del tasks[dd]
            if dd.exception() is None:
                tasks[asyncio.Task(gen.__anext__())] = gen
                yield dd.result()
            elif not isinstance(dd.exception(), StopAsyncIteration):
                yield dd.result()


async def gen():
    i = 0
    for _ in range(2):
        await asyncio.sleep(1.33)
        yield i
        i += 1
    yield "asds"


async def gen2():
    i = 0
    for _ in range(30):
        await asyncio.sleep(1.34)
        yield i
        i -= 1


async def printer():
    async for x in azip(gen(), gen2()):
        print(x)

asyncio.run(printer())
