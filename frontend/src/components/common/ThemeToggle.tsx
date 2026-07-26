import { useEffect, useState } from 'react'

type ThemeChoice = 'light' | 'dark' | 'system'

function applyTheme(choice: ThemeChoice) {
  const root = document.documentElement
  const resolved =
    choice === 'system'
      ? window.matchMedia('(prefers-color-scheme: dark)').matches
        ? 'dark'
        : 'light'
      : choice
  root.classList.toggle('dark', resolved === 'dark')
}

export function ThemeToggle({
  value,
  onChange,
}: {
  value: ThemeChoice
  onChange: (choice: ThemeChoice) => void
}) {
  const [local, setLocal] = useState(value)

  useEffect(() => {
    setLocal(value)
    applyTheme(value)
  }, [value])

  return (
    <label className="flex items-center gap-2 text-sm">
      <span className="sr-only">Theme</span>
      <select
        aria-label="Theme selector"
        className="rounded-md border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 px-2 py-1 text-sm text-slate-900 dark:text-slate-100"
        value={local}
        onChange={(e) => {
          const next = e.target.value as ThemeChoice
          setLocal(next)
          applyTheme(next)
          onChange(next)
        }}
      >
        <option value="system">System</option>
        <option value="light">Light</option>
        <option value="dark">Dark</option>
      </select>
    </label>
  )
}
