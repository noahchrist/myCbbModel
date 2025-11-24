import { useEffect } from 'react';
import { supabase } from '../lib/supabaseClient';
import { toast, ToastContainer } from 'react-toastify';
import 'react-toastify/dist/ReactToastify.css';

const VerifiedPage = () => {
  useEffect(() => {
    const handleVerification = async () => {
      // Sign out the user immediately
      await supabase.auth.signOut();
      
      // Show success message
      toast.success('Email verified! Log in to continue', {
        position: 'top-center',
        autoClose: 5000,
        hideProgressBar: true,
        closeOnClick: true,
        pauseOnHover: true,
        draggable: true,
        style: {
          backgroundColor: 'white',
          color: 'black',
          border: '2px solid #00ff00',
          borderRadius: '8px',
          fontFamily: 'inherit'
        }
      });
      
      // Redirect to home page after a short delay
      setTimeout(() => {
        window.location.href = '/';
      }, 2000);
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
      <ToastContainer />
    </div>
  );
};

export default VerifiedPage;