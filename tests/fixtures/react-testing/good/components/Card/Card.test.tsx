import { render, screen } from '@testing-library/react'
import { expect, it } from 'vitest'
import { Card } from '.'

it('shows the title', () => {
  render(<Card title="Hello" />)
  expect(screen.getByText('Hello')).toBeInTheDocument()
})
