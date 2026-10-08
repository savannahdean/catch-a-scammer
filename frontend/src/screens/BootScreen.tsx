// A short fake boot sequence between the title screen and the desktop.
import { useEffect, useState } from 'react'
import { brand } from '../theme'

const LINES = ['mounting case volumes', 'attaching intelligence indexes', 'connecting secure messenger', 'restoring desktop session']
const BOOT_MS = 2200

export function BootScreen({ onDone }: { onDone: () => void }) {
  const [p, setP] = useState(0)
  useEffect(() => {
    const t0 = performance.now()
    let frame = 0
    const tick = (t: number) => {
      const v = Math.min(1, (t - t0) / BOOT_MS)
      setP(v)
      if (v < 1) frame = requestAnimationFrame(tick)
      else onDone()
    }
    frame = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frame)
  }, [onDone])

  return (
    <main className="screen boot" onClick={onDone} title="Click to skip">
      <div className="boot-name">
        {brand.OS_NAME} {brand.OS_VERSION}
      </div>
      <div className="boot-agency">{brand.AGENCY}</div>
      <div className="boot-bar">
        <div className="boot-fill" style={{ width: `${p * 100}%` }} />
      </div>
      <div className="boot-line">{LINES[Math.min(LINES.length - 1, Math.floor(p * LINES.length))]}</div>
    </main>
  )
}
