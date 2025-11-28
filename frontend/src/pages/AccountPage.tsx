import { User } from '@supabase/supabase-js';
import { supabase } from '../lib/supabaseClient';

interface AccountPageProps {
  user: User | null;
  onLogout: () => void;
}

const AccountPage = ({ user, onLogout }: AccountPageProps) => {
  const handleLogout = async () => {
    await supabase.auth.signOut();
    onLogout();
  };

  return (
    <div className="page">
      <div className="page-header">
        <h2>Account</h2>
      </div>

      <div className="page-content">
        <div className="account-info">
          <h2>Welcome, {user?.user_metadata?.display_name || user?.email}</h2>
          <p>Profile settings and preferences coming soon...</p>
        </div>
        
        <div style={{ marginTop: '2rem', paddingTop: '2rem', borderTop: '1px solid #333' }}>
          <button 
            onClick={handleLogout}
            className="btn btn-outline"
            style={{ color: 'var(--danger)', borderColor: 'var(--danger)' }}
          >
            Logout
          </button>
        </div>
      </div>
    </div>
  );
};

export default AccountPage;