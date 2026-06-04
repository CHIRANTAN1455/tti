import { useState } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { motion } from 'framer-motion';
import { ArrowLeft, Eye, EyeOff } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { useAuth } from '@/context/AuthContext';
import { toast } from 'sonner';

// Logo component
const Logo = ({ className = "w-12 h-12" }) => (
  <img 
    src="https://customer-assets.emergentagent.com/job_ett-india/artifacts/ksfgr2qo_image.png" 
    alt="TTI Logo" 
    className={className}
  />
);

const LoginPage = () => {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);

  const from = location.state?.from || '/dashboard';

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!email || !password) {
      toast.error('Please fill in all fields');
      return;
    }

    setLoading(true);
    try {
      await login(email, password);
      toast.success('Welcome back!');
      navigate(from, { replace: true });
    } catch (error) {
      console.error('Login error:', error);
      const message = error.response?.data?.detail || 'Invalid email or password';
      toast.error(message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#f8fafa] flex items-center justify-center px-6 py-12">
      {/* Wavy Background */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden z-0">
        <svg className="absolute top-0 left-0 w-full opacity-30" viewBox="0 0 1440 320" preserveAspectRatio="none">
          <path fill="#d4eded" d="M0,192L60,186.7C120,181,240,171,360,181.3C480,192,600,224,720,213.3C840,203,960,149,1080,144C1200,139,1320,181,1380,202.7L1440,224L1440,0L1380,0C1320,0,1200,0,1080,0C960,0,840,0,720,0C600,0,480,0,360,0C240,0,120,0,60,0L0,0Z"></path>
        </svg>
      </div>

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="w-full max-w-md relative z-10"
      >
        {/* Back Link */}
        <Link 
          to="/" 
          className="inline-flex items-center gap-2 px-4 py-2 rounded-full border border-slate-200 text-navy-500 hover:text-navy-900 hover:border-slate-300 transition-all bg-white mb-8"
          data-testid="back-home-link"
        >
          <ArrowLeft className="w-4 h-4" />
          <span className="font-dm-sans text-sm">Back to Home</span>
        </Link>

        <Card className="border-slate-200 shadow-card bg-white rounded-xl">
          <CardHeader className="text-center pb-2">
            <Logo className="w-14 h-14 mx-auto mb-4" />
            <CardTitle className="text-2xl font-playfair text-navy-900">
              Welcome Back
            </CardTitle>
            <CardDescription className="font-dm-sans">
              Sign in to access your TTI account
            </CardDescription>
          </CardHeader>
          
          <CardContent className="pt-6">
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="email" className="font-dm-sans text-navy-700">
                  Email
                </Label>
                <Input
                  id="email"
                  type="email"
                  placeholder="you@example.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="h-12 font-dm-sans bg-slate-50 border-slate-200 focus:bg-white rounded-lg"
                  data-testid="email-input"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="password" className="font-dm-sans text-navy-700">
                  Password
                </Label>
                <div className="relative">
                  <Input
                    id="password"
                    type={showPassword ? 'text' : 'password'}
                    placeholder="••••••••"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="h-12 font-dm-sans bg-slate-50 border-slate-200 focus:bg-white pr-10 rounded-lg"
                    data-testid="password-input"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-navy-400 hover:text-navy-600"
                  >
                    {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>

              <Button 
                type="submit" 
                className="w-full h-12 bg-teal hover:bg-teal/90 font-dm-sans font-medium mt-6 rounded-lg"
                disabled={loading}
                data-testid="login-submit-btn"
              >
                {loading ? (
                  <div className="flex items-center gap-2">
                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                    Signing in...
                  </div>
                ) : (
                  'Sign In'
                )}
              </Button>
            </form>

            <div className="mt-6 text-center">
              <p className="font-dm-sans text-sm text-navy-500">
                Don't have an account?{' '}
                <Link 
                  to="/signup" 
                  className="text-teal hover:text-teal/80 font-medium"
                  data-testid="signup-link"
                >
                  Sign up
                </Link>
              </p>
            </div>
          </CardContent>
        </Card>
      </motion.div>
    </div>
  );
};

export default LoginPage;
