import { act, renderHook } from '@testing-library/react'
import { expect, it } from 'vitest'
import { useCart } from '../useCart'

it('adds items', () => {
  const { result } = renderHook(() => useCart())
  act(() => result.current.add('a'))
  expect(result.current.items).toEqual(['a'])
})
