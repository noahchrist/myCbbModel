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
  isActive: boolean;
}


const CommunityPage = () => {
  const [communityModels, setCommunityModels] = useState<CommunityModel[]>([]);
  const [loading, setLoading] = useState(true);
  const [collapsedCards, setCollapsedCards] = useState<Set<number>>(new Set());
  const [isMobile, setIsMobile] = useState(window.innerWidth <= 768);
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
      const activeModels = (data.models || []).filter((model: CommunityModel) => model.isActive);
      setCommunityModels(activeModels);
      const cardsPerRow = getCardsPerRow();
      const initialCollapsed = new Set<number>();
      activeModels.forEach((_: CommunityModel, index: number) => {
        if (index >= cardsPerRow) initialCollapsed.add(index);
      });
      setCollapsedCards(initialCollapsed);
    } catch (error) {
      console.error('Error fetching community models:', error);
    }
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


  /* END OF SEASON MAINTENANCE - disabled until data pipeline is fixed
  const fetchTopPicks = async (date: string) => {
    try {
      const response = await fetch(`${API_URL}/todays-top-picks?date=${date}`);
      const data = await response.json();
      const bets: Bet[] = data.bets || [];
      const uniqueModelIds = new Set(bets.map(bet => bet.modelId));
      const totalModelCount = uniqueModelIds.size;
      const pickMap = new Map<string, PickData>();
      bets.forEach(bet => {
        if (bet.pick && bet.gameId) {
          const uniqueKey = `${bet.gameId}:${bet.pick}:${bet.wl || 'pending'}`;
          let price = 0;
          if (bet.pick.includes('Over') || bet.pick.includes('Under')) {
            price = bet.pick.includes('Over') ? bet.prices.over : bet.prices.under;
          } else {
            price = bet.pick.includes(bet.homeTeam) ? bet.prices.homeSpread : bet.prices.awaySpread;
          }
          const existing = pickMap.get(uniqueKey);
          if (existing) {
            existing.totalEdge += bet.edge;
            existing.modelCount += 1;
          } else {
            pickMap.set(uniqueKey, { totalEdge: bet.edge, modelCount: 1, price, result: bet.wl });
          }
        }
      });
      const aggregatedPicks = Array.from(pickMap.entries())
        .map(([key, data]) => {
          const [gameId, pick] = key.split(':');
          const bet = bets.find(b => b.gameId === gameId && b.pick === pick);
          const formattedPick = bet && (pick.includes('Over') || pick.includes('Under'))
            ? `${bet.homeTeam} vs ${bet.awayTeam} ${pick}` : pick;
          return { pick: formattedPick, totalEdge: data.totalEdge / totalModelCount, modelCount: data.modelCount, price: data.price, result: data.result };
        })
        .filter(pick => pick.totalEdge >= 3.0)
        .sort((a, b) => b.totalEdge - a.totalEdge)
        .slice(0, 5);
      setTopPicks(aggregatedPicks);
    } catch (error) {
      console.error('Error fetching top picks:', error);
    }
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

  const getAllModelsStats = () => {
    const totalWins = allModelsData.reduce((sum, model) => sum + model.wins, 0);
    const totalLosses = allModelsData.reduce((sum, model) => sum + model.losses, 0);
    const totalUnitsBet = allModelsData.reduce((sum, model) => sum + model.unitsBet, 0);
    const totalUnitsWon = allModelsData.reduce((sum, model) => sum + model.unitsWon, 0);
    const roi = totalUnitsBet > 0 ? (totalUnitsWon / totalUnitsBet * 100) : 0;
    return {
      record: `${totalWins}-${totalLosses}`,
      unitsBet: totalUnitsBet.toFixed(2),
      unitsWon: totalUnitsWon > 0 ? `+${totalUnitsWon.toFixed(2)}` : totalUnitsWon.toFixed(2),
      roi: `${roi.toFixed(1)}%`
    };
  };
  */

  useEffect(() => {
    const fetchData = async () => {
      await fetchCommunityModels();
      setLoading(false);
    };
    fetchData();
  }, []);

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
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', position: 'relative', justifyContent: isMobile ? 'center' : 'flex-start' }}>
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
      </div>

      <div className="page-content">
        <div className="top-picks-section">
          <div className="empty-state">2025-2026 season stats coming soon</div>
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
                  <span className="stat-value">0-0</span>
                </div>
                <div className="stat">
                  <span className="stat-label">Units Bet</span>
                  <span className="stat-value">0</span>
                </div>
                <div className="stat">
                  <span className="stat-label">Units Won</span>
                  <span className="stat-value">0</span>
                </div>
                <div className="stat">
                  <span className="stat-label">ROI</span>
                  <span className="stat-value">0%</span>
                </div>
              </div>
            </div>
            <div className="model-card community performance" style={{ cursor: 'default' }}>
              <h3 className="model-name">All Models</h3>
              <div className="model-creator">🏋️ weightroom.io</div>
              <div className="model-stats">
                <div className="stat">
                  <span className="stat-label">Record</span>
                  <span className="stat-value">0-0</span>
                </div>
                <div className="stat">
                  <span className="stat-label">Units Bet</span>
                  <span className="stat-value">0</span>
                </div>
                <div className="stat">
                  <span className="stat-label">Units Won</span>
                  <span className="stat-value">0</span>
                </div>
                <div className="stat">
                  <span className="stat-label">ROI</span>
                  <span className="stat-value">0%</span>
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
                        <span className="stat-value" style={{ color: modelStyle.colors.secondary }}>0-0</span>
                      </div>
                      {!isCollapsed && (
                        <>
                          <div className="stat">
                            <span className="stat-label" style={{ color: modelStyle.colors.primary }}>Style</span>
                            <span className="stat-value" style={{ color: modelStyle.colors.secondary }}>{model.bettingStyle}</span>
                          </div>
                          <div className="stat">
                            <span className="stat-label" style={{ color: modelStyle.colors.primary }}>Units Bet</span>
                            <span className="stat-value" style={{ color: modelStyle.colors.secondary }}>0</span>
                          </div>
                          <div className="stat">
                            <span className="stat-label" style={{ color: modelStyle.colors.primary }}>Units Won</span>
                            <span className="stat-value" style={{ color: modelStyle.colors.secondary }}>0</span>
                          </div>
                          <div className="stat">
                            <span className="stat-label" style={{ color: modelStyle.colors.primary }}>ROI</span>
                            <span className="stat-value" style={{ color: modelStyle.colors.secondary }}>0%</span>
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