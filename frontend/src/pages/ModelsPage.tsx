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

interface DailyPick {
  summary: string;
  unitsBet: number;
  edge: number;
  homeTeam: string;
  awayTeam: string;
}

interface ModelsPageProps {
  user: User | null;
}

const ModelsPage = ({ user }: ModelsPageProps) => {
  const [userModels, setUserModels] = useState<UserModel[]>([]);
  const [showCreatePage, setShowCreatePage] = useState(false);
  const [selectedModel, setSelectedModel] = useState<UserModel | null>(null);
  const [modelPicks, setModelPicks] = useState<{[key: number]: DailyPick[]}>({});
  const [selectedDate] = useState(() => {
    const now = new Date();
    const estDate = new Date(now.toLocaleString("en-US", {timeZone: "America/New_York"}));
    const year = estDate.getFullYear();
    const month = String(estDate.getMonth() + 1).padStart(2, '0');
    const day = String(estDate.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
  });

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

  const getModelColors = (tenDigit: number) => {
    if (!tenDigit) return { primary: '#333', secondary: '#666' };
    const digits = tenDigit.toString().padStart(10, '0');
    const first6 = digits.slice(0, 6);
    const last6 = digits.slice(-6);
    
    const adjustColor = (hex: string) => {
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

  const getModelStyle = (tenDigit: number) => {
    const colors = getModelColors(tenDigit);
    return {
      background: `linear-gradient(135deg, ${colors.primary}40, ${colors.secondary}40)`,
      backgroundColor: 'var(--background)',
      border: `4px solid ${colors.primary}`,
      boxShadow: `0 8px 16px ${colors.secondary}70, inset 0 1px 0 ${colors.primary}30`,
      colors
    };
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
      
      // Fetch daily picks for each model
      const picksPromises = (data.models || []).map(async (model: UserModel) => {
        try {
          const picksResponse = await fetch(`${API_URL}/model-daily-picks/${model.id}?date=${selectedDate}`, {
            headers: { Authorization: `Bearer ${session.access_token}` }
          });
          const picksData = await picksResponse.json();
          return { modelId: model.id, picks: picksData.picks || [] };
        } catch (error) {
          console.error(`Error fetching picks for model ${model.id}:`, error);
          return { modelId: model.id, picks: [] };
        }
      });
      
      const allPicks = await Promise.all(picksPromises);
      const picksMap = allPicks.reduce((acc, { modelId, picks }) => {
        acc[modelId] = picks;
        return acc;
      }, {} as {[key: number]: DailyPick[]});
      
      setModelPicks(picksMap);
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
          <h2>Log in to create and view models</h2>
        </div>
      </div>
    );
  }

  if (selectedModel) {
    return (
      <ModelHistoryPage 
        user={user} 
        model={selectedModel}
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
        onModelCreated={() => {
          showToast('Model created successfully!', 'success');
          fetchUserModels();
        }}
      />
    );
  }

  return (
    <div className="page">
      <div className="page-header">
        <h2>My Models</h2>
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
              return (
                <div key={model.id} className="model-card" style={modelStyle} onClick={() => setSelectedModel(model)}>
                  <h3 className="model-name" style={{ color: modelStyle.colors.primary, fontSize: '2rem' }}>{model.modelName}</h3>
                  <div className="model-stats-horizontal" style={{ color: modelStyle.colors.primary, marginBottom: '1rem', textAlign: 'center' }}>
                    Record: <span style={{ color: modelStyle.colors.secondary }}>{model.wins}-{model.losses}</span> | 
                    Units: <span style={{ color: modelStyle.colors.secondary }}>{model.unitsWon}</span> | 
                    ROI: <span style={{ color: modelStyle.colors.secondary }}>{model.roi}%</span>
                  </div>
                  <div className="model-picks" style={{ fontSize: '0.9rem', color: modelStyle.colors.secondary }}>
                    {modelPicks[model.id]?.slice(0, 5).map((pick, index) => (
                      <div key={index} style={{ marginBottom: '0.75rem' }}>
                        <div style={{ fontWeight: 'bold', color: modelStyle.colors.primary, marginBottom: '0.25rem' }}>
                          {index + 1}. {pick.homeTeam} vs {pick.awayTeam}
                        </div>
                        <div>{pick.summary}</div>
                      </div>
                    )) || <div>No picks for today</div>}
                  </div>
                </div>
              );
            })}
          </div>
        )}


      </div>


      
      <ToastContainer />
    </div>
  );
};

export default ModelsPage;