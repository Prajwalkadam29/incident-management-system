import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import LoginPage from '@/pages/LoginPage'
import DashboardPage from '@/pages/DashboardPage'
import IncidentDetailPage from '@/pages/IncidentDetailPage'
import RCAFormPage from '@/pages/RCAFormPage'
import IncidentHistoryPage from '@/pages/IncidentHistoryPage'

function PrivateRoute({ children }) {
  const token = localStorage.getItem('ims_token')
  return token ? children : <Navigate to="/login" replace />
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/" element={<PrivateRoute><DashboardPage /></PrivateRoute>} />
        <Route path="/history" element={<PrivateRoute><IncidentHistoryPage /></PrivateRoute>} />
        <Route path="/incidents/:id" element={<PrivateRoute><IncidentDetailPage /></PrivateRoute>} />
        <Route path="/incidents/:id/rca" element={<PrivateRoute><RCAFormPage /></PrivateRoute>} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}