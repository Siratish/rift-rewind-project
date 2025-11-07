import React, { useRef, useEffect, useState } from 'react';
import { BrowserRouter as Router, Routes, Route, useLocation } from 'react-router-dom';
import { AnimatePresence, motion } from 'framer-motion';
import LandingPage from './components/LandingPage.jsx';
import InsightsPage from './components/InsightsPage.jsx';
import NavBar from './components/NavBar.jsx';

function AnimatedRoutes() {
  const location = useLocation();
  const prevRef = useRef(location.pathname);
  const [variantKey, setVariantKey] = useState('default');

  useEffect(() => {
    const prev = prevRef.current;
    // If navigating from progress -> insights, use a zoom transition
    if (prev === '/progress' && location.pathname === '/insights') {
      setVariantKey('zoom');
    } else {
      setVariantKey('default');
    }
    prevRef.current = location.pathname;
  }, [location.pathname]);

  const variants = {
    default: {
      initial: { opacity: 0, y: 8 },
      animate: { opacity: 1, y: 0 },
      exit: { opacity: 0, y: -8 },
      transition: { duration: 0.32 }
    },
    zoom: {
      initial: { opacity: 0, scale: 0.96 },
      animate: { opacity: 1, scale: 1 },
      exit: { opacity: 0, scale: 1.02 },
      transition: { duration: 0.4 }
    }
  };
  return (
    <AnimatePresence mode="wait">
      <motion.div
        key={location.pathname}
        initial={variants[variantKey].initial}
        animate={variants[variantKey].animate}
        exit={variants[variantKey].exit}
        transition={variants[variantKey].transition}
      >
        <Routes location={location} key={location.pathname}>
          <Route path="/" element={<LandingPage />} />
          <Route path="/:region/:gameName/:tagLine" element={<InsightsPage />} />
        </Routes>
      </motion.div>
    </AnimatePresence>
  );
}

export default function App() {
  return (
    <Router>
      <div className="flex flex-col min-h-screen">
        <NavBar />
        <div className="flex-grow">
          <AnimatedRoutes />
        </div>
        <footer className="w-full py-3 flex flex-col sm:flex-row items-center justify-center text-text-secondary text-xs gap-2 mt-auto">
          <div>Built for Rift Rewind Hackathon • Powered by AWS</div>
        </footer>
      </div>
    </Router>
  );
}