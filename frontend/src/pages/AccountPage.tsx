import { User } from '@supabase/supabase-js';

interface AccountPageProps {
  user: User | null;
}

const AccountPage = ({ user }: AccountPageProps) => {
  return (
    <div className="page">
      <div className="page-header">
        <h1>Account</h1>
      </div>

      <div className="page-content">
        <div className="account-info">
          <h2>Welcome, {user?.user_metadata?.display_name || user?.email}</h2>
          <p>Profile settings and preferences coming soon...</p>
        </div>
      </div>
    </div>
  );
};

export default AccountPage;