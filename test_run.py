import asyncio


async def hello():
    await asyncio.sleep(4)
    print("hello world")


async def main():
    print("main start")
    asyncio.create_task(hello())
    print("main after create task")

asyncio.get_event_loop().run_until_complete(main())
asyncio.get_event_loop().run_forever()
