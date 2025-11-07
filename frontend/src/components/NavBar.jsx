import React, { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';

export default function NavBar() {
    const navigate = useNavigate();
    const location = useLocation();
    const isLanding = location.pathname === '/';
    const [scrolled, setScrolled] = useState(false);

    useEffect(() => {
        const handleScroll = () => {
            setScrolled(window.scrollY > 20);
        };

        window.addEventListener('scroll', handleScroll);
        return () => window.removeEventListener('scroll', handleScroll);
    }, []);

    return (
        <nav className={`w-full fixed top-0 left-0 z-40 transition-all duration-300 backdrop-blur-sm border-b ${scrolled ? 'bg-panel-secondary/90 border-accent-gold/10' : 'bg-transparent border-transparent'}`}>
            <div className="max-w-6xl mx-auto flex items-center justify-between px-4 py-2">
                <div
                    className="flex items-center gap-2 cursor-pointer select-none"
                    onClick={() => navigate('/')}
                >
                    <img
                        src="/rift-trivia.png"
                        alt="Rift Trivia logo"
                        className="h-7 w-7 object-contain"
                        loading="eager"
                    />
                    <div className="font-bold text-lg riot-gold">Rift Trivia</div>
                </div>
            </div>
        </nav>
    );
}
