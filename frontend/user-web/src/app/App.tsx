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
import { SessionReceiptPage } from '../features/charging/SessionReceiptPage';
import { LiveChargingPage } from '../features/charging/LiveChargingPage';
import { AdminLayout, RequireAdmin } from '../features/admin/AdminLayout';
import { ActivityPage } from '../features/admin/ActivityPage';
import { AlertsPage } from '../features/admin/AlertsPage';
import { BookingsAdminPage } from '../features/admin/BookingsPage';
import { KiosksPage } from '../features/admin/KiosksPage';
import { OperatorsPage } from '../features/admin/OperatorsPage';
import { OverviewPage } from '../features/admin/OverviewPage';
import { PaymentsPage } from '../features/admin/PaymentsPage';
import { SimulatorPage } from '../features/admin/SimulatorPage';
import { StationEditPage } from '../features/admin/StationEditPage';
import { StationsPage } from '../features/admin/StationsPage';
import { UsersPage } from '../features/admin/UsersPage';
import { ProfilePage } from '../features/profile/ProfilePage';
import { VehiclesPage } from '../features/profile/VehiclesPage';
import { AppLayout } from '../components/layout/AppLayout';
import { ErrorBoundary } from '../components/layout/ErrorBoundary';
import { NotFoundPage } from '../components/layout/NotFoundPage';
import { OfflineBanner } from '../components/layout/OfflineBanner';
import { PublicLayout } from '../components/layout/PublicLayout';
import { SkeletonBlock, ToastProvider } from '../components/ui';

// The component style guide exists only while developing; it is not part of the production build.
const StyleGuidePage = import.meta.env.DEV ? lazy(() => import('../features/dev/StyleGuidePage')) : null;

export const App: React.FC = () => {
  return (
    <ErrorBoundary>
    <AuthProvider>
      <ToastProvider>
        <BrowserRouter>
          <OfflineBanner />
          <Routes>
            {/* Pages anyone can open */}
            <Route element={<PublicLayout />}>
              <Route path="/" element={<LandingPage />} />
              <Route path="/login" element={<LoginPage />} />
              <Route path="/register" element={<RegisterPage />} />
              <Route path="*" element={<NotFoundPage />} />
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
              <Route path="/receipts/session/:sessionId" element={<SessionReceiptPage />} />
              <Route path="/charging" element={<ChargingPage />} />
              <Route path="/charging/:sessionId" element={<LiveChargingPage />} />
              <Route path="/profile" element={<ProfilePage />} />
              <Route path="/profile/vehicles" element={<VehiclesPage />} />

            </Route>

            {/* The admin has its own screen (header, sidebar, no driver tabs). The server checks the role on every request;
                RequireAdmin only keeps the pages out of sight. */}
            <Route
              path="/admin"
              element={
                <ProtectedRoute>
                  <RequireAdmin>
                    <AdminLayout />
                  </RequireAdmin>
                </ProtectedRoute>
              }
            >
              <Route index element={<OverviewPage />} />
              <Route path="stations" element={<StationsPage />} />
              <Route path="stations/:stationId" element={<StationEditPage />} />
              <Route path="operators" element={<OperatorsPage />} />
              <Route path="bookings" element={<BookingsAdminPage />} />
              <Route path="payments" element={<PaymentsPage />} />
              <Route path="kiosks" element={<KiosksPage />} />
              <Route path="simulator" element={<SimulatorPage />} />
              <Route path="users" element={<UsersPage />} />
              <Route path="alerts" element={<AlertsPage />} />
              <Route path="activity" element={<ActivityPage />} />
            </Route>

            {/* The old address of the stations page */}
            <Route path="/dashboard" element={<Navigate to="/explore" replace />} />
          </Routes>
        </BrowserRouter>
      </ToastProvider>
    </AuthProvider>
    </ErrorBoundary>
  );
};

export default App;
