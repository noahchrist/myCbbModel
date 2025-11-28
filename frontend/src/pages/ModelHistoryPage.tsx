import { useState, useEffect } from 'react';
import { User } from '@supabase/supabase-js';
import { supabase } from '../lib/supabaseClient';
import { toast, ToastContainer } from 'react-toastify';
import 'react-toastify/dist/ReactToastify.css';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

interface ModelHistoryProps {
  user: User | null;
  modelId: number;
  modelName: string;
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

const ModelHistoryPage = ({ user, modelId, modelName, onBack, onDelete }: ModelHistoryProps) => {
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

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

  const handleDeleteModel = async () => {
    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session?.access_token) return;

      const response = await fetch(`${API_URL}/delete-model/${modelId}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${session.access_token}` }
      });

      if (response.ok) {
        showToast('Model deleted successfully!', 'success');
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

      const response = await fetch(`${API_URL}/model-history/${modelId}`, {
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
    if (user && modelId) {
      fetchModelHistory();
    }
  }, [user, modelId]);

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
      <div className="page-header">
        <div>
          <button onClick={onBack} className="btn btn-outline">← Back to Models</button>
          <h1>{modelName} History</h1>
        </div>
        <button 
          onClick={() => setShowDeleteConfirm(true)}
          className="btn btn-outline"
          style={{ color: 'var(--danger)', borderColor: 'var(--danger)' }}
        >
          Delete Model
        </button>
      </div>

      <div className="page-content">
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
      </div>
      
      {showDeleteConfirm && (
        <div className="modal-overlay">
          <div className="modal" style={{ textAlign: 'center' }}>
            <h2>Delete Model</h2>
            <p>Are you sure you want to delete "{modelName}"? This action cannot be undone.</p>
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