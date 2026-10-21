import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { parseSearch, removeToken } from '@chargespot/shared';
import type { ConnectorType, ParsedSearch } from '@chargespot/shared';
import { SnapSheet } from '../../components/ui';
import type { Snap } from '../../components/ui';
import { apiFetch } from '../../lib/api';
import { useMediaQuery } from '../../lib/useMediaQuery';
import { ExploreList } from './ExploreList';
import { FilterBar } from './FilterBar';
import { StationMap } from './StationMap';
import { loadExploreView, saveExploreView } from './exploreView';
import type { ExploreView } from './exploreView';
import { withoutFilter } from './filterLabels';
import type {
  AreaSuggestion, LatLng, MapBounds, MapFocus, Place, StationSummary, SuggestResponse,
} from './types';
import { useExploreFilters } from './useExploreFilters';
import type { ExploreFilters } from './useExploreFilters';
import { useGeocode } from './useGeocode';
import { useGeolocation } from './useGeolocation';
import { useLoosenFilter } from './useLoosenFilter';
import { useRecentSearches } from './useRecentSearches';
import { useVehicles } from '../profile/useVehicles';
import { useRealtimeRefresh } from '../../lib/useRealtimeRefresh';
import { useRecommendations } from './useRecommendations';
import { suggestUrl, useSearchSuggest } from './useSearchSuggest';
import { useStations } from './useStations';

/** The search from the landing page is only acted on once, even if you come back to this page. */
const HANDLED_QUERY_KEY = 'chargespot:explore-handled-query';
/** The default vehicle's plug is put into the filter once per session; after that the driver's own choices rule. */
const VEHICLE_PREFILL_KEY = 'chargespot:vehicle-prefill-done';

const matchesText = (station: StationSummary, text: string): boolean => {
  const q = text.trim().toLowerCase();
  if (!q) return true;
  return [station.name, station.address, station.city, station.operator_name].some((field) => field?.toLowerCase().includes(q));
};

const sameName = (a: string | null | undefined, b: string) => !!a && a.trim().toLowerCase() === b.trim().toLowerCase();

/** The filters a typed search asks for. Plugs replace the current plug choice; other words add to the filters. */
function filtersFrom(parsed: ParsedSearch): Partial<ExploreFilters> {
  const change: Partial<ExploreFilters> = {};
  if (parsed.connectors.length) change.connectors = parsed.connectors;
  if (parsed.fast) change.fast = true;
  if (parsed.minPowerKw !== undefined) change.minKw = parsed.minPowerKw;
  if (parsed.maxPricePerKwh !== undefined) change.maxPrice = parsed.maxPricePerKwh;
  if (parsed.openNow) change.openNow = true;
  return change;
}

/**
 * Explore: a map of charging stations with a list beside it (desktop) or in a sheet over it (phone).
 *
 * - The map loads the stations in the area you are looking at, once it stops moving.
 * - Filters live in the page address, so a view can be shared and Back works.
 * - The search box understands filters ("fast ccs2"), suggests stations, operators and
 *   cities while typing, and looks up places only when Enter is pressed.
 * - Tapping a station selects its pin; tapping the selected one again opens the station page.
 */
export const ExplorePage: React.FC = () => {
  const navigate = useNavigate();
  const isDesktop = useMediaQuery('(min-width: 1024px)');
  const { filters, update, clearFilters, hasFilters } = useExploreFilters();

  const [initialView] = useState<ExploreView>(loadExploreView);
  const [bounds, setBounds] = useState<MapBounds | null>(null);
  const [view, setView] = useState<ExploreView>(initialView);
  const [focus, setFocus] = useState<MapFocus | null>(null);
  const focusCount = useRef(0);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [snap, setSnap] = useState<Snap>('peek');

  // The search box: what is typed, whether its suggestions are open, and whether the
  // list is being narrowed by what is typed (only until the search is submitted).
  const [queryText, setQueryText] = useState(filters.query);
  const [searchOpen, setSearchOpen] = useState(false);
  const [typing, setTyping] = useState(false);
  const parsed = useMemo(() => parseSearch(queryText), [queryText]);

  const flyTo = useCallback((center: LatLng, options: Pick<MapFocus, 'zoom' | 'bbox'> = {}) => {
    focusCount.current += 1;
    setFocus({ nonce: focusCount.current, center, ...options });
  }, []);

  const geolocation = useGeolocation((found) => flyTo(found, { zoom: 14 }));
  const geocode = useGeocode();
  const recentSearches = useRecentSearches();
  const { defaultVehicle, loading: vehiclesLoading } = useVehicles();

  // Distances are measured from the user when we know where they are, otherwise from the map centre.
  const reference = geolocation.location ?? view.center;
  const stationQuery = useStations(bounds, reference, filters);
  const recs = useRecommendations(reference, filters.connectors);
  const suggest = useSearchSuggest(parsed.text, reference, searchOpen);

  // Live updates for the nearest stations on screen (a channel each, so not hundreds): when one changes,
  // ask the API again. Pins whose free count changed flash. Stations further down the list refresh by polling.
  const nearestIds = stationQuery.stations.slice(0, 20).map((s) => s.station_id);
  useRealtimeRefresh(nearestIds, stationQuery.refresh);

  const noResults = !stationQuery.loading && !stationQuery.error && stationQuery.stations.length === 0;
  const loosen = useLoosenFilter(stationQuery.settledBounds, reference, filters, noResults && hasFilters);

  // The default vehicle picks the plug filter, once per session, and only if nothing is chosen yet.
  const filtersAreEmpty = !hasFilters;
  const updateFilters = update;
  useEffect(() => {
    if (vehiclesLoading) return;
    let done = false;
    try {
      done = sessionStorage.getItem(VEHICLE_PREFILL_KEY) === '1';
      sessionStorage.setItem(VEHICLE_PREFILL_KEY, '1');
    } catch {
      // Storage blocked: the prefill may repeat on reload, which is harmless.
    }
    if (!done && defaultVehicle && filtersAreEmpty) updateFilters({ connectors: [defaultVehicle.connector_type as ConnectorType] });
    // Only once the vehicles have loaded.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [vehiclesLoading]);

  const handleViewChange = useCallback((newBounds: MapBounds, newView: ExploreView) => {
    setBounds(newBounds);
    setView(newView);
    saveExploreView(newView);
  }, []);

  // While typing, the list narrows to names that match (no network).
  const listText = typing ? parsed.text : '';
  const visibleStations = useMemo(() => stationQuery.stations.filter((s) => matchesText(s, listText)), [stationQuery.stations, listText]);

  const select = (stationId: string) => {
    if (stationId === selectedId) {
      navigate(`/stations/${stationId}`);
      return;
    }
    setSelectedId(stationId);
    if (!isDesktop && snap === 'peek') setSnap('half');
  };

  // Show the selected card in the list (it may be off-screen when you tapped its pin).
  useEffect(() => {
    if (selectedId) document.getElementById(`station-card-${selectedId}`)?.scrollIntoView({ block: 'center', behavior: 'smooth' });
  }, [selectedId]);

  const finishSearch = (text: string) => {
    setQueryText(text);
    setTyping(false);
    setSearchOpen(false);
  };

  const focusPlace = (place: Place) => flyTo({ lat: place.lat, lng: place.lng }, place.bbox ? { bbox: place.bbox } : { zoom: 14 });

  const pickStation = (station: StationSummary) => {
    finishSearch(station.name);
    if (station.station_id === selectedId) {
      navigate(`/stations/${station.station_id}`);
      return;
    }
    setSelectedId(station.station_id);
    flyTo({ lat: station.latitude, lng: station.longitude }, { zoom: 15 });
    if (!isDesktop) setSnap('half');
  };

  const pickArea = (kind: 'operator' | 'city', area: AreaSuggestion) => {
    recentSearches.add(area.name);
    geocode.clear();
    if (kind === 'operator') {
      finishSearch('');
      update({ operator: area.name, query: '' }, { push: true });
    } else {
      finishSearch(area.name);
      update({ query: area.name }, { push: true });
    }
    const [south, north, west, east] = area.bbox;
    flyTo({ lat: area.latitude, lng: area.longitude }, { bbox: [south, north, west, east] });
  };

  const submitSearch = async (text: string) => {
    const search = parseSearch(text);
    const q = search.text;
    recentSearches.add(text);
    geocode.clear();
    finishSearch(q);
    update({ ...filtersFrom(search), query: q }, { push: true });

    if (search.nearMe) geolocation.request();
    if (!q) return;

    // "near Bopal" / "in Gandhinagar" is clearly a place. Otherwise look in our own data first.
    let found: SuggestResponse | null = null;
    if (!search.placeHint) {
      const local = stationQuery.stations.find((s) => sameName(s.name, q));
      if (local) return pickStation(local);
      try {
        found = await apiFetch<SuggestResponse>(suggestUrl(q, reference));
      } catch {
        found = null; // our search is down: still try the place search
      }
      const station = found?.stations.find((s) => sameName(s.name, q));
      if (station) return pickStation(station);
      // A misspelt operator ("tata powr") counts too, when the API is confident about the spelling.
      const operator = found?.operators.find((o) => sameName(o.name, q) || sameName(o.name, found?.did_you_mean ?? ''));
      if (operator) return pickArea('operator', operator);
      const city = found?.cities.find((c) => sameName(c.name, q));
      if (city) return pickArea('city', city);
    }

    // A place: ask the geocoder once (only now, never while typing) and fly there.
    const places = await geocode.search(q);
    if (places[0]) focusPlace(places[0]);
    else if (found?.stations[0]) pickStation(found.stations[0]); // no such place, but a station mentions it
  };

  // Arrived from the landing page with ?q=... : act on it once.
  const submitRef = useRef(submitSearch);
  useEffect(() => {
    submitRef.current = submitSearch;
  });
  useEffect(() => {
    const q = filters.query;
    let handled: string | null = null;
    try {
      handled = sessionStorage.getItem(HANDLED_QUERY_KEY);
    } catch {
      // Storage blocked: the search may run again on reload, which is harmless.
    }
    if (q && handled !== q) {
      try {
        sessionStorage.setItem(HANDLED_QUERY_KEY, q);
      } catch {
        // See above.
      }
      void submitRef.current(q);
    }
    // Only on first load.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const list = (
    <ExploreList
      stations={visibleStations}
      loading={stationQuery.loading}
      refreshing={stationQuery.refreshing}
      error={stationQuery.error}
      onRetry={stationQuery.retry}
      truncated={stationQuery.truncated}
      recommendations={recs.error ? [] : recs.recommendations}
      recommendationsFromUser={geolocation.location !== null}
      selectedId={selectedId}
      onSelect={select}
      showDistance={geolocation.location !== null}
      hasFilters={hasFilters}
      onClearFilters={() => {
        clearFilters();
        finishSearch('');
      }}
      loosen={loosen}
      onLoosen={(key) => update(withoutFilter(key))}
      locationStatus={geolocation.status}
      onLocate={geolocation.request}
    />
  );

  return (
    <div className="flex h-[calc(100dvh-3.5rem-4rem-env(safe-area-inset-bottom))] lg:h-[calc(100dvh-3.5rem)]">
      {isDesktop && (
        <aside aria-label="Charging stations" className="w-[400px] shrink-0 overflow-y-auto border-r border-border p-4">
          {list}
        </aside>
      )}

      {/* The map isolates its own layers (see StationMap), so the search bar and sheet float above it. */}
      <div className="relative min-w-0 flex-1">
        <StationMap
          stations={stationQuery.stations}
          selectedId={selectedId}
          userLocation={geolocation.location}
          initialView={initialView}
          focus={focus}
          onViewChange={handleViewChange}
          onSelect={select}
        />

        <FilterBar
          filters={filters}
          onFiltersChange={update}
          search={{
            value: queryText,
            onChange: (text) => {
              setQueryText(text);
              setTyping(true);
            },
            onSubmit: (text) => void submitSearch(text),
            parsed,
            onRemoveToken: (token) => {
              setQueryText(removeToken(queryText, token));
              setTyping(true);
            },
            suggestions: suggest.data,
            suggestLoading: suggest.loading,
            suggestError: suggest.error,
            recent: recentSearches.recent,
            onClearRecent: recentSearches.clear,
            onPickStation: pickStation,
            onPickArea: pickArea,
            onLocate: () => {
              setSearchOpen(false);
              geolocation.request();
            },
            locating: geolocation.status === 'asking',
            open: searchOpen,
            onOpenChange: setSearchOpen,
            fullScreen: !isDesktop,
          }}
          placeStatus={geocode.status}
          places={geocode.places}
          onPickPlace={(place) => {
            focusPlace(place);
            geocode.clear();
          }}
          onDismissPlaces={geocode.clear}
        />

        {!isDesktop && (
          <SnapSheet
            snap={snap}
            onSnapChange={setSnap}
            label="Nearby stations"
            summary={
              <p className="num text-sm font-bold">
                {stationQuery.loading ? 'Loading stations…' : `${visibleStations.length} station${visibleStations.length === 1 ? '' : 's'} in this area`}
              </p>
            }
          >
            {list}
          </SnapSheet>
        )}
      </div>
    </div>
  );
};
