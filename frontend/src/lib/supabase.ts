import { createClient } from '@supabase/supabase-js';

const rawUrl = import.meta.env.VITE_SUPABASE_URL || '';
const rawKey = import.meta.env.VITE_SUPABASE_ANON_KEY || '';

// Automatically sanitize URL to base Supabase project URL (removes /rest/v1/ suffix if present)
const sanitizeUrl = (url: string): string => {
  if (!url) return '';
  return url.trim().replace(/\/rest\/v1\/?$/i, '').replace(/\/+$/, '');
};

const supabaseUrl = sanitizeUrl(rawUrl);
const supabaseAnonKey = rawKey.trim();

const isConfigured = 
  Boolean(supabaseUrl) && 
  !supabaseUrl.includes('your-supabase-project') &&
  Boolean(supabaseAnonKey) && 
  supabaseAnonKey !== 'your-supabase-anon-key-here';

if (!isConfigured) {
  console.warn(
    'Supabase environment variables (VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY) are missing or placeholder values. Please update your .env file.'
  );
}

// Fallback dummy URL to prevent createClient initialization crash if env is missing
const validUrl = supabaseUrl && supabaseUrl.startsWith('http') ? supabaseUrl : 'https://placeholder.supabase.co';
const validKey = supabaseAnonKey || 'placeholder-key';

export const supabase = createClient(validUrl, validKey);
export const isSupabaseConfigured = () => isConfigured;
