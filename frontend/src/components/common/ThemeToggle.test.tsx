import { describe, expect, it, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { ThemeToggle } from './ThemeToggle'

describe('ThemeToggle', () => {
  it('renders the current theme value', () => {
    render(<ThemeToggle value="dark" onChange={vi.fn()} />)
    expect(screen.getByLabelText('Theme selector')).toHaveValue('dark')
  })

  it('calls onChange and toggles the document .dark class when switched', () => {
    const onChange = vi.fn()
    render(<ThemeToggle value="light" onChange={onChange} />)
    fireEvent.change(screen.getByLabelText('Theme selector'), { target: { value: 'dark' } })
    expect(onChange).toHaveBeenCalledWith('dark')
    expect(document.documentElement.classList.contains('dark')).toBe(true)
  })
})
