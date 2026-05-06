/**
 * Feature flags — env-var driven for B-1 cutover.
 *
 * NEXT_PUBLIC_USE_NEW_AGENT controls whether ChatPanel renders the new
 * useChat-driven NewAgentChat (true) or LegacyChat (false). Default: false
 * until Phase D flip.
 */
export const featureFlags = {
  useNewAgent: process.env.NEXT_PUBLIC_USE_NEW_AGENT === 'true',
} as const;

export type FeatureFlags = typeof featureFlags;
