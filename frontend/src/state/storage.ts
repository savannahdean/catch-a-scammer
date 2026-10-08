// Small wrapper over localStorage. It only holds conveniences for this browser
// (the open case, the study participant id, which chat messages you've read).
// Private windows and blocked storage throw, so every call is guarded and the
// game works without it.
const PREFIX = 'cas.'

export const store = {
  get(key: string): string | null {
    try {
      return window.localStorage.getItem(PREFIX + key)
    } catch {
      return null
    }
  },
  set(key: string, value: string): void {
    try {
      window.localStorage.setItem(PREFIX + key, value)
    } catch {
      /* storage unavailable: fine */
    }
  },
  remove(key: string): void {
    try {
      window.localStorage.removeItem(PREFIX + key)
    } catch {
      /* storage unavailable: fine */
    }
  },
  getNumber(key: string): number | null {
    const v = store.get(key)
    const n = v == null ? NaN : Number(v)
    return Number.isFinite(n) ? n : null
  },
  setNumber(key: string, n: number): void {
    store.set(key, String(n))
  },
}
