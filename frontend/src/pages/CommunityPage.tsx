import { useState, useEffect } from 'react';
import { LineChart, Line, XAxis, YAxis, Tooltip, ReferenceLine, ResponsiveContainer } from 'recharts';

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

interface PerformanceBox {
  wins: number;
  losses: number;
  unitsBet: string;
  unitsWon: string;
  roi: string;
}

interface SeasonSummary {
  overall: { wins: number; losses: number; unitsBet: number; unitsWon: number; roi: number };
  byType: { spread: { wins: number; losses: number }; total: { wins: number; losses: number } };
  byFavDog: { fav: { wins: number; losses: number }; dog: { wins: number; losses: number } };
  byOverUnder: { over: { wins: number; losses: number }; under: { wins: number; losses: number } };
  timeSeries: { date: string; cumulativeUnitsWon: number }[];
}

const defaultPerf: PerformanceBox = { wins: 0, losses: 0, unitsBet: '0', unitsWon: '0', roi: '0%' };

const formatRecord = (wins: number, losses: number) => {
  const total = wins + losses;
  const pct = total > 0 ? (wins / total * 100).toFixed(1) : '0.0';
  return `${wins}-${losses} (${pct}%)`;
};

const CommunityPage = () => {
  const [communityModels, setCommunityModels] = useState<CommunityModel[]>([]);
  const [loading, setLoading] = useState(true);
  const [isMobile, setIsMobile] = useState(window.innerWidth <= 768);
  const [seasonSummary, setSeasonSummary] = useState<SeasonSummary | null>(null);
  const [topPicksPerf, setTopPicksPerf] = useState<PerformanceBox>(defaultPerf);
  const [allModelsPerf, setAllModelsPerf] = useState<PerformanceBox>(defaultPerf);

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
      const activeModels = (data.models || []).filter((model: CommunityModel) => model.isActive);
      setCommunityModels(activeModels);
    } catch (error) {
      console.error('Error fetching community models:', error);
    }
  };

  const fetchSeasonSummary = async () => {
    try {
      const response = await fetch(`${API_URL}/season-summary`);
      const data = await response.json();
      // Fill all calendar dates so chart spacing is even (carry cumulative forward on no-game days)
      if (data.timeSeries) {
        const map = new Map<string, number>(data.timeSeries.map((d: { date: string; cumulativeUnitsWon: number }) => [d.date, d.cumulativeUnitsWon]));
        const filled: { date: string; cumulativeUnitsWon: number }[] = [];
        const cur = new Date('2025-12-02T00:00:00Z');
        const end = new Date('2026-03-10T00:00:00Z');
        let lastVal = 0;
        while (cur <= end) {
          const dateStr = cur.toISOString().slice(0, 10);
          if (map.has(dateStr)) lastVal = map.get(dateStr)!;
          filled.push({ date: dateStr, cumulativeUnitsWon: lastVal });
          cur.setUTCDate(cur.getUTCDate() + 1);
        }
        data.timeSeries = filled;
      }
      setSeasonSummary(data);
    } catch (error) {
      console.error('Error fetching season summary:', error);
    }
  };

  const fetchTopPicksPerformance = async () => {
    try {
      const response = await fetch(`${API_URL}/top-picks-performance`);
      const data = await response.json();
      const [w, l] = (data.record || '0-0').split('-').map(Number);
      setTopPicksPerf({
        wins: w || 0,
        losses: l || 0,
        unitsBet: (data.unitsBet || 0).toFixed(2),
        unitsWon: data.unitsWon > 0 ? `+${(data.unitsWon || 0).toFixed(2)}` : (data.unitsWon || 0).toFixed(2),
        roi: `${(data.roi || 0).toFixed(1)}%`
      });
    } catch (error) {
      console.error('Error fetching top picks performance:', error);
    }
  };

  const fetchAllModelsPerformance = async () => {
    try {
      const response = await fetch(`${API_URL}/all-models-performance`);
      const data = await response.json();
      const [w, l] = (data.record || '0-0').split('-').map(Number);
      setAllModelsPerf({
        wins: w || 0,
        losses: l || 0,
        unitsBet: (data.unitsBet || 0).toFixed(2),
        unitsWon: data.unitsWon > 0 ? `+${(data.unitsWon || 0).toFixed(2)}` : (data.unitsWon || 0).toFixed(2),
        roi: `${(data.roi || 0).toFixed(1)}%`
      });
    } catch (error) {
      console.error('Error fetching all models performance:', error);
    }
  };

useEffect(() => {
    const fetchData = async () => {
      await Promise.all([
        fetchCommunityModels(),
        fetchSeasonSummary(),
        fetchTopPicksPerformance(),
        fetchAllModelsPerformance(),
      ]);
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

  const formatUnitsWon = (val: number) =>
    val > 0 ? `+${val.toFixed(2)}` : val.toFixed(2);

  return (
    <div className="page">
      <div className="page-header">
        <h2 style={{ justifyContent: isMobile ? 'center' : 'flex-start' }}>2025-2026 Season Summary</h2>
      </div>

      <div className="page-content">
        <div className="top-picks-section">
          {seasonSummary ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
              {/* Top Picks + Breakdown side by side */}
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '1rem' }}>
                {/* Top Picks box */}
                <div className="model-card community performance" style={{ cursor: 'default', flex: '1 1 220px' }}>
                  <h3 className="model-name">Top Picks</h3>
                  <div className="model-creator">🏋️ weightroom.io</div>
                  <div className="model-stats">
                    <div className="stat">
                      <span className="stat-label">Record</span>
                      <span className="stat-value">{formatRecord(topPicksPerf.wins, topPicksPerf.losses)}</span>
                    </div>
                    <div className="stat">
                      <span className="stat-label">Units Bet</span>
                      <span className="stat-value">{topPicksPerf.unitsBet}</span>
                    </div>
                    <div className="stat">
                      <span className="stat-label">Units Won</span>
                      <span className="stat-value">{topPicksPerf.unitsWon}</span>
                    </div>
                    <div className="stat">
                      <span className="stat-label">ROI</span>
                      <span className="stat-value">{topPicksPerf.roi}</span>
                    </div>
                  </div>
                </div>

                {/* Breakdown box */}
                <div className="model-card community performance" style={{ cursor: 'default', flex: '1 1 220px' }}>
                  <h3 className="model-name">Breakdown</h3>
                  <div className="model-creator">🏋️ weightroom.io</div>
                  <div className="model-stats">
                    <div className="stat">
                      <span className="stat-label">Spread</span>
                      <span className="stat-value">{formatRecord(seasonSummary.byType.spread.wins, seasonSummary.byType.spread.losses)}</span>
                    </div>
                    <div className="stat">
                      <span className="stat-label">Favorites</span>
                      <span className="stat-value">{formatRecord(seasonSummary.byFavDog.fav.wins, seasonSummary.byFavDog.fav.losses)}</span>
                    </div>
                    <div className="stat">
                      <span className="stat-label">Underdogs</span>
                      <span className="stat-value">{formatRecord(seasonSummary.byFavDog.dog.wins, seasonSummary.byFavDog.dog.losses)}</span>
                    </div>
                    <div className="stat">
                      <span className="stat-label">Totals</span>
                      <span className="stat-value">{formatRecord(seasonSummary.byType.total.wins, seasonSummary.byType.total.losses)}</span>
                    </div>
                    <div className="stat">
                      <span className="stat-label">Overs</span>
                      <span className="stat-value">{formatRecord(seasonSummary.byOverUnder.over.wins, seasonSummary.byOverUnder.over.losses)}</span>
                    </div>
                    <div className="stat">
                      <span className="stat-label">Unders</span>
                      <span className="stat-value">{formatRecord(seasonSummary.byOverUnder.under.wins, seasonSummary.byOverUnder.under.losses)}</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Cumulative units line chart */}
              {seasonSummary.timeSeries.length > 0 && (
                <div className="model-card community performance" style={{ cursor: 'default' }}>
                  <h3 className="model-name" style={{ textAlign: 'center' }}>Units Won</h3>
                  <div className="model-creator" style={{ textAlign: 'center', marginBottom: '0.75rem' }}>🏋️ weightroom.io</div>
                  <div style={{ width: '100%', height: 240 }}>
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={seasonSummary.timeSeries} margin={{ top: 8, right: 16, left: 0, bottom: 8 }}>
                        <XAxis
                          dataKey="date"
                          tick={{ fontSize: 11, fill: 'var(--text-secondary)' }}
                          tickFormatter={(val: string) => val.slice(5)}
                          ticks={(() => {
                            const ticks: string[] = [];
                            const current = new Date('2025-12-02T00:00:00Z');
                            const end = new Date('2026-03-10T00:00:00Z');
                            while (current <= end) {
                              ticks.push(current.toISOString().slice(0, 10));
                              current.setUTCDate(current.getUTCDate() + 7);
                            }
                            return ticks;
                          })()}
                        />
                        <YAxis
                          tick={{ fontSize: 11, fill: 'var(--text-secondary)' }}
                          tickFormatter={(val: number) => val.toFixed(1)}
                          width={48}
                        />
                        <Tooltip
                          formatter={(val: number) => [val.toFixed(2), 'Cumulative Units']}
                          labelFormatter={(label: string) => `Date: ${label}`}
                          contentStyle={{ background: 'var(--background)', border: '1px solid var(--border)', fontSize: 12 }}
                        />
                        <ReferenceLine y={0} stroke="var(--text-secondary)" strokeDasharray="4 2" />
                        <Line
                          type="monotone"
                          dataKey="cumulativeUnitsWon"
                          stroke="var(--primary)"
                          dot={false}
                          strokeWidth={2}
                        />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              )}
            </div>
          ) : (
            !loading && <div className="empty-state">No season data available</div>
          )}
        </div>

        <div className="community-models-section">
          {isMobile ? (
            <h2 style={{ textAlign: 'center', marginBottom: '1rem' }}>Community Models</h2>
          ) : (
            <div className="page-header">
              <h2>Community Models</h2>
            </div>
          )}
          {loading ? (
            <div className="loading">Loading community models...</div>
          ) : (
            <div className="models-grid">
              {/* All Models card — always first */}
              <div className="model-card community performance" style={{ cursor: 'default', alignSelf: 'stretch' }}>
                <h3 className="model-name" style={{ fontSize: '1.5rem', marginBottom: '0.1rem' }}>All Models</h3>
                <div className="model-creator" style={{ textAlign: 'center' }}>🏋️ weightroom.io</div>
                <div className="model-stats">
                  <div className="stat">
                    <span className="stat-label">Record</span>
                    <span className="stat-value">{formatRecord(allModelsPerf.wins, allModelsPerf.losses)}</span>
                  </div>
                  <div className="stat">
                    <span className="stat-label">Style</span>
                    <span className="stat-value">Aggregate</span>
                  </div>
                  <div className="stat">
                    <span className="stat-label">Units Bet</span>
                    <span className="stat-value">{allModelsPerf.unitsBet}</span>
                  </div>
                  <div className="stat">
                    <span className="stat-label">Units Won</span>
                    <span className="stat-value">{allModelsPerf.unitsWon}</span>
                  </div>
                  <div className="stat">
                    <span className="stat-label">ROI</span>
                    <span className="stat-value">{allModelsPerf.roi}</span>
                  </div>
                </div>
              </div>

              {communityModels.length === 0 ? (
                <div className="empty-state">No community models available</div>
              ) : (
                communityModels.map((model, index) => {
                  const modelStyle = getModelStyle(model.tenDigit);
                  return (
                    <div
                      key={index}
                      className="model-card community"
                      style={{ ...modelStyle, alignSelf: 'stretch' }}
                    >
                      <h3 className="model-name" style={{ color: modelStyle.colors.primary, fontSize: '1.5rem', marginBottom: '0.1rem' }}>{model.modelName}</h3>
                      <div className="model-creator" style={{ color: modelStyle.colors.secondary, textAlign: 'center' }}>{model.userName}</div>
                      <div className="model-stats">
                        <div className="stat">
                          <span className="stat-label" style={{ color: modelStyle.colors.primary }}>Record</span>
                          <span className="stat-value" style={{ color: modelStyle.colors.secondary }}>{formatRecord(model.wins, model.losses)}</span>
                        </div>
                        <div className="stat">
                          <span className="stat-label" style={{ color: modelStyle.colors.primary }}>Style</span>
                          <span className="stat-value" style={{ color: modelStyle.colors.secondary }}>{model.bettingStyle}</span>
                        </div>
                        <div className="stat">
                          <span className="stat-label" style={{ color: modelStyle.colors.primary }}>Units Bet</span>
                          <span className="stat-value" style={{ color: modelStyle.colors.secondary }}>{model.unitsBet.toFixed(2)}</span>
                        </div>
                        <div className="stat">
                          <span className="stat-label" style={{ color: modelStyle.colors.primary }}>Units Won</span>
                          <span className="stat-value" style={{ color: modelStyle.colors.secondary }}>{formatUnitsWon(model.unitsWon)}</span>
                        </div>
                        <div className="stat">
                          <span className="stat-label" style={{ color: modelStyle.colors.primary }}>ROI</span>
                          <span className="stat-value" style={{ color: modelStyle.colors.secondary }}>{model.roi.toFixed(1)}%</span>
                        </div>
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default CommunityPage;
