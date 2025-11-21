import { createClient } from '@supabase/supabase-js';

const SUPABASE_URL = 'https://guohwckbrahxhmijawoh.supabase.co';
const SUPABASE_ANON_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imd1b2h3Y2ticmFoeGhtaWphd29oIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjI5MDIxOTYsImV4cCI6MjA3ODQ3ODE5Nn0.8RLb2465dlPO0vf3QRUwHKCzzBsAj3WDz5FDlQeJtqI';

export const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
  auth: {
    persistSession: true, // keeps user logged in in localStorage
  },
});
