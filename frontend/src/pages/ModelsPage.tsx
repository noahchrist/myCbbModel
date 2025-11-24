import { useState, useEffect } from 'react';
import { User } from '@supabase/supabase-js';
import { supabase } from '../lib/supabaseClient';
import { toast, ToastContainer } from 'react-toastify';
import 'react-toastify/dist/ReactToastify.css';
import ModelHistoryPage from './ModelHistoryPage';
import CreateModelPage from './CreateModelPage';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

interface UserModel {
  id: number;
  modelName: string;
  tenDigit: number;
  wins: number;
  losses: number;
  unitsWon: number;
  roi: number;
  weights?: {
    weightGenOff: number;
    weightGenDef: number;
    weightPace: number;
    weightThrees: number;
    weightFts: number;
    weightPerDef: number;
    weightIntDef: number;
    weightBoards: number;
    weightPlaymaking: number;
    weightIntangibles: number;
  };
}

interface Slider {
  id: number;
  category: string;
  value: number;
}

interface ModelsPageProps {
  user: User | null;
}

const ModelsPage = ({ user }: ModelsPageProps) => {
  const [userModels, setUserModels] = useState<UserModel[]>([]);
  const [sliders, setSliders] = useState<Slider[]>([
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
  const [showCreatePage, setShowCreatePage] = useState(false);

  const [selectedModel, setSelectedModel] = useState<UserModel | null>(null);
  const [selectedModelForSliders, setSelectedModelForSliders] = useState<UserModel | null>(null);

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

  const getModelColors = (tenDigit) => {
    if (!tenDigit) return { primary: '#333', secondary: '#666' };
    const digits = tenDigit.toString().padStart(10, '0');
    const first6 = digits.slice(0, 6);
    const last6 = digits.slice(-6);
    
    const adjustColor = (hex) => {
      const num = parseInt(hex, 16);
      const r = (num >> 16) & 255;
      const g = (num >> 8) & 255;
      const b = num & 255;
      const brightness = (r * 299 + g * 587 + b * 114) / 1000;
      
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
      background: `linear-gradient(135deg, ${colors.primary}40, ${colors.secondary}40)`,
      backgroundColor: 'var(--background)',
      border: `4px solid ${colors.primary}`,
      boxShadow: `0 8px 16px ${colors.secondary}70, inset 0 1px 0 ${colors.primary}30`,
      colors
    };
  };

  const handleSliderChange = (id: number, newValue: number) => {
    setSliders(prev => prev.map(slider => 
      slider.id === id ? { ...slider, value: newValue } : slider
    ));
  };

  const fetchUserModels = async () => {
    if (!user) return;
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



  useEffect(() => {
    if (user) {
      fetchUserModels();
    }
  }, [user]);



  if (!user) {
    return (
      <div className="page">
        <div className="empty-state">
          <h2>Please log in to view your models</h2>
        </div>
      </div>
    );
  }

  if (selectedModel) {
    return (
      <ModelHistoryPage 
        user={user} 
        modelId={selectedModel.id} 
        modelName={selectedModel.modelName}
        onBack={() => setSelectedModel(null)}
        onDelete={() => {
          showToast('Model deleted successfully!', 'success');
          fetchUserModels();
        }}
      />
    );
  }

  if (showCreatePage) {
    return (
      <CreateModelPage 
        user={user}
        onBack={() => setShowCreatePage(false)}
        onModelCreated={() => fetchUserModels()}
      />
    );
  }

  return (
    <div className="page">
      <div className="page-header">
        <h1>My Models</h1>
        <button onClick={() => setShowCreatePage(true)} className="btn btn-primary">
          Create Model
        </button>
      </div>

      <div className="page-content">
        {userModels.length === 0 ? (
          <div className="empty-state">
            <p>You have no models yet. Create one to get started!</p>
          </div>
        ) : (
          <div className="models-grid">
            {userModels.map(model => {
              const modelStyle = getModelStyle(model.tenDigit);
              const isSelected = selectedModelForSliders?.id === model.id;
              return (
                <div key={model.id} className={`model-card ${isSelected ? 'selected' : ''}`} style={modelStyle} onClick={() => {
                  if (isSelected) {
                    setSelectedModelForSliders(null);
                  } else {
                    setSelectedModelForSliders(model);
                    if (model.weights) {
                      setSliders([
                        { id: 1, category: 'General Offense', value: model.weights.weightGenOff + 1 },
                        { id: 2, category: 'General Defense', value: model.weights.weightGenDef + 1 },
                        { id: 3, category: 'Pace', value: model.weights.weightPace + 1 },
                        { id: 4, category: 'Three Point Shooting', value: model.weights.weightThrees + 1 },
                        { id: 5, category: 'Free Throw Shooting', value: model.weights.weightFts + 1 },
                        { id: 6, category: 'Perimeter Defense', value: model.weights.weightPerDef + 1 },
                        { id: 7, category: 'Interior Defense', value: model.weights.weightIntDef + 1 },
                        { id: 8, category: 'Rebounding', value: model.weights.weightBoards + 1 },
                        { id: 9, category: 'Playmaking', value: model.weights.weightPlaymaking + 1 },
                        { id: 10, category: 'Intangibles', value: model.weights.weightIntangibles + 1 }
                      ]);
                    }
                  }
                }}>

                  <h3 className="model-name" style={{ color: modelStyle.colors.primary }}>{model.modelName}</h3>
                  <div className="model-stats">
                    <div className="stat">
                      <span className="stat-label" style={{ color: modelStyle.colors.secondary }}>Record</span>
                      <span className="stat-value" style={{ color: modelStyle.colors.primary }}>{model.wins}-{model.losses}</span>
                    </div>
                    <div className="stat">
                      <span className="stat-label" style={{ color: modelStyle.colors.secondary }}>Units</span>
                      <span className="stat-value" style={{ color: modelStyle.colors.primary }}>{model.unitsWon}</span>
                    </div>
                    <div className="stat">
                      <span className="stat-label" style={{ color: modelStyle.colors.secondary }}>ROI</span>
                      <span className="stat-value" style={{ color: modelStyle.colors.primary }}>{model.roi}%</span>
                    </div>
                  </div>
                  <button 
                    className="btn btn-outline"
                    style={{ marginTop: '0.5rem', fontSize: '0.75rem', padding: '0.25rem 0.5rem' }}
                    onClick={(e) => {
                      e.stopPropagation();
                      setSelectedModel(model);
                    }}
                  >
                    View History
                  </button>
                </div>
              );
            })}
          </div>
        )}

        {selectedModelForSliders && (
          <div className="sliders-section">
            <h2>{selectedModelForSliders.modelName} Configuration</h2>
            <div className="sliders-grid">
              <div className="slider-column">
                <h3>Offensive</h3>
                {sliders.filter(s => [1, 3, 4, 5, 9].includes(s.id)).map(slider => (
                  <div key={slider.id} className="slider-item">
                    <div className="slider-header">
                      <span className="slider-label">{slider.category}</span>
                      <span className="slider-value">{slider.value}</span>
                    </div>
                    <input
                      type="range"
                      min="1"
                      max="10"
                      step="1"
                      value={slider.value}
                      className="slider"
                      disabled
                    />
                  </div>
                ))}
              </div>
              
              <div className="slider-column">
                <h3>Defensive</h3>
                {sliders.filter(s => [2, 6, 7, 8, 10].includes(s.id)).map(slider => (
                  <div key={slider.id} className="slider-item">
                    <div className="slider-header">
                      <span className="slider-label">{slider.category}</span>
                      <span className="slider-value">{slider.value}</span>
                    </div>
                    <input
                      type="range"
                      min="1"
                      max="10"
                      step="1"
                      value={slider.value}
                      className="slider"
                      disabled
                    />
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>


      
      <ToastContainer />
    </div>
  );
};

export default ModelsPage;