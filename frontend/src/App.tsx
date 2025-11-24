import { useState, useEffect } from 'react';
import { User } from '@supabase/supabase-js';
import { supabase } from './lib/supabaseClient';
import Layout from './components/Layout';
import GamesPage from './pages/GamesPage';
import ModelsPage from './pages/ModelsPage';
import CommunityPage from './pages/CommunityPage';
import AccountPage from './pages/AccountPage';

type TabType = 'home' | 'models' | 'community' | 'account';

const App = () => {
  const [activeTab, setActiveTab] = useState<TabType>('home');
  const [user, setUser] = useState<User | null>(null);

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
        return <AccountPage user={user} />;
      default:
        return <GamesPage />;
    }
  };

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