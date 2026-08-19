import { useMemo, useState } from 'react';
import { motion } from 'framer-motion';
import { Check, MapPin, Sparkles, Stethoscope, Trophy } from 'lucide-react';

/**
 * CourseJourneyMap — a horizontal "learning path" roadmap connecting the
 * 10 wellness prerequisite modules into Clinical Level 1 & 2, with the
 * coming-soon specialty programs shown as optional branches at the end.
 *
 * Props:
 *  - courses: full course list (all tracks)
 *  - enrolledIds: Set<string> of course ids the current user has paid for
 *  - quizPassedIds: Set<string> of course ids the current user has passed the quiz for
 *  - onSelect: (course) => void — called when a node is clicked
 */
const moduleNumber = (title) => parseInt(title.match(/Module (\d+)/)?.[1] || '0', 10);

const CourseJourneyMap = ({ courses = [], enrolledIds = new Set(), quizPassedIds = new Set(), onSelect }) => {
  const [hoverId, setHoverId] = useState(null);

  const { path, specialty } = useMemo(() => {
    const modules = courses
      .filter((c) => c.track === 'wellness' && c.level === 'module')
      .sort((a, b) => moduleNumber(a.title) - moduleNumber(b.title))
      .map((c, i) => ({ ...c, _kind: 'node', _short: `M${i + 1}`, _tone: 'teal' }));

    const clinical = courses
      .filter((c) => c.track === 'clinical' && (c.level === 'level1' || c.level === 'level2'))
      .sort((a, b) => a.level.localeCompare(b.level))
      .map((c) => ({ ...c, _kind: 'node', _short: c.level === 'level1' ? 'C1' : 'C2', _tone: 'navy' }));

    const built = [...modules];
    if (clinical.length) {
      built.push({ _kind: 'divider', id: 'divider', label: 'Clinical Track Begins' });
      built.push(...clinical);
    }

    const advanced = courses.filter((c) => c.level === 'advanced');
    return { path: built, specialty: advanced };
  }, [courses]);

  const nodeCourses = path.filter((p) => p._kind === 'node');
  const enrolledCount = nodeCourses.filter((c) => enrolledIds.has(c.id)).length;
  const nextIndex = nodeCourses.findIndex((c) => !enrolledIds.has(c.id));
  const progressPct = nodeCourses.length ? Math.round((enrolledCount / nodeCourses.length) * 100) : 0;

  if (!nodeCourses.length) return null;

  return (
    <div className="rounded-2xl border border-slate-200 bg-white shadow-sm p-6 md:p-8" data-testid="course-journey-map">
      <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-3 mb-8">
        <div>
          <p className="text-xs font-dm-sans font-semibold uppercase tracking-wide text-teal mb-1">
            The Full Path
          </p>
          <h3 className="text-2xl font-playfair font-semibold text-navy-900">Your Learning Journey</h3>
          <p className="font-dm-sans text-sm text-navy-500 mt-1">
            10 prerequisite modules build the foundation, then the Clinical Track takes you to certification.
          </p>
        </div>
        {enrolledIds.size > 0 && (
          <div className="flex items-center gap-3 flex-shrink-0">
            <div className="w-28 h-2 rounded-full bg-slate-100 overflow-hidden">
              <motion.div
                className="h-full bg-gradient-to-r from-teal to-navy-700 rounded-full"
                initial={{ width: 0 }}
                animate={{ width: `${progressPct}%` }}
                transition={{ duration: 0.8, ease: 'easeOut' }}
              />
            </div>
            <span className="text-xs font-dm-sans text-navy-500 whitespace-nowrap">{progressPct}% complete</span>
          </div>
        )}
      </div>

      {/* Path */}
      <div className="relative overflow-x-auto pb-2 -mx-2 px-2">
        <div className="relative flex items-center min-w-max py-6" style={{ minWidth: `${path.length * 96}px` }}>
          {/* Connecting line */}
          <div className="absolute left-0 right-0 top-1/2 -translate-y-1/2 h-1 rounded-full bg-slate-100 mx-8" />
          <motion.div
            className="absolute left-0 top-1/2 -translate-y-1/2 h-1 rounded-full bg-gradient-to-r from-teal to-navy-700 mx-8"
            initial={{ width: 0 }}
            animate={{ width: nodeCourses.length > 1 ? `calc(${(enrolledCount / (nodeCourses.length - 1)) * 100}% - ${enrolledCount ? 64 : 0}px)` : 0 }}
            transition={{ duration: 1, ease: 'easeOut' }}
          />

          {path.map((item, i) => {
            if (item._kind === 'divider') {
              return (
                <div key={item.id} className="relative z-10 flex flex-col items-center flex-shrink-0 w-24">
                  <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-navy-900 text-white shadow-md">
                    <Stethoscope className="w-3 h-3" />
                    <span className="text-[10px] font-dm-sans font-semibold uppercase tracking-wide whitespace-nowrap">
                      {item.label}
                    </span>
                  </div>
                </div>
              );
            }

            const enrolled = enrolledIds.has(item.id);
            const quizPassed = quizPassedIds.has(item.id);
            const isNext = i === nextIndex;
            const teal = item._tone === 'teal';

            return (
              <div
                key={item.id}
                className="relative z-10 flex flex-col items-center flex-shrink-0 w-24"
                onMouseEnter={() => setHoverId(item.id)}
                onMouseLeave={() => setHoverId(null)}
              >
                <motion.button
                  onClick={() => onSelect?.(item)}
                  whileHover={{ scale: 1.08 }}
                  whileTap={{ scale: 0.96 }}
                  className={`relative w-14 h-14 rounded-full flex items-center justify-center font-dm-sans font-bold text-sm border-2 transition-colors ${
                    enrolled
                      ? teal
                        ? 'bg-teal border-teal text-white'
                        : 'bg-navy-900 border-navy-900 text-white'
                      : teal
                      ? 'bg-teal/10 border-teal/40 text-teal'
                      : 'bg-navy-100 border-navy-300 text-navy-700'
                  }`}
                  data-testid={`journey-node-${item.id}`}
                >
                  {enrolled ? <Check className="w-5 h-5" /> : item._short}
                  {quizPassed && (
                    <span
                      className="absolute -bottom-1 -right-1 w-5 h-5 rounded-full bg-amber-400 border-2 border-white flex items-center justify-center"
                      title="Quiz passed"
                      data-testid={`journey-quiz-badge-${item.id}`}
                    >
                      <Trophy className="w-2.5 h-2.5 text-white" />
                    </span>
                  )}
                  {isNext && (
                    <motion.span
                      className={`absolute inset-0 rounded-full border-2 ${teal ? 'border-teal' : 'border-navy-700'}`}
                      animate={{ scale: [1, 1.4, 1], opacity: [0.7, 0, 0.7] }}
                      transition={{ duration: 1.8, repeat: Infinity, ease: 'easeInOut' }}
                    />
                  )}
                  {isNext && (
                    <span className={`absolute -top-6 left-1/2 -translate-x-1/2 flex items-center gap-1 px-2 py-0.5 rounded-full text-[9px] font-dm-sans font-semibold whitespace-nowrap ${teal ? 'bg-teal text-white' : 'bg-navy-900 text-white'}`}>
                      <MapPin className="w-2.5 h-2.5" /> Next
                    </span>
                  )}
                </motion.button>
                <p
                  className={`mt-2 text-[11px] font-dm-sans text-center leading-tight transition-colors ${
                    hoverId === item.id ? 'text-navy-900 font-medium' : 'text-navy-400'
                  }`}
                >
                  {item.title.replace(/^Module \d+ — /, '').replace(/^ETT /, '')}
                </p>
              </div>
            );
          })}
        </div>
      </div>

      {/* Specialty branches */}
      {specialty.length > 0 && (
        <div className="mt-6 pt-6 border-t border-slate-100">
          <div className="flex items-center gap-2 mb-3">
            <Sparkles className="w-4 h-4 text-navy-400" />
            <p className="text-xs font-dm-sans font-semibold uppercase tracking-wide text-navy-400">
              Optional Specialty Tracks
            </p>
          </div>
          <div className="flex flex-wrap gap-3">
            {specialty.map((c) => (
              <button
                key={c.id}
                onClick={() => onSelect?.(c)}
                className="px-4 py-2 rounded-full border border-dashed border-slate-300 text-xs font-dm-sans text-navy-500 hover:border-navy-400 hover:text-navy-900 transition-colors bg-slate-50"
                data-testid={`journey-specialty-${c.id}`}
              >
                {c.title}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default CourseJourneyMap;
