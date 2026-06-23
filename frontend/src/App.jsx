import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { Toaster } from 'react-hot-toast'
import { AuthProvider } from './context/AuthContext'
import ProtectedRoute from './components/ProtectedRoute'
import Navbar from './components/Navbar'
import Login from './pages/Login'
import Register from './pages/Register'
import Dashboard from './pages/Dashboard'
import Predict from './pages/Predict'
import BatchUpload from './pages/BatchUpload'
import History from './pages/History'
import Customers from './pages/Customers'

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Toaster position="top-right" toastOptions={{ duration: 4000 }} />
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route
            path="/"
            element={
              <ProtectedRoute>
                <div className="min-h-screen flex flex-col">
                  <Navbar />
                  <main className="flex-1 container mx-auto max-w-7xl px-4 py-8">
                    <Navigate to="/dashboard" replace />
                  </main>
                </div>
              </ProtectedRoute>
            }
          />
          {[
            ['/dashboard', <Dashboard />],
            ['/predict', <Predict />],
            ['/batch', <BatchUpload />],
            ['/history', <History />],
            ['/customers', <Customers />],
          ].map(([path, element]) => (
            <Route
              key={path}
              path={path}
              element={
                <ProtectedRoute>
                  <div className="min-h-screen flex flex-col bg-gray-50">
                    <Navbar />
                    <main className="flex-1 container mx-auto max-w-7xl px-4 py-8">
                      {element}
                    </main>
                  </div>
                </ProtectedRoute>
              }
            />
          ))}
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}
