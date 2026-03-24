import React, { useState, useEffect } from 'react'
import './App.css'
import { AuthProvider } from './contexts/AuthContext'
import { RoomProvider } from './contexts/RoomContext'
import { ThemeProvider } from './contexts/ThemeContext'
import LandingPage from './pages/LandingPage'
import RoomPage from './pages/RoomPage'
import AuthModal from './components/AuthModal'
import { BrowserRouter, Routes, Route, Navigate, useNavigate, useParams } from 'react-router-dom'

function AppRoutes() {
  const [showAuth, setShowAuth] = useState(false)

  return (
    <>
      {showAuth && <AuthModal onClose={() => setShowAuth(false)} />}
      <Routes>
        <Route 
          path="/" 
          element={
            <LandingPage 
              onRoomJoined={(roomCode) => {
                window.location.href = `/${roomCode}`
              }} 
            />
          } 
        />
        <Route 
          path="/:roomCode" 
          element={
            <RoomPageWrapper 
              onShowAuth={() => setShowAuth(true)}
            />
          } 
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </>
  )
}

function RoomPageWrapper({ onShowAuth }: { onShowAuth: () => void }) {
  const { roomCode } = useParams()
  
  if (!roomCode) {
    return <Navigate to="/" replace />
  }
  
  return (
    <RoomPage 
      roomCode={roomCode} 
      onLeaveRoom={() => {
        window.location.href = '/'
      }} 
      onShowAuth={onShowAuth}
    />
  )
}

function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <RoomProvider>
          <BrowserRouter>
            <AppRoutes />
          </BrowserRouter>
        </RoomProvider>
      </AuthProvider>
    </ThemeProvider>
  )
}

export default App
