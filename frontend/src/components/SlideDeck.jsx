import { useCallback, useEffect, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ChevronLeft, ChevronRight, Maximize, Minimize, Presentation, Quote } from 'lucide-react';

/**
 * SlideDeck — an animated, interactive "PPT-style" presentation for course
 * content. Supports keyboard navigation, a true fullscreen present mode,
 * and three slide types: title, content (staggered bullets), closing (quote).
 *
 * Slide shape: { type: 'title'|'content'|'closing', eyebrow, title, subtitle, points, quote }
 */
const TONES = {
  teal: { from: '#0f172a', via: '#134e4a', to: '#0f172a', accent: '#2FBFAE' },
  navy: { from: '#0f172a', via: '#1e293b', to: '#0f172a', accent: '#64748b' },
};

const SlideDeck = ({ slides = [], tone = 'teal' }) => {
  const [index, setIndex] = useState(0);
  const [direction, setDirection] = useState(1);
  const [fullscreen, setFullscreen] = useState(false);
  const containerRef = useRef(null);
  const colors = TONES[tone] || TONES.teal;

  const goTo = useCallback((next) => {
    setDirection(next > index ? 1 : -1);
    setIndex(Math.max(0, Math.min(slides.length - 1, next)));
  }, [index, slides.length]);

  const next = useCallback(() => goTo(index + 1), [goTo, index]);
  const prev = useCallback(() => goTo(index - 1), [goTo, index]);

  useEffect(() => {
    const onKey = (e) => {
      if (e.key === 'ArrowRight' || e.key === ' ') next();
      if (e.key === 'ArrowLeft') prev();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [next, prev]);

  useEffect(() => {
    const onFsChange = () => setFullscreen(!!document.fullscreenElement);
    document.addEventListener('fullscreenchange', onFsChange);
    return () => document.removeEventListener('fullscreenchange', onFsChange);
  }, []);

  const toggleFullscreen = () => {
    if (!document.fullscreenElement) {
      containerRef.current?.requestFullscreen?.();
    } else {
      document.exitFullscreen?.();
    }
  };

  if (!slides.length) return null;
  const slide = slides[index];

  return (
    <div
      ref={containerRef}
      className={`relative rounded-2xl overflow-hidden shadow-lg select-none ${fullscreen ? 'w-screen h-screen flex flex-col justify-center' : ''}`}
      style={{ background: `linear-gradient(135deg, ${colors.from}, ${colors.via}, ${colors.to})` }}
      data-testid="slide-deck"
    >
      {/* Ambient decorative orbs */}
      <div className="absolute inset-0 pointer-events-none overflow-hidden">
        <motion.div
          className="absolute w-72 h-72 rounded-full opacity-20 blur-3xl"
          style={{ background: colors.accent, top: '-10%', left: '-5%' }}
          animate={{ x: [0, 30, 0], y: [0, 20, 0] }}
          transition={{ duration: 12, repeat: Infinity, ease: 'easeInOut' }}
        />
        <motion.div
          className="absolute w-64 h-64 rounded-full opacity-10 blur-3xl"
          style={{ background: colors.accent, bottom: '-10%', right: '-5%' }}
          animate={{ x: [0, -20, 0], y: [0, -25, 0] }}
          transition={{ duration: 14, repeat: Infinity, ease: 'easeInOut' }}
        />
      </div>

      {/* Toolbar */}
      <div className="relative z-20 flex items-center justify-between px-5 py-3">
        <div className="flex items-center gap-2 text-white/60 font-dm-sans text-xs">
          <Presentation className="w-3.5 h-3.5" />
          <span>
            Slide {index + 1} / {slides.length}
          </span>
        </div>
        <button
          onClick={toggleFullscreen}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-white/10 hover:bg-white/20 text-white/80 text-xs font-dm-sans transition-colors"
          data-testid="slide-fullscreen-toggle"
        >
          {fullscreen ? <Minimize className="w-3.5 h-3.5" /> : <Maximize className="w-3.5 h-3.5" />}
          {fullscreen ? 'Exit' : 'Present'}
        </button>
      </div>

      {/* Slide content */}
      <div className={`relative z-10 flex items-center justify-center px-8 sm:px-16 ${fullscreen ? 'flex-1' : 'min-h-[380px] py-10'}`}>
        <AnimatePresence mode="wait" custom={direction}>
          <motion.div
            key={index}
            custom={direction}
            initial={{ opacity: 0, x: direction * 60 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: direction * -60 }}
            transition={{ duration: 0.35, ease: 'easeOut' }}
            className="w-full max-w-2xl text-center"
          >
            {slide.type === 'title' && (
              <>
                {slide.eyebrow && (
                  <motion.span
                    initial={{ opacity: 0, y: -8 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.1 }}
                    className="inline-block px-4 py-1.5 rounded-full text-xs font-dm-sans font-semibold uppercase tracking-wider mb-6"
                    style={{ background: `${colors.accent}22`, color: colors.accent }}
                  >
                    {slide.eyebrow}
                  </motion.span>
                )}
                <h2 className="text-3xl sm:text-4xl font-playfair font-bold text-white mb-4 leading-tight">
                  {slide.title}
                </h2>
                {slide.subtitle && (
                  <motion.p
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: 0.3 }}
                    className="font-dm-sans text-white/70 text-lg"
                  >
                    {slide.subtitle}
                  </motion.p>
                )}
              </>
            )}

            {slide.type === 'content' && (
              <>
                {slide.eyebrow && (
                  <p className="font-dm-sans text-xs font-semibold uppercase tracking-wider mb-3" style={{ color: colors.accent }}>
                    {slide.eyebrow}
                  </p>
                )}
                <h3 className="text-2xl sm:text-3xl font-playfair font-semibold text-white mb-6">
                  {slide.title}
                </h3>
                <ul className="space-y-3 text-left inline-block">
                  {slide.points?.map((point, i) => (
                    <motion.li
                      key={i}
                      initial={{ opacity: 0, x: -12 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: 0.15 + i * 0.09 }}
                      className="flex items-start gap-3"
                    >
                      <span className="mt-2 w-1.5 h-1.5 rounded-full flex-shrink-0" style={{ background: colors.accent }} />
                      <span className="font-dm-sans text-white/85 leading-relaxed">{point}</span>
                    </motion.li>
                  ))}
                </ul>
              </>
            )}

            {slide.type === 'closing' && (
              <>
                {slide.quote ? (
                  <>
                    <Quote className="w-8 h-8 mx-auto mb-5 opacity-40" style={{ color: colors.accent }} />
                    <p className="text-xl sm:text-2xl font-playfair italic text-white leading-relaxed">
                      {slide.quote}
                    </p>
                  </>
                ) : (
                  <>
                    {slide.eyebrow && (
                      <p className="font-dm-sans text-xs font-semibold uppercase tracking-wider mb-3" style={{ color: colors.accent }}>
                        {slide.eyebrow}
                      </p>
                    )}
                    <h3 className="text-2xl sm:text-3xl font-playfair font-semibold text-white mb-6">{slide.title}</h3>
                    <ul className="space-y-3 text-left inline-block">
                      {slide.points?.map((point, i) => (
                        <motion.li
                          key={i}
                          initial={{ opacity: 0, x: -12 }}
                          animate={{ opacity: 1, x: 0 }}
                          transition={{ delay: 0.15 + i * 0.09 }}
                          className="flex items-start gap-3"
                        >
                          <span className="mt-2 w-1.5 h-1.5 rounded-full flex-shrink-0" style={{ background: colors.accent }} />
                          <span className="font-dm-sans text-white/85 leading-relaxed">{point}</span>
                        </motion.li>
                      ))}
                    </ul>
                  </>
                )}
              </>
            )}
          </motion.div>
        </AnimatePresence>
      </div>

      {/* Nav arrows */}
      <button
        onClick={prev}
        disabled={index === 0}
        className="absolute z-20 left-3 top-1/2 -translate-y-1/2 w-9 h-9 rounded-full bg-white/10 hover:bg-white/20 disabled:opacity-20 disabled:hover:bg-white/10 flex items-center justify-center transition-colors"
        data-testid="slide-prev"
      >
        <ChevronLeft className="w-5 h-5 text-white" />
      </button>
      <button
        onClick={next}
        disabled={index === slides.length - 1}
        className="absolute z-20 right-3 top-1/2 -translate-y-1/2 w-9 h-9 rounded-full bg-white/10 hover:bg-white/20 disabled:opacity-20 disabled:hover:bg-white/10 flex items-center justify-center transition-colors"
        data-testid="slide-next"
      >
        <ChevronRight className="w-5 h-5 text-white" />
      </button>

      {/* Progress dots */}
      <div className="relative z-20 flex items-center justify-center gap-1.5 pb-5 flex-wrap px-8">
        {slides.map((_, i) => (
          <button
            key={i}
            onClick={() => goTo(i)}
            className="h-1.5 rounded-full transition-all"
            style={{
              width: i === index ? 20 : 6,
              background: i === index ? colors.accent : 'rgba(255,255,255,0.25)',
            }}
            data-testid={`slide-dot-${i}`}
            aria-label={`Go to slide ${i + 1}`}
          />
        ))}
      </div>
    </div>
  );
};

export default SlideDeck;
