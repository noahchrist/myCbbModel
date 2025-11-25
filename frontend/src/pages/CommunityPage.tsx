import { useState, useEffect } from 'react';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

interface CommunityModel {
  id: number;
  modelName: string;
  userName: string;
  bettingStyle: string;
  tenDigit: number;
  wins: number;
  losses: number;
  unitsWon: number;
  roi: number;
}

interface Bet {
  gameId: string;
  pick: string;
  unitsBet: number;
  homeTeam: string;
  awayTeam: string;
  prices: {
    homeSpread: number;
    awaySpread: number;
    over: number;
    under: number;
  };
}

interface TopPick {
  pick: string;
  totalUnits: number;
  price: number;
}

interface PickData {
  totalUnits: number;
  price: number;
}

const CommunityPage = () => {
  const [communityModels, setCommunityModels] = useState<CommunityModel[]>([]);
  const [topPicks, setTopPicks] = useState<TopPick[]>([]);
  const [loading, setLoading] = useState(true);

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
      background: `linear-gradient(135deg, ${colors.primary}40, ${colors.secondary}40), var(--background)`,
      backgroundColor: 'var(--background)',
      border: `4px solid ${colors.primary}`,
      boxShadow: `0 8px 16px ${colors.secondary}70, inset 0 1px 0 ${colors.primary}30`,
      colors
    };
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

  const fetchTopPicks = async () => {
    try {
      const response = await fetch(`${API_URL}/todays-top-picks`);
      const data = await response.json();
      const bets: Bet[] = data.bets || [];
      
      // Aggregate bets by pick
      const pickMap = new Map<string, PickData>();
      
      bets.forEach(bet => {
        if (bet.pick) {
          const existing = pickMap.get(bet.pick);
          if (existing) {
            existing.totalUnits += bet.unitsBet;
          } else {
            // Format pick with team names for totals and determine price
            let formattedPick = bet.pick;
            let price = 0;
            
            if (bet.pick.includes('Over') || bet.pick.includes('Under')) {
              formattedPick = `${bet.homeTeam} vs ${bet.awayTeam} ${bet.pick}`;
              price = bet.pick.includes('Over') ? bet.prices.over : bet.prices.under;
            } else {
              // Spread bet
              price = bet.prices.homeSpread || bet.prices.awaySpread;
            }
            
            pickMap.set(formattedPick, {
              totalUnits: bet.unitsBet,
              price: price
            });
          }
        }
      });
      
      // Convert to array and sort by total units
      const aggregatedPicks = Array.from(pickMap.entries())
        .map(([pick, data]) => ({
          pick,
          totalUnits: data.totalUnits,
          price: data.price
        }))
        .sort((a, b) => b.totalUnits - a.totalUnits)
        .slice(0, 5);
      
      setTopPicks(aggregatedPicks);
    } catch (error) {
      console.error('Error fetching top picks:', error);
    }
  };

  useEffect(() => {
    const fetchData = async () => {
      await Promise.all([fetchCommunityModels(), fetchTopPicks()]);
      setLoading(false);
    };
    fetchData();
  }, []);

  return (
    <div className="page">
      <div className="page-content">
        <div className="top-picks-section">
          <h2>Today's Top Picks</h2>
          {loading ? (
            <div className="loading">Loading picks...</div>
          ) : topPicks.length === 0 ? (
            <div className="empty-state">No picks available for today</div>
          ) : (
            <div className="picks-list">
              {topPicks.map((pick, index) => (
                <div key={index} className="pick-row">
                  <div className="pick-info">
                    <span className="pick-name">{pick.pick}</span>
                    <span className="pick-price">({pick.price > 0 ? '+' : ''}{pick.price})</span>
                  </div>
                  <div className="pick-units">{pick.totalUnits} units</div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="community-models-section">
          <h2>Community Models</h2>
          {loading ? (
            <div className="loading">Loading community models...</div>
          ) : communityModels.length === 0 ? (
            <div className="empty-state">No community models available</div>
          ) : (
            <div className="models-grid">
              {communityModels.map((model, index) => {
                const modelStyle = getModelStyle(model.tenDigit);
                return (
                  <div key={index} className="model-card community" style={modelStyle}>
                    <h3 className="model-name" style={{ color: modelStyle.colors.primary }}>{model.modelName}</h3>
                    <div className="model-creator" style={{ color: modelStyle.colors.secondary }}>by {model.userName}</div>
                    <div className="model-stats">
                      <div className="stat">
                        <span className="stat-label" style={{ color: modelStyle.colors.secondary }}>Style</span>
                        <span className="stat-value" style={{ color: modelStyle.colors.primary }}>{model.bettingStyle}</span>
                      </div>
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
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default CommunityPage;