declare module 'react-native-zeroconf' {
    import { EventEmitter } from 'events';

    export interface ZeroconfService {
        name: string;
        fullName: string;
        addresses: string[];
        port: number;
        txt: Record<string, string>;
    }

    export default class Zeroconf extends EventEmitter {
        constructor();
        scan(type: string, protocol: string, domain?: string): void;
        stop(): void;
        publishService(type: string, protocol: string, domain: string, name: string, port: number, txt?: Record<string, string>): void;
        unpublishService(name: string): void;
        getServices(): Record<string, ZeroconfService>;
        unbind(): void;
    }
}
