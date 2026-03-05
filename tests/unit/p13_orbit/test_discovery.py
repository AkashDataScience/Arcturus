import pytest
import asyncio
from zeroconf.asyncio import AsyncZeroconf, AsyncServiceBrowser
from zeroconf import ServiceListener
from nodes.discovery import GatewayAdvertiser

class TestListener(ServiceListener):
    def __init__(self):
        super().__init__()
        self.found_services = []

    def add_service(self, zc, type_, name):
        self.found_services.append(name)

    def update_service(self, zc, type_, name):
        pass

    def remove_service(self, zc, type_, name):
        pass

@pytest.mark.asyncio
async def test_mdns_advertisement_discovery():
    """Verify that the GatewayAdvertiser correctly broadcasts the service."""
    advertiser = GatewayAdvertiser(port=8888, name="Test-Arcturus")
    
    # Start zeroconf browser
    aiozc = AsyncZeroconf()
    listener = TestListener()
    browser = AsyncServiceBrowser(aiozc.zeroconf, "_arcturus._tcp.local.", listener)
    
    try:
        await advertiser.start()
        
        # Wait for discovery (mDNS can be slow)
        max_wait = 10
        start_time = asyncio.get_event_loop().time()
        found = False
        
        while asyncio.get_event_loop().time() - start_time < max_wait:
            for name in listener.found_services:
                if "Test-Arcturus" in name:
                    found = True
                    break
            if found:
                break
            await asyncio.sleep(0.5)
            
        assert found, f"Gateway service was not discovered. Found: {listener.found_services}"
        
    finally:
        await advertiser.stop()
        await aiozc.async_close()
