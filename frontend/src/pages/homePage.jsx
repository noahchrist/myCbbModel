import { useState } from 'react';

const HomePage = () => {
  const [sliders, setSliders] = useState([
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

  const handleSliderChange = (id, newValue) => {
    setSliders(prev => prev.map(slider => 
      slider.id === id ? { ...slider, value: newValue } : slider
    ));
  };

  return (
    <div className="homepage">
      {/* Header */}
      <header className="header">
        <h1 className="title">weightroom.io</h1>
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
          <div style={{ display: 'flex', justifyContent: 'center', marginTop: '2rem' }}>
            <button>Train Model</button>
          </div>
        </div>
      </main>
    </div>
  );
};

export default HomePage;