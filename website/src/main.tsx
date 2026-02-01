import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import './index.css';
import App from './App.tsx';
import SignInPage from './pages/auth/SignInPage.tsx';
import DemoLayout from './pages/demo/DemoLayout.tsx';
import DemoPage from './pages/demo/DemoPage.tsx';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<App />} />
        <Route path="/sign-in" element={<SignInPage />} />
        <Route path="/sign-up" element={<SignInPage />} />
        <Route
          path="/demo/:role"
          element={
            <DemoLayout>
              <DemoPage />
            </DemoLayout>
          }
        />
      </Routes>
    </BrowserRouter>
  </StrictMode>
);
