import { useEffect, useMemo, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Sparkles, ExternalLink, ChevronLeft, ChevronRight, Pause, Play } from 'lucide-react';
import AnimatedAvatar from '@/components/AnimatedAvatar';

/**
 * ModuleContentCards — an interactive "learn with a guide" panel.
 * Renders course.content_cards with an animated avatar that narrates each
 * card's key points one at a time (auto-advancing, pausable).
 *
 * Expected card shape:
 *   { title: string, points: string[], insight?: string, sources?: {label,url}[] }
 */
const ModuleContentCards = ({ cards = [], tone = 'teal' }) => {
  const [activeCard, setActiveCard] = useState(0);
  const [activePoint, setActivePoint] = useState(0);
  const [playing, setPlaying] = useState(true);

  const card = cards[activeCard];
  const points = useMemo(() => card?.points || [], [card]);

  // Reset point index whenever the active card changes
  useEffect(() => {
    setActivePoint(0);
  }, [activeCard]);

  // Auto-advance through the current card's points, then to the next card
  useEffect(() => {
    if (!playing || points.length === 0) return;
    const timer = setTimeout(() => {
      if (activePoint < points.length - 1) {
        setActivePoint((p) => p + 1);
      } else if (activeCard < cards.length - 1) {
        setActiveCard((c) => c + 1);
      } else {
        setPlaying(false);
      }
    }, 3400);
    return () => clearTimeout(timer);
  }, [playing, activePoint, points.length, activeCard, cards.length]);

  if (!cards.length) return null;

  const goPrev = () => {
    setPlaying(false);
    setActiveCard((c) => Math.max(0, c - 1));
  };
  const goNext = () => {
    setPlaying(false);
    setActiveCard((c) => Math.min(cards.length - 1, c + 1));
  };

  const accent = tone === 'navy' ? 'text-navy-700' : 'text-teal';
  const accentBg = tone === 'navy' ? 'bg-navy-100' : 'bg-teal/10';
  const accentBorder = tone === 'navy' ? 'border-navy-200' : 'border-teal/20';

  return (
    <div className="rounded-2xl border border-slate-200 bg-white shadow-sm overflow-hidden" data-testid="module-content-cards">
      {/* Header with avatar */}
      <div className={`flex items-center gap-4 px-6 py-5 border-b ${accentBorder} ${accentBg}`}>
        <AnimatedAvatar speaking={playing} tone={tone} size={64} />
        <div className="flex-1 min-w-0">
          <p className={`text-xs font-dm-sans font-semibold uppercase tracking-wide ${accent}`}>
            Your AI Learning Guide
          </p>
          <h3 className="font-playfair font-semibold text-navy-900 text-lg truncate">
            {card?.title}
          </h3>
        </div>
        <button
          onClick={() => setPlaying((p) => !p)}
          className={`flex-shrink-0 w-9 h-9 rounded-full flex items-center justify-center border ${accentBorder} bg-white hover:bg-slate-50 transition-colors`}
          aria-label={playing ? 'Pause narration' : 'Play narration'}
          data-testid="avatar-play-toggle"
        >
          {playing ? <Pause className="w-4 h-4 text-navy-700" /> : <Play className="w-4 h-4 text-navy-700" />}
        </button>
      </div>

      {/* Card tabs */}
      {cards.length > 1 && (
        <div className="flex gap-2 px-6 pt-4 overflow-x-auto">
          {cards.map((c, i) => (
            <button
              key={i}
              onClick={() => { setPlaying(false); setActiveCard(i); }}
              className={`flex-shrink-0 px-3 py-1.5 rounded-full text-xs font-dm-sans border transition-colors whitespace-nowrap ${
                i === activeCard
                  ? `${accentBg} ${accent} ${accentBorder} font-semibold`
                  : 'border-slate-200 text-navy-400 hover:text-navy-600'
              }`}
              data-testid={`content-card-tab-${i}`}
            >
              {c.title}
            </button>
          ))}
        </div>
      )}

      {/* Active card content */}
      <div className="px-6 py-6">
        <AnimatePresence mode="wait">
          <motion.div
            key={`${activeCard}`}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.3 }}
          >
            <ul className="space-y-3 mb-4">
              {points.map((point, i) => (
                <motion.li
                  key={i}
                  className="flex items-start gap-3"
                  animate={{ opacity: i <= activePoint ? 1 : 0.35 }}
                  transition={{ duration: 0.35 }}
                >
                  <span
                    className={`flex-shrink-0 mt-1 w-2 h-2 rounded-full ${
                      i === activePoint && playing ? `${tone === 'navy' ? 'bg-navy-700' : 'bg-teal'} animate-pulse` : 'bg-slate-300'
                    }`}
                  />
                  <span className="font-dm-sans text-navy-600 leading-relaxed">{point}</span>
                </motion.li>
              ))}
            </ul>

            {card?.insight && (
              <div className={`flex items-start gap-2.5 p-3.5 rounded-xl ${accentBg} mb-4`}>
                <Sparkles className={`w-4 h-4 mt-0.5 flex-shrink-0 ${accent}`} />
                <p className="font-dm-sans text-sm text-navy-700 leading-relaxed">
                  <span className="font-semibold">Latest research: </span>
                  {card.insight}
                </p>
              </div>
            )}

            {card?.sources?.length > 0 && (
              <div className="flex flex-wrap gap-2">
                {card.sources.map((s, i) => (
                  <a
                    key={i}
                    href={s.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1.5 text-xs font-dm-sans text-navy-400 hover:text-navy-700 border border-slate-200 rounded-full px-3 py-1 transition-colors"
                    data-testid={`content-card-source-${i}`}
                  >
                    {s.label}
                    <ExternalLink className="w-3 h-3" />
                  </a>
                ))}
              </div>
            )}
          </motion.div>
        </AnimatePresence>
      </div>

      {/* Navigation */}
      {cards.length > 1 && (
        <div className="flex items-center justify-between px-6 pb-5">
          <button
            onClick={goPrev}
            disabled={activeCard === 0}
            className="flex items-center gap-1 text-sm font-dm-sans text-navy-400 hover:text-navy-700 disabled:opacity-30 disabled:hover:text-navy-400 transition-colors"
            data-testid="content-card-prev"
          >
            <ChevronLeft className="w-4 h-4" /> Prev
          </button>
          <span className="text-xs font-dm-sans text-navy-400">
            {activeCard + 1} / {cards.length}
          </span>
          <button
            onClick={goNext}
            disabled={activeCard === cards.length - 1}
            className="flex items-center gap-1 text-sm font-dm-sans text-navy-400 hover:text-navy-700 disabled:opacity-30 disabled:hover:text-navy-400 transition-colors"
            data-testid="content-card-next"
          >
            Next <ChevronRight className="w-4 h-4" />
          </button>
        </div>
      )}
    </div>
  );
};

export default ModuleContentCards;
