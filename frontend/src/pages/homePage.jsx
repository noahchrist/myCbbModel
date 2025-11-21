import { useState, useEffect } from 'react';
import { supabase } from '../lib/supabaseClient';
import { toast, ToastContainer } from 'react-toastify';
import 'react-toastify/dist/ReactToastify.css';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const showToast = (message, type = 'info') => {
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
  const [showModelModal, setShowModelModal] = useState(false);
  const [modelNames, setModelNames] = useState([]);
  const [selectedModelName, setSelectedModelName] = useState('');
  const [selectedBettingStyle, setSelectedBettingStyle] = useState('');
  const [showModelDetailModal, setShowModelDetailModal] = useState(false);
  const [selectedModel, setSelectedModel] = useState(null);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [isCreatingModel, setIsCreatingModel] = useState(false);
  const [userModels, setUserModels] = useState([]);
  const [communityModels, setCommunityModels] = useState([]);
  const [modelHistory, setModelHistory] = useState([]);
  const [loadingHistory, setLoadingHistory] = useState(false);

  const getModelColors = (tenDigit) => {
    if (!tenDigit) return { primary: '#333', secondary: '#666' };
    const digits = tenDigit.toString().padStart(10, '0');
    const first6 = digits.slice(0, 6);
    const last6 = digits.slice(-6);
    
    // Ensure colors have enough contrast by adjusting brightness
    const adjustColor = (hex) => {
      const num = parseInt(hex, 16);
      const r = (num >> 16) & 255;
      const g = (num >> 8) & 255;
      const b = num & 255;
      const brightness = (r * 299 + g * 587 + b * 114) / 1000;
      
      // If too light, darken it; if too dark, lighten it
      if (brightness > 200) {
        return `#${Math.max(0, r - 80).toString(16).padStart(2, '0')}${Math.max(0, g - 80).toString(16).padStart(2, '0')}${Math.max(0, b - 80).toString(16).padStart(2, '0')}`;
      } else if (brightness < 80) {
        return `#${Math.min(255, r + 100).toString(16).padStart(2, '0')}${Math.min(255, g + 100).toString(16).padStart(2, '0')}${Math.min(255, b + 100).toString(16).padStart(2, '0')}`;
      }
      return `#${hex}`;
    };
    
    return {
      primary: adjustColor(first6),
      secondary: adjustColor(last6)
    };
  };

  const getModelStyle = (tenDigit) => {
    const colors = getModelColors(tenDigit);
    return {
      background: `linear-gradient(135deg, ${colors.primary}20, ${colors.secondary}20)`,
      border: `2px solid ${colors.primary}`,
      boxShadow: `0 4px 8px ${colors.secondary}30`,
      colors
    };
  };

  const handleSliderChange = (id, newValue) => {
    setSliders(prev => prev.map(slider => 
      slider.id === id ? { ...slider, value: newValue } : slider
    ));
  };

  const fetchGames = async (date) => {
    setLoading(true);
    try {
      const response = await fetch(`${API_URL}/games/${date}`);
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
          const response = await fetch(`${API_URL}/me`, {
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
        showToast('Check your email for verification!', 'success');
      } else {
        const user = await signIn(loginForm.email, loginForm.password);
        console.log('User signed in:', user);
        setUser(user);
        
        // Sync user to local database on sign in
        try {
          const { data: { session } } = await supabase.auth.getSession();
          if (session?.access_token) {
            await fetch(`${API_URL}/me`, {
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
      showToast(error.message, 'error');
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

  const fetchModelNames = async () => {
    try {
      const response = await fetch(`${API_URL}/model-names`);
      const data = await response.json();
      setModelNames(data.names);
    } catch (error) {
      console.error('Error fetching model names:', error);
    }
  };

  const fetchUserModels = async () => {
    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session?.access_token) return;

      const response = await fetch(`${API_URL}/user-models`, {
        headers: { Authorization: `Bearer ${session.access_token}` }
      });
      const data = await response.json();
      setUserModels(data.models || []);
    } catch (error) {
      console.error('Error fetching user models:', error);
    }
  };

  const fetchCommunityModels = async () => {
    try {
      const response = await fetch(`${API_URL}/community-models`);
      const data = await response.json();
      setCommunityModels(data.models || []);
    } catch (error) {
      console.error('Error fetching community models:', error);
    }
  };

  const fetchModelHistory = async (modelId) => {
    try {
      setLoadingHistory(true);
      const { data: { session } } = await supabase.auth.getSession();
      
      // Include auth header if available, but don't require it for community models
      const headers = {};
      if (session?.access_token) {
        headers.Authorization = `Bearer ${session.access_token}`;
      }

      const response = await fetch(`${API_URL}/model-history/${modelId}`, { headers });
      const data = await response.json();
      setModelHistory(data.predictions || []);
    } catch (error) {
      console.error('Error fetching model history:', error);
      setModelHistory([]);
    } finally {
      setLoadingHistory(false);
    }
  };

  const handleDeleteModel = async () => {
    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session?.access_token) return;

      const response = await fetch(`${API_URL}/delete-model/${selectedModel.id}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${session.access_token}` }
      });

      if (response.ok) {
        showToast('Model deleted successfully!', 'success');
        setShowDeleteConfirm(false);
        setShowModelDetailModal(false);
        fetchUserModels();
        fetchCommunityModels();
      } else {
        showToast('Error deleting model', 'error');
      }
    } catch (error) {
      console.error('Error deleting model:', error);
      showToast('Error deleting model', 'error');
    }
  };

  const handleFinalizeModel = async () => {
    try {
      setIsCreatingModel(true);
      const { data: { session } } = await supabase.auth.getSession();
      if (!session?.access_token) {
        showToast('Please log in to create a model', 'error');
        setIsCreatingModel(false);
        return;
      }

      const tenDigitArray = sliders.map(s => s.value - 1);
      // Shuffle the array
      for (let i = tenDigitArray.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [tenDigitArray[i], tenDigitArray[j]] = [tenDigitArray[j], tenDigitArray[i]];
      }
      const tenDigit = tenDigitArray.join('');
      
      const modelData = {
        modelName: selectedModelName,
        bettingStyle: selectedBettingStyle,
        tenDigit: parseInt(tenDigit),
        weights: {
          weightGenOff: sliders[0].value - 1,
          weightGenDef: sliders[1].value - 1,
          weightPace: sliders[2].value - 1,
          weightThrees: sliders[3].value - 1,
          weightFts: sliders[4].value - 1,
          weightPerDef: sliders[5].value - 1,
          weightIntDef: sliders[6].value - 1,
          weightBoards: sliders[7].value - 1,
          weightPlaymaking: sliders[8].value - 1,
          weightIntangibles: sliders[9].value - 1
        },
        rejectedNames: modelNames.filter(name => name !== selectedModelName)
      };

      const response = await fetch(`${API_URL}/create-model`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${session.access_token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(modelData)
      });

      if (response.ok) {
        showToast('Model created successfully!', 'success');
        setShowModelModal(false);
        setSelectedModelName('');
        setSelectedBettingStyle('');
        setSliders(prev => prev.map(slider => ({ ...slider, value: 5 })));
        fetchUserModels();
      } else {
        showToast('Error creating model', 'error');
      }
    } catch (error) {
      console.error('Error creating model:', error);
      showToast('Error creating model', 'error');
    } finally {
      setIsCreatingModel(false);
    }
  };

  useEffect(() => {
    if (showModelModal) {
      fetchModelNames();
    }
  }, [showModelModal]);

  useEffect(() => {
    if (activeSection === 'My Models' && user) {
      fetchUserModels();
    }
  }, [activeSection, user]);

  useEffect(() => {
    if (activeSection === 'Community') {
      fetchCommunityModels();
    }
  }, [activeSection]);

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
            {/* User Models Display */}
            <div className="user-models-section">
              {userModels.length === 0 ? (
                <div className="no-models-message">
                  You have no models, create one below
                </div>
              ) : (
                <div className="models-grid">
                  {userModels.map(model => {
                    const modelStyle = getModelStyle(model.tenDigit);
                    return (
                      <div key={model.id} className="model-box" style={{...modelStyle, cursor: 'pointer'}} onClick={() => { setSelectedModel(model); setShowModelDetailModal(true); fetchModelHistory(model.id); }}>
                        <h3 className="model-name" style={{ color: modelStyle.colors.primary, fontSize: '1.5rem', fontWeight: 'bold' }}>{model.modelName}</h3>
                        <div className="model-stats">
                          <div className="stat-row">
                            <span className="stat-label" style={{ color: modelStyle.colors.secondary }}>Featured pick:</span>
                            <span className="stat-value" style={{ color: modelStyle.colors.primary }}>{model.featuredPick || 'None'}</span>
                          </div>
                          <div className="stat-row">
                            <span className="stat-label" style={{ color: modelStyle.colors.secondary }}>Overall record:</span>
                            <span className="stat-value" style={{ color: modelStyle.colors.primary }}>{model.wins || 0}-{model.losses || 0}</span>
                          </div>
                          <div className="stat-row">
                            <span className="stat-label" style={{ color: modelStyle.colors.secondary }}>Units won:</span>
                            <span className="stat-value" style={{ color: modelStyle.colors.primary }}>{model.unitsWon || 0}</span>
                          </div>
                          <div className="stat-row">
                            <span className="stat-label" style={{ color: modelStyle.colors.secondary }}>ROI:</span>
                            <span className="stat-value" style={{ color: modelStyle.colors.primary }}>{model.roi || 0}%</span>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
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
                        min="1"
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
                        min="1"
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
              <button onClick={() => setShowModelModal(true)}>Train New Model</button>
            </div>
          </div>
        )}
        
        {activeSection === 'Community' && (
          <div className="community-content">
            <div className="top-picks-section" style={{ marginBottom: '2rem' }}>
              <h2>Top Picks for {new Date().toLocaleDateString('en-US', { 
                weekday: 'long', 
                year: 'numeric', 
                month: 'long', 
                day: 'numeric' 
              })}</h2>
              <div style={{ textAlign: 'center', padding: '20px', color: '#666' }}>
                Picks coming soon...
              </div>
            </div>
            <h2>Community Models</h2>
            {communityModels.length === 0 ? (
              <div>Loading community models...</div>
            ) : (
              <div className="models-grid">
                {communityModels.map((model, index) => {
                  const modelStyle = getModelStyle(model.tenDigit);
                  return (
                    <div key={index} className="model-box" style={{...modelStyle, cursor: 'pointer'}} onClick={() => { setSelectedModel(model); setShowModelDetailModal(true); fetchModelHistory(model.id); }}>
                      <h3 className="model-name" style={{ color: modelStyle.colors.primary, fontSize: '1.5rem', fontWeight: 'bold' }}>{model.modelName}</h3>
                      <div className="model-stats">
                        <div className="stat-row">
                          <span className="stat-label" style={{ color: modelStyle.colors.secondary }}>Created by:</span>
                          <span className="stat-value" style={{ color: modelStyle.colors.primary }}>{model.userName}</span>
                        </div>
                        <div className="stat-row">
                          <span className="stat-label" style={{ color: modelStyle.colors.secondary }}>Style:</span>
                          <span className="stat-value" style={{ color: modelStyle.colors.primary }}>{model.bettingStyle}</span>
                        </div>
                        <div className="stat-row">
                          <span className="stat-label" style={{ color: modelStyle.colors.secondary }}>Record:</span>
                          <span className="stat-value" style={{ color: modelStyle.colors.primary }}>{model.wins}-{model.losses}</span>
                        </div>
                        <div className="stat-row">
                          <span className="stat-label" style={{ color: modelStyle.colors.secondary }}>Units won:</span>
                          <span className="stat-value" style={{ color: modelStyle.colors.primary }}>{model.unitsWon}</span>
                        </div>
                        <div className="stat-row">
                          <span className="stat-label" style={{ color: modelStyle.colors.secondary }}>ROI:</span>
                          <span className="stat-value" style={{ color: modelStyle.colors.primary }}>{model.roi}%</span>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
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

      {/* Loading Overlay */}
      {isCreatingModel && (
        <div className="modal-overlay" style={{ backgroundColor: 'rgba(0, 0, 0, 0.7)', zIndex: 2000 }}>
          <div style={{ color: 'white', fontSize: '1.5rem', textAlign: 'center' }}>
            <div style={{ marginBottom: '1rem' }}>Creating Model...</div>
            <div style={{ 
              border: '4px solid #f3f3f3',
              borderTop: '4px solid #00ff00',
              borderRadius: '50%',
              width: '40px',
              height: '40px',
              animation: 'spin 1s linear infinite',
              margin: '0 auto'
            }}></div>
          </div>
        </div>
      )}

      {/* Model Creation Modal */}
      {showModelModal && (
        <div className="modal-overlay" onClick={() => {
          setShowModelModal(false);
          setSelectedModelName('');
          setSelectedBettingStyle('');
        }}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <button className="modal-close" onClick={() => {
              setShowModelModal(false);
              setSelectedModelName('');
              setSelectedBettingStyle('');
            }}>×</button>
            <h2>Create New Model</h2>
            
            <div className="model-settings">
              <h3>Current Slider Settings:</h3>
              {sliders.map(slider => (
                <div key={slider.id} className="setting-row">
                  <span>{slider.category}: {slider.value}</span>
                </div>
              ))}
            </div>
            
            <div className="model-names">
              <h3>Select Model Name:</h3>
              {modelNames.map((name, index) => (
                <label key={index} className="radio-option">
                  <input
                    type="radio"
                    name="modelName"
                    value={name}
                    checked={selectedModelName === name}
                    onChange={(e) => setSelectedModelName(e.target.value)}
                  />
                  {name}
                </label>
              ))}
            </div>
            
            <div className="betting-styles">
              <h3>Select Betting Style:</h3>
              {['Aggressive', 'Moderate', 'Reserved'].map(style => (
                <label key={style} className="radio-option">
                  <input
                    type="radio"
                    name="bettingStyle"
                    value={style}
                    checked={selectedBettingStyle === style}
                    onChange={(e) => setSelectedBettingStyle(e.target.value)}
                  />
                  {style}
                </label>
              ))}
            </div>
            
            <button 
              className="finalize-button"
              disabled={!selectedModelName || !selectedBettingStyle || isCreatingModel}
              onClick={handleFinalizeModel}
              style={{
                opacity: (!selectedModelName || !selectedBettingStyle || isCreatingModel) ? 0.5 : 1,
                cursor: (!selectedModelName || !selectedBettingStyle || isCreatingModel) ? 'not-allowed' : 'pointer'
              }}
            >
              {isCreatingModel ? 'Creating Model...' : 'Finalize Model'}
            </button>
          </div>
        </div>
      )}

      {/* Model Detail Modal */}
      {showModelDetailModal && (
        <div className="modal-overlay" onClick={() => setShowModelDetailModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ 
            maxWidth: '800px', 
            maxHeight: '80vh', 
            overflow: 'auto',
            background: `linear-gradient(135deg, #${(parseInt(selectedModel?.tenDigit?.toString().slice(0, 6) || 'ffffff', 16) | 0xf0f0f0).toString(16).slice(-6)} 0%, #${(parseInt(selectedModel?.tenDigit?.toString().slice(-6) || 'ffffff', 16) | 0xf0f0f0).toString(16).slice(-6)} 100%)`,
            border: `2px solid #${(parseInt(selectedModel?.tenDigit?.toString().slice(0, 6) || 'cccccc', 16) | 0xc0c0c0).toString(16).slice(-6)}`,
            color: '#333'
          }}>
            <button className="modal-close" onClick={() => setShowModelDetailModal(false)} style={{
              color: '#333'
            }}>×</button>
            <h2 style={{
              color: `#${selectedModel?.tenDigit?.toString().slice(0, 6) || '333333'}`
            }}>{selectedModel?.modelName}</h2>
            
            {loadingHistory ? (
              <div style={{ textAlign: 'center', padding: '20px' }}>Loading history...</div>
            ) : modelHistory.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '20px' }}>No betting history available</div>
            ) : (
              <div className="model-history">
                <h3 style={{
                  color: `#${selectedModel?.tenDigit?.toString().slice(0, 6) || '333333'}`
                }}>Betting History</h3>
                <table style={{ width: '100%', borderCollapse: 'collapse', marginTop: '10px' }}>
                  <thead>
                    <tr style={{ borderBottom: `2px solid #${(parseInt(selectedModel?.tenDigit?.toString().slice(0, 6) || 'cccccc', 16) | 0xe0e0e0).toString(16).slice(-6)}` }}>
                      <th style={{ 
                        textAlign: 'left', 
                        padding: '8px', 
                        fontWeight: 'bold',
                        color: `#${selectedModel?.tenDigit?.toString().slice(0, 6) || '333333'}`
                      }}>Date</th>
                      <th style={{ 
                        textAlign: 'left', 
                        padding: '8px', 
                        fontWeight: 'bold',
                        color: `#${selectedModel?.tenDigit?.toString().slice(0, 6) || '333333'}`
                      }}>Pick</th>
                      <th style={{ 
                        textAlign: 'left', 
                        padding: '8px', 
                        fontWeight: 'bold',
                        color: `#${selectedModel?.tenDigit?.toString().slice(0, 6) || '333333'}`
                      }}>Units</th>
                    </tr>
                  </thead>
                  <tbody>
                    {modelHistory.map((prediction, index) => {
                      const isWin = prediction.result === 'w';
                      const unitsDisplay = prediction.unitsWon > 0 ? `+${prediction.unitsWon.toFixed(2)}u` : `${prediction.unitsWon.toFixed(2)}u`;
                      const textColor = '#555';
                      
                      return (
                        <tr key={index} style={{ borderBottom: `1px solid #${(parseInt(selectedModel?.tenDigit?.toString().slice(0, 6) || 'eeeeee', 16) | 0xf0f0f0).toString(16).slice(-6)}` }}>
                          <td style={{ textAlign: 'left', padding: '8px', color: textColor }}>
                            {new Date(prediction.date).toLocaleDateString('en-US', { month: 'numeric', day: 'numeric' })}
                          </td>
                          <td style={{ textAlign: 'left', padding: '8px', color: textColor }}>
                            {prediction.teamPick} {prediction.price > 0 ? `+${prediction.price}` : prediction.price}
                          </td>
                          <td style={{ textAlign: 'left', padding: '8px', fontWeight: 'bold', color: isWin ? 'green' : 'red' }}>
                            {unitsDisplay}
                          </td>
                        </tr>
                      );
                    })})
                  </tbody>
                </table>
              </div>
            )}
            
            {activeSection === 'My Models' && userModels.some(model => model.id === selectedModel?.id) && (
              <button 
                className="delete-button"
                onClick={() => setShowDeleteConfirm(true)}
                style={{ backgroundColor: '#ff4444', color: 'white', marginTop: '20px' }}
              >
                Delete Model
              </button>
            )}
          </div>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {showDeleteConfirm && (
        <div className="modal-overlay" onClick={() => setShowDeleteConfirm(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <h2>Confirm Delete</h2>
            <p>Are you sure you want to delete "{selectedModel?.modelName}"? This action cannot be undone.</p>
            <div style={{ display: 'flex', gap: '10px', justifyContent: 'center', marginTop: '20px' }}>
              <button onClick={() => setShowDeleteConfirm(false)}>Cancel</button>
              <button 
                onClick={handleDeleteModel}
                style={{ backgroundColor: '#ff4444', color: 'white' }}
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      )}

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
      
      <ToastContainer />
    </div>
  );
};

export default HomePage;