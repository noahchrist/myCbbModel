import { useState, useEffect } from 'react';
import { User } from '@supabase/supabase-js';
import { supabase } from './lib/supabaseClient';
import Layout from './components/Layout';
import GamesPage from './pages/GamesPage';
import ModelsPage from './pages/ModelsPage';
import CommunityPage from './pages/CommunityPage';
import AccountPage from './pages/AccountPage';
import VerifiedPage from './pages/VerifiedPage';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

type TabType = 'home' | 'models' | 'community' | 'account';

const App = () => {
  const [activeTab, setActiveTab] = useState<TabType>('home');
  const [user, setUser] = useState<User | null>(null);

  // Check if we're on the verification page
  const isVerificationPage = window.location.pathname === '/auth/verified';

  useEffect(() => {
    // Check for existing session
    supabase.auth.getSession().then(({ data: { session } }) => {
      setUser(session?.user ?? null);
    });

    // Listen for auth changes
    const { data: { subscription } } = supabase.auth.onAuthStateChange((event, session) => {
      setUser(session?.user ?? null);
    });

    return () => subscription.unsubscribe();
  }, []);

  const renderPage = () => {
    switch (activeTab) {
      case 'home':
        return <GamesPage />;
      case 'models':
        return <ModelsPage user={user} />;
      case 'community':
        return <CommunityPage />;
      case 'account':
        return <AccountPage user={user} onLogout={() => { setUser(null); setActiveTab('home'); }} />;
      default:
        return <GamesPage />;
    }
  };

  // Show verification page if on that route
  if (isVerificationPage) {
    return <VerifiedPage />;
  }

  return (
    <Layout 
      activeTab={activeTab} 
      setActiveTab={setActiveTab} 
      user={user} 
      setUser={setUser}
    >
      {renderPage()}
    </Layout>
  );
};

export default App;