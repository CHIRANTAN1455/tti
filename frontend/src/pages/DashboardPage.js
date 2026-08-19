import { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { LogOut, BookOpen, Calendar, Award, ArrowRight, Trophy } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { useAuth } from '@/context/AuthContext';
import CourseJourneyMap from '@/components/CourseJourneyMap';
import CertificateCard from '@/components/CertificateCard';
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

const DashboardPage = () => {
  const { user, token, logout } = useAuth();
  const navigate = useNavigate();
  const [enrollments, setEnrollments] = useState([]);
  const [courses, setCourses] = useState([]);
  const [quizResults, setQuizResults] = useState([]);
  const [certificates, setCertificates] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchEnrollments = async () => {
      try {
        const response = await axios.get(`${API}/enrollments/my`, {
          headers: { Authorization: `Bearer ${token}` }
        });
        setEnrollments(response.data);
      } catch (error) {
        console.error('Error fetching enrollments:', error);
      } finally {
        setLoading(false);
      }
    };
    fetchEnrollments();
    axios.get(`${API}/courses`).then((res) => setCourses(res.data)).catch(() => {});
    axios
      .get(`${API}/quiz-results/my`, { headers: { Authorization: `Bearer ${token}` } })
      .then((res) => setQuizResults(res.data))
      .catch(() => {});
    axios
      .get(`${API}/certificates/my`, { headers: { Authorization: `Bearer ${token}` } })
      .then((res) => setCertificates(res.data))
      .catch(() => {});
  }, [token]);

  const enrolledIds = new Set(enrollments.map((e) => e.course.id));
  const quizPassedIds = new Set(quizResults.filter((r) => r.passed).map((r) => r.course_id));

  const handleLogout = () => {
    logout();
    toast.success('Signed out successfully');
    navigate('/', { replace: true });
  };

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
        <svg className="absolute top-0 left-0 w-full opacity-30" viewBox="0 0 1440 320" preserveAspectRatio="none">
          <path fill="#d4eded" d="M0,192L60,186.7C120,181,240,171,360,181.3C480,192,600,224,720,213.3C840,203,960,149,1080,144C1200,139,1320,181,1380,202.7L1440,224L1440,0L1380,0C1320,0,1200,0,1080,0C960,0,840,0,720,0C600,0,480,0,360,0C240,0,120,0,60,0L0,0Z"></path>
        </svg>
      </div>

      {/* Navigation */}
      <nav className="fixed top-0 left-0 right-0 z-50 bg-white/90 backdrop-blur-md border-b border-slate-100">
        <div className="max-w-7xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <Link to="/" className="flex items-center gap-3">
              <Logo className="w-8 h-8" />
              <span className="font-playfair font-semibold text-navy-900">TTI Dashboard</span>
            </Link>
            
            <div className="flex items-center gap-4">
              <span className="text-sm font-dm-sans text-navy-600">
                {user?.name}
              </span>
              <Button 
                variant="outline" 
                size="sm"
                onClick={handleLogout}
                className="font-dm-sans rounded-lg"
                data-testid="logout-btn"
              >
                <LogOut className="w-4 h-4 mr-2" />
                Sign Out
              </Button>
            </div>
          </div>
        </div>
      </nav>

      {/* Content */}
      <div className="pt-24 pb-12 px-6 relative z-10">
        <div className="max-w-6xl mx-auto">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
          >
            {/* Header */}
            <div className="mb-8">
              <h1 className="text-3xl font-playfair font-bold text-navy-900 mb-2" data-testid="dashboard-title">
                Welcome, {user?.name}
              </h1>
              <p className="font-dm-sans text-navy-500">
                Manage your enrolled courses and access training materials
              </p>
            </div>

            {/* Stats */}
            <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
              <Card className="border-slate-200 shadow-card bg-white rounded-xl">
                <CardContent className="p-6 flex items-center gap-4">
                  <div className="w-12 h-12 rounded-full bg-teal/10 flex items-center justify-center">
                    <BookOpen className="w-6 h-6 text-teal" />
                  </div>
                  <div>
                    <p className="text-2xl font-playfair font-bold text-navy-900">
                      {enrollments.length}
                    </p>
                    <p className="text-sm font-dm-sans text-navy-500">Enrolled Courses</p>
                  </div>
                </CardContent>
              </Card>
              
              <Card className="border-slate-200 shadow-card bg-white rounded-xl">
                <CardContent className="p-6 flex items-center gap-4">
                  <div className="w-12 h-12 rounded-full bg-emerald-100 flex items-center justify-center">
                    <Award className="w-6 h-6 text-emerald-600" />
                  </div>
                  <div>
                    <p className="text-2xl font-playfair font-bold text-navy-900">
                      {enrollments.filter(e => e.course?.level === 'level2').length}
                    </p>
                    <p className="text-sm font-dm-sans text-navy-500">Certifications</p>
                  </div>
                </CardContent>
              </Card>
              
              <Card className="border-slate-200 shadow-card bg-white rounded-xl">
                <CardContent className="p-6 flex items-center gap-4">
                  <div className="w-12 h-12 rounded-full bg-amber-100 flex items-center justify-center">
                    <Calendar className="w-6 h-6 text-amber-600" />
                  </div>
                  <div>
                    <p className="text-2xl font-playfair font-bold text-navy-900">
                      {enrollments.length > 0 ? 'Active' : 'None'}
                    </p>
                    <p className="text-sm font-dm-sans text-navy-500">Upcoming Sessions</p>
                  </div>
                </CardContent>
              </Card>

              <Card className="border-slate-200 shadow-card bg-white rounded-xl">
                <CardContent className="p-6 flex items-center gap-4">
                  <div className="w-12 h-12 rounded-full bg-purple-100 flex items-center justify-center">
                    <Trophy className="w-6 h-6 text-purple-600" />
                  </div>
                  <div>
                    <p className="text-2xl font-playfair font-bold text-navy-900">
                      {quizPassedIds.size}
                    </p>
                    <p className="text-sm font-dm-sans text-navy-500">Quizzes Passed</p>
                  </div>
                </CardContent>
              </Card>
            </div>

            {/* Journey Map */}
            {courses.length > 0 && (
              <div className="mb-8">
                <CourseJourneyMap
                  courses={courses}
                  enrolledIds={enrolledIds}
                  quizPassedIds={quizPassedIds}
                  onSelect={(c) => navigate(`/courses/${c.id}`)}
                />
              </div>
            )}

            {/* Certificates */}
            {certificates.length > 0 && (
              <div className="mb-8">
                <h2 className="text-2xl font-playfair font-semibold text-navy-900 mb-4">Certificates</h2>
                <div className="grid sm:grid-cols-2 gap-4">
                  {certificates.map((c) => (
                    <CertificateCard key={c.track} {...c} />
                  ))}
                </div>
              </div>
            )}

            {/* Enrolled Courses */}
            <Card className="border-slate-200 shadow-card bg-white rounded-xl">
              <CardHeader>
                <CardTitle className="font-playfair text-navy-900">
                  My Enrolled Courses
                </CardTitle>
              </CardHeader>
              <CardContent>
                {loading ? (
                  <div className="flex justify-center py-12">
                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-teal"></div>
                  </div>
                ) : enrollments.length === 0 ? (
                  <div className="text-center py-12">
                    <BookOpen className="w-12 h-12 text-navy-300 mx-auto mb-4" />
                    <h3 className="text-lg font-playfair font-semibold text-navy-900 mb-2">
                      No Courses Yet
                    </h3>
                    <p className="font-dm-sans text-navy-500 mb-6">
                      Start your transformation journey by enrolling in a course
                    </p>
                    <div className="flex gap-4 justify-center">
                      <Link to="/wellness">
                        <Button className="bg-teal hover:bg-teal/90 font-dm-sans rounded-lg" data-testid="browse-wellness-btn">
                          Wellness Track
                        </Button>
                      </Link>
                      <Link to="/clinical">
                        <Button className="bg-navy-900 hover:bg-navy-800 font-dm-sans rounded-lg" data-testid="browse-clinical-btn">
                          Clinical Track
                        </Button>
                      </Link>
                    </div>
                  </div>
                ) : (
                  <div className="space-y-4">
                    {enrollments.map((item, index) => (
                      <div key={item.enrollment.id}>
                        <div className="flex items-center justify-between p-4 rounded-xl bg-slate-50 hover:bg-slate-100 transition-colors">
                          <div className="flex-1">
                            <div className="flex items-center gap-3 mb-2">
                              <h3 className="font-playfair font-semibold text-navy-900">
                                {item.course.title}
                              </h3>
                              <Badge 
                                className={`font-dm-sans text-xs border-0 ${item.course.track === 'wellness' ? 'bg-teal/10 text-teal' : 'bg-navy-100 text-navy-700'}`}
                              >
                                {item.course.track}
                              </Badge>
                            </div>
                            <div className="flex items-center gap-4 text-sm font-dm-sans text-navy-500">
                              <span className="flex items-center gap-1">
                                <Calendar className="w-4 h-4" />
                                {item.course.schedule}
                              </span>
                              <span>{item.course.location}</span>
                            </div>
                          </div>
                          <div className="flex items-center gap-4">
                            <Badge className="bg-emerald-100 text-emerald-700 font-dm-sans border-0">
                              Enrolled
                            </Badge>
                            <Button 
                              variant="outline" 
                              size="sm"
                              className="font-dm-sans rounded-lg"
                              onClick={() => navigate(`/courses/${item.course.id}`)}
                            >
                              View
                              <ArrowRight className="w-3 h-3 ml-1" />
                            </Button>
                          </div>
                        </div>
                        {index < enrollments.length - 1 && <Separator className="my-2" />}
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Quick Links */}
            {enrollments.length > 0 && (
              <div className="mt-8 grid sm:grid-cols-2 gap-4">
                <Card className="border-slate-200 shadow-card hover:shadow-card-hover transition-all cursor-pointer bg-white rounded-xl">
                  <CardContent className="p-6">
                    <h3 className="font-playfair font-semibold text-navy-900 mb-2">
                      Training Materials
                    </h3>
                    <p className="text-sm font-dm-sans text-navy-500 mb-4">
                      Access course resources, protocols, and supplementary materials
                    </p>
                    <Button variant="outline" size="sm" className="font-dm-sans rounded-lg">
                      Coming Soon
                    </Button>
                  </CardContent>
                </Card>
                
                <Card className="border-slate-200 shadow-card hover:shadow-card-hover transition-all cursor-pointer bg-white rounded-xl">
                  <CardContent className="p-6">
                    <h3 className="font-playfair font-semibold text-navy-900 mb-2">
                      Consultation Calls
                    </h3>
                    <p className="text-sm font-dm-sans text-navy-500 mb-4">
                      Schedule monthly consultation calls with ETT instructors
                    </p>
                    <Button variant="outline" size="sm" className="font-dm-sans rounded-lg">
                      Coming Soon
                    </Button>
                  </CardContent>
                </Card>
              </div>
            )}
          </motion.div>
        </div>
      </div>
    </div>
  );
};

export default DashboardPage;
