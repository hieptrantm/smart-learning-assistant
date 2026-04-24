import React from 'react';
import ReactDOM from 'react-dom/client';
import './index.css';
import App from './App';
import { BrowserRouter as Router, Route, Routes } from 'react-router-dom';
import SignIn from './app/sign-in/sign-in';
import SignUp from './app/sign-up/sign-up';
import UserDetailPage from './app/user-detail/user-detail';
import AuthProvider from './service/auth/authProvider';
import GoogleAuthProvider from './service/auth/googleProvider';
import SetPassword from './app/set-password/set-password';
import VerifyEmail from './app/verify-email/verify-email';
import ForgotPassword from './app/forgot-password/forgot-password'
import DetectionDetail from './app/detect-detail/detect-detail';
import { Toaster } from 'react-hot-toast';

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <React.StrictMode>
    <Toaster position='bottom-right' />
    <AuthProvider>
      <GoogleAuthProvider>
        <Router>
          <Routes>
            <Route path="/" element={<App />} />
            <Route path="/sign-in" element={<SignIn />} />
            <Route path="/sign-up" element={<SignUp />} />
            <Route path="/user-detail" element={<UserDetailPage />} />
            <Route path="/set-password" element={<SetPassword />} />
            <Route path="/verify-email" element={<VerifyEmail />} />
            <Route path='/forgot-password' element={<ForgotPassword />} />
            <Route path='/detection/:encodedId' element={<DetectionDetail />} />
            <Route path="*" element={<h1>404 Not Found</h1>} />
          </Routes>
        </Router>
      </GoogleAuthProvider>
    </AuthProvider>
  </React.StrictMode>
);