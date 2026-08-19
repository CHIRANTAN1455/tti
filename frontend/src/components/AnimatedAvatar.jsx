import { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

/**
 * AnimatedAvatar — a lightweight, self-contained "AI guide" character.
 * No external assets/network calls: pure inline SVG + CSS/Framer Motion animation.
 *
 * Props:
 *  - speaking: boolean — when true, mouth/aura animate as if narrating
 *  - tone: 'teal' | 'navy' — accent color, matches wellness/clinical tracks
 *  - size: pixel size of the avatar (default 72)
 */
const TONES = {
  teal: {
    from: '#2FBFAE',
    to: '#1a8f83',
    glow: 'rgba(47, 191, 174, 0.35)',
  },
  navy: {
    from: '#334155',
    to: '#0F172A',
    glow: 'rgba(51, 65, 85, 0.35)',
  },
};

const AnimatedAvatar = ({ speaking = false, tone = 'teal', size = 72, className = '' }) => {
  const [blink, setBlink] = useState(false);
  const colors = TONES[tone] || TONES.teal;

  // Periodic blink, independent of speaking state
  useEffect(() => {
    let timeout;
    const scheduleBlink = () => {
      timeout = setTimeout(() => {
        setBlink(true);
        setTimeout(() => setBlink(false), 140);
        scheduleBlink();
      }, 2200 + Math.random() * 2200);
    };
    scheduleBlink();
    return () => clearTimeout(timeout);
  }, []);

  return (
    <div
      className={`relative inline-flex items-center justify-center ${className}`}
      style={{ width: size, height: size }}
      data-testid="animated-avatar"
    >
      {/* Ambient glow / aura */}
      <motion.div
        className="absolute inset-0 rounded-full"
        style={{ background: colors.glow, filter: 'blur(10px)' }}
        animate={
          speaking
            ? { scale: [1, 1.18, 1], opacity: [0.6, 0.95, 0.6] }
            : { scale: [1, 1.06, 1], opacity: [0.45, 0.6, 0.45] }
        }
        transition={{ duration: speaking ? 1.1 : 3, repeat: Infinity, ease: 'easeInOut' }}
      />

      {/* Speaking sound-wave rings */}
      <AnimatePresence>
        {speaking && (
          <motion.div
            className="absolute inset-0 rounded-full border-2"
            style={{ borderColor: colors.from }}
            initial={{ scale: 0.9, opacity: 0.7 }}
            animate={{ scale: 1.55, opacity: 0 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 1.4, repeat: Infinity, ease: 'easeOut' }}
          />
        )}
      </AnimatePresence>

      {/* Body — gentle float/breathe */}
      <motion.svg
        viewBox="0 0 100 100"
        width={size * 0.86}
        height={size * 0.86}
        className="relative z-10 drop-shadow-md"
        animate={{ y: [0, -2.5, 0] }}
        transition={{ duration: 3.2, repeat: Infinity, ease: 'easeInOut' }}
      >
        <defs>
          <linearGradient id={`avatar-grad-${tone}`} x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor={colors.from} />
            <stop offset="100%" stopColor={colors.to} />
          </linearGradient>
        </defs>

        {/* Head */}
        <circle cx="50" cy="50" r="38" fill={`url(#avatar-grad-${tone})`} />

        {/* Inner highlight */}
        <circle cx="38" cy="36" r="10" fill="rgba(255,255,255,0.18)" />

        {/* Eyes */}
        <motion.g animate={{ scaleY: blink ? 0.1 : 1 }} transition={{ duration: 0.12 }} style={{ originY: '0.5px', transformBox: 'fill-box', transformOrigin: 'center' }}>
          <circle cx="38" cy="48" r="4.2" fill="white" />
          <circle cx="62" cy="48" r="4.2" fill="white" />
        </motion.g>

        {/* Mouth — talking pulse when speaking, soft smile otherwise */}
        {speaking ? (
          <motion.ellipse
            cx="50"
            cy="66"
            rx="9"
            ry="4"
            fill="white"
            animate={{ ry: [2, 6, 3, 5.5, 2] }}
            transition={{ duration: 0.9, repeat: Infinity, ease: 'easeInOut' }}
          />
        ) : (
          <path d="M40 64 Q50 71 60 64" stroke="white" strokeWidth="3.2" strokeLinecap="round" fill="none" />
        )}
      </motion.svg>
    </div>
  );
};

export default AnimatedAvatar;
