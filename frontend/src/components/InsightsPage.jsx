import React, { useEffect, useState, useRef, useCallback } from 'react';
import { useParams, useSearchParams, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import SummonerBanner from './SummonerBanner.jsx';
import ShareCardPreview from './ShareCardPreview.jsx';
import BackgroundParticles from './BackgroundParticles.jsx';
import useWebSocket from '../hooks/useWebSocket.jsx';
import { fetchSummoner } from '../api.jsx';

export default function InsightsPage() {
    const { region, gameName, tagLine } = useParams();
    const [searchParams] = useSearchParams();
    const navigate = useNavigate();
    
    const [payload, setPayload] = useState(null);
    const [loading, setLoading] = useState(true);
    const [statusMessage, setStatusMessage] = useState('Calibrating arcane analyzers...');
    const [progress, setProgress] = useState(0);
    const [totalMatches, setTotalMatches] = useState(0);
    const totalMatchesRef = useRef(0); // Use ref to avoid closure issues
    const summonerResp = useRef(null);
    const wsRef = useRef(null); // Store WebSocket reference
    
    // Quiz state
    const [currentFactIndex, setCurrentFactIndex] = useState(0);
    const [selectedAnswer, setSelectedAnswer] = useState(null);
    const [showResult, setShowResult] = useState(false);
    const [answeredFacts, setAnsweredFacts] = useState([]); // Track which facts have been answered
    const [correctAnswers, setCorrectAnswers] = useState([]); // Track correct answers
    // Animation state for showing fact/context after highlight
    const [showFact, setShowFact] = useState(false);
    // Track if highlight animation has run for this question
    const [highlightedIndex, setHighlightedIndex] = useState(null);

    // Reset showFact and highlightedIndex when question changes or showResult resets
    useEffect(() => {
        setShowFact(false);
        setHighlightedIndex(null);
    }, [currentFactIndex, showResult]);

    // Initialize: check sessionStorage or fetch from API
    useEffect(() => {
        const initializeData = async () => {
            // Check if we have data in sessionStorage from LandingPage
            const cachedResponse = sessionStorage.getItem('rr_summoner_response');
            const cachedFinal = sessionStorage.getItem('rr_final');
            
            // Verify cached data matches current URL params
            let cacheValid = false;
            if (cachedResponse) {
                const cached = JSON.parse(cachedResponse);
                const cachedRiotId = `${cached.summoner?.gameName || ''}#${cached.summoner?.tagLine || ''}`;
                const currentRiotId = `${gameName}#${tagLine}`;
                cacheValid = cachedRiotId.toLowerCase() === currentRiotId.toLowerCase() && 
                             (cached.summoner?.region || cached.routing_value)?.toLowerCase() === region.toLowerCase();
            }
            
            if (!cacheValid) {
                // Clear stale cache including progress and reset state
                sessionStorage.removeItem('rr_summoner_response');
                sessionStorage.removeItem('rr_final');
                sessionStorage.removeItem('rr_progress');
                setPayload(null); // Clear old payload
                setProgress(0);
                setStatusMessage('Calibrating arcane analyzers...');
            }
            
            if (cacheValid && cachedFinal) {
                // Already have insights for this account, show them
                setPayload(JSON.parse(cachedFinal));
                setLoading(false);
                return;
            }
            
            // Try to restore progress state if available
            const cachedProgress = sessionStorage.getItem('rr_progress');
            if (cacheValid && cachedProgress) {
                try {
                    const progressData = JSON.parse(cachedProgress);
                    setProgress(progressData.progress || 0);
                    setStatusMessage(progressData.statusMessage || 'Calibrating arcane analyzers...');
                    setTotalMatches(progressData.totalMatches || 0);
                    totalMatchesRef.current = progressData.totalMatches || 0;
                } catch (e) {
                    console.warn('Failed to restore progress:', e);
                }
            }
            
            if (cacheValid && cachedResponse) {
                // Have summoner response for this account, use it
                summonerResp.current = JSON.parse(cachedResponse);
            } else {
                // No cache or cache invalid, fetch from API using URL params
                try {
                    const summonerName = `${gameName}#${tagLine}`;
                    const body = await fetchSummoner(summonerName, region);
                    summonerResp.current = body;
                    sessionStorage.setItem('rr_summoner_response', JSON.stringify(body));
                    
                    // If final_exists is true, we might want to fetch the insights directly
                    // For now, we'll still run through the progress flow
                } catch (err) {
                    console.error('Failed to fetch summoner:', err);
                    navigate('/');
                    return;
                }
            }
            
            // Continue to progress/loading state
            setLoading(true);
        };
        
        initializeData();
    }, [region, gameName, tagLine, navigate]);

    // Fun facts management (rotate every 30s while loading)

    // Fun facts management (rotate every 30s while loading)
    const [funFacts, setFunFacts] = useState([]);
    const [funFact, setFunFact] = useState('');

    // Fetch fun facts from public
    useEffect(() => {
        let cancelled = false;
        fetch('/fun-facts.txt')
            .then((r) => r.text())
            .then((txt) => {
                if (cancelled) return;
                const arr = txt.split(/\r?\n/).map((s) => s.trim()).filter(Boolean);
                setFunFacts(arr);
                if (!funFact && arr.length) {
                    const initial = arr[Math.floor(Math.random() * arr.length)];
                    setFunFact(initial);
                }
            })
            .catch(() => {
                // Silently ignore; UI will just hide the line if empty
            });
        return () => { cancelled = true; };
    }, []);

    // Rotate fun fact every 30 seconds during loading
    useEffect(() => {
        if (!loading || funFacts.length === 0) return;
        // Ensure we have an initial value
        if (!funFact) {
            const initial = funFacts[Math.floor(Math.random() * funFacts.length)];
            setFunFact(initial);
        }
        const pickNext = () => {
            setFunFact((prev) => {
                if (funFacts.length <= 1) return funFacts[0] || prev || '';
                let next = prev;
                // Avoid immediate repeat
                while (next === prev) {
                    next = funFacts[Math.floor(Math.random() * funFacts.length)];
                }
                return next;
            });
        };
        const id = setInterval(pickNext, 30000);
        return () => clearInterval(id);
    }, [loading, funFacts, funFact]);

    const handleWebSocketMessage = useCallback((data) => {
        switch (data.state) {
            case 'BUSY': {
                setStatusMessage('Another seeker is already weaving this tale... ⌛');
                setProgress(0);
                // Clear progress cache and close WebSocket
                sessionStorage.removeItem('rr_progress');
                // Show error message after a short delay
                setTimeout(() => {
                    alert('⌛ This chronicle is already being woven by another request!\n\nPlease wait for the current generation to complete, then try again in a few moments.');
                    navigate('/');
                }, 500);
                break;
            }
            case 'START_RETRIEVE_MATCH': {
                setTotalMatches(data.total);
                totalMatchesRef.current = data.total;
                setStatusMessage(`Peering into ${data.total} echoes...`);
                setProgress(5);
                // Cache progress
                sessionStorage.setItem('rr_progress', JSON.stringify({
                    progress: 5,
                    statusMessage: `Peering into ${data.total} echoes...`,
                    totalMatches: data.total
                }));
                break;
            }
            case 'RETRIEVING_MATCH': {
                const total = totalMatchesRef.current || data.total || 1;
                const percent = Math.min(5 + Math.round((data.count / total) * 70), 75);
                setProgress(percent);
                setStatusMessage(`Collecting shards: ${data.count} / ${total}`);
                // Cache progress
                sessionStorage.setItem('rr_progress', JSON.stringify({
                    progress: percent,
                    statusMessage: `Collecting shards: ${data.count} / ${total}`,
                    totalMatches: total
                }));
                break;
            }
            case 'PROCESSING_MATCH': {
                setStatusMessage('Distilling patterns from the chaos...');
                setProgress(75);
                // Cache progress
                sessionStorage.setItem('rr_progress', JSON.stringify({
                    progress: 75,
                    statusMessage: 'Distilling patterns from the chaos...',
                    totalMatches: totalMatchesRef.current
                }));
                break;
            }
            case 'GENERATING_FACTS': {
                setStatusMessage('Assembling enchanted trivia...');
                setProgress(90);
                // Cache progress
                sessionStorage.setItem('rr_progress', JSON.stringify({
                    progress: 90,
                    statusMessage: 'Assembling enchanted trivia...',
                    totalMatches: totalMatchesRef.current
                }));
                break;
            }
            case 'COMPLETE': {
                setStatusMessage('Finalizing your chronicle...');
                setProgress(100);
                const resultPayload = { quizFacts: data.result, summoner: summonerResp.current?.summoner };
                sessionStorage.setItem('rr_final', JSON.stringify(resultPayload));
                // Clear progress cache as we're done
                sessionStorage.removeItem('rr_progress');
                setTimeout(() => {
                    setPayload(resultPayload);
                    setLoading(false);
                }, 800);
                break;
            }
            default:
                break;
        }
    }, [navigate]);

    const handleWebSocketClose = useCallback(() => {
        setStatusMessage('Connection closed');
    }, []);

    // Real WebSocket handling
    const { connected, send } = useWebSocket({
        shouldConnect: loading && !!summonerResp.current,
        onOpen: (evt, ws) => {
            setStatusMessage('Connected. Sending startJob...');
            const raw = sessionStorage.getItem('rr_summoner_response');
            if (!raw) return;
            const body = JSON.parse(raw);
            const msg = {
                action: 'startJob',
                puuid: body?.summoner?.puuid,
                year: body?.year,
                summary_exists: body?.summary_exists,
                final_exists: body?.final_exists,
                routing_value: body?.routing_value
            };
            ws.send(JSON.stringify(msg));
        },
        onMessage: handleWebSocketMessage,
        onClose: handleWebSocketClose,
    });

    // Show loading/progress UI
    if (loading) {
        const summoner = summonerResp.current?.summoner || {};
        
        return (
            <div className="px-8 pt-20 pb-8 bg-gradient-to-b from-background to-background-darker min-h-[calc(100vh-3rem)]">
                <BackgroundParticles />
                
                <div className="max-w-2xl mx-auto">
                    {/* SummonerBanner at top */}
                    <div className="mb-8">
                        <SummonerBanner summoner={summoner} />
                    </div>
                    
                    <div className="rr-panel">
                        <h2 className="text-2xl riot-gold mb-6">Summoning your season’s story...</h2>

                        <div className="progress-track mb-3">
                            <div className="progress-fill" style={{ width: `${progress}%` }} />
                        </div>

                        <div className="flex gap-3 items-center mb-6">
                            <div className="relative inline-flex items-center justify-center">
                                <div className="rr-spinner" />
                                <div className="absolute text-xs font-semibold riot-gold">{progress}%</div>
                            </div>
                            <div className="text-sm text-text-secondary flex-1">{statusMessage}</div>
                        </div>

                            { funFact && (
                                <div className="text-xs text-text-secondary bg-panel-secondary/30 p-3 rounded-lg border border-accent-gold/5">
                                    Fun fact 💡: {funFact}
                                </div>
                            )}
                    </div>
                </div>
            </div>
        );
    }

    // Show insights UI
    if (!payload) {
        return (
            <div className="flex items-center justify-center bg-background min-h-[calc(100vh-3rem)]">
                <div className="p-6 text-text-secondary">No insights yet — start a new Rift Trivia from the landing page ✨</div>
            </div>
        );
    }

    const quizFacts = payload.quizFacts || [];
    const summoner = payload.summoner || {};
    const allAnswered = answeredFacts.length === quizFacts.length;
    const showSummary = allAnswered && currentFactIndex >= quizFacts.length;
    
    // Handle answer selection
    const handleAnswerClick = (choice) => {
        if (showResult) return; // Already answered
        setSelectedAnswer(choice);
        setShowResult(true);
        if (!answeredFacts.includes(currentFactIndex)) {
            setAnsweredFacts([...answeredFacts, currentFactIndex]);
            // Track if answer is correct
            const isCorrect = choice === quizFacts[currentFactIndex]?.correct_answer;
            if (isCorrect) {
                setCorrectAnswers([...correctAnswers, currentFactIndex]);
            }
        }
    };
    
    // Go to next fact
    const handleNext = () => {
        if (currentFactIndex < quizFacts.length - 1) {
            setCurrentFactIndex(currentFactIndex + 1);
            setSelectedAnswer(null);
            setShowResult(false);
        }
    };
    
    // Go to previous fact
    const handlePrevious = () => {
        if (currentFactIndex > 0) {
            setCurrentFactIndex(currentFactIndex - 1);
            setSelectedAnswer(null);
            setShowResult(false);
        }
    };
    
    // Show summary
    const handleShowSummary = () => {
        setCurrentFactIndex(quizFacts.length); // Move past the last fact to trigger summary
    };
    
    const currentFact = quizFacts[currentFactIndex];
    const isCorrect = selectedAnswer === currentFact?.correct_answer;

    return (
        <div className="px-8 pt-20 pb-8 bg-gradient-to-b from-background to-background-darker min-h-[calc(100vh-3rem)]">
            <BackgroundParticles />
            
            <div className="max-w-2xl mx-auto">
                {/* Show SummonerBanner only in quiz mode, not in summary */}
                {!showSummary && (
                    <div className="mb-8">
                        <SummonerBanner summoner={summoner} />
                    </div>
                )}
                
                {!showSummary ? (
                    /* Quiz Mode - One fact at a time */
                    <motion.div 
                        key={currentFactIndex}
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -20 }}
                        className="rr-panel"
                    >
                        {/* Progress indicator */}
                        <div className="flex justify-between items-center mb-6">
                            <div className="text-sm text-text-secondary">
                                Trivia {currentFactIndex + 1} of {quizFacts.length}
                            </div>
                        </div>
                        
                        {/* Question */}
                        <div className="mb-6">
                            <h3 className="text-2xl font-bold riot-gold mb-4">{currentFact?.question}</h3>
                        </div>
                        
                        {/* Choices */}
                        <div className="flex flex-wrap justify-center gap-3 mb-6">
                            {currentFact?.choices?.map((choice, idx) => {
                                const isSelected = selectedAnswer === choice;
                                const isCorrectAnswer = choice === currentFact.correct_answer;
                                let bgClass = 'bg-panel-secondary/60 hover:bg-panel-secondary/90';
                                if (showResult && isSelected) {
                                    bgClass = isCorrect 
                                        ? 'bg-green-500/40' 
                                        : 'bg-red-500/40';
                                } else if (showResult && isCorrectAnswer) {
                                    bgClass = 'bg-green-500/40';
                                }

                                // Animate the correct choice button after answering, only once
                                if (showResult && isCorrectAnswer && highlightedIndex === null) {
                                    return (
                                        <motion.button
                                            key={idx}
                                            onClick={() => handleAnswerClick(choice)}
                                            disabled={showResult}
                                            className={`px-6 py-4 rounded-lg text-center transition-all ${bgClass} ${!showResult ? 'cursor-pointer' : 'cursor-default'} flex-1 min-w-[120px]`}
                                            initial={{ scale: 1, boxShadow: '0 0 0px 0px #0000' }}
                                            animate={selectedAnswer === choice
                                                ? { scale: [1, 1.08, 1], boxShadow: ['0 0 0px 0px #0000', '0 0 24px 6px #eab30888', '0 0 0px 0px #0000'] }
                                                : { scale: [1, 1.08, 1], boxShadow: ['0 0 0px 0px #0000', '0 0 24px 6px #eab30888', '0 0 0px 0px #0000'] }
                                            }
                                            transition={{ duration: 0.45, times: [0, 0.5, 1] }}
                                            onAnimationComplete={() => {
                                                setHighlightedIndex(idx);
                                                setShowFact(true);
                                            }}
                                        >
                                            {choice}
                                        </motion.button>
                                    );
                                }
                                // After animation, render as normal button
                                return (
                                    <button
                                        key={idx}
                                        onClick={() => handleAnswerClick(choice)}
                                        disabled={showResult}
                                        className={`px-6 py-4 rounded-lg text-center transition-all ${bgClass} ${!showResult ? 'cursor-pointer' : 'cursor-default'} flex-1 min-w-[120px]`}
                                    >
                                        {choice}
                                    </button>
                                );
                            })}
                        </div>
                        
                        {/* Result - Show fact/context after highlight animation on correct choice */}
                        {showResult && showFact && (
                            <motion.div
                                initial={{ opacity: 0, y: 12 }}
                                animate={{ opacity: 1, y: 0 }}
                                className="space-y-4"
                            >
                                <div className="p-4 rounded-lg bg-panel-secondary/30">
                                    <div className="flex items-baseline gap-2 font-semibold riot-gold mb-2">
                                        <span>Fact:</span>
                                        <span className="text-text-primary font-normal">{currentFact.fact}</span>
                                    </div>
                                    <div className="text-sm text-text-secondary">{currentFact.context}</div>
                                </div>
                                {/* Navigation */}
                                <div className="flex justify-end pt-4">
                                    {currentFactIndex < quizFacts.length - 1 ? (
                                        <button
                                            onClick={handleNext}
                                            className="px-6 py-2 btn-cta"
                                        >
                                            Next →
                                        </button>
                                    ) : (
                                        <button
                                            onClick={handleShowSummary}
                                            className="px-6 py-2 btn-cta"
                                        >
                                            View Summary 🎉
                                        </button>
                                    )}
                                </div>
                            </motion.div>
                        )}
                    </motion.div>
                ) : (
                    /* Summary Mode - Show only share card */
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        className="flex justify-center"
                    >
                        <div className="rr-panel max-w-md">
                            <div className="text-center mb-6">
                                <h4 className="font-bold mb-2 riot-gold text-2xl">Your Rift Trivia 2024</h4>
                                
                                {/* Score display integrated into header */}
                                <div className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-panel-secondary/30 border border-accent-gold/20 mb-3">
                                    <span className="text-sm text-text-secondary">Score:</span>
                                    <span className="text-xl font-bold riot-gold">{correctAnswers.length}/{quizFacts.length}</span>
                                    <span className="text-lg">
                                        {correctAnswers.length === quizFacts.length 
                                            ? "🎉" 
                                            : correctAnswers.length >= quizFacts.length / 2
                                            ? "👏"
                                            : "🎮"}
                                    </span>
                                </div>
                                
                                <p className="text-sm text-text-secondary">Share your year-end recap with friends!</p>
                            </div>
                            
                            <ShareCardPreview payload={payload} />
                        </div>
                    </motion.div>
                )}
            </div>
        </div>
    );
}