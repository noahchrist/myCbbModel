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
  unitsBet: number;
  unitsWon: number;
  roi: number;
}

interface Bet {
  gameId: string;
  pick: string;
  edge: number;
  homeTeam: string;
  awayTeam: string;
  wl: string | null;
  modelId: number;
  prices: {
    homeSpread: number;
    awaySpread: number;
    over: number;
    under: number;
  };
}

interface TopPick {
  pick: string;
  totalEdge: number;
  modelCount: number;
  price: number;
  result: string | null;
}

interface PickData {
  totalEdge: number;
  modelCount: number;
  price: number;
  result: string | null;
}

const CommunityPage = () => {
  const [communityModels, setCommunityModels] = useState<CommunityModel[]>([]);
  const [topPicks, setTopPicks] = useState<TopPick[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedDate, setSelectedDate] = useState(() => {
    const now = new Date();
    const estDate = new Date(now.toLocaleString("en-US", {timeZone: "America/New_York"}));
    const year = estDate.getFullYear();
    const month = String(estDate.getMonth() + 1).padStart(2, '0');
    const day = String(estDate.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
  });
  const [collapsedCards, setCollapsedCards] = useState<Set<number>>(new Set());
  const [isMobile, setIsMobile] = useState(window.innerWidth <= 768);
  const [topPicksPerformance, setTopPicksPerformance] = useState({
    record: '0-0',
    unitsBet: '0',
    unitsWon: '0',
    roi: '0%'
  });
  const [showTooltip, setShowTooltip] = useState(false);

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

  const getCardsPerRow = () => {
    const containerWidth = window.innerWidth - 48; // Account for padding
    const cardMinWidth = 280;
    const gap = 24; // 1.5rem gap
    return Math.floor((containerWidth + gap) / (cardMinWidth + gap)) || 1;
  };

  const fetchCommunityModels = async () => {
    try {
      const response = await fetch(`${API_URL}/community-models`);
      const data = await response.json();
      setCommunityModels(data.models || []);
      // Initialize collapsed state - collapse all except top row
      const cardsPerRow = getCardsPerRow();
      const initialCollapsed = new Set<number>();
      data.models?.forEach((model: CommunityModel, index: number) => {
        if (index >= cardsPerRow) initialCollapsed.add(index);
      });
      setCollapsedCards(initialCollapsed);
    } catch (error) {
      console.error('Error fetching community models:', error);
    }
  };

  const fetchTopPicks = async (date: string) => {
    try {
      const response = await fetch(`${API_URL}/todays-top-picks?date=${date}`);
      const data = await response.json();
      const bets: Bet[] = data.bets || [];
      
      // Get unique model count
      const uniqueModelIds = new Set(bets.map(bet => bet.modelId));
      const totalModelCount = uniqueModelIds.size;
      
      // Aggregate bets by unique pick (gameId + pick combination)
      const pickMap = new Map<string, PickData>();
      
      bets.forEach(bet => {
        if (bet.pick && bet.gameId) {
          // Create unique key combining gameId, pick, and result (w_l is same for all models)
          const uniqueKey = `${bet.gameId}:${bet.pick}:${bet.wl || 'pending'}`;
          
          // Format pick with team names for totals and determine price
          let formattedPick = bet.pick;
          let price = 0;
          
          if (bet.pick.includes('Over') || bet.pick.includes('Under')) {
            formattedPick = `${bet.homeTeam} vs ${bet.awayTeam} ${bet.pick}`;
            price = bet.pick.includes('Over') ? bet.prices.over : bet.prices.under;
          } else {
            // Spread bet - determine price based on which team is picked
            if (bet.pick.includes(bet.homeTeam)) {
              price = bet.prices.homeSpread;
            } else {
              price = bet.prices.awaySpread;
            }
          }
          
          const existing = pickMap.get(uniqueKey);
          if (existing) {
            // Same pick from multiple models - add edge and increment count
            existing.totalEdge += bet.edge;
            existing.modelCount += 1;
          } else {
            // New unique pick
            pickMap.set(uniqueKey, {
              totalEdge: bet.edge,
              modelCount: 1,
              price: price,
              result: bet.wl
            });
          }
        }
      });
      
      // Convert to array and sort by total edge
      const aggregatedPicks = Array.from(pickMap.entries())
        .map(([key, data]) => {
          const [gameId, pick] = key.split(':');
          
          // Format pick with team names for totals
          const bet = bets.find(b => b.gameId === gameId && b.pick === pick);
          const formattedPick = bet && (pick.includes('Over') || pick.includes('Under')) 
            ? `${bet.homeTeam} vs ${bet.awayTeam} ${pick}`
            : pick;
          
          return {
            pick: formattedPick,
            totalEdge: data.totalEdge / totalModelCount,
            modelCount: data.modelCount,
            price: data.price,
            result: data.result
          };
        })
        .filter(pick => pick.totalEdge >= 3.0)
        .sort((a, b) => b.totalEdge - a.totalEdge)
        .slice(0, 5);
      
      setTopPicks(aggregatedPicks);
    } catch (error) {
      console.error('Error fetching top picks:', error);
    }
  };
  
  const changeDate = (days: number) => {
    const newDate = new Date(selectedDate + 'T00:00:00');
    newDate.setDate(newDate.getDate() + days);
    const dateString = newDate.toISOString().split('T')[0];
    setSelectedDate(dateString);
  };
  
  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr + 'T00:00:00');
    return date.toLocaleDateString('en-US', { 
      weekday: 'long', 
      month: 'long', 
      day: 'numeric' 
    });
  };
  
  const getPickStyle = (result: string | null) => {
    if (result === 'w') {
      return {
        border: '2px solid #c8e6c9'
      };
    } else if (result === 'l') {
      return {
        border: '2px solid #e8b4b4'
      };
    }
    return {};
  };

  const toggleCardCollapse = (index: number) => {
    setCollapsedCards(prev => {
      const newSet = new Set(prev);
      if (newSet.has(index)) {
        newSet.delete(index);
      } else {
        newSet.add(index);
      }
      return newSet;
    });
  };

  const showAllCards = () => {
    setCollapsedCards(new Set());
  };

  const hideAllCards = () => {
    const allIndices = new Set(communityModels.map((_, index) => index));
    setCollapsedCards(allIndices);
  };

  const getAllModelsStats = () => {
    const totalWins = communityModels.reduce((sum, model) => sum + model.wins, 0);
    const totalLosses = communityModels.reduce((sum, model) => sum + model.losses, 0);
    const totalUnitsBet = communityModels.reduce((sum, model) => sum + model.unitsBet, 0);
    const totalUnitsWon = communityModels.reduce((sum, model) => sum + model.unitsWon, 0);
    const roi = totalUnitsBet > 0 ? (totalUnitsWon / totalUnitsBet * 100) : 0;
    
    return {
      record: `${totalWins}-${totalLosses}`,
      unitsBet: totalUnitsBet.toFixed(2),
      unitsWon: totalUnitsWon > 0 ? `+${totalUnitsWon.toFixed(2)}` : totalUnitsWon.toFixed(2),
      roi: `${roi.toFixed(1)}%`
    };
  };

  const fetchTopPicksPerformance = async () => {
    try {
      const response = await fetch(`${API_URL}/top-picks-performance`);
      const data = await response.json();
      setTopPicksPerformance({
        record: data.record || '0-0',
        unitsBet: (data.unitsBet || 0).toString(),
        unitsWon: data.unitsWon > 0 ? `+${data.unitsWon || 0}` : (data.unitsWon || 0).toString(),
        roi: `${data.roi || 0}%`
      });
    } catch (error) {
      console.error('Error fetching top picks performance:', error);
    }
  };

  useEffect(() => {
    const fetchData = async () => {
      await Promise.all([fetchCommunityModels(), fetchTopPicks(selectedDate), fetchTopPicksPerformance()]);
      setLoading(false);
    };
    fetchData();
  }, [selectedDate]);

  useEffect(() => {
    const handleResize = () => {
      setIsMobile(window.innerWidth <= 768);
    };
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  return (
    <div className="page">
      <div className="page-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', position: 'relative' }}>
          <h2>Top Picks</h2>
          <span 
            className="tooltip-trigger"
            onMouseEnter={() => setShowTooltip(true)}
            onMouseLeave={() => setShowTooltip(false)}
            onClick={() => setShowTooltip(!showTooltip)}
          >
            ?
          </span>
          {showTooltip && (
            <div className="tooltip">
              A summary of the top picks based on the predictions of all community models (CE = Composite Edge)
            </div>
          )}
        </div>
        <div className="date-nav">
          <button onClick={() => changeDate(-1)} className="btn btn-outline">←</button>
          <span className="selected-date">{formatDate(selectedDate)}</span>
          <button onClick={() => changeDate(1)} className="btn btn-outline">→</button>
        </div>
      </div>
      
      <div className="page-content">
        <div className="top-picks-section">
          {loading ? (
            <div className="loading">Loading picks...</div>
          ) : topPicks.length === 0 ? (
            <div className="empty-state">No picks available for {formatDate(selectedDate)}</div>
          ) : (
            <div className="picks-list">
              {topPicks.map((pick, index) => (
                <div key={index} className="pick-row" style={getPickStyle(pick.result)}>
                  <div className="pick-info">
                    <span className="pick-name">{pick.pick} ({pick.price > 0 ? '+' : ''}{pick.price})</span>
                  </div>
                  <div className="pick-edge">{pick.totalEdge.toFixed(1)} CE</div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="community-performance-section">
          <div className="page-header">
            <h2>Community Performance</h2>
          </div>
          <div className="models-grid">
            <div className="model-card community performance" style={{ cursor: 'default' }}>
              <h3 className="model-name">Top Picks</h3>
              <div className="model-creator">🏋️ weightroom.io</div>
              <div className="model-stats">
                <div className="stat">
                  <span className="stat-label">Record</span>
                  <span className="stat-value">{topPicksPerformance.record}</span>
                </div>
                <div className="stat">
                  <span className="stat-label">Units Bet</span>
                  <span className="stat-value">{topPicksPerformance.unitsBet}</span>
                </div>
                <div className="stat">
                  <span className="stat-label">Units Won</span>
                  <span className="stat-value">{topPicksPerformance.unitsWon}</span>
                </div>
                <div className="stat">
                  <span className="stat-label">ROI</span>
                  <span className="stat-value">{topPicksPerformance.roi}</span>
                </div>
              </div>
            </div>
            <div className="model-card community performance" style={{ cursor: 'default' }}>
              <h3 className="model-name">All Models</h3>
              <div className="model-creator">🏋️ weightroom.io</div>
              <div className="model-stats">
                <div className="stat">
                  <span className="stat-label">Record</span>
                  <span className="stat-value">{getAllModelsStats().record}</span>
                </div>
                <div className="stat">
                  <span className="stat-label">Units Bet</span>
                  <span className="stat-value">{getAllModelsStats().unitsBet}</span>
                </div>
                <div className="stat">
                  <span className="stat-label">Units Won</span>
                  <span className="stat-value">{getAllModelsStats().unitsWon}</span>
                </div>
                <div className="stat">
                  <span className="stat-label">ROI</span>
                  <span className="stat-value">{getAllModelsStats().roi}</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div className="community-models-section">
          {isMobile ? (
            <>
              <h2 style={{ textAlign: 'center', marginBottom: '1rem' }}>Community Models</h2>
              <div style={{ display: 'flex', gap: '0.5rem', fontSize: '0.9rem', justifyContent: 'center', marginBottom: '1.5rem' }}>
                <span onClick={showAllCards} style={{ cursor: 'pointer', color: 'var(--primary)' }}>Show All</span>
                <span>/</span>
                <span onClick={hideAllCards} style={{ cursor: 'pointer', color: 'var(--primary)' }}>Hide All</span>
              </div>
            </>
          ) : (
            <div className="page-header">
              <h2>Community Models</h2>
              <div style={{ display: 'flex', gap: '0.5rem', fontSize: '0.9rem' }}>
                <span onClick={showAllCards} style={{ cursor: 'pointer', color: 'var(--primary)' }}>Show All</span>
                <span>/</span>
                <span onClick={hideAllCards} style={{ cursor: 'pointer', color: 'var(--primary)' }}>Hide All</span>
              </div>
            </div>
          )}
          {loading ? (
            <div className="loading">Loading community models...</div>
          ) : communityModels.length === 0 ? (
            <div className="empty-state">No community models available</div>
          ) : (
            <div className="models-grid">
              {communityModels.map((model, index) => {
                const modelStyle = getModelStyle(model.tenDigit);
                const isCollapsed = collapsedCards.has(index);
                return (
                  <div 
                    key={index} 
                    className={`model-card community ${isCollapsed ? 'collapsed' : ''}`} 
                    style={{
                      ...modelStyle,
                      alignSelf: isCollapsed ? 'start' : 'stretch'
                    }}
                    onClick={() => toggleCardCollapse(index)}
                  >
                    <h3 className="model-name" style={{ color: modelStyle.colors.primary, fontSize: '1.5rem', marginBottom: '0.1rem' }}>{model.modelName}</h3>
                    <div className="model-creator" style={{ color: modelStyle.colors.secondary, textAlign: 'center' }}>{model.userName}</div>
                    <div className="model-stats">
                      <div className="stat">
                        <span className="stat-label" style={{ color: modelStyle.colors.primary }}>Record</span>
                        <span className="stat-value" style={{ color: modelStyle.colors.secondary }}>{model.wins}-{model.losses}</span>
                      </div>
                      {!isCollapsed && (
                        <>
                          <div className="stat">
                            <span className="stat-label" style={{ color: modelStyle.colors.primary }}>Style</span>
                            <span className="stat-value" style={{ color: modelStyle.colors.secondary }}>{model.bettingStyle}</span>
                          </div>
                          <div className="stat">
                            <span className="stat-label" style={{ color: modelStyle.colors.primary }}>Units Bet</span>
                            <span className="stat-value" style={{ color: modelStyle.colors.secondary }}>{model.unitsBet}</span>
                          </div>
                          <div className="stat">
                            <span className="stat-label" style={{ color: modelStyle.colors.primary }}>Units Won</span>
                            <span className="stat-value" style={{ color: modelStyle.colors.secondary }}>{model.unitsWon > 0 ? '+' : ''}{model.unitsWon}</span>
                          </div>
                          <div className="stat">
                            <span className="stat-label" style={{ color: modelStyle.colors.primary }}>ROI</span>
                            <span className="stat-value" style={{ color: modelStyle.colors.secondary }}>{model.roi}%</span>
                          </div>
                        </>
                      )}
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