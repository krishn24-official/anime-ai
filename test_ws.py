import asyncio
import websockets

async def test():
    try:
        async with websockets.connect('ws://localhost:8000/ws?last_checked=0') as ws:
            print('Connected!')
    except Exception as e:
        print('Error:', repr(e))

asyncio.run(test())
