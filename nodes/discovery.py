"""mDNS Discovery for Arcturus Gateway.

Advertises the Arcturus gateway service on the local network using Bonjour/mDNS,
allowing mobile and desktop nodes to discover the gateway without manual IP entry.
"""

import socket
import logging
import asyncio
from zeroconf.asyncio import AsyncZeroconf
from zeroconf import ServiceInfo

logger = logging.getLogger(__name__)

class GatewayAdvertiser:
    """Advertises the Arcturus gateway as a '_arcturus._tcp.local.' service."""

    def __init__(self, port: int = 8000, name: str = "Arcturus-Gateway"):
        self.port = port
        self.name = name
        self.service_type = "_arcturus._tcp.local."
        self.aiozc = None
        self.service_info = None

    def _get_local_ip(self) -> str:
        """Get the primary local IP address."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(0)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    async def start(self):
        """Start advertising the service."""
        if self.aiozc:
            return

        local_ip = self._get_local_ip()
        logger.info("Starting mDNS advertisement for %s at %s:%d", self.name, local_ip, self.port)
        
        desc = {"version": "1.0.0", "vendor": "School of AI"}
        
        self.service_info = ServiceInfo(
            self.service_type,
            f"{self.name}.{self.service_type}",
            addresses=[socket.inet_aton(local_ip)],
            port=self.port,
            properties=desc,
            server=f"{self.name.lower()}.local.",
        )
        
        self.aiozc = AsyncZeroconf()
        await self.aiozc.zeroconf.async_register_service(self.service_info)

    async def stop(self):
        """Stop advertising the service."""
        if self.aiozc:
            logger.info("Stopping mDNS advertisement")
            await self.aiozc.zeroconf.async_unregister_service(self.service_info)
            await self.aiozc.async_close()
            self.aiozc = None
            self.service_info = None

if __name__ == "__main__":
    # Test script for standalone execution
    import time
    logging.basicConfig(level=logging.INFO)
    advertiser = GatewayAdvertiser()
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(advertiser.start())
        print("M-DNS Advertising... Press Ctrl+C to stop.")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        loop.run_until_complete(advertiser.stop())
