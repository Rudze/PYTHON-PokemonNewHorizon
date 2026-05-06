import asyncio
import contextlib
import json
import queue
import threading

import websockets
from websockets.exceptions import ConnectionClosed

RETRY_DELAY = 5  # seconds between reconnect attempts


class NetworkClient:
    """
    WebSocket client that runs in a background daemon thread so it never
    blocks the Pygame game loop. Reconnects automatically after any failure.

    Usage each frame:
        client.send({"type": "move", ...})   # fire-and-forget
        for msg in client.poll():            # drain received messages
            handle(msg)
    """

    def __init__(self, url: str) -> None:
        self.url = url
        self.incoming: queue.Queue[dict] = queue.Queue()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._send_queue: asyncio.Queue | None = None
        self._connected = False
        threading.Thread(target=self._run, daemon=True, name="NetworkThread").start()

    # ------------------------------------------------------------------
    # Background thread
    # ------------------------------------------------------------------

    def _run(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._connect_loop())

    async def _connect_loop(self) -> None:
        """Retry connection indefinitely with a fixed delay between attempts."""
        while True:
            self._send_queue = asyncio.Queue()
            try:
                async with websockets.connect(self.url) as ws:
                    self._connected = True
                    print(f"[Network] Connected to {self.url}")
                    await self._session(ws)
            except ConnectionClosed:
                pass
            except Exception as e:
                print(f"[Network] Connection failed: {e}")
            finally:
                self._connected = False

            print(f"[Network] Disconnected — retrying in {RETRY_DELAY}s…")
            await asyncio.sleep(RETRY_DELAY)

    async def _session(self, ws) -> None:
        """Run recv + send concurrently; stop both when either finishes."""
        recv = asyncio.create_task(self._recv(ws))
        send = asyncio.create_task(self._send(ws))
        try:
            done, pending = await asyncio.wait({recv, send}, return_when=asyncio.FIRST_COMPLETED)
            for t in pending:
                t.cancel()
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await t
        finally:
            recv.cancel()
            send.cancel()

    async def _recv(self, ws) -> None:
        async for raw in ws:
            try:
                self.incoming.put_nowait(json.loads(raw))
            except Exception:
                pass

    async def _send(self, ws) -> None:
        while True:
            raw = await self._send_queue.get()
            await ws.send(raw)  # raises ConnectionClosed → exits _session

    # ------------------------------------------------------------------
    # Game-loop API (called from the main thread)
    # ------------------------------------------------------------------

    def send(self, data: dict) -> None:
        """Enqueue a message to be sent. Thread-safe, non-blocking."""
        if self._loop and self._send_queue and self._connected:
            self._loop.call_soon_threadsafe(self._send_queue.put_nowait, json.dumps(data))

    def poll(self) -> list[dict]:
        """Return all messages received since the last call. Non-blocking."""
        msgs: list[dict] = []
        while True:
            try:
                msgs.append(self.incoming.get_nowait())
            except queue.Empty:
                break
        return msgs

    @property
    def connected(self) -> bool:
        return self._connected
