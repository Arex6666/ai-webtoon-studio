/**
 * Media URL utilities — resolves MinIO storage keys to presigned URLs.
 */
import { useState, useEffect } from 'react'
import { apiGet } from './client'

/**
 * Check if a string is a storage key (not a full URL).
 */
export function isStorageKey(value: string): boolean {
  return !value.startsWith('http://') && !value.startsWith('https://') && !value.startsWith('data:')
}

/**
 * Fetch a fresh presigned URL for a MinIO storage key.
 */
export async function getMediaUrl(storageKey: string): Promise<string> {
  const resp = await apiGet<{ url: string; expires_in: number }>(
    `/api/v1/media/url?key=${encodeURIComponent(storageKey)}`
  )
  return resp.url
}

/**
 * React hook that resolves a storage key or URL to a displayable URL.
 *
 * - If `keyOrUrl` is already a full URL (http/https/data), returns it as-is.
 * - If `keyOrUrl` is a storage key, fetches a presigned URL from the backend.
 * - Returns `null` while loading or if `keyOrUrl` is null/undefined.
 */
export function useMediaUrl(keyOrUrl: string | null | undefined): string | null {
  const [url, setUrl] = useState<string | null>(null)

  useEffect(() => {
    if (!keyOrUrl) {
      setUrl(null)
      return
    }

    if (!isStorageKey(keyOrUrl)) {
      // Already a full URL, use directly
      setUrl(keyOrUrl)
      return
    }

    // Fetch presigned URL
    let cancelled = false
    getMediaUrl(keyOrUrl)
      .then((presignedUrl) => {
        if (!cancelled) setUrl(presignedUrl)
      })
      .catch((err) => {
        console.error('[useMediaUrl] Failed to resolve storage key:', keyOrUrl, err)
        if (!cancelled) setUrl(null)
      })

    return () => { cancelled = true }
  }, [keyOrUrl])

  return url
}
