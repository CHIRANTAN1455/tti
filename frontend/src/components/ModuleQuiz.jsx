import { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Brain, Check, X, RotateCcw, Trophy, ArrowRight, Sparkles, Lock, Clock } from 'lucide-react';
import axios from 'axios';
import { useAuth } from '@/context/AuthContext';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const PASS_THRESHOLD = 0.9;
const MAX_ATTEMPTS = 3;

const formatUnlockTime = (iso) => {
  const target = new Date(iso);
  const diffMs = target - new Date();
  if (diffMs <= 0) return 'now';
  const mins = Math.ceil(diffMs / 60000);
  if (mins < 60) return `${mins} minute${mins === 1 ? '' : 's'}`;
  const hrs = Math.floor(mins / 60);
  const rem = mins % 60;
  return `${hrs}h ${rem}m`;
};

/**
 * ModuleQuiz — an interactive knowledge check for a course.
 * Requires 90% to pass, allows 3 attempts per cycle, then locks retries for
 * 1 hour (server-enforced). Stages: intro -> active -> results, plus a
 * dedicated "locked" stage when attempts are exhausted.
 */
const ModuleQuiz = ({ questions = [], courseId, tone = 'teal', onPassed }) => {
  const { user, token } = useAuth();
  const [stage, setStage] = useState('intro'); // intro | active | results | locked
  const [index, setIndex] = useState(0);
  const [selected, setSelected] = useState(null);
  const [answers, setAnswers] = useState([]);
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState(null); // last known server-side quiz_results doc
  const [lockedUntil, setLockedUntil] = useState(null);

  useEffect(() => {
    if (!user || !token || !courseId) return;
    axios
      .get(`${API}/quiz-results/my`, { headers: { Authorization: `Bearer ${token}` } })
      .then((res) => {
        const match = res.data.find((r) => r.course_id === courseId);
        if (match) {
          setStatus(match);
          if (match.locked_until && new Date(match.locked_until) > new Date()) {
            setLockedUntil(match.locked_until);
            setStage('locked');
          }
        }
      })
      .catch(() => {});
  }, [user, token, courseId]);

  if (!questions.length) return null;

  const accent = tone === 'navy' ? 'text-navy-700' : 'text-teal';
  const accentBg = tone === 'navy' ? 'bg-navy-100' : 'bg-teal/10';
  const accentSolid = tone === 'navy' ? 'bg-navy-900 hover:bg-navy-800' : 'bg-teal hover:bg-teal/90';
  const accentBorder = tone === 'navy' ? 'border-navy-200' : 'border-teal/20';

  const question = questions[index];
  const score = answers.filter(Boolean).length;
  const pct = questions.length ? Math.round((score / questions.length) * 100) : 0;
  const passed = pct / 100 >= PASS_THRESHOLD;
  const attemptsUsed = status?.passed ? 0 : status?.attempts || 0;
  const attemptsRemaining = Math.max(0, MAX_ATTEMPTS - attemptsUsed);

  const start = () => {
    if (lockedUntil && new Date(lockedUntil) > new Date()) {
      setStage('locked');
      return;
    }
    setStage('active');
    setIndex(0);
    setSelected(null);
    setAnswers([]);
  };

  const choose = (optIndex) => {
    if (selected !== null) return;
    setSelected(optIndex);
    setAnswers((prev) => [...prev, optIndex === question.correct_index]);
  };

  const next = async () => {
    if (index < questions.length - 1) {
      setIndex((i) => i + 1);
      setSelected(null);
      return;
    }

    const finalAnswers = [...answers];
    const finalScore = finalAnswers.filter(Boolean).length;
    const finalPassed = finalScore / questions.length >= PASS_THRESHOLD;

    if (!user || !token || !courseId) {
      setStage('results');
      return;
    }

    setSaving(true);
    try {
      const res = await axios.post(
        `${API}/quiz-results`,
        { course_id: courseId, score: finalScore, total: questions.length },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      setStatus(res.data);
      setStage('results');
      if (finalPassed) onPassed?.();
    } catch (e) {
      if (e.response?.status === 403) {
        // Ran out of attempts server-side — surface the lockout instead of a fake result
        const match = e.response.data?.detail?.match(/after (.+)\.?$/);
        const until = match ? match[1].replace(/\.$/, '') : null;
        setLockedUntil(until);
        setStage('locked');
      } else {
        setStage('results');
      }
    } finally {
      setSaving(false);
    }
  };

  const alreadyPassed = status?.passed;

  return (
    <div className="rounded-2xl border border-slate-200 bg-white shadow-sm overflow-hidden" data-testid="module-quiz">
      <div className={`flex items-center gap-3 px-6 py-5 border-b ${accentBorder} ${accentBg}`}>
        <div className={`w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0 ${tone === 'navy' ? 'bg-navy-900' : 'bg-teal'}`}>
          <Brain className="w-5 h-5 text-white" />
        </div>
        <div>
          <p className={`text-xs font-dm-sans font-semibold uppercase tracking-wide ${accent}`}>Test Your Knowledge</p>
          <h3 className="font-playfair font-semibold text-navy-900 text-lg">Quick Quiz</h3>
        </div>
      </div>

      <div className="p-6">
        <AnimatePresence mode="wait">
          {stage === 'intro' && (
            <motion.div key="intro" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="text-center py-4">
              {alreadyPassed && (
                <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-emerald-100 text-emerald-700 text-xs font-dm-sans font-medium mb-4">
                  <Check className="w-3 h-3" /> Already passed — best score {status.best_score}/{status.best_total}
                </div>
              )}
              <p className="font-dm-sans text-navy-500 mb-2">
                {questions.length} questions · get 90% or higher to pass
              </p>
              {!alreadyPassed && (
                <p className="font-dm-sans text-xs text-navy-400 mb-6">
                  {attemptsRemaining} of {MAX_ATTEMPTS} attempts remaining before a 1-hour cooldown
                </p>
              )}
              {alreadyPassed && <div className="mb-6" />}
              <button
                onClick={start}
                className={`inline-flex items-center gap-2 px-6 py-3 rounded-lg text-white font-dm-sans font-medium transition-colors ${accentSolid}`}
                data-testid="quiz-start-btn"
              >
                {alreadyPassed ? 'Retake Quiz' : 'Start Quiz'} <ArrowRight className="w-4 h-4" />
              </button>
            </motion.div>
          )}

          {stage === 'locked' && (
            <motion.div key="locked" initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="text-center py-4">
              <div className="w-16 h-16 rounded-full bg-amber-100 flex items-center justify-center mx-auto mb-4">
                <Lock className="w-7 h-7 text-amber-600" />
              </div>
              <h4 className="font-playfair font-semibold text-navy-900 text-xl mb-2">Maximum Attempts Reached</h4>
              <p className="font-dm-sans text-navy-500 mb-1 max-w-sm mx-auto">
                You've used all {MAX_ATTEMPTS} attempts without reaching 90%. Head back through the content cards above to
                review the material.
              </p>
              <p className="flex items-center justify-center gap-1.5 font-dm-sans text-sm text-navy-400 mt-4" data-testid="quiz-lock-timer">
                <Clock className="w-4 h-4" />
                You can try again in {lockedUntil ? formatUnlockTime(lockedUntil) : 'about an hour'}
              </p>
            </motion.div>
          )}

          {stage === 'active' && (
            <motion.div key={`q-${index}`} initial={{ opacity: 0, x: 12 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -12 }} transition={{ duration: 0.25 }}>
              {/* Progress */}
              <div className="flex items-center gap-2 mb-5">
                {questions.map((_, i) => (
                  <div
                    key={i}
                    className={`h-1.5 flex-1 rounded-full ${
                      i < index ? (tone === 'navy' ? 'bg-navy-700' : 'bg-teal') : i === index ? (tone === 'navy' ? 'bg-navy-300' : 'bg-teal/40') : 'bg-slate-100'
                    }`}
                  />
                ))}
              </div>
              <p className="text-xs font-dm-sans text-navy-400 mb-2">
                Question {index + 1} of {questions.length}
              </p>
              <h4 className="font-dm-sans font-medium text-navy-900 text-lg mb-5 leading-relaxed">
                {question.question}
              </h4>

              <div className="space-y-3 mb-5">
                {question.options.map((opt, i) => {
                  const isCorrect = i === question.correct_index;
                  const isChosen = i === selected;
                  const revealed = selected !== null;
                  return (
                    <button
                      key={i}
                      onClick={() => choose(i)}
                      disabled={revealed}
                      className={`w-full text-left px-4 py-3 rounded-xl border font-dm-sans text-sm transition-colors flex items-center justify-between gap-3 ${
                        revealed && isCorrect
                          ? 'border-emerald-400 bg-emerald-50 text-emerald-800'
                          : revealed && isChosen && !isCorrect
                          ? 'border-red-300 bg-red-50 text-red-700'
                          : revealed
                          ? 'border-slate-100 text-navy-300'
                          : 'border-slate-200 text-navy-700 hover:border-slate-300 hover:bg-slate-50 cursor-pointer'
                      }`}
                      data-testid={`quiz-option-${i}`}
                    >
                      <span>{opt}</span>
                      {revealed && isCorrect && <Check className="w-4 h-4 flex-shrink-0" />}
                      {revealed && isChosen && !isCorrect && <X className="w-4 h-4 flex-shrink-0" />}
                    </button>
                  );
                })}
              </div>

              <AnimatePresence>
                {selected !== null && question.explanation && (
                  <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: 'auto' }}
                    exit={{ opacity: 0, height: 0 }}
                    className={`flex items-start gap-2.5 p-3.5 rounded-xl ${accentBg} mb-5 overflow-hidden`}
                  >
                    <Sparkles className={`w-4 h-4 mt-0.5 flex-shrink-0 ${accent}`} />
                    <p className="font-dm-sans text-sm text-navy-700 leading-relaxed">{question.explanation}</p>
                  </motion.div>
                )}
              </AnimatePresence>

              {selected !== null && (
                <motion.button
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  onClick={next}
                  disabled={saving}
                  className={`inline-flex items-center gap-2 px-6 py-3 rounded-lg text-white font-dm-sans font-medium transition-colors disabled:opacity-60 ${accentSolid}`}
                  data-testid="quiz-next-btn"
                >
                  {index < questions.length - 1 ? 'Next Question' : saving ? 'Saving…' : 'See Results'}
                  <ArrowRight className="w-4 h-4" />
                </motion.button>
              )}
            </motion.div>
          )}

          {stage === 'results' && (
            <motion.div key="results" initial={{ opacity: 0, scale: 0.96 }} animate={{ opacity: 1, scale: 1 }} className="text-center py-4">
              <motion.div
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                transition={{ type: 'spring', stiffness: 200, damping: 12, delay: 0.1 }}
                className={`w-16 h-16 rounded-full flex items-center justify-center mx-auto mb-4 ${
                  passed ? 'bg-emerald-100' : 'bg-amber-100'
                }`}
              >
                <Trophy className={`w-8 h-8 ${passed ? 'text-emerald-600' : 'text-amber-600'}`} />
              </motion.div>
              <h4 className="font-playfair font-semibold text-navy-900 text-2xl mb-1" data-testid="quiz-score">
                {score} / {questions.length}
              </h4>
              <p className="font-dm-sans text-navy-500 mb-2">
                {passed
                  ? "You've passed — 90%+ shows a strong grasp of this material."
                  : `You need 90% to pass. Review the content above and try again.`}
              </p>
              {!passed && user && (
                <p className="font-dm-sans text-xs text-navy-400 mb-6">
                  {Math.max(0, MAX_ATTEMPTS - (status?.attempts || 0))} of {MAX_ATTEMPTS} attempts remaining
                </p>
              )}
              {passed && <div className="mb-6" />}
              <button
                onClick={start}
                className="inline-flex items-center gap-2 px-6 py-3 rounded-lg border border-slate-200 text-navy-700 font-dm-sans font-medium hover:bg-slate-50 transition-colors"
                data-testid="quiz-retry-btn"
              >
                <RotateCcw className="w-4 h-4" /> Retake Quiz
              </button>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
};

export default ModuleQuiz;
