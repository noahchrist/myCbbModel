import { useEffect } from 'react';
import { supabase } from '../lib/supabaseClient';

const VerifiedPage = () => {
  useEffect(() => {
    const handleVerification = async () => {
      // Sign out the user immediately
      await supabase.auth.signOut();
      
      // Redirect to home page after delay
      setTimeout(() => {
        window.location.href = '/';
      }, 4000);
    };
    
    handleVerification();
  }, []);

  return (
    <div className="app">
      <div style={{ 
        display: 'flex', 
        justifyContent: 'center', 
        alignItems: 'center', 
        height: '100vh',
        flexDirection: 'column',
        gap: '20px'
      }}>
        <h1>🎉 Email Verified!</h1>
        <p>Redirecting you to log in...</p>
      </div>

    </div>
  );
};

export default VerifiedPage;