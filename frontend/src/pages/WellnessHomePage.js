import { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { ArrowLeft, Calendar, MapPin, Clock, Lock, ArrowRight } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { useAuth } from '@/context/AuthContext';
import AnimatedAvatar from '@/components/AnimatedAvatar';
import axios from 'axios';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// Logo component
const Logo = ({ className = "w-8 h-8" }) => (
  <img 
    src="https://customer-assets.emergentagent.com/job_ett-india/artifacts/ksfgr2qo_image.png" 
    alt="TTI Logo" 
    className={className}
  />
);

const WellnessHomePage = () => {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [courses, setCourses] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchCourses = async () => {
      try {
        const response = await axios.get(`${API}/courses?track=wellness`);
        setCourses(response.data);
      } catch (error) {
        console.error('Error fetching courses:', error);
      } finally {
        setLoading(false);
      }
    };
    fetchCourses();
  }, []);

  const formatPrice = (price) => {
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      maximumFractionDigits: 0
    }).format(price);
  };

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
      </div>

      {/* Navigation */}
      <nav className="fixed top-0 left-0 right-0 z-50 bg-white/90 backdrop-blur-md border-b border-slate-100">
        <div className="max-w-7xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-6">
              <Link 
                to="/" 
                className="flex items-center gap-2 px-4 py-2 rounded-full border border-slate-200 text-navy-500 hover:text-navy-900 hover:border-slate-300 transition-all bg-white"
                data-testid="back-home-link"
              >
                <ArrowLeft className="w-4 h-4" />
                <span className="font-dm-sans text-sm">Back</span>
              </Link>
              <Link to="/" className="flex items-center gap-3">
                <Logo className="w-8 h-8" />
                <span className="font-playfair font-semibold text-navy-900">TraumaTransformationInstitute</span>
              </Link>
            </div>
            
            <div className="flex items-center gap-4">
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

      {/* Hero */}
      <section className="pt-28 pb-12 px-6 relative z-10">
        <div className="max-w-6xl mx-auto">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
          >
            <Badge className="mb-4 bg-teal/10 text-teal hover:bg-teal/20 font-dm-sans border-0 px-4 py-1.5">
              Wellness Track
            </Badge>
            <h1 className="text-4xl md:text-5xl font-playfair font-bold text-navy-900 mb-4">
              ETT Wellness Programs
            </h1>
            <p className="text-lg font-dm-sans text-navy-500 max-w-2xl">
              Transform your practice with Emotional Transformation Therapy. Programs designed for wellness professionals and personal seekers.
            </p>
          </motion.div>
        </div>
      </section>

      {/* Courses Grid */}
      <section className="px-6 pb-24 relative z-10">
        <div className="max-w-6xl mx-auto">
          {loading ? (
            <div className="flex justify-center py-12">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-teal"></div>
            </div>
          ) : (
            <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
              {courses.map((course, index) => (
                <motion.div
                  key={course.id}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.4, delay: index * 0.1 }}
                >
                  <Card 
                    className={`h-full bg-white border-slate-200 shadow-card hover:shadow-card-hover transition-all duration-500 cursor-pointer group rounded-xl ${course.is_coming_soon ? 'opacity-80' : ''}`}
                    onClick={() => !course.is_coming_soon && navigate(`/courses/${course.id}`)}
                    data-testid={`course-card-${course.id}`}
                  >
                    <CardContent className="p-6 flex flex-col h-full">
                      <div className="flex items-start justify-between mb-4">
                        {course.content_cards?.length > 0 ? (
                          <div className="flex items-center gap-2" data-testid={`ai-guide-hint-${course.id}`}>
                            <AnimatedAvatar tone="teal" size={32} />
                            <span className="text-[11px] font-dm-sans font-medium text-teal">AI Guide</span>
                          </div>
                        ) : (
                          <div className="w-8 h-8 rounded bg-slate-100 flex items-center justify-center">
                            <div className="w-4 h-1 bg-slate-300 rounded"></div>
                          </div>
                        )}
                        {course.is_coming_soon && (
                          <Badge className="bg-slate-100 text-slate-600 font-dm-sans border-0 text-xs">
                            <Lock className="w-3 h-3 mr-1" />
                            Coming Soon
                          </Badge>
                        )}
                      </div>
                      
                      <h3 className="text-xl font-playfair font-semibold text-navy-900 mb-2 group-hover:text-teal transition-colors">
                        {course.title}
                      </h3>
                      
                      <p className="text-sm font-dm-sans text-navy-500 mb-4 flex-grow leading-relaxed">
                        {course.description}
                      </p>
                      
                      <div className="space-y-2 text-sm font-dm-sans text-navy-400 mb-4">
                        <div className="flex items-center gap-2">
                          <Calendar className="w-4 h-4" />
                          <span>{course.schedule || 'TBD'}</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <MapPin className="w-4 h-4" />
                          <span>{course.location || 'TBD'}</span>
                        </div>
                      </div>
                      
                      <div className="pt-4 border-t border-slate-100 flex items-center justify-between">
                        <div>
                          <span className="text-2xl font-playfair font-bold text-navy-900">
                            {formatPrice(course.price)}
                          </span>
                        </div>
                        {!course.is_coming_soon && (
                          <Button 
                            size="sm" 
                            className="bg-teal hover:bg-teal/90 font-dm-sans rounded-lg"
                            data-testid={`view-course-${course.id}`}
                          >
                            View
                            <ArrowRight className="w-3 h-3 ml-1" />
                          </Button>
                        )}
                      </div>
                    </CardContent>
                  </Card>
                </motion.div>
              ))}
            </div>
          )}
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-slate-100 py-8 px-6 bg-white/80 relative z-10">
        <div className="max-w-6xl mx-auto text-center">
          <span className="font-dm-sans text-sm text-navy-500">
            © 2025 Trauma Transformation Institute
          </span>
        </div>
      </footer>
    </div>
  );
};

export default WellnessHomePage;
