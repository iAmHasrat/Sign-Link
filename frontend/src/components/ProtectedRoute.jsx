import { Navigate, Outlet } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext.jsx';

export function ProtectedRoute() {
  const { loading, user } = useAuth();
  if (loading) return <div className="center-screen">Loading...</div>;
  return user ? <Outlet /> : <Navigate to="/login" replace />;
}
