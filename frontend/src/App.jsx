import { useState } from 'react';
import GlobalStyles from './components/GlobalStyles';
import Login from './pages/Login';
import ResidentPortal from './pages/ResidentPortal';
import GuardDashboard from './pages/GuardDashboard';
import AdminTower from './pages/AdminTower';

export default function App() {
  const [currentView, setCurrentView] = useState('login'); // login, Resident, Security, Admin

  const handleLogin = (role) => {
    setCurrentView(role);
  };

  const handleLogout = () => {
    setCurrentView('login');
  };

  return (
    <>
      <GlobalStyles />
      {currentView === 'login' && <Login onLogin={handleLogin} />}
      {currentView === 'Resident' && <ResidentPortal onLogout={handleLogout} />}
      {currentView === 'Security' && <GuardDashboard onLogout={handleLogout} />}
      {currentView === 'Admin' && <AdminTower onLogout={handleLogout} />}
    </>
  );
}