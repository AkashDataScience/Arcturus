import React, { createContext, useContext, useState, useEffect } from 'react';
import { Platform } from 'react-native';
import Zeroconf, { ZeroconfService } from 'react-native-zeroconf';

interface DiscoveryContextType {
    gatewayUrl: string | null;
    isSearching: boolean;
    error: string | null;
}

const DiscoveryContext = createContext<DiscoveryContextType>({
    gatewayUrl: null,
    isSearching: true,
    error: null,
});

export const DiscoveryProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const [gatewayUrl, setGatewayUrl] = useState<string | null>(null);
    const [isSearching, setIsSearching] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        // mDNS is a native-only feature. Skip on web.
        if (Platform.OS === 'web') {
            const hostname = typeof window !== 'undefined' ? window.location.hostname : 'localhost';
            const url = `http://${hostname}:8000`;
            console.log('mDNS Browser: Web detected, using gateway URL:', url);
            setGatewayUrl(url);
            setIsSearching(false);
            return;
        }

        let zeroconf: any = null;
        try {
            zeroconf = new Zeroconf();

            zeroconf.on('start', () => {
                console.log('mDNS Browser: Searching for Arcturus Gateway...');
                setIsSearching(true);
            });

            zeroconf.on('found', (name: string) => {
                console.log('mDNS Browser: Found service:', name);
            });

            zeroconf.on('resolved', (service: ZeroconfService) => {
                if (service.name.includes('Arcturus-Gateway')) {
                    const ip = service.addresses[0];
                    const port = service.port;
                    const url = `http://${ip}:${port}`;
                    console.log('mDNS Browser: Resolved Arcturus Gateway at', url);
                    setGatewayUrl(url);
                    setIsSearching(false);
                    if (zeroconf) zeroconf.stop();
                }
            });

            zeroconf.on('error', (err: Error) => {
                console.error('mDNS Browser Error:', err);
                setError('Discovery failed');
                setIsSearching(false);
            });

            // Start scan for our custom service type
            zeroconf.scan('arcturus', 'tcp', 'local.');
        } catch (e) {
            console.error('Failed to initialize Zeroconf:', e);
            setIsSearching(false);
        }

        // Fallback for development if mDNS is slow/unreliable in emulator
        const timeout = setTimeout(() => {
            if (isSearching && !gatewayUrl) {
                console.warn('mDNS Browser: Discovery timed out, using fallback localhost');
                setGatewayUrl('http://localhost:8000');
                setIsSearching(false);
            }
        }, 5000);

        return () => {
            if (zeroconf) {
                try {
                    zeroconf.stop();
                    zeroconf.unbind();
                } catch (e) { }
            }
            clearTimeout(timeout);
        };
    }, [isSearching, gatewayUrl]);

    return (
        <DiscoveryContext.Provider value={{ gatewayUrl, isSearching, error }}>
            {children}
        </DiscoveryContext.Provider>
    );
};

export const useDiscovery = () => useContext(DiscoveryContext);
