-- Universal schema for MySQL and PostgreSQL
-- Compatible with both database systems

-- Users table
CREATE TABLE users (
    user_id UUID PRIMARY KEY,
    display_name VARCHAR(255),
    role VARCHAR(50) DEFAULT 'user',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Model names table (static lookup table)
CREATE TABLE model_names (
    model_name_id SERIAL PRIMARY KEY,
    model_name VARCHAR(255) UNIQUE NOT NULL,
    user_id UUID NULL, -- NULL when available, UUID when claimed by user
    times_rejected INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE SET NULL
);

-- Model details table
CREATE TABLE model_details (
    model_id SERIAL PRIMARY KEY,
    user_id UUID NOT NULL,
    model_name VARCHAR(255) NOT NULL,
    date_created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    model_seed INTEGER UNIQUE NOT NULL,
    betting_style VARCHAR(50),
    ten_digit INTEGER,
    model_path TEXT,
    weight_gen_off DECIMAL(5,3),
    weight_gen_def DECIMAL(5,3),
    weight_pace DECIMAL(5,3),
    weight_threes DECIMAL(5,3),
    weight_fts DECIMAL(5,3),
    weight_per_def DECIMAL(5,3),
    weight_int_def DECIMAL(5,3),
    weight_boards DECIMAL(5,3),
    weight_playmaking DECIMAL(5,3),
    weight_intangibles DECIMAL(5,3),
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- Games table
CREATE TABLE games (
    game_id SERIAL PRIMARY KEY,
    home_team VARCHAR(100) NOT NULL,
    away_team VARCHAR(100) NOT NULL,
    game_date DATE NOT NULL,
    commence_time TIMESTAMP,
    home_score INTEGER,
    away_score INTEGER,
    pt_diff DECIMAL(5,2),
    pt_total DECIMAL(5,2),
    fd_home_hh_price DECIMAL(6,2),
    fd_away_hh_price DECIMAL(6,2),
    fd_home_spread DECIMAL(4,1),
    fd_home_spread_price DECIMAL(6,2),
    fd_away_spread DECIMAL(4,1),
    fd_away_spread_price DECIMAL(6,2),
    fd_over DECIMAL(5,1),
    fd_over_price DECIMAL(6,2),
    fd_under DECIMAL(5,1),
    fd_under_price DECIMAL(6,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Model predictions table
CREATE TABLE model_predictions (
    prediction_id SERIAL PRIMARY KEY,
    model_id INTEGER NOT NULL,
    game_id INTEGER NOT NULL,
    date_predicted DATE NOT NULL,
    home_team VARCHAR(100) NOT NULL,
    away_team VARCHAR(100) NOT NULL,
    bet_type VARCHAR(20) NOT NULL,
    predicted_pt_diff DECIMAL(5,2),
    predicted_pt_total DECIMAL(5,2),
    fd_home_spread DECIMAL(4,1),
    fd_home_spread_price DECIMAL(6,2),
    fd_away_spread DECIMAL(4,1),
    fd_away_spread_price DECIMAL(6,2),
    fd_over DECIMAL(5,1),
    fd_over_price DECIMAL(6,2),
    fd_under DECIMAL(5,1),
    fd_under_price DECIMAL(6,2),
    units_bet DECIMAL(6,2),
    units_won DECIMAL(6,2),
    win_loss VARCHAR(1),
    is_completed BOOLEAN DEFAULT FALSE,
    summary TEXT,
    edge DECIMAL(5,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (model_id) REFERENCES model_details(model_id) ON DELETE CASCADE,
    FOREIGN KEY (game_id) REFERENCES games(game_id) ON DELETE CASCADE
);

-- Training data table
CREATE TABLE training_data (
    training_id SERIAL PRIMARY KEY,
    home_team_id INTEGER,
    away_team_id INTEGER,
    home_team VARCHAR(100) NOT NULL,
    away_team VARCHAR(100) NOT NULL,
    home_score INTEGER,
    away_score INTEGER,
    win_loss VARCHAR(1),
    pt_diff DECIMAL(5,2),
    pt_total DECIMAL(5,2),
    game_date DATE NOT NULL,
    season VARCHAR(10),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for performance
CREATE INDEX idx_games_date ON games(game_date);
CREATE INDEX idx_games_teams ON games(home_team, away_team);
CREATE INDEX idx_predictions_model ON model_predictions(model_id);
CREATE INDEX idx_predictions_date ON model_predictions(date_predicted);
CREATE INDEX idx_predictions_completed ON model_predictions(is_completed);
CREATE INDEX idx_model_details_user ON model_details(user_id);
CREATE INDEX idx_training_data_date ON training_data(game_date);
CREATE INDEX idx_training_data_season ON training_data(season);