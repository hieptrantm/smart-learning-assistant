import { useState } from 'react';
import './App.css';
import Navbarr from './components/navbar/navbar';
import Homepage from './components/homepage/homepage';
import Chatbot from './components/chatbot/chatbot';
import StudyPlanner from './components/study-planner/study-planner';
import ImportDocs from './components/import-docs/import-docs';
import Dashboard from './components/dashboard/dashboard';
import { useAuth } from './service/auth/useAuth.js';
import toast from 'react-hot-toast';

function App() {
  const [mainContent, setMainContent] = useState("Home")
  const { user, isLoaded } = useAuth();

  const onTabChange = (tab) => {
    if (!user && tab !== "Home") {
      toast.error("Vui lòng đăng nhập để sử dụng tính năng này.");
      return;
    }
    setMainContent(tab)
  }

  const renderScreen = () => {
    switch (mainContent) {
      case "Home":
        return <Homepage onNavigate={onTabChange} user={user} />;
      case "Chatbot":
        return user ? <Chatbot user={user} /> : <Homepage onNavigate={onTabChange} user={user} />;
      case "Planner":
        return user ? <StudyPlanner user={user} /> : <Homepage onNavigate={onTabChange} user={user} />;
      case "Import":
        return user ? <ImportDocs user={user} /> : <Homepage onNavigate={onTabChange} user={user} />;
      case "Dashboard":
        return user ? <Dashboard user={user} /> : <Homepage onNavigate={onTabChange} user={user} />;
      default:
        return <Homepage onNavigate={onTabChange} user={user} />;
    }
  };

  return (
    <div className="app-container">
      <div className='main-content'>
        <div className='navbar'>
          <Navbarr onTabChange={onTabChange} activeTab={mainContent} user={user} isLoaded={isLoaded}/>
        </div>
        <div className='content-area'>
          {renderScreen()}
        </div>
      </div>
    </div>
  );
}

export default App;