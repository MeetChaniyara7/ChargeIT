import React, { lazy, Suspense } from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { AuthProvider } from '../features/auth/AuthContext';
import { ProtectedRoute } from '../features/auth/ProtectedRoute';
import { LoginPage } from '../features/auth/LoginPage';
import { RegisterPage } from '../features/auth/RegisterPage';
import { LandingPage } from '../features/home/LandingPage';
import { ExplorePage } from '../features/stations/ExplorePage';
import { StationPage } from '../features/stations/StationPage';
import { BookingsPage } from '../features/bookings/BookingsPage';
import { HoldPage } from '../features/bookings/HoldPage';
import { ReceiptPage } from '../features/bookings/ReceiptPage';
import { TicketPage } from '../features/bookings/TicketPage';
import { ChargingPage } from '../features/charging/ChargingPage';
import { ProfilePage } from '../features/profile/ProfilePage';
import { VehiclesPage } from '../features/profile/VehiclesPage';
import { AppLayout } from '../components/layout/AppLayout';
import { PublicLayout } from '../components/layout/PublicLayout';
import { SkeletonBlock, ToastProvider } from '../components/ui';

// The component style guide exists only while developing; it is not part of the production build.
const StyleGuidePage = import.meta.env.DEV ? lazy(() => import('../features/dev/StyleGuidePage')) : null;

export const App: React.FC = () => {
  return (
    <AuthProvider>
      <ToastProvider>
        <BrowserRouter>
          <Routes>
            {/* Pages anyone can open */}
            <Route element={<PublicLayout />}>
              <Route path="/" element={<LandingPage />} />
              <Route path="/login" element={<LoginPage />} />
              <Route path="/register" element={<RegisterPage />} />
              {StyleGuidePage && (
                <Route
                  path="/dev/ui"
                  element={
                    <Suspense fallback={<SkeletonBlock className="m-4 h-64" />}>
                      <StyleGuidePage />
                    </Suspense>
                  }
                />
              )}
            </Route>

            {/* Signed-in pages */}
            <Route
              element={
                <ProtectedRoute>
                  <AppLayout />
                </ProtectedRoute>
              }
            >
              <Route path="/explore" element={<ExplorePage />} />
              <Route path="/stations/:stationId" element={<StationPage />} />
              <Route path="/bookings" element={<BookingsPage />} />
              <Route path="/book/:bookingId" element={<HoldPage />} />
              <Route path="/tickets/:bookingId" element={<TicketPage />} />
              <Route path="/receipts/:bookingId" element={<ReceiptPage />} />
              <Route path="/charging" element={<ChargingPage />} />
              <Route path="/profile" element={<ProfilePage />} />
              <Route path="/profile/vehicles" element={<VehiclesPage />} />
            </Route>

            {/* The old address of the stations page */}
            <Route path="/dashboard" element={<Navigate to="/explore" replace />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </BrowserRouter>
      </ToastProvider>
    </AuthProvider>
  );
};

export default App;
