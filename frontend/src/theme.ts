// The colour scheme. Which ones exist is spice/themes.py; their colours are the
// [data-theme] blocks in styles.css. The server stamps the saved one onto <html>
// before first paint; this re-applies it after /api/health (the Vite dev server
// serves index.html unstamped) and when Settings changes it.

export function applyTheme(key: string | undefined) {
  if (!key) return
  document.documentElement.dataset.theme = key
  // The browser chrome colour follows the page ground.
  const bg = getComputedStyle(document.documentElement).getPropertyValue('--bg').trim()
  document.querySelector('meta[name="theme-color"]')?.setAttribute('content', bg)
}
