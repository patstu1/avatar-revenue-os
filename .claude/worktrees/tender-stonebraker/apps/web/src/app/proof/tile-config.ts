/**
 * Tile configuration for the 16-screen ProofHook wall.
 *
 * Layout: 4 columns × 4 rows = 16 tiles. Each tile represents a facet of
 * the ProofHook creative engine. Videos are optional — when absent, the
 * CSS ambient gradient acts as the media surface so the experience works
 * without assets, and can be upgraded by dropping files into /public/videos/.
 *
 * Coordinate system: (col, row) starting at (0, 0) in the top-left. The
 * split animation stagger is derived from each tile's distance to the
 * wall center at (1.5, 1.5).
 */

export type TileCategory =
  | 'capture'
  | 'production'
  | 'performance'
  | 'creative'
  | 'distribution'
  | 'intelligence';

export interface WallTile {
  id: string;
  col: number; // 0..3
  row: number; // 0..3
  title: string;
  subtitle: string;
  category: TileCategory;
  /**
   * Optional video source. Relative path under /public (e.g. '/videos/tile-01.mp4').
   * When omitted, the tile renders the ambient gradient + grain treatment.
   */
  videoSrc?: string;
  /**
   * Optional poster image (shown before video plays, or as fallback).
   */
  posterSrc?: string;
  /**
   * Tuple of two HSL strings that drive the ambient gradient when no video
   * is present. Chosen to feel cohesive across the wall (all dark graphite
   * with a cyan/aqua signal accent).
   */
  gradient: [string, string];
  /**
   * Accent color used for hover glow, active outline, and metadata text.
   */
  accent: string;
  /**
   * Whether this tile should lift in the post-split interactive stage.
   * Exactly one tile should be featured. The featured tile gets high-fidelity
   * media playback; non-featured tiles stay lightweight until hovered.
   */
  featured?: boolean;
}

/**
 * Hero video that spans the full wall in stage 2 (unified).
 * Optional — when absent, the wall uses a CSS-driven cinematic ambient
 * composition that communicates the same energy.
 */
export const UNIFIED_HERO = {
  videoSrc: '/videos/hero-unified.mp4',
  posterSrc: '/videos/hero-unified-poster.jpg',
} as const;

/**
 * The 16 tiles, arranged by row:
 *   Row 0 — Capture       (on-set / studio / talent / art dept)
 *   Row 1 — Production    (edit / hook / VO / brand system)
 *   Row 2 — Distribution  (ads / platforms / schedule / pitch)
 *   Row 3 — Intelligence  (analytics / proof / revenue / deal room)
 */
export const TILES: WallTile[] = [
  // ---- Row 0 — Capture ------------------------------------------------
  {
    id: 'tile-01',
    col: 0,
    row: 0,
    title: 'On-Set',
    subtitle: 'Creator live shoot',
    category: 'capture',
    videoSrc: '/videos/tile-01.mp4',
    gradient: ['hsl(192, 42%, 8%)', 'hsl(190, 70%, 18%)'],
    accent: '#38e1ff',
  },
  {
    id: 'tile-02',
    col: 1,
    row: 0,
    title: 'Product Capture',
    subtitle: 'Hero product frame',
    category: 'capture',
    videoSrc: '/videos/tile-02.mp4',
    gradient: ['hsl(210, 28%, 9%)', 'hsl(200, 52%, 22%)'],
    accent: '#6ee9ff',
  },
  {
    id: 'tile-03',
    col: 2,
    row: 0,
    title: 'Set Design',
    subtitle: 'Controlled environment',
    category: 'capture',
    videoSrc: '/videos/tile-03.mp4',
    gradient: ['hsl(215, 35%, 8%)', 'hsl(205, 48%, 20%)'],
    accent: '#4fd8ff',
  },
  {
    id: 'tile-04',
    col: 3,
    row: 0,
    title: 'Talent Review',
    subtitle: 'Creator casting pool',
    category: 'capture',
    videoSrc: '/videos/tile-04.mp4',
    gradient: ['hsl(196, 40%, 9%)', 'hsl(190, 55%, 21%)'],
    accent: '#5cf2ff',
  },

  // ---- Row 1 — Production --------------------------------------------
  {
    id: 'tile-05',
    col: 0,
    row: 1,
    title: 'Edit Timeline',
    subtitle: 'Multitrack assembly',
    category: 'production',
    videoSrc: '/videos/tile-05.mp4',
    gradient: ['hsl(205, 32%, 9%)', 'hsl(198, 56%, 22%)'],
    accent: '#56e4ff',
  },
  {
    id: 'tile-06',
    col: 1,
    row: 1,
    title: 'Hook Test',
    subtitle: '3-second attention check',
    category: 'creative',
    videoSrc: '/videos/tile-06.mp4',
    gradient: ['hsl(198, 42%, 8%)', 'hsl(192, 62%, 22%)'],
    accent: '#4ff0ff',
    featured: true,
  },
  {
    id: 'tile-07',
    col: 2,
    row: 1,
    title: 'Voice Booth',
    subtitle: 'VO + caption sync',
    category: 'production',
    videoSrc: '/videos/tile-07.mp4',
    gradient: ['hsl(212, 32%, 8%)', 'hsl(202, 56%, 22%)'],
    accent: '#5bf0ff',
  },
  {
    id: 'tile-08',
    col: 3,
    row: 1,
    title: 'Brand System',
    subtitle: 'Design tokens live',
    category: 'creative',
    videoSrc: '/videos/tile-08.mp4',
    gradient: ['hsl(208, 36%, 9%)', 'hsl(198, 52%, 21%)'],
    accent: '#60e9ff',
  },

  // ---- Row 2 — Distribution ------------------------------------------
  {
    id: 'tile-09',
    col: 0,
    row: 2,
    title: 'Ad Performance',
    subtitle: 'Live ROAS feed',
    category: 'performance',
    videoSrc: '/videos/tile-09.mp4',
    gradient: ['hsl(220, 30%, 10%)', 'hsl(205, 58%, 22%)'],
    accent: '#7ceaff',
  },
  {
    id: 'tile-10',
    col: 1,
    row: 2,
    title: 'Distribution',
    subtitle: 'Cross-channel push',
    category: 'distribution',
    videoSrc: '/videos/tile-10.mp4',
    gradient: ['hsl(204, 34%, 9%)', 'hsl(196, 54%, 20%)'],
    accent: '#62e6ff',
  },
  {
    id: 'tile-11',
    col: 2,
    row: 2,
    title: 'Platform Native',
    subtitle: 'Per-channel cuts',
    category: 'distribution',
    videoSrc: '/videos/tile-11.mp4',
    gradient: ['hsl(200, 34%, 9%)', 'hsl(192, 56%, 21%)'],
    accent: '#68ecff',
  },
  {
    id: 'tile-12',
    col: 3,
    row: 2,
    title: 'Schedule',
    subtitle: 'Always-on release',
    category: 'distribution',
    videoSrc: '/videos/tile-12.mp4',
    gradient: ['hsl(210, 32%, 9%)', 'hsl(198, 54%, 22%)'],
    accent: '#58e8ff',
  },

  // ---- Row 3 — Intelligence ------------------------------------------
  {
    id: 'tile-13',
    col: 0,
    row: 3,
    title: 'Analytics',
    subtitle: 'Signal dashboard',
    category: 'intelligence',
    videoSrc: '/videos/tile-13.mp4',
    gradient: ['hsl(218, 30%, 9%)', 'hsl(208, 52%, 21%)'],
    accent: '#6beaff',
  },
  {
    id: 'tile-14',
    col: 1,
    row: 3,
    title: 'Proof Stack',
    subtitle: 'Verified results',
    category: 'intelligence',
    videoSrc: '/videos/tile-14.mp4',
    gradient: ['hsl(206, 36%, 9%)', 'hsl(196, 56%, 21%)'],
    accent: '#4fe4ff',
  },
  {
    id: 'tile-15',
    col: 2,
    row: 3,
    title: 'Revenue Intel',
    subtitle: 'Attribution engine',
    category: 'performance',
    videoSrc: '/videos/tile-15.mp4',
    gradient: ['hsl(214, 32%, 9%)', 'hsl(204, 52%, 22%)'],
    accent: '#72e7ff',
  },
  {
    id: 'tile-16',
    col: 3,
    row: 3,
    title: 'Deal Room',
    subtitle: 'Client pitch preview',
    category: 'distribution',
    videoSrc: '/videos/tile-16.mp4',
    gradient: ['hsl(202, 34%, 9%)', 'hsl(194, 56%, 21%)'],
    accent: '#5be5ff',
  },
];

/**
 * Welcome sequence text, displayed over the wall in stage 1.
 * Shown as one unified composition — never duplicated per tile.
 */
export const WELCOME_LINES = [
  'Hello.',
  'Welcome to ProofHook.',
  'Turn what you know into what you\u2019re known for.',
  'Well, let me show you around.',
] as const;

/**
 * Stage timings in milliseconds. Tuned for a premium, controlled pace.
 * Total first-load intro duration: ~10.3s (welcome 5s + unified hold 3.5s + split 1.8s).
 */
export const STAGE_TIMINGS = {
  // Welcome: each line delay (absolute from stage start)
  welcomeLine1: 400,
  welcomeLine2: 1500,
  welcomeLine3: 2700,
  welcomeLine4: 3900,
  welcomeEnd: 5000,
  // Unified hero hold after welcome completes
  unifiedHold: 3500,
  // Split transition duration
  splitDuration: 1800,
} as const;

/**
 * Key used for session-scoped persistence. Intro plays only once per
 * browser session; subsequent navigations jump straight to interactive.
 *
 * Bump the version suffix whenever the intro choreography changes
 * materially — doing so orphans any previously-stored flag and makes
 * every user see the fresh sequence on their next visit.
 */
export const SESSION_KEY = 'proofhook_intro_played_v4';

/**
 * Wall grid shape — keep this in sync with the CSS grid-template values.
 * `COLS * ROWS` should always equal `TILES.length`.
 */
export const GRID_COLS = 4;
export const GRID_ROWS = 4;
