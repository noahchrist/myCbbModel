import { useState, useEffect } from 'react';
import { User } from '@supabase/supabase-js';
import { supabase } from '../lib/supabaseClient';
import { toast, ToastContainer } from 'react-toastify';
import 'react-toastify/dist/ReactToastify.css';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

interface Slider {
  id: number;
  category: string;
  value: number;
}

interface CreateModelPageProps {
  user: User | null;
  onBack: () => void;
  onModelCreated: () => void;
}

const CreateModelPage = ({ user, onBack, onModelCreated }: CreateModelPageProps) => {
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
  const [modelNames, setModelNames] = useState<string[]>([]);
  const [selectedModelName, setSelectedModelName] = useState('');
  const [selectedBettingStyle, setSelectedBettingStyle] = useState('');
  const [isCreating, setIsCreating] = useState(false);

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

  const handleSliderChange = (id: number, newValue: number) => {
    setSliders(prev => prev.map(slider => 
      slider.id === id ? { ...slider, value: newValue } : slider
    ));
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

  const handleCreateModel = async () => {
    if (!selectedModelName || !selectedBettingStyle) return;
    
    setIsCreating(true);
    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session?.access_token) return;

      const tenDigitArray = sliders.map(s => s.value - 1);
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
        onModelCreated();
        onBack();
      } else {
        showToast('Error creating model', 'error');
      }
    } catch (error) {
      console.error('Error creating model:', error);
      showToast('Error creating model', 'error');
    } finally {
      setIsCreating(false);
    }
  };

  useEffect(() => {
    fetchModelNames();
  }, []);

  return (
    <div className="page">
      <div className="page-header">
        <button onClick={onBack} className="btn btn-outline">← Back to Models</button>
        <h1>Create New Model</h1>
      </div>

      <div className="page-content">
        <div className="create-model-grid">
          <div className="sliders-card">
            <h2>Model Configuration</h2>
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
                      onChange={(e) => handleSliderChange(slider.id, parseInt(e.target.value))}
                      className="slider"
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
                      onChange={(e) => handleSliderChange(slider.id, parseInt(e.target.value))}
                      className="slider"
                    />
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="model-options-card">
            <h2>Model Options</h2>
            
            <div className="form-section">
              <h3>Model Name</h3>
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
            
            <div className="form-section">
              <h3>Betting Style</h3>
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
              className="btn btn-primary full-width"
              disabled={!selectedModelName || !selectedBettingStyle || isCreating}
              onClick={handleCreateModel}
            >
              {isCreating ? 'Creating...' : 'Create Model'}
            </button>
          </div>
        </div>
      </div>

      {isCreating && (
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
      
      <ToastContainer />
    </div>
  );
};

export default CreateModelPage;