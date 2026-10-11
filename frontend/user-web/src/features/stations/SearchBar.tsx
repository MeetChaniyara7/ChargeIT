import React, { useState } from 'react';
import { MapPin, Search, X } from 'lucide-react';
import { Button, IconButton, TextInput } from '../../components/ui';

interface SearchBarProps {
  onSearchSubmit?: (query: string) => void;
  onRequestLocation?: () => void;
  currentCityQuery?: string;
}

/** Search box for stations ("Enter" to search) with a "Near me" button. */
export const SearchBar: React.FC<SearchBarProps> = ({ onSearchSubmit, onRequestLocation, currentCityQuery = '' }) => {
  const [query, setQuery] = useState(currentCityQuery);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSearchSubmit?.(query);
  };

  const handleClear = () => {
    setQuery('');
    onSearchSubmit?.('');
  };

  return (
    <form role="search" onSubmit={handleSubmit} className="flex w-full max-w-2xl items-center gap-2">
      <label htmlFor="station-search" className="sr-only">
        Search stations by name, address or city
      </label>
      <div className="relative flex-1">
        <Search className="pointer-events-none absolute left-3 top-1/2 size-5 -translate-y-1/2 text-muted" aria-hidden="true" />
        <TextInput
          id="station-search"
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search by station, area or city"
          className="pl-10 pr-11 [&::-webkit-search-cancel-button]:hidden"
        />
        {query && (
          <IconButton aria-label="Clear search" onClick={handleClear} className="absolute right-0 top-0">
            <X className="size-4" aria-hidden="true" />
          </IconButton>
        )}
      </div>
      {onRequestLocation && (
        <Button variant="secondary" onClick={onRequestLocation} icon={<MapPin className="size-4" aria-hidden="true" />}>
          <span className="hidden sm:inline">Near me</span>
          <span className="sr-only sm:hidden">Near me</span>
        </Button>
      )}
    </form>
  );
};
