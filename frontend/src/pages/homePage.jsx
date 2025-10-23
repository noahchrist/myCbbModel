import { useState } from 'react';

const HomePage = () => {
  const [sliders, setSliders] = useState([
    { id: 1, category: 'Offensive Rating', value: 5 },
    { id: 2, category: 'Defensive Rating', value: 5 },
    { id: 3, category: 'Pace', value: 5 },
    { id: 4, category: 'Rebounding', value: 5 },
    { id: 5, category: 'Turnovers', value: 5 },
    { id: 6, category: 'Free Throw Rate', value: 5 },
    { id: 7, category: 'Three Point %', value: 5 },
    { id: 8, category: 'Experience', value: 5 },
    { id: 9, category: 'Strength of Schedule', value: 5 },
    { id: 10, category: 'Home Court Advantage', value: 5 }
  ]);

  const handleSliderChange = (id, newValue) => {
    setSliders(prev => prev.map(slider => 
      slider.id === id ? { ...slider, value: newValue } : slider
    ));
  };

  return (
    <div className="homepage">
      {/* Header */}
      <header className="header">
        <h1 className="title">myCbbModel</h1>
        <div className="auth-section">
          <span>Sign In / Register</span>
        </div>
      </header>

      {/* Navigation */}
      <nav className="navigation">
        <button className="nav-button active">Home</button>
        <button className="nav-button">My Models</button>
        <button className="nav-button">Community</button>
        <button className="nav-button">Data Explorer</button>
      </nav>

      {/* Main Content */}
      <main className="main-content">
        <div className="sliders-container">
          {sliders.map(slider => (
            <div key={slider.id} className="slider-row">
              <div className="slider-category">{slider.category}</div>
              <div className="slider-wrapper">
                <input
                  type="range"
                  min="0"
                  max="10"
                  step="1"
                  value={slider.value}
                  onChange={(e) => handleSliderChange(slider.id, parseInt(e.target.value))}
                  className="slider"
                />
              </div>
              <div className="slider-percentage">{slider.value}</div>
            </div>
          ))}
        </div>
      </main>
    </div>
  );
};

export default HomePage;