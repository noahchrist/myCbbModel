import { useState, useEffect } from 'react';
import { User } from '@supabase/supabase-js';
import { supabase } from '../lib/supabaseClient';
import { toast, ToastContainer } from 'react-toastify';
import 'react-toastify/dist/ReactToastify.css';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

interface ModelHistoryProps {
  user: User | null;
  model: UserModel;
  onBack: () => void;
  onDelete: () => void;
}

interface HistoryEntry {
  date: string;
  teamPick: string;
  price: number;
  unitsWon: number;
  result: string;
}

interface Slider {
  id: number;
  category: string;
  value: number;
}

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

const ModelHistoryPage = ({ user, model, onBack, onDelete }: ModelHistoryProps) => {
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [sliders, setSliders] = useState<Slider[]>([]);

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

  const handleDeleteModel = async () => {
    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session?.access_token) return;

      const response = await fetch(`${API_URL}/delete-model/${model.id}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${session.access_token}` }
      });

      if (response.ok) {
        onDelete();
        onBack();
      } else {
        showToast('Error deleting model', 'error');
      }
    } catch (error) {
      console.error('Error deleting model:', error);
    }
  };

  const fetchModelHistory = async () => {
    if (!user) return;
    setLoading(true);
    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session?.access_token) return;

      const response = await fetch(`${API_URL}/model-history/${model.id}`, {
        headers: { Authorization: `Bearer ${session.access_token}` }
      });
      const data = await response.json();
      setHistory(data.predictions || []);
    } catch (error) {
      console.error('Error fetching model history:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (user && model.id) {
      fetchModelHistory();
      // Initialize sliders with model weights
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
  }, [user, model.id]);

  if (!user) {
    return (
      <div className="page">
        <div className="empty-state">
          <h2>Please log in to view model history</h2>
        </div>
      </div>
    );
  }

  return (
    <div className="page">
      <div className="page-header" style={{ justifyContent: 'flex-start' }}>
        <button onClick={onBack} className="btn btn-outline">←</button>
        <h2>{model.modelName}</h2>
      </div>

      <div className="page-content">
        {sliders.length > 0 && (
          <div className="sliders-card" style={{ ...getModelStyle(model.tenDigit), marginBottom: '2rem' }}>
            <h2 style={{ borderBottom: `2px solid ${getModelColors(model.tenDigit).primary}`, paddingBottom: '0.5rem', marginBottom: '1rem', color: getModelColors(model.tenDigit).primary }}>Feature Configuration</h2>
            <div className="sliders-grid">
              <div className="slider-column">
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
        {loading ? (
          <div className="loading">Loading history...</div>
        ) : history.length === 0 ? (
          <div className="empty-state">
            <p>No betting history available for this model yet.</p>
          </div>
        ) : (
          <div className="history-table">
            <div className="table-header" style={{ display: 'grid', gridTemplateColumns: '1fr 3fr 1fr', gap: '1rem' }}>
              <div>Date</div>
              <div>Pick</div>
              <div>Units</div>
            </div>
            {history.map((entry, index) => (
              <div key={index} className="table-row" style={{ display: 'grid', gridTemplateColumns: '1fr 3fr 1fr', gap: '1rem', padding: '0.75rem', marginBottom: '0.5rem', borderRadius: '4px' }}>
                <div>{new Date(entry.date).toLocaleDateString()}</div>
                <div>{entry.teamPick} ({entry.price > 0 ? `+${entry.price}` : entry.price})</div>
                <div className={entry.result === 'w' ? 'positive' : entry.result === 'l' ? 'negative' : ''}>
                  {entry.result === 'w' ? '+' : entry.result === 'l' ? '-' : ''}{Math.abs(entry.unitsWon || 0).toFixed(2)}
                </div>
              </div>
            ))}
          </div>
        )}
        
        <div style={{ display: 'flex', justifyContent: 'center', marginTop: '2rem', paddingBottom: '2rem' }}>
          <button 
            onClick={() => setShowDeleteConfirm(true)}
            className="btn btn-outline"
            style={{ color: 'var(--danger)', borderColor: 'var(--danger)' }}
          >
            Delete Model
          </button>
        </div>
      </div>
      
      {showDeleteConfirm && (
        <div className="modal-overlay">
          <div className="modal" style={{ textAlign: 'center' }}>
            <h2>Delete Model</h2>
            <p>Are you sure you want to delete "{model.modelName}"? This action cannot be undone.</p>
            <div style={{ display: 'flex', gap: '1rem', marginTop: '1.5rem', justifyContent: 'center' }}>
              <button 
                className="btn btn-outline" 
                onClick={() => setShowDeleteConfirm(false)}
              >
                Cancel
              </button>
              <button 
                className="btn btn-primary" 
                style={{ background: 'var(--danger)', borderColor: 'var(--danger)' }}
                onClick={() => {
                  setShowDeleteConfirm(false);
                  handleDeleteModel();
                }}
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      )}
      
      <ToastContainer />
    </div>
  );
};

export default ModelHistoryPage;