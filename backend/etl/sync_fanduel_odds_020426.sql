-- Sync FanDuel odds from server (mastercopy020426.db) to Supabase
-- Run date: 2026-02-04
-- These are the odds that were used for server predictions this morning

--UPDATE games SET fd_home_spread = 9.5, fd_home_spread_price = -110, fd_away_spread = -9.5, fd_away_spread_price = -110, fd_over = 150.5, fd_over_price = -115, fd_under = 150.5, fd_under_price = -105 WHERE game_id = 'cb556896b94415ccf16e514243805e34';

--copy master.db to local
--run 1/2 to load games to supabase
--create sql statements to align odds from .db to supabase
--run query in supabase to match to top picks on site