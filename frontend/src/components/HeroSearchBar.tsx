import React, { useState } from 'react';
import { Search, MapPin, X } from 'lucide-react';

interface HeroSearchBarProps {
  onSearchSubmit?: (query: string) => void;
  onRequestLocation?: () => void;
  currentCityQuery?: string;
}

export const HeroSearchBar: React.FC<HeroSearchBarProps> = ({
  onSearchSubmit,
  onRequestLocation,
  currentCityQuery = '',
}) => {
  const [query, setQuery] = useState(currentCityQuery);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (onSearchSubmit) {
      onSearchSubmit(query);
    }
  };

  const handleClear = () => {
    setQuery('');
    if (onSearchSubmit) {
      onSearchSubmit('');
    }
  };

  return (
    <div className="w-full max-w-2xl mx-auto px-4 my-6">
      <form onSubmit={handleSubmit} className="relative">
        {/* Signature Element: Animated Electric Current Rotating Conic Border */}
        <div className="electric-current-container">
          <div className="electric-inner-pill py-2.5 px-4 sm:px-5">
            {/* Search Icon */}
            <div className="text-cyan-400 shrink-0 mr-3 flex items-center">
              <Search className="w-5 h-5 stroke-[2.2]" />
            </div>

            {/* Main Input */}
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search for charging stations near you (e.g. San Francisco, Downtown...)"
              className="w-full bg-transparent text-white placeholder-slate-400 text-sm font-medium focus:outline-none pr-3"
            />

            {/* Clear Button if text entered */}
            {query && (
              <button
                type="button"
                onClick={handleClear}
                className="text-slate-400 hover:text-white p-1 rounded-full hover:bg-slate-800 transition-colors mr-2 cursor-pointer"
                title="Clear search"
              >
                <X className="w-4 h-4" />
              </button>
            )}

            {/* Geolocation Button Stub */}
            {onRequestLocation && (
              <button
                type="button"
                onClick={onRequestLocation}
                className="flex items-center space-x-1.5 px-3 py-1.5 rounded-full bg-cyan-500/10 hover:bg-cyan-500/20 text-cyan-300 border border-cyan-500/20 text-xs font-semibold shrink-0 transition-colors cursor-pointer"
                title="Use current location"
              >
                <MapPin className="w-3.5 h-3.5 text-cyan-400" />
                <span className="hidden sm:inline">Near Me</span>
              </button>
            )}
          </div>
        </div>
      </form>
    </div>
  );
};
