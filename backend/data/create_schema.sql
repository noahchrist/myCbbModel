-- Create schema for myCbbModel database

-- Users table
CREATE TABLE users (
    id TEXT PRIMARY KEY,
    displayName TEXT,
    role TEXT DEFAULT 'user'
);

-- Model names table
CREATE TABLE modelNames (
    modelName TEXT PRIMARY KEY,
    userId TEXT,
    timesRejected INTEGER DEFAULT 0,
    FOREIGN KEY (userId) REFERENCES users(id)
);

-- Model details table
CREATE TABLE modelDetails (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    userId TEXT,
    modelName TEXT,
    dateCreated TEXT,
    modelSeed INTEGER UNIQUE,
    bettingStyle TEXT,
    tenDigit INTEGER,
    modelPath TEXT,
    weightGenOff REAL,
    weightGenDef REAL,
    weightPace REAL,
    weightThrees REAL,
    weightFts REAL,
    weightPerDef REAL,
    weightIntDef REAL,
    weightBoards REAL,
    weightPlaymaking REAL,
    weightIntangibles REAL,
    FOREIGN KEY (userId) REFERENCES users(id)
);

-- Games table
CREATE TABLE games2026 (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    home_team TEXT,
    away_team TEXT,
    game_date TEXT,
    commence_time TEXT,
    home_score INTEGER,
    away_score INTEGER,
    pt_diff REAL,
    pt_total REAL,
    fd_home_hhPrice REAL,
    fd_away_hhPrice REAL,
    fd_home_spread REAL,
    fd_home_spreadPrice REAL,
    fd_away_spread REAL,
    fd_away_spreadPrice REAL,
    fd_over REAL,
    fd_overPrice REAL,
    fd_under REAL,
    fd_underPrice REAL
);

-- Model predictions table
CREATE TABLE modelPredictions (
    predictionId INTEGER PRIMARY KEY AUTOINCREMENT,
    modelId INTEGER,
    game_id INTEGER,
    datePredicted TEXT,
    home_team TEXT,
    away_team TEXT,
    bet_type TEXT,
    predicted_pt_diff REAL,
    predicted_pt_total REAL,
    fd_home_spread REAL,
    fd_home_spreadPrice REAL,
    fd_away_spread REAL,
    fd_away_spreadPrice REAL,
    fd_over REAL,
    fd_overPrice REAL,
    fd_under REAL,
    fd_underPrice REAL,
    unitsBet REAL,
    unitsWon REAL,
    w_l TEXT,
    is_completed INTEGER DEFAULT 0,
    summary TEXT,
    edge REAL,
    FOREIGN KEY (modelId) REFERENCES modelDetails(id)
);

-- Training data table
CREATE TABLE setAlpha (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    home_id INTEGER,
    away_id INTEGER,
    home_team TEXT,
    away_team TEXT,
    home_score INTEGER,
    away_score INTEGER,
    win_loss TEXT,
    pt_diff REAL,
    pt_total REAL,
    date TEXT,
    season TEXT
    -- Additional feature columns would be added here based on the actual training data
);

-- Create indexes for better performance
CREATE INDEX idx_games_date ON games2026(game_date);
CREATE INDEX idx_predictions_model ON modelPredictions(modelId);
CREATE INDEX idx_predictions_date ON modelPredictions(datePredicted);
CREATE INDEX idx_model_details_user ON modelDetails(userId);