import { useState, useEffect } from 'react';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

interface Game {
  home_team: string;
  away_team: string;
  commence_time: string;
  home_score: number | null;
  away_score: number | null;
  fd_home_hhPrice: number;
  fd_away_hhPrice: number;
  fd_home_spread: number;
  fd_away_spread: number;
  fd_home_spreadPrice: number;
  fd_away_spreadPrice: number;
  fd_over: number;
  fd_under: number;
  fd_overPrice: number;
  fd_underPrice: number;
}

const GamesPage = () => {
  const [currentDate, setCurrentDate] = useState(() => {
    const today = new Date();
    return today.toISOString().split('T')[0];
  });
  const [games, setGames] = useState<Game[]>([]);
  const [loading, setLoading] = useState(false);

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
    const newDate = new Date(currentDate);
    newDate.setDate(newDate.getDate() + days);
    const dateString = newDate.toISOString().split('T')[0];
    setCurrentDate(dateString);
  };

  const formatTime = (timeString: string | null) => {
    if (!timeString) return 'TBD';
    const date = new Date(timeString);
    return date.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
  };

  const formatOdds = (odds: number | null) => {
    if (!odds) return 'N/A';
    return odds > 0 ? `+${odds}` : `${odds}`;
  };

  const isGameCompleted = (game: Game) => {
    return game.home_score !== null && game.away_score !== null;
  };

  const getBettingResults = (game: Game) => {
    if (!isGameCompleted(game)) return {};
    
    const homeWon = game.home_score! > game.away_score!;
    const pointDiff = game.home_score! - game.away_score!;
    const totalPoints = game.home_score! + game.away_score!;
    
    return {
      moneyline: { homeWins: homeWon, awayWins: !homeWon },
      spread: {
        homeWins: pointDiff + (game.fd_home_spread || 0) > 0,
        awayWins: pointDiff + (game.fd_away_spread || 0) < 0
      },
      total: {
        overWins: totalPoints > (game.fd_over || 0),
        underWins: totalPoints < (game.fd_under || 0)
      }
    };
  };

  useEffect(() => {
    fetchGames(currentDate);
  }, [currentDate]);

  return (
    <div className="page">
      <div className="page-header">
        <div className="date-nav">
          <button onClick={() => changeDate(-1)} className="btn btn-outline">←</button>
          <h2 className="date-title">
            {new Date(currentDate + 'T00:00:00').toLocaleDateString('en-US', { 
              weekday: 'long', 
              month: 'long', 
              day: 'numeric' 
            })}
          </h2>
          <button onClick={() => changeDate(1)} className="btn btn-outline">→</button>
        </div>
      </div>
      
      <div className="page-content">
        {loading ? (
          <div className="loading">Loading games...</div>
        ) : games.length === 0 ? (
          <div className="empty-state">No games scheduled for this date</div>
        ) : (
          <div className="games-by-time">
            {Object.entries(
              games.reduce((acc, game) => {
                const time = formatTime(game.commence_time);
                if (!acc[time]) acc[time] = [];
                acc[time].push(game);
                return acc;
              }, {} as Record<string, Game[]>)
            ).map(([time, timeGames]) => (
              <div key={time} className="time-group">
                <div className="time-header">{time}</div>
                <div className="games-row">
                  {timeGames.map((game, index) => (
                    <div key={index} className="game-card">
                <div className="game-header">
                  <div className="game-status">
                    {game.home_score !== null ? 'Final' : 'Scheduled'}
                  </div>
                </div>
                
                <div className="game-odds">
                  <div className="odds-header"></div>
                  <div className="odds-header">Moneyline</div>
                  <div className="odds-header">Spread</div>
                  <div className="odds-header">Total</div>
                  
                  <div className={`odds-team-label ${isGameCompleted(game) && getBettingResults(game).moneyline?.awayWins ? 'winner' : ''}`}>
                    {game.away_team} {game.away_score !== null ? `(${game.away_score})` : ''}
                  </div>
                  <div className={`odds-cell ${isGameCompleted(game) && getBettingResults(game).moneyline?.awayWins ? 'winning-bet' : ''}`}>
                    {formatOdds(game.fd_away_hhPrice)}
                  </div>
                  <div className={`odds-cell ${isGameCompleted(game) && getBettingResults(game).spread?.awayWins ? 'winning-bet' : ''}`}>
                    {game.fd_away_spread ? `${game.fd_away_spread > 0 ? '+' : ''}${game.fd_away_spread}` : 'N/A'}
                    <br/><small>({formatOdds(game.fd_away_spreadPrice)})</small>
                  </div>
                  <div className={`odds-cell ${isGameCompleted(game) && getBettingResults(game).total?.overWins ? 'winning-bet' : ''}`}>
                    O{game.fd_over || 'N/A'}
                    <br/><small>({formatOdds(game.fd_overPrice)})</small>
                  </div>
                  
                  <div className={`odds-team-label ${isGameCompleted(game) && getBettingResults(game).moneyline?.homeWins ? 'winner' : ''}`}>
                    {game.home_team} {game.home_score !== null ? `(${game.home_score})` : ''}
                  </div>
                  <div className={`odds-cell ${isGameCompleted(game) && getBettingResults(game).moneyline?.homeWins ? 'winning-bet' : ''}`}>
                    {formatOdds(game.fd_home_hhPrice)}
                  </div>
                  <div className={`odds-cell ${isGameCompleted(game) && getBettingResults(game).spread?.homeWins ? 'winning-bet' : ''}`}>
                    {game.fd_home_spread ? `${game.fd_home_spread > 0 ? '+' : ''}${game.fd_home_spread}` : 'N/A'}
                    <br/><small>({formatOdds(game.fd_home_spreadPrice)})</small>
                  </div>
                  <div className={`odds-cell ${isGameCompleted(game) && getBettingResults(game).total?.underWins ? 'winning-bet' : ''}`}>
                    U{game.fd_under || 'N/A'}
                    <br/><small>({formatOdds(game.fd_underPrice)})</small>
                  </div>
                </div>
              </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default GamesPage;