import { useState } from 'react';
import { TopBar } from './components/TopBar';
import { AboutPage } from './pages/AboutPage';
import { HomePage } from './pages/HomePage';
import { SubmitPage } from './pages/SubmitPage';
import { View } from './types';
import './App.css';

function App() {
  const [activeView, setActiveView] = useState<View>('home');

  return (
    <div className="app-shell">
      <TopBar activeView={activeView} onNavigate={setActiveView} />

      <main>
        {activeView === 'home' && <HomePage onNavigate={setActiveView} />}
        {activeView === 'about' && <AboutPage onNavigate={setActiveView} />}
        {activeView === 'submit' && <SubmitPage />}
      </main>
    </div>
  );
}

export default App;
