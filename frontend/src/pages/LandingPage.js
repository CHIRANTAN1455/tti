import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { ArrowRight, Leaf, Brain, Heart, Stethoscope, Award, BookOpen } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useAuth } from '@/context/AuthContext';
import CourseJourneyMap from '@/components/CourseJourneyMap';
import axios from 'axios';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// Logo component using the provided image
const Logo = ({ className = "w-10 h-10" }) => (
  <img 
    src="https://customer-assets.emergentagent.com/job_ett-india/artifacts/ksfgr2qo_image.png" 
    alt="TTI Logo" 
    className={className}
  />
);

const LandingPage = () => {
  const { user, token } = useAuth();
  const navigate = useNavigate();
  const [courses, setCourses] = useState([]);
  const [enrolledIds, setEnrolledIds] = useState(new Set());
  const [quizPassedIds, setQuizPassedIds] = useState(new Set());

  useEffect(() => {
    axios.get(`${API}/courses`).then((res) => setCourses(res.data)).catch(() => {});
  }, []);

  useEffect(() => {
    if (!user || !token) {
      setEnrolledIds(new Set());
      setQuizPassedIds(new Set());
      return;
    }
    axios
      .get(`${API}/enrollments/my`, { headers: { Authorization: `Bearer ${token}` } })
      .then((res) => setEnrolledIds(new Set(res.data.map((e) => e.course.id))))
      .catch(() => {});
    axios
      .get(`${API}/quiz-results/my`, { headers: { Authorization: `Bearer ${token}` } })
      .then((res) => setQuizPassedIds(new Set(res.data.filter((r) => r.passed).map((r) => r.course_id))))
      .catch(() => {});
  }, [user, token]);

  return (
    <div className="min-h-screen bg-[#f8fafa]">
      {/* Wavy Background */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden z-0">
        <svg className="absolute top-0 left-0 w-full opacity-40" viewBox="0 0 1440 320" preserveAspectRatio="none">
          <path fill="#d4eded" d="M0,192L60,186.7C120,181,240,171,360,181.3C480,192,600,224,720,213.3C840,203,960,149,1080,144C1200,139,1320,181,1380,202.7L1440,224L1440,0L1380,0C1320,0,1200,0,1080,0C960,0,840,0,720,0C600,0,480,0,360,0C240,0,120,0,60,0L0,0Z"></path>
        </svg>
        <svg className="absolute top-20 left-0 w-full opacity-30" viewBox="0 0 1440 320" preserveAspectRatio="none">
          <path fill="#c5e8e8" d="M0,64L48,80C96,96,192,128,288,128C384,128,480,96,576,106.7C672,117,768,171,864,181.3C960,192,1056,160,1152,133.3C1248,107,1344,85,1392,74.7L1440,64L1440,0L1392,0C1344,0,1248,0,1152,0C1056,0,960,0,864,0C768,0,672,0,576,0C480,0,384,0,288,0C192,0,96,0,48,0L0,0Z"></path>
        </svg>
        <svg className="absolute top-40 left-0 w-full opacity-25" viewBox="0 0 1440 320" preserveAspectRatio="none">
          <path fill="#b8e2e2" d="M0,256L60,240C120,224,240,192,360,186.7C480,181,600,203,720,224C840,245,960,267,1080,256C1200,245,1320,203,1380,181.3L1440,160L1440,0L1380,0C1320,0,1200,0,1080,0C960,0,840,0,720,0C600,0,480,0,360,0C240,0,120,0,60,0L0,0Z"></path>
        </svg>
      </div>

      {/* Navigation */}
      <nav className="fixed top-0 left-0 right-0 z-50 bg-white/90 backdrop-blur-md border-b border-slate-100">
        <div className="max-w-7xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <Link to="/" className="flex items-center gap-3" data-testid="logo-link">
              <Logo className="w-10 h-10" />
              <span className="font-playfair font-semibold text-navy-900 text-lg tracking-tight">
                TraumaTransformationInstitute
              </span>
            </Link>
            
            <div className="flex items-center gap-6">
              <Link 
                to="/about" 
                className="text-sm font-dm-sans text-navy-600 hover:text-navy-900 transition-colors"
                data-testid="about-link"
              >
                About Us
              </Link>
              {user ? (
                <Link to="/dashboard">
                  <Button 
                    variant="outline" 
                    className="font-dm-sans border-navy-900 text-navy-900 hover:bg-navy-900 hover:text-white rounded-lg"
                    data-testid="dashboard-btn"
                  >
                    Dashboard
                  </Button>
                </Link>
              ) : (
                <Link to="/login">
                  <Button 
                    variant="outline" 
                    className="font-dm-sans border-navy-900 text-navy-900 hover:bg-navy-900 hover:text-white rounded-lg"
                    data-testid="login-btn"
                  >
                    Sign In
                  </Button>
                </Link>
              )}
            </div>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="pt-36 pb-16 px-6 relative z-10">
        <div className="max-w-4xl mx-auto text-center">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
          >
            <div className="inline-flex items-center gap-2 px-5 py-2.5 rounded-full bg-white/80 border border-teal/20 mb-10 shadow-sm">
              <span className="w-2 h-2 bg-teal rounded-full animate-pulse"></span>
              <span className="text-sm font-dm-sans text-teal font-medium">Programs Open - Applications Welcome</span>
            </div>
            
            <h1 className="text-5xl md:text-6xl lg:text-7xl font-playfair font-bold text-navy-900 tracking-tight leading-tight mb-8 italic">
              Choose Your Path
            </h1>
            
            <p className="text-lg md:text-xl font-dm-sans text-navy-600 max-w-2xl mx-auto leading-relaxed">
              Transform lives through Emotional Transformation Therapy. Select your journey—Wellness for personal growth or Clinical for professional mastery.
            </p>
          </motion.div>
        </div>
      </section>

      {/* Path Selection Cards */}
      <section className="px-6 pb-24 relative z-10">
        <div className="max-w-6xl mx-auto">
          <div className="grid md:grid-cols-2 gap-8">
            {/* Wellness Track Card */}
            <motion.div
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.6, delay: 0.2 }}
              whileHover={{ y: -4 }}
              className="group"
            >
              <div 
                className="bg-white rounded-xl border border-slate-200 p-8 md:p-10 shadow-card hover:shadow-card-hover transition-all duration-500 cursor-pointer h-full flex flex-col"
                onClick={() => navigate('/wellness')}
                data-testid="wellness-track-card"
              >
                <div className="mb-6">
                  <span className="inline-block px-4 py-1.5 text-xs font-dm-sans font-semibold tracking-wider uppercase bg-teal/10 text-teal rounded-full">
                    Wellness Track
                  </span>
                </div>
                
                <h2 className="text-3xl font-playfair font-semibold text-navy-900 mb-4">
                  ETT Wellness Model
                </h2>
                
                <p className="text-navy-500 font-dm-sans mb-8 leading-relaxed">
                  Foundations of ETT for wellness professionals and personal seekers
                </p>
                
                <div className="space-y-4 flex-grow">
                  <div className="flex items-start gap-3">
                    <div className="w-8 h-8 rounded-full bg-teal/10 flex items-center justify-center flex-shrink-0">
                      <Leaf className="w-4 h-4 text-teal" />
                    </div>
                    <span className="text-navy-600 font-dm-sans text-sm leading-relaxed">
                      Level 1: Emotional regulation & stress reduction
                    </span>
                  </div>
                  
                  <div className="flex items-start gap-3">
                    <div className="w-8 h-8 rounded-full bg-teal/10 flex items-center justify-center flex-shrink-0">
                      <Heart className="w-4 h-4 text-teal" />
                    </div>
                    <span className="text-navy-600 font-dm-sans text-sm leading-relaxed">
                      Somatic healing & spiritual wellness pathways
                    </span>
                  </div>
                  
                  <div className="flex items-start gap-3">
                    <div className="w-8 h-8 rounded-full bg-teal/10 flex items-center justify-center flex-shrink-0">
                      <Brain className="w-4 h-4 text-teal" />
                    </div>
                    <span className="text-navy-600 font-dm-sans text-sm leading-relaxed">
                      Self-paced personal transformation
                    </span>
                  </div>
                </div>
                
                <Button 
                  className="mt-8 w-full bg-teal hover:bg-teal/90 text-white font-dm-sans font-medium py-6 rounded-lg group-hover:translate-x-0 transition-all"
                  data-testid="explore-wellness-btn"
                >
                  Explore Wellness Track
                  <ArrowRight className="ml-2 w-4 h-4 group-hover:translate-x-1 transition-transform" />
                </Button>
              </div>
            </motion.div>

            {/* Clinical Track Card */}
            <motion.div
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.6, delay: 0.3 }}
              whileHover={{ y: -4 }}
              className="group"
            >
              <div 
                className="bg-white rounded-xl border border-slate-200 p-8 md:p-10 shadow-card hover:shadow-card-hover transition-all duration-500 cursor-pointer h-full flex flex-col"
                onClick={() => navigate('/clinical')}
                data-testid="clinical-track-card"
              >
                <div className="mb-6">
                  <span className="inline-block px-4 py-1.5 text-xs font-dm-sans font-semibold tracking-wider uppercase bg-navy-100 text-navy-700 rounded-full">
                    Clinical Track
                  </span>
                </div>
                
                <h2 className="text-3xl font-playfair font-semibold text-navy-900 mb-4">
                  ETT Clinical Model
                </h2>
                
                <p className="text-navy-500 font-dm-sans mb-8 leading-relaxed">
                  Advanced training for licensed mental health professionals
                </p>
                
                <div className="space-y-4 flex-grow">
                  <div className="flex items-start gap-3">
                    <div className="w-8 h-8 rounded-full bg-navy-100 flex items-center justify-center flex-shrink-0">
                      <Stethoscope className="w-4 h-4 text-navy-600" />
                    </div>
                    <span className="text-navy-600 font-dm-sans text-sm leading-relaxed">
                      Level 1-2: Core ETT techniques & attachment work
                    </span>
                  </div>
                  
                  <div className="flex items-start gap-3">
                    <div className="w-8 h-8 rounded-full bg-navy-100 flex items-center justify-center flex-shrink-0">
                      <BookOpen className="w-4 h-4 text-navy-600" />
                    </div>
                    <span className="text-navy-600 font-dm-sans text-sm leading-relaxed">
                      Advanced: Somatic applications & spiritual integration
                    </span>
                  </div>
                  
                  <div className="flex items-start gap-3">
                    <div className="w-8 h-8 rounded-full bg-navy-100 flex items-center justify-center flex-shrink-0">
                      <Award className="w-4 h-4 text-navy-600" />
                    </div>
                    <span className="text-navy-600 font-dm-sans text-sm leading-relaxed">
                      Certification for clinical practice
                    </span>
                  </div>
                </div>
                
                <Button 
                  className="mt-8 w-full bg-navy-900 hover:bg-navy-800 text-white font-dm-sans font-medium py-6 rounded-lg group-hover:translate-x-0 transition-all"
                  data-testid="explore-clinical-btn"
                >
                  Explore Clinical Track
                  <ArrowRight className="ml-2 w-4 h-4 group-hover:translate-x-1 transition-transform" />
                </Button>
              </div>
            </motion.div>
          </div>
        </div>
      </section>

      {/* Journey Map */}
      {courses.length > 0 && (
        <section className="px-6 pb-24 relative z-10">
          <div className="max-w-6xl mx-auto">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5 }}
            >
              <CourseJourneyMap
                courses={courses}
                enrolledIds={enrolledIds}
                quizPassedIds={quizPassedIds}
                onSelect={(c) => navigate(`/courses/${c.id}`)}
              />
            </motion.div>
          </div>
        </section>
      )}

      {/* Footer */}
      <footer className="border-t border-slate-100 py-12 px-6 bg-white/80 relative z-10">
        <div className="max-w-6xl mx-auto">
          <div className="flex flex-col md:flex-row justify-between items-center gap-6">
            <div className="flex items-center gap-3">
              <Logo className="w-8 h-8" />
              <span className="font-dm-sans text-sm text-navy-600">
                Trauma Transformation Institute
              </span>
            </div>
            
            <div className="flex items-center gap-6 text-sm font-dm-sans text-navy-500">
              <Link to="/about" className="hover:text-navy-900 transition-colors">About</Link>
              <a href="mailto:contact@tti-india.com" className="hover:text-navy-900 transition-colors">Contact</a>
              <span>© 2025 TTI India</span>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
};

export default LandingPage;
