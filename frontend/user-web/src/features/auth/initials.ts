/** Initials for an avatar: "Meet Chaniyara" -> "MC", "meet@x.com" -> "ME". */
export function initialsOf(name: string | undefined | null, email: string | undefined | null): string {
  const source = (name || email || '?').trim();
  const words = source.split(/\s+/).filter(Boolean);
  const letters = words.length > 1 ? words[0][0] + words[words.length - 1][0] : source.slice(0, 2);
  return letters.toUpperCase();
}
