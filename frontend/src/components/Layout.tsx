import { useState, useEffect, ReactNode } from 'react';
import { User } from '@supabase/supabase-js';
import { supabase } from '../lib/supabaseClient';
import { toast, ToastContainer } from 'react-toastify';
import 'react-toastify/dist/ReactToastify.css';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

type TabType = 'home' | 'models' | 'community' | 'account';

interface LayoutProps {
  children: ReactNode;
  activeTab: TabType;
  setActiveTab: (tab: TabType) => void;
  user: User | null;
  setUser: (user: User | null) => void;
}

const Layout = ({ children, activeTab, setActiveTab, user, setUser }: LayoutProps) => {
  const [showLoginModal, setShowLoginModal] = useState(false);
  const [isSignUp, setIsSignUp] = useState(false);
  const [loginForm, setLoginForm] = useState({ email: '', password: '', displayName: '' });
  const [authLoading, setAuthLoading] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const showToast = (message: string, type: 'info' | 'success' | 'error' = 'info') => {
    toast[type](message, {
      position: 'top-center',
      autoClose: 3000,
      hideProgressBar: true,
      closeOnClick: true,
      pauseOnHover: true,
      draggable: true,
      style: {
        backgroundColor: 'white',
        color: 'black',
        border: '2px solid #00ff00',
        borderRadius: '8px',
        fontFamily: 'inherit'
      }
    });
  };

  const handleLoginClick = () => {
    setShowLoginModal(true);
    setIsSignUp(false);
  };

  const handleCloseModal = () => {
    setShowLoginModal(false);
    setLoginForm({ email: '', password: '', displayName: '' });
  };

  const signUp = async (email: string, password: string, displayName: string) => {
    const { data, error } = await supabase.auth.signUp({
      email,
      password,
      options: {
        data: { display_name: displayName },
        emailRedirectTo: `${window.location.origin}/auth/verified`
      },
    });
    if (error) throw error;
    return data.user;
  };

  const signIn = async (email: string, password: string) => {
    const { data, error } = await supabase.auth.signInWithPassword({ email, password });
    if (error) throw error;
    return data.user;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setAuthLoading(true);
    try {
      if (isSignUp) {
        await signUp(loginForm.email, loginForm.password, loginForm.displayName);
        showToast('Check your email for verification!', 'success');
        handleCloseModal();
      } else {
        const user = await signIn(loginForm.email, loginForm.password);
        setUser(user);
        setActiveTab('models');
        handleCloseModal();
        
        // Sync user to local database after successful login
        try {
          const { data: { session } } = await supabase.auth.getSession();
          if (session?.access_token) {
            await fetch(`${API_URL}/me`, {
              headers: { Authorization: `Bearer ${session.access_token}` }
            });
          }
        } catch (error) {
          console.error('Error syncing user to local DB:', error);
        }
      }
    } catch (error) {
      console.error('Auth error:', error);
      showToast((error as Error).message, 'error');
    } finally {
      setAuthLoading(false);
    }
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setLoginForm({ ...loginForm, [e.target.name]: e.target.value });
  };

  const handleLogout = async () => {
    setUser(null);
    await supabase.auth.signOut();
    setActiveTab('home');
  };

  const handleNavClick = (tab: TabType) => {
    setActiveTab(tab);
    setMobileMenuOpen(false);
  };

  return (
    <div className="app">
      <header className="header">
        <div className="header-content">
          <h1 className="logo">🏋️ weightroom.io</h1>
          <button 
            className="mobile-menu-btn"
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
          >
            ☰
          </button>
          {!user && (
            <button onClick={handleLoginClick} className="btn btn-primary">Login</button>
          )}
        </div>
      </header>

      <nav className="nav">
        <div className="nav-content">
          <button 
            className={`nav-btn ${activeTab === 'home' ? 'active' : ''}`}
            onClick={() => handleNavClick('home')}
          >
            Games
          </button>
          <button 
            className={`nav-btn ${activeTab === 'models' ? 'active' : ''}`}
            onClick={() => handleNavClick('models')}
          >
            My Models
          </button>
          <button 
            className={`nav-btn ${activeTab === 'community' ? 'active' : ''}`}
            onClick={() => handleNavClick('community')}
          >
            Community
          </button>
          {user && (
            <button 
              className={`nav-btn ${activeTab === 'account' ? 'active' : ''}`}
              onClick={() => handleNavClick('account')}
            >
              Account
            </button>
          )}
        </div>
      </nav>

      <nav className={`nav-mobile ${mobileMenuOpen ? 'open' : ''}`}>
        <button 
          className={`nav-btn ${activeTab === 'home' ? 'active' : ''}`}
          onClick={() => handleNavClick('home')}
        >
          Games
        </button>
        <button 
          className={`nav-btn ${activeTab === 'models' ? 'active' : ''}`}
          onClick={() => handleNavClick('models')}
        >
          My Models
        </button>
        <button 
          className={`nav-btn ${activeTab === 'community' ? 'active' : ''}`}
          onClick={() => handleNavClick('community')}
        >
          Community
        </button>
        {user && (
          <button 
            className={`nav-btn ${activeTab === 'account' ? 'active' : ''}`}
            onClick={() => handleNavClick('account')}
          >
            Account
          </button>
        )}
        {!user && (
          <button 
            className="nav-btn"
            onClick={() => {
              handleLoginClick();
              setMobileMenuOpen(false);
            }}
          >
            Login
          </button>
        )}
      </nav>

      <main className="main">
        {children}
      </main>

      {showLoginModal && (
        <div className="modal-overlay" onClick={handleCloseModal}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <button className="modal-close" onClick={handleCloseModal}>×</button>
            <h2>{isSignUp ? 'Create Account' : 'Login'}</h2>
            <form onSubmit={handleSubmit}>
              {isSignUp && (
                <div className="form-group">
                  <label>Username</label>
                  <input
                    type="text"
                    name="displayName"
                    value={loginForm.displayName}
                    onChange={handleInputChange}
                    required
                  />
                </div>
              )}
              <div className="form-group">
                <label>Email</label>
                <input
                  type="email"
                  name="email"
                  value={loginForm.email}
                  onChange={handleInputChange}
                  required
                />
              </div>
              <div className="form-group">
                <label>Password</label>
                <input
                  type="password"
                  name="password"
                  value={loginForm.password}
                  onChange={handleInputChange}
                  required
                />
              </div>
              <button type="submit" className="btn btn-primary full-width" disabled={authLoading}>
                {authLoading ? 'Loading...' : (isSignUp ? 'Create Account' : 'Login')}
              </button>
            </form>
            <p className="auth-toggle">
              {isSignUp ? 'Already have an account?' : "Don't have an account?"}
              <button 
                type="button" 
                className="link-btn"
                onClick={() => setIsSignUp(!isSignUp)}
              >
                {isSignUp ? 'Login' : 'Create Account'}
              </button>
            </p>
          </div>
        </div>
      )}
      
      <ToastContainer />
    </div>
  );
};

export default Layout;