import React from 'react';

export default function BackgroundParticles() {
    // Render a handful of blurred circles that float subtly; purely decorative
    return (
        <div className="rr-particles" aria-hidden="true">
            <div className="rr-particle particle-1" />
            <div className="rr-particle particle-2" />
            <div className="rr-particle particle-3" />
            <div className="rr-particle particle-4" />
            <div className="rr-particle particle-5" />
            <div className="rr-particle particle-6" />
        </div>
    );
}