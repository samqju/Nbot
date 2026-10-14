import asyncio
import unittest
import itertools
from nbot.v5.g4_forward_capture_runner import PublicShardFanIn,ReceivedFrame,G4CollectorHold


class Socket:
    def __init__(self,raw,ended=False):self.raw=raw;self.ended=ended
    async def __aenter__(self):return self
    async def __aexit__(self,*args):return False
    async def __aiter__(self):
        yield self.raw
        if not self.ended:await asyncio.Future()


class ShardTests(unittest.TestCase):
    def test_backpressure_keeps_original_receipt_clock_order(self):
        class BusySocket(Socket):
            async def __aiter__(self):
                while True:yield self.raw
        async def run():
            endpoint='wss://fstream.binance.com/public/stream?streams='+ '/'.join(f'coin{i:02d}usdt@bookTicker' for i in range(50))
            clock=itertools.count(1)
            async with PublicShardFanIn(endpoint,lambda url:BusySocket(url),lambda:next(clock)) as fan:
                times=[(await fan.__anext__()).received_ms for _ in range(200)]
                self.assertEqual(times,sorted(times));self.assertEqual(len(set(times)),200)
        asyncio.run(run())
    def test_exact_disjoint_population_and_receipt_time(self):
        async def run():
            urls=[]
            def factory(url):urls.append(url);return Socket(url)
            endpoint='wss://fstream.binance.com/public/stream?streams='+ '/'.join(f'coin{i:02d}usdt@bookTicker' for i in range(50))
            async with PublicShardFanIn(endpoint,factory,lambda:12345) as fan:
                frame=await fan.__anext__()
                self.assertIsInstance(frame,ReceivedFrame)
                self.assertEqual(frame.received_ms,12345)
                names=[n for url in urls for n in url.split('?streams=')[1].split('/')]
                self.assertEqual(len(urls),5);self.assertEqual(len(set(names)),50)
        asyncio.run(run())

    def test_one_shard_eof_fails_entire_logical_route(self):
        async def run():
            endpoint='wss://fstream.binance.com/public/stream?streams=btcusdt@bookTicker'
            async with PublicShardFanIn(endpoint,lambda url:Socket('fixture',ended=True),lambda:12345) as fan:
                await asyncio.sleep(0)
                with self.assertRaisesRegex(ValueError,'SHARD_ENDED'):await fan.__anext__()
        asyncio.run(run())

    def test_duplicate_streams_never_create_competing_capture(self):
        with self.assertRaisesRegex(ValueError,'POPULATION_INVALID'):
            PublicShardFanIn('wss://fstream.binance.com/public/stream?streams=btcusdt@bookTicker/btcusdt@bookTicker',None,None)
