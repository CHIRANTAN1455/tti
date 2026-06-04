import { useState, useEffect } from 'react';
import { Link, useParams, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { ArrowLeft, Calendar, MapPin, Clock, Users, Check, CreditCard } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import { Separator } from '@/components/ui/separator';
import { useAuth } from '@/context/AuthContext';
import { toast } from 'sonner';
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

const CourseDetailsPage = () => {
  const { courseId } = useParams();
  const { user, token } = useAuth();
  const navigate = useNavigate();
  const [course, setCourse] = useState(null);
  const [loading, setLoading] = useState(true);
  const [enrolling, setEnrolling] = useState(false);

  useEffect(() => {
    const fetchCourse = async () => {
      try {
        const response = await axios.get(`${API}/courses/${courseId}`);
        setCourse(response.data);
      } catch (error) {
        console.error('Error fetching course:', error);
        toast.error('Course not found');
        navigate('/');
      } finally {
        setLoading(false);
      }
    };
    fetchCourse();
  }, [courseId, navigate]);

  const formatPrice = (price) => {
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      maximumFractionDigits: 0
    }).format(price);
  };

  const handleEnroll = async () => {
    if (!user) {
      toast.info('Please sign in to enroll');
      navigate('/login', { state: { from: `/courses/${courseId}` } });
      return;
    }

    setEnrolling(true);
    try {
      const response = await axios.post(
        `${API}/enrollments/checkout`,
        {
          course_id: courseId,
          origin_url: window.location.origin
        },
        {
          headers: { Authorization: `Bearer ${token}` }
        }
      );
      
      // Redirect to Stripe checkout
      window.location.href = response.data.checkout_url;
    } catch (error) {
      console.error('Enrollment error:', error);
      const message = error.response?.data?.detail || 'Failed to start enrollment';
      toast.error(message);
      setEnrolling(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#f8fafa]">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-teal"></div>
      </div>
    );
  }

  if (!course) {
    return null;
  }

  const totalPrice = course.price + (course.equipment_fee || 0);
  const isWellness = course.track === 'wellness';

  return (
    <div className="min-h-screen bg-[#f8fafa]">
      {/* Wavy Background */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden z-0">
        <svg className="absolute top-0 left-0 w-full opacity-30" viewBox="0 0 1440 320" preserveAspectRatio="none">
          <path fill="#d4eded" d="M0,192L60,186.7C120,181,240,171,360,181.3C480,192,600,224,720,213.3C840,203,960,149,1080,144C1200,139,1320,181,1380,202.7L1440,224L1440,0L1380,0C1320,0,1200,0,1080,0C960,0,840,0,720,0C600,0,480,0,360,0C240,0,120,0,60,0L0,0Z"></path>
        </svg>
      </div>

      {/* Navigation */}
      <nav className="fixed top-0 left-0 right-0 z-50 bg-white/90 backdrop-blur-md border-b border-slate-100">
        <div className="max-w-7xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-6">
              <Link 
                to={isWellness ? '/wellness' : '/clinical'} 
                className="flex items-center gap-2 px-4 py-2 rounded-full border border-slate-200 text-navy-500 hover:text-navy-900 hover:border-slate-300 transition-all bg-white"
                data-testid="back-link"
              >
                <ArrowLeft className="w-4 h-4" />
                <span className="font-dm-sans text-sm">Back to Courses</span>
              </Link>
            </div>
            
            <div className="flex items-center gap-4">
              {user ? (
                <Link to="/dashboard">
                  <Button variant="outline" className="font-dm-sans rounded-lg" data-testid="dashboard-btn">
                    Dashboard
                  </Button>
                </Link>
              ) : (
                <Link to="/login">
                  <Button variant="outline" className="font-dm-sans rounded-lg" data-testid="login-btn">
                    Sign In
                  </Button>
                </Link>
              )}
            </div>
          </div>
        </div>
      </nav>

      {/* Content */}
      <div className="pt-24 pb-24 px-6 relative z-10">
        <div className="max-w-6xl mx-auto">
          <div className="grid lg:grid-cols-3 gap-12">
            {/* Main Content */}
            <motion.div 
              className="lg:col-span-2"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5 }}
            >
              <Badge 
                className={`mb-4 font-dm-sans border-0 px-4 py-1.5 ${isWellness ? 'bg-teal/10 text-teal' : 'bg-navy-100 text-navy-700'}`}
              >
                {course.track.charAt(0).toUpperCase() + course.track.slice(1)} Track - {course.level}
              </Badge>
              
              <h1 className="text-4xl md:text-5xl font-playfair font-bold text-navy-900 mb-6" data-testid="course-title">
                {course.title}
              </h1>
              
              <p className="text-lg font-dm-sans text-navy-500 mb-8 leading-relaxed">
                {course.detailed_description || course.description}
              </p>

              {/* Course Info */}
              <div className="grid sm:grid-cols-2 gap-4 mb-10">
                <div className="flex items-center gap-3 p-4 bg-white rounded-xl border border-slate-100 shadow-sm">
                  <Calendar className="w-5 h-5 text-teal" />
                  <div>
                    <p className="text-xs font-dm-sans text-navy-400 uppercase tracking-wide">Schedule</p>
                    <p className="font-dm-sans text-navy-900">{course.schedule}</p>
                  </div>
                </div>
                <div className="flex items-center gap-3 p-4 bg-white rounded-xl border border-slate-100 shadow-sm">
                  <MapPin className="w-5 h-5 text-teal" />
                  <div>
                    <p className="text-xs font-dm-sans text-navy-400 uppercase tracking-wide">Location</p>
                    <p className="font-dm-sans text-navy-900">{course.location}</p>
                  </div>
                </div>
                <div className="flex items-center gap-3 p-4 bg-white rounded-xl border border-slate-100 shadow-sm">
                  <Clock className="w-5 h-5 text-teal" />
                  <div>
                    <p className="text-xs font-dm-sans text-navy-400 uppercase tracking-wide">Duration</p>
                    <p className="font-dm-sans text-navy-900">{course.duration}</p>
                  </div>
                </div>
                <div className="flex items-center gap-3 p-4 bg-white rounded-xl border border-slate-100 shadow-sm">
                  <Users className="w-5 h-5 text-teal" />
                  <div>
                    <p className="text-xs font-dm-sans text-navy-400 uppercase tracking-wide">Instructor</p>
                    <p className="font-dm-sans text-navy-900">{course.instructor}</p>
                  </div>
                </div>
              </div>

              {/* Features */}
              <div>
                <h2 className="text-2xl font-playfair font-semibold text-navy-900 mb-6">
                  What You'll Learn
                </h2>
                <div className="grid sm:grid-cols-2 gap-4">
                  {course.features?.map((feature, index) => (
                    <div key={index} className="flex items-start gap-3">
                      <div className={`w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0 ${isWellness ? 'bg-teal/10' : 'bg-navy-100'}`}>
                        <Check className={`w-3 h-3 ${isWellness ? 'text-teal' : 'text-navy-600'}`} />
                      </div>
                      <span className="font-dm-sans text-navy-600">{feature}</span>
                    </div>
                  ))}
                </div>
              </div>
            </motion.div>

            {/* Sidebar - Enrollment Card */}
            <motion.div
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.5, delay: 0.2 }}
            >
              <Card className="sticky top-28 border-slate-200 shadow-card-hover rounded-xl bg-white">
                <CardContent className="p-6">
                  <div className="mb-6">
                    <div className="flex items-baseline gap-2 mb-2">
                      <span className="text-4xl font-playfair font-bold text-navy-900">
                        {formatPrice(course.price)}
                      </span>
                    </div>
                    {course.equipment_fee > 0 && (
                      <p className="text-sm font-dm-sans text-navy-400">
                        + {formatPrice(course.equipment_fee)} equipment fee
                      </p>
                    )}
                  </div>

                  <Separator className="my-6" />

                  <div className="space-y-3 mb-6">
                    <div className="flex justify-between text-sm font-dm-sans">
                      <span className="text-navy-500">Course Fee</span>
                      <span className="text-navy-900">{formatPrice(course.price)}</span>
                    </div>
                    {course.equipment_fee > 0 && (
                      <div className="flex justify-between text-sm font-dm-sans">
                        <span className="text-navy-500">Equipment Fee</span>
                        <span className="text-navy-900">{formatPrice(course.equipment_fee)}</span>
                      </div>
                    )}
                    <Separator />
                    <div className="flex justify-between font-dm-sans font-semibold">
                      <span className="text-navy-900">Total</span>
                      <span className="text-navy-900">{formatPrice(totalPrice)}</span>
                    </div>
                  </div>

                  <Button 
                    className={`w-full py-6 font-dm-sans font-medium rounded-lg ${isWellness ? 'bg-teal hover:bg-teal/90' : 'bg-navy-900 hover:bg-navy-800'}`}
                    onClick={handleEnroll}
                    disabled={enrolling}
                    data-testid="enroll-btn"
                  >
                    {enrolling ? (
                      <div className="flex items-center gap-2">
                        <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                        Processing...
                      </div>
                    ) : (
                      <>
                        <CreditCard className="w-4 h-4 mr-2" />
                        Enroll Now
                      </>
                    )}
                  </Button>

                  <p className="text-xs font-dm-sans text-navy-400 text-center mt-4">
                    Secure payment via Stripe
                  </p>

                  <div className="mt-6 p-4 bg-slate-50 rounded-lg border border-slate-100">
                    <p className="text-sm font-dm-sans text-navy-600">
                      <strong>Note:</strong> Complete prerequisite modules before advancing to higher levels.
                    </p>
                  </div>
                </CardContent>
              </Card>
            </motion.div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default CourseDetailsPage;
