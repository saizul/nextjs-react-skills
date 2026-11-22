import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it, vi } from 'vitest'
import { Button } from './Button'

it('calls onClick', async () => {
  const user = userEvent.setup()
  const onClick = vi.fn()
  render(<Button label="Save" onClick={onClick} />)
  await user.click(screen.getByRole('button', { name: 'Save' }))
  expect(onClick).toHaveBeenCalledOnce()
})
