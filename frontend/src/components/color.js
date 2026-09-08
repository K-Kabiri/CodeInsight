/**
 * Small color helpers for the neon accents sprinkled across the
 * screens. Keeping the hex -> rgba conversion here lets sx styles
 * compose alpha variants of a single accent (border tint, glow
 * shadows, hover states) without a color library.
 */

export function withAlpha(hex, alpha) {
  const compact = hex.replace('#', '')
  const full =
    compact.length === 3
      ? compact
          .split('')
          .map((character) => character + character)
          .join('')
      : compact
  const number = Number.parseInt(full, 16)
  const r = (number >> 16) & 255
  const g = (number >> 8) & 255
  const b = number & 255
  return `rgba(${r}, ${g}, ${b}, ${alpha})`
}
