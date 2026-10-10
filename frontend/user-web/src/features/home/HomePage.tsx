import React from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { Zap, MapPin, CalendarClock, ArrowRight, BatteryCharging, CheckCircle } from 'lucide-react';

export const HomePage: React.FC = () => {
  const { user } = useAuth();

  return (
    <div className="max-w-7xl mx-auto px-4 lg:px-8 py-16">
      {/* Hero Section */}
      <div className="text-center max-w-3xl mx-auto mb-16 space-y-6">
        <div className="inline-flex items-center space-x-2 px-4 py-1.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs font-semibold">
          <Zap className="w-3.5 h-3.5" />
          <span>BookMyShow for EV charging</span>
        </div>

        <h1 className="text-4xl sm:text-6xl font-extrabold text-white tracking-tight leading-tight">
          Book your <span className="gradient-text">EV charger</span> before you arrive
        </h1>

        <p className="text-lg text-slate-300 leading-relaxed">
          Find nearby charging stations, see which chargers are free, reserve a time slot and start charging at the station with a one-time code.
        </p>

        <div className="flex flex-col sm:flex-row items-center justify-center gap-4 pt-4">
          {user ? (
            <Link
              to="/dashboard"
              className="w-full sm:w-auto px-8 py-4 rounded-xl gradient-btn text-white font-semibold flex items-center justify-center space-x-2 shadow-xl shadow-emerald-950/50"
            >
              <span>Go to Dashboard</span>
              <ArrowRight className="w-5 h-5" />
            </Link>
          ) : (
            <>
              <Link
                to="/register"
                className="w-full sm:w-auto px-8 py-4 rounded-xl gradient-btn text-white font-semibold flex items-center justify-center space-x-2 shadow-xl shadow-emerald-950/50"
              >
                <span>Get Started Now</span>
                <ArrowRight className="w-5 h-5" />
              </Link>
              <Link
                to="/login"
                className="w-full sm:w-auto px-8 py-4 rounded-xl bg-slate-900 hover:bg-slate-800 border border-slate-700 text-slate-200 font-semibold flex items-center justify-center transition-colors"
              >
                <span>Sign In</span>
              </Link>
            </>
          )}
        </div>
      </div>

      {/* Feature Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-8 mb-16">
        <div className="p-8 rounded-2xl glass-card relative group hover:border-emerald-500/30 transition-all">
          <div className="w-12 h-12 rounded-xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400 mb-6">
            <MapPin className="w-6 h-6" />
          </div>
          <h3 className="text-xl font-bold text-white mb-2">Find a charger</h3>
          <p className="text-sm text-slate-400 leading-relaxed">
            Search the map for stations near you, filter by connector type and get the best station suggested for your trip.
          </p>
        </div>

        <div className="p-8 rounded-2xl glass-card relative group hover:border-cyan-500/30 transition-all">
          <div className="w-12 h-12 rounded-xl bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center text-cyan-400 mb-6">
            <BatteryCharging className="w-6 h-6" />
          </div>
          <h3 className="text-xl font-bold text-white mb-2">Charge with a code</h3>
          <p className="text-sm text-slate-400 leading-relaxed">
            Enter your one-time code at the station screen to start. Watch progress on your phone and pay when you're done.
          </p>
        </div>

        <div className="p-8 rounded-2xl glass-card relative group hover:border-purple-500/30 transition-all">
          <div className="w-12 h-12 rounded-xl bg-purple-500/10 border border-purple-500/20 flex items-center justify-center text-purple-400 mb-6">
            <CalendarClock className="w-6 h-6" />
          </div>
          <h3 className="text-xl font-bold text-white mb-2">Reserve a slot</h3>
          <p className="text-sm text-slate-400 leading-relaxed">
            Pick a 30-minute slot like picking a movie seat. Your charger is held for you, and no one can double-book it.
          </p>
        </div>
      </div>

      {/* Tech Specs */}
      <div className="p-8 rounded-2xl bg-slate-900/60 border border-slate-800 text-left">
        <h4 className="text-lg font-bold text-white mb-4 flex items-center gap-2">
          <CheckCircle className="w-5 h-5 text-emerald-400" />
          Built with
        </h4>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-xs font-mono text-slate-300">
          <div className="p-3 rounded-lg bg-slate-950/80 border border-slate-800">
            <span className="text-slate-500 block">Web app</span>
            <span className="text-emerald-400 font-semibold">React + Vite</span>
          </div>
          <div className="p-3 rounded-lg bg-slate-950/80 border border-slate-800">
            <span className="text-slate-500 block">Language</span>
            <span className="text-emerald-400 font-semibold">TypeScript</span>
          </div>
          <div className="p-3 rounded-lg bg-slate-950/80 border border-slate-800">
            <span className="text-slate-500 block">API</span>
            <span className="text-emerald-400 font-semibold">FastAPI (Python)</span>
          </div>
          <div className="p-3 rounded-lg bg-slate-950/80 border border-slate-800">
            <span className="text-slate-500 block">Database</span>
            <span className="text-emerald-400 font-semibold">PostgreSQL</span>
          </div>
        </div>
      </div>
    </div>
  );
};
