import { render, fireEvent } from '@testing-library/react'
import { Header } from './Header'

describe.only('Header', () => {
  it('renders', async () => {
    const { container } = render(<Header />)
    await new Promise((r) => setTimeout(r, 500))
    expect(container.querySelector('header')).toMatchSnapshot()
  })
  it.skip('later', () => {})
})
