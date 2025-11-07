import React, { useEffect, useState, useRef } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import useWebSocket from '../hooks/useWebSocket.jsx';
import BackgroundParticles from './BackgroundParticles.jsx';

// Mock data for demo mode
const MOCK_SUMMONER_RESPONSE = {
    summoner: {
        puuid: "a4dfc9b2-913b-4e22-a6f4-82394a91c1f8",
        gameName: "StrawberrySeraphine",
        tagLine: "main",
        region: "NA1",
        profileIconId: 6653,
        level: 274
    },
    routing_value: "sea",
    year: new Date().getFullYear() - 1,
    summary_exists: false,
    final_exists: false
};

const MOCK_WS_MESSAGES = [
    { state: "START_RETRIEVE_MATCH", total: 220 },
    { state: "RETRIEVING_MATCH", count: 40 },
    { state: "RETRIEVING_MATCH", count: 150 },
    { state: "RETRIEVING_MATCH", count: 220 },
    { state: "PROCESSING_MATCH" },
    { state: "GENERATING_FACTS" },
    {
        state: "COMPLETE",
        result: [
            {
                fact: "You played 412 matches this year — your busiest month was August with 67 games!",
                context: "Looks like the grind was real during summer break. Your dedication paid off — you climbed two ranks that month alone.",
                question: "True or False: You played your most games in July.",
                choices: ["True", "False"],
                correct_answer: "False"
            },
            {
                fact: "Your favorite champion was Ahri with a 58% win rate over 45 games.",
                context: "Foxfire Ahri mains never go out of style. You charmed your enemies — and the victory screen — more than half the time!",
                question: `Which champion did you play the most in ${new Date().getFullYear() - 1}?`,
                choices: ["Ahri", "Lux", "Yone", "Kai'Sa"],
                correct_answer: "Ahri"
            },
            {
                fact: "You had your longest win streak of 7 games in May.",
                context: "Seven straight wins — unstoppable energy! Maybe the stars aligned, or maybe it was just peak confidence time.",
                question: "True or False: Your longest win streak was 7 games.",
                choices: ["True", "False"],
                correct_answer: "True"
            },
            {
                fact: "In Arena mode, you scored 23 double kills and 3 triple kills.",
                context: "Seems like the 2v2v2v2 chaos suits you! You thrive in short, high-pressure fights.",
                question: "How many triple kills did you get in Arena mode?",
                choices: ["1", "2", "3", "5"],
                correct_answer: "3"
            },
            {
                fact: "Across all games, you assisted teammates 1,820 times.",
                context: "That's nearly 8 assists per game — talk about a supportive legend. You make your team shine!",
                question: "True or False: You averaged less than 5 assists per game this year.",
                choices: ["True", "False"],
                correct_answer: "False"
            },
            {
                fact: "You averaged 32 wards per 10 games — higher than 78% of players in your region.",
                context: "Vision wins games, and clearly you know it. The map was your canvas!",
                question: "What percentile were you in for ward placement?",
                choices: ["40%", "60%", "78%", "90%"],
                correct_answer: "78%"
            },
            {
                fact: "Your fastest win was a 17-minute stomp with Kai'Sa bot lane.",
                context: "That poor enemy Nexus didn't know what hit it. Sometimes teamwork just *clicks*.",
                question: "True or False: Your fastest win lasted under 20 minutes.",
                choices: ["True", "False"],
                correct_answer: "True"
            },
            {
                fact: "Your most common death cause was from junglers — 38% of your deaths came from ganks.",
                context: "Maybe invest in a few extra Control Wards next year. Those junglers have your name marked!",
                question: "What percentage of your deaths came from enemy junglers?",
                choices: ["20%", "28%", "38%", "45%"],
                correct_answer: "38%"
            },
            {
                fact: "Your most played role was Mid — where you spent 46% of your total game time.",
                context: "The heart of the Rift belongs to you. Whether roaming or outplaying, Mid lane was your stage for epic moments.",
                question: "True or False: You played Mid more than any other role.",
                choices: ["True", "False"],
                correct_answer: "True"
            },
            {
                fact: "Overall, you secured 147 objectives — that's 33 dragons, 21 barons, and 93 towers.",
                context: "Objective control king! You made sure every fight counted for something.",
                question: "How many barons did you help secure this year?",
                choices: ["10", "21", "27", "33"],
                correct_answer: "21"
            }
        ]
    }
];

export default function ProgressPage() {
    const navigate = useNavigate();
    const [searchParams] = useSearchParams();
    const [statusMessage, setStatusMessage] = useState('Preparing scan...');
    const [progress, setProgress] = useState(0);
    const [payload, setPayload] = useState(null);
    const summonerResp = useRef(null);
    const isDemo = searchParams.get('demo') === 'true';

    useEffect(() => {
        // Handle demo mode
        if (isDemo) {
            sessionStorage.setItem('rr_summoner_response', JSON.stringify(MOCK_SUMMONER_RESPONSE));
            summonerResp.current = MOCK_SUMMONER_RESPONSE;
            return;
        }

        // Normal flow
        const raw = sessionStorage.getItem('rr_summoner_response');
        if (!raw) {
            navigate('/');
            return;
        }
        summonerResp.current = JSON.parse(raw);
    }, [navigate, isDemo]);

    // Simulated WebSocket handling for demo mode
    useEffect(() => {
        if (!isDemo || !summonerResp.current) return;

        let timeoutIds = [];
        const delays = [0, 2000, 4000, 6000, 8000, 10000, 12000]; // Staged delays

        MOCK_WS_MESSAGES.forEach((msg, idx) => {
            const timeoutId = setTimeout(() => {
                handleWebSocketMessage(msg);
            }, delays[idx] || 0);
            timeoutIds.push(timeoutId);
        });

        return () => timeoutIds.forEach(id => clearTimeout(id));
    }, [isDemo]);

    // Handle both real and mock WebSocket messages
    const handleWebSocketMessage = (data) => {
        if (data.state === 'START_RETRIEVE_MATCH') {
            setStatusMessage(`Retrieving matches: 0 / ${data.total}`);
            setProgress(5);
        } else if (data.state === 'RETRIEVING_MATCH') {
            const percent = Math.min(5 + Math.round((data.count / data.total) * 60), 65);
            setProgress(percent);
            setStatusMessage(`Retrieving matches: ${data.count} / ${data.total}`);
        } else if (data.state === 'PROCESSING_MATCH') {
            setStatusMessage('Processing matches (ETL & KB sync)...');
            setProgress(75);
        } else if (data.state === 'GENERATING_FACTS') {
            setStatusMessage('Generating facts (Bedrock calls)...');
            setProgress(90);
        } else if (data.state === 'COMPLETE') {
            setStatusMessage('Complete — preparing insights');
            setProgress(100);
            // data.result is expected to be the final array
            const resultPayload = { quizFacts: data.result, summoner: summonerResp.current?.summoner };
            sessionStorage.setItem('rr_final', JSON.stringify(resultPayload));
            setTimeout(() => navigate('/insights'), 800);
        }
    };

    // Real WebSocket handling
    const { connected, send } = useWebSocket({
        shouldConnect: !isDemo && !!summonerResp.current, // Only connect WebSocket in non-demo mode
        onOpen: () => {
            setStatusMessage('Connected. Sending startJob...');
            // Read summoner response from sessionStorage again (ensures it's available)
            const raw = sessionStorage.getItem('rr_summoner_response');
            if (!raw) return;
            const body = JSON.parse(raw);
            const puuid = body?.summoner?.puuid;
            const year = body?.year;
            const summary_exists = body?.summary_exists;
            const final_exists = body?.final_exists;
            const routing_value = body?.routing_value;
            // Send startJob to server to kick Step Function via backend
            const msg = { action: 'startJob', puuid, year, summary_exists, final_exists, routing_value };
            send(msg);
        },
        onMessage: handleWebSocketMessage,
        onClose: () => setStatusMessage('Connection closed'),
    });

    return (
        <div className="min-h-screen flex items-center justify-center p-6">
            <BackgroundParticles />
            <div className="max-w-2xl w-full rr-panel">
                <h2 className="text-2xl riot-gold mb-2">Scanning your match history...</h2>
                <p className="text-text-secondary mb-6">{statusMessage}</p>

                <div className="progress-track mb-4">
                    <div className="progress-fill" style={{ width: `${progress}%` }} />
                </div>

                <div className="flex gap-3 items-center">
                    <div className="rr-spinner" />
                    <div className="text-sm text-text-secondary">{progress}%</div>
                </div>

                <div className="mt-6 text-xs text-text-secondary bg-panel-secondary/30 p-3 rounded-lg border border-accent-gold/5">
                    Tip: Keep this page open — we will send updates from the backend as the Step Function progresses.
                </div>
            </div>
        </div>
    );
}