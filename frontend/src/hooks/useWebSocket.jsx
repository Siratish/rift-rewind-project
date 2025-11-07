import { useEffect, useRef, useState } from 'react';
import { WS_URL } from '../config.jsx';

export default function useWebSocket({ onOpen, onMessage, onClose, shouldConnect = true }) {
    const wsRef = useRef(null);
    const [connected, setConnected] = useState(false);
    
    // Store callbacks in refs to avoid recreating WebSocket on callback changes
    const onOpenRef = useRef(onOpen);
    const onMessageRef = useRef(onMessage);
    const onCloseRef = useRef(onClose);
    
    // Update refs when callbacks change
    useEffect(() => {
        onOpenRef.current = onOpen;
        onMessageRef.current = onMessage;
        onCloseRef.current = onClose;
    }, [onOpen, onMessage, onClose]);

    useEffect(() => {
        if (!shouldConnect || !WS_URL) return;
        
        console.log('Creating WebSocket connection...');
        const ws = new WebSocket(WS_URL);
        wsRef.current = ws;

        ws.onopen = (evt) => {
            console.log('WebSocket connected');
            setConnected(true);
            onOpenRef.current && onOpenRef.current(evt, ws);
        };

        ws.onmessage = (evt) => {
            let data;
            try { data = JSON.parse(evt.data); } catch (e) { console.warn('Invalid WS payload', e); return; }
            onMessageRef.current && onMessageRef.current(data, ws);
        };

        ws.onclose = (evt) => {
            console.log('WebSocket closed');
            setConnected(false);
            onCloseRef.current && onCloseRef.current(evt, ws);
        };

        ws.onerror = (err) => {
            console.error('WS error', err);
        };

        return () => {
            console.log('Cleaning up WebSocket connection...');
            try { ws.close(); } catch (e) { }
        };
    }, [shouldConnect]); // Only recreate when shouldConnect changes

    const send = (msg) => {
        const ws = wsRef.current;
        if (!ws || ws.readyState !== WebSocket.OPEN) return false;
        ws.send(JSON.stringify(msg));
        return true;
    };

    return { connected, send };
}
