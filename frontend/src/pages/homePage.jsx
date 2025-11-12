import { useState, useEffect } from 'react';
import { supabase } from '../lib/supabaseClient';

const HomePage = () => {
  const [activeSection, setActiveSection] = useState('Home');
  const [isMobile, setIsMobile] = useState(false);
  const [showLoginModal, setShowLoginModal] = useState(false);
  const [isSignUp, setIsSignUp] = useState(false);
  const [loginForm, setLoginForm] = useState({ email: '', password: '', displayName: '' });
  const [user, setUser] = useState(null);
  const [authLoading, setAuthLoading] = useState(false);
  const [currentDate, setCurrentDate] = useState(() => {
    const today = new Date();
    const year = today.getFullYear();
    const month = String(today.getMonth() + 1).padStart(2, '0');
    const day = String(today.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
  });
  const [games, setGames] = useState([]);
  const [loading, setLoading] = useState(false);
  const [sliders, setSliders] = useState([
    { id: 1, category: 'General Offense', value: 5 },
    { id: 2, category: 'General Defense', value: 5 },
    { id: 3, category: 'Pace', value: 5 },
    { id: 4, category: 'Three Point Shooting', value: 5 },
    { id: 5, category: 'Free Throw Shooting', value: 5 },
    { id: 6, category: 'Perimeter Defense', value: 5 },
    { id: 7, category: 'Interior Defense', value: 5 },
    { id: 8, category: 'Rebounding', value: 5 },
    { id: 9, category: 'Playmaking', value: 5 },
    { id: 10, category: 'Intangibles', value: 5 }
  ]);

  const handleSliderChange = (id, newValue) => {
    setSliders(prev => prev.map(slider => 
      slider.id === id ? { ...slider, value: newValue } : slider
    ));
  };

  const fetchGames = async (date) => {
    setLoading(true);
    try {
      const response = await fetch(`http://localhost:8000/games/${date}`);
      const data = await response.json();
      setGames(Array.isArray(data) ? data : []);
    } catch (error) {
      console.error('Error fetching games:', error);
      setGames([]);
    } finally {
      setLoading(false);
    }
  };

  const changeDate = (days) => {
    const [year, month, day] = currentDate.split('-').map(Number);
    const newDate = new Date(year, month - 1, day);
    newDate.setDate(newDate.getDate() + days);
    const newYear = newDate.getFullYear();
    const newMonth = String(newDate.getMonth() + 1).padStart(2, '0');
    const newDay = String(newDate.getDate()).padStart(2, '0');
    const dateString = `${newYear}-${newMonth}-${newDay}`;
    setCurrentDate(dateString);
    fetchGames(dateString);
  };

  const formatTime = (timeString) => {
    if (!timeString) return 'TBD';
    const date = new Date(timeString);
    return date.toLocaleTimeString('en-US', { 
      hour: 'numeric', 
      minute: '2-digit'
    });
  };

  const formatOdds = (odds) => {
    if (!odds) return 'N/A';
    return odds > 0 ? `+${odds}` : `${odds}`;
  };

  const isGameCompleted = (game) => {
    return game.home_score !== null && game.away_score !== null;
  };

  const getWinnerClass = (isWinner) => {
    return isWinner ? 'winner' : 'loser';
  };

  const getBettingResults = (game) => {
    if (!isGameCompleted(game)) return {};
    
    const homeWon = game.home_score > game.away_score;
    const spreadResult = game.pt_diff + (game.fd_home_spread || 0) > 0;
    const totalResult = game.pt_total > (game.fd_over || 0);
    
    return {
      h2h: { homeWins: homeWon, awayWins: !homeWon },
      spread: { homeWins: spreadResult, awayWins: !spreadResult },
      total: { overWins: totalResult, underWins: !totalResult }
    };
  };

  const handleLoginClick = () => {
    setShowLoginModal(true);
    setIsSignUp(false);
  };

  const handleCloseModal = () => {
    setShowLoginModal(false);
    setLoginForm({ email: '', password: '', displayName: '' });
  };

  const signUp = async (email, password, displayName) => {
    const { data, error } = await supabase.auth.signUp({
      email,
      password,
      options: {
        data: {
          display_name: displayName,
        },
      },
    });

    if (error) throw error;
    
    // Sync new user to local database with custom display name
    if (data.user) {
      try {
        console.log('Attempting to sync new user with displayName:', displayName);
        const { data: { session } } = await supabase.auth.getSession();
        console.log('Session:', session);
        if (session?.access_token) {
          const response = await fetch('http://localhost:8000/me', {
            method: 'POST',
            headers: { 
              Authorization: `Bearer ${session.access_token}`,
              'Content-Type': 'application/json'
            },
            body: JSON.stringify({ displayName })
          });
          console.log('Sync response:', await response.json());
        }
      } catch (error) {
        console.error('Failed to sync new user:', error);
      }
    }
    
    return data.user;
  };

  const signIn = async (email, password) => {
    const { data, error } = await supabase.auth.signInWithPassword({
      email,
      password,
    });

    if (error) throw error;
    return data.user;
  };

  const signOut = async () => {
    const { error } = await supabase.auth.signOut();
    if (error) throw error;
  };

  const handleInputChange = (e) => {
    setLoginForm({ ...loginForm, [e.target.name]: e.target.value });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setAuthLoading(true);
    
    try {
      if (isSignUp) {
        const user = await signUp(loginForm.email, loginForm.password, loginForm.displayName);
        console.log('User signed up:', user);
        alert('Check your email for verification!');
      } else {
        const user = await signIn(loginForm.email, loginForm.password);
        console.log('User signed in:', user);
        setUser(user);
        
        // Sync user to local database on sign in
        try {
          const { data: { session } } = await supabase.auth.getSession();
          if (session?.access_token) {
            await fetch('http://localhost:8000/me', {
              headers: { Authorization: `Bearer ${session.access_token}` }
            });
          }
        } catch (error) {
          console.error('Failed to sync user on login:', error);
        }
        
        setActiveSection('My Models');
        setTimeout(() => window.scrollTo(0, 0), 100);
      }
      handleCloseModal();
    } catch (error) {
      console.error('Auth error:', error);
      alert(error.message);
    } finally {
      setAuthLoading(false);
    }
  };

  const handleLogout = async () => {
    try {
      await signOut();
      setUser(null);
    } catch (error) {
      console.error('Logout error:', error);
    }
  };

  useEffect(() => {
    if (activeSection === 'Home') {
      fetchGames(currentDate);
    }
  }, [activeSection, currentDate]);

  useEffect(() => {
    const mediaQuery = window.matchMedia('(max-width: 768px)');
    setIsMobile(mediaQuery.matches);
    
    const handleChange = (e) => setIsMobile(e.matches);
    mediaQuery.addEventListener('change', handleChange);
    
    return () => mediaQuery.removeEventListener('change', handleChange);
  }, []);

  useEffect(() => {
    // Check for existing session
    supabase.auth.getSession().then(({ data: { session } }) => {
      setUser(session?.user ?? null);
    });

    // Listen for auth changes
    const { data: { subscription } } = supabase.auth.onAuthStateChange((event, session) => {
      setUser(session?.user ?? null);
    });

    return () => subscription.unsubscribe();
  }, []);



  return (
    <div className="homepage">
      {/* Header */}
      <header className="header">
        <h1 className="title">🏋️ weightroom.io 🏋️</h1>
      </header>

      {/* Navigation */}
      <nav className="navigation">
        <button 
          className={`nav-button ${activeSection === 'Home' ? 'active' : ''}`}
          onClick={() => setActiveSection('Home')}
        >
          Home
        </button>
        <button 
          className={`nav-button ${activeSection === 'My Models' ? 'active' : ''}`}
          onClick={() => setActiveSection('My Models')}
        >
          My Models
        </button>
        <button 
          className={`nav-button ${activeSection === 'Community' ? 'active' : ''}`}
          onClick={() => setActiveSection('Community')}
        >
          Community
        </button>
        {user ? (
          <button 
            className={`nav-button ${activeSection === 'Account' ? 'active' : ''}`}
            onClick={() => setActiveSection('Account')}
          >
            Account
          </button>
        ) : (
          <button 
            className="nav-button"
            onClick={handleLoginClick}
          >
            Login
          </button>
        )}
      </nav>

      {/* Main Content */}
      <main className="main-content">
        {activeSection === 'Home' && (
          <div className="home-content">
            <div className="date-navigation">
              <button onClick={() => changeDate(-1)}>←</button>
              <h2>{new Date(currentDate + 'T00:00:00').toLocaleDateString('en-US', { 
                weekday: 'long', 
                year: 'numeric', 
                month: 'long', 
                day: 'numeric' 
              })}</h2>
              <button onClick={() => changeDate(1)}>→</button>
            </div>
            
            {loading ? (
              <div>Loading games...</div>
            ) : games.length === 0 ? (
              <div>No games scheduled for this date</div>
            ) : (
              <div className="games-list">
                {games.map((game, index) => (
                  <div key={index} className="game-card">
                    <div className="game-top">
                      <div className="game-time">{formatTime(game.commence_time)}</div>
                      <div className="teams">
                        <div className={`home-team ${isGameCompleted(game) ? getWinnerClass(game.home_score > game.away_score) : ''}`}>
                          {game.home_team}{isGameCompleted(game) ? ` (${game.home_score})` : ''}
                        </div>
                        <div className={`away-team ${isGameCompleted(game) ? getWinnerClass(game.away_score > game.home_score) : ''}`}>
                          {game.away_team}{isGameCompleted(game) ? ` (${game.away_score})` : ''}
                        </div>
                      </div>
                      <div className="h2h">
                        <div className={`home-h2h ${isGameCompleted(game) && game.fd_home_hhPrice ? getWinnerClass(getBettingResults(game).h2h.homeWins) : ''}`}>
                          {formatOdds(game.fd_home_hhPrice)}
                        </div>
                        <div className={`away-h2h ${isGameCompleted(game) && game.fd_away_hhPrice ? getWinnerClass(getBettingResults(game).h2h.awayWins) : ''}`}>
                          {formatOdds(game.fd_away_hhPrice)}
                        </div>
                      </div>
                      <div className="spreads">
                        <div className={`home-spread ${isGameCompleted(game) && game.fd_home_spread ? getWinnerClass(getBettingResults(game).spread.homeWins) : ''}`}>
                          {game.fd_home_spread ? `${game.fd_home_spread > 0 ? '+' : ''}${game.fd_home_spread}` : 'N/A'} ({formatOdds(game.fd_home_spreadPrice)})
                        </div>
                        <div className={`away-spread ${isGameCompleted(game) && game.fd_away_spread ? getWinnerClass(getBettingResults(game).spread.awayWins) : ''}`}>
                          {game.fd_away_spread ? `${game.fd_away_spread > 0 ? '+' : ''}${game.fd_away_spread}` : 'N/A'} ({formatOdds(game.fd_away_spreadPrice)})
                        </div>
                      </div>
                      <div className="totals">
                        <div className={`over ${isGameCompleted(game) && game.fd_over ? getWinnerClass(getBettingResults(game).total.overWins) : ''}`}>
                          O{game.fd_over || 'N/A'} ({formatOdds(game.fd_overPrice)})
                        </div>
                        <div className={`under ${isGameCompleted(game) && game.fd_under ? getWinnerClass(getBettingResults(game).total.underWins) : ''}`}>
                          U{game.fd_under || 'N/A'} ({formatOdds(game.fd_underPrice)})
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
        
        {activeSection === 'My Models' && (
          <div className="sliders-container">
            {sliders.map(slider => (
              <div key={slider.id} className="slider-row">
                {isMobile ? (
                  <>
                    <div className="slider-category-mobile">
                      {slider.category} - {slider.value}
                    </div>
                    <div className="slider-wrapper">
                      <input
                        type="range"
                        min="0"
                        max="10"
                        step="1"
                        value={slider.value}
                        onChange={(e) => handleSliderChange(slider.id, parseInt(e.target.value))}
                        className="slider"
                      />
                    </div>
                  </>
                ) : (
                  <>
                    <div className="slider-category">{slider.category}</div>
                    <div className="slider-wrapper">
                      <input
                        type="range"
                        min="0"
                        max="10"
                        step="1"
                        value={slider.value}
                        onChange={(e) => handleSliderChange(slider.id, parseInt(e.target.value))}
                        className="slider"
                      />
                    </div>
                    <div className="slider-percentage">{slider.value}</div>
                  </>
                )}
              </div>
            ))}
            <div style={{ display: 'flex', justifyContent: 'center', marginTop: '2rem' }}>
              <button>Train Model</button>
            </div>
          </div>
        )}
        
        {activeSection === 'Community' && (
          <div className="community-content">
            <h2>Community section coming soon</h2>
          </div>
        )}
        
        {activeSection === 'Account' && (
          <div className="account-content">
            <h2>Welcome, {user?.user_metadata?.display_name || user?.email}</h2>
            <p>Profile page coming soon</p>
            <button onClick={async () => {
              await handleLogout();
              setActiveSection('Home');
            }}>Logout</button>
          </div>
        )}
        
      </main>

      {/* Login Modal */}
      {showLoginModal && (
        <div className="modal-overlay" onClick={handleCloseModal}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <button className="modal-close" onClick={handleCloseModal}>×</button>
            <h2>{isSignUp ? 'Create Account' : 'Login'}</h2>
            <form onSubmit={handleSubmit}>
              {isSignUp && (
                <div className="form-row">
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
              <div className="form-row">
                <label>Email</label>
                <input
                  type="email"
                  name="email"
                  value={loginForm.email}
                  onChange={handleInputChange}
                  required
                />
              </div>
              <div className="form-row">
                <label>Password</label>
                <input
                  type="password"
                  name="password"
                  value={loginForm.password}
                  onChange={handleInputChange}
                  required
                />
              </div>
              <button type="submit" className="submit-button" disabled={authLoading}>
                {authLoading ? 'Loading...' : (isSignUp ? 'Create Account' : 'Login')}
              </button>
            </form>
            <p className="toggle-auth">
              {isSignUp ? 'Already have an account?' : "Don't have an account?"}
              <button 
                type="button" 
                className="link-button"
                onClick={() => setIsSignUp(!isSignUp)}
              >
                {isSignUp ? 'Login' : 'Create Account'}
              </button>
            </p>
          </div>
        </div>
      )}
    </div>
  );
};

export default HomePage;