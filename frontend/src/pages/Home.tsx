import React from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Zap, ShieldCheck, Database, ArrowRight, BatteryCharging, CheckCircle } from 'lucide-react';

export const Home: React.FC = () => {
  const { user } = useAuth();

  return (
    <div className="max-w-7xl mx-auto px-4 lg:px-8 py-16">
      {/* Hero Section */}
      <div className="text-center max-w-3xl mx-auto mb-16 space-y-6">
        <div className="inline-flex items-center space-x-2 px-4 py-1.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs font-semibold">
          <Zap className="w-3.5 h-3.5" />
          <span>Phase 1 Complete: Supabase Auth Ready</span>
        </div>

        <h1 className="text-4xl sm:text-6xl font-extrabold text-white tracking-tight leading-tight">
          Next-Gen <span className="gradient-text">EV Charging</span> Management Platform
        </h1>

        <p className="text-lg text-slate-300 leading-relaxed">
          A secure, high-performance web solution built with React, Vite, TypeScript, and Supabase Auth. Structured specifically for local PostgreSQL integration.
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
            <ShieldCheck className="w-6 h-6" />
          </div>
          <h3 className="text-xl font-bold text-white mb-2">Supabase Auth</h3>
          <p className="text-sm text-slate-400 leading-relaxed">
            Secure user sign up, email/password login, JWT session persistence, and protected route guards.
          </p>
        </div>

        <div className="p-8 rounded-2xl glass-card relative group hover:border-cyan-500/30 transition-all">
          <div className="w-12 h-12 rounded-xl bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center text-cyan-400 mb-6">
            <BatteryCharging className="w-6 h-6" />
          </div>
          <h3 className="text-xl font-bold text-white mb-2">Clean Architecture</h3>
          <p className="text-sm text-slate-400 leading-relaxed">
            Modular React components, strict TypeScript contracts, and AuthContext abstraction for easy scaling.
          </p>
        </div>

        <div className="p-8 rounded-2xl glass-card relative group hover:border-purple-500/30 transition-all">
          <div className="w-12 h-12 rounded-xl bg-purple-500/10 border border-purple-500/20 flex items-center justify-center text-purple-400 mb-6">
            <Database className="w-6 h-6" />
          </div>
          <h3 className="text-xl font-bold text-white mb-2">Local PostgreSQL Ready</h3>
          <p className="text-sm text-slate-400 leading-relaxed">
            Decoupled business logic ready to connect DBeaver managed local PostgreSQL for charging stations & reservations.
          </p>
        </div>
      </div>

      {/* Tech Specs */}
      <div className="p-8 rounded-2xl bg-slate-900/60 border border-slate-800 text-left">
        <h4 className="text-lg font-bold text-white mb-4 flex items-center gap-2">
          <CheckCircle className="w-5 h-5 text-emerald-400" />
          System Tech Stack & Architecture Specs
        </h4>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-xs font-mono text-slate-300">
          <div className="p-3 rounded-lg bg-slate-950/80 border border-slate-800">
            <span className="text-slate-500 block">Frontend Framework</span>
            <span className="text-emerald-400 font-semibold">React + Vite</span>
          </div>
          <div className="p-3 rounded-lg bg-slate-950/80 border border-slate-800">
            <span className="text-slate-500 block">Language</span>
            <span className="text-emerald-400 font-semibold">TypeScript (Strict)</span>
          </div>
          <div className="p-3 rounded-lg bg-slate-950/80 border border-slate-800">
            <span className="text-slate-500 block">Authentication</span>
            <span className="text-emerald-400 font-semibold">Supabase Auth</span>
          </div>
          <div className="p-3 rounded-lg bg-slate-950/80 border border-slate-800">
            <span className="text-slate-500 block">Phase 2 DB Target</span>
            <span className="text-emerald-400 font-semibold">Local PostgreSQL</span>
          </div>
        </div>
      </div>
    </div>
  );
};
