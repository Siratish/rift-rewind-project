import { useEffect, useRef, useState } from 'react';
import { WS_URL } from '../config.jsx';

export default function useWebSocket({ onOpen, onMessage, onClose, shouldConnect = true }) {
    const wsRef = useRef(null);
    const [connected, setConnected] = useState(false);

    useEffect(() => {
        if (!shouldConnect || !WS_URL) return;
        const ws = new WebSocket(WS_URL);
        wsRef.current = ws;

        ws.onopen = (evt) => {
            setConnected(true);
            onOpen && onOpen(evt, ws);
        };

        ws.onmessage = (evt) => {
            let data;
            try { data = JSON.parse(evt.data); } catch (e) { console.warn('Invalid WS payload', e); return; }
            onMessage && onMessage(data, ws);
        };

        ws.onclose = (evt) => {
            setConnected(false);
            onClose && onClose(evt, ws);
        };

        ws.onerror = (err) => {
            console.error('WS error', err);
        };

        return () => {
            try { ws.close(); } catch (e) { }
        };
    }, [onOpen, onMessage, onClose, shouldConnect]);

    const send = (msg) => {
        const ws = wsRef.current;
        if (!ws || ws.readyState !== WebSocket.OPEN) return false;
        ws.send(JSON.stringify(msg));
        return true;
    };

    return { connected, send };
}
