import { describe, expect, it } from 'vitest'
import { isValidElement } from 'react'
import { paragraphs, renderEmphasis } from './text'

describe('renderEmphasis', () => {
  it('turns **bold** into an element, never literal asterisks', () => {
    const parts = renderEmphasis('**Where:** the right half-space')
    const bold = parts.filter(isValidElement)
    expect(bold).toHaveLength(1)
    expect(parts.filter((p) => typeof p === 'string').join('')).not.toContain('*')
  })

  it('leaves plain prose untouched', () => {
    expect(renderEmphasis('no markup here')).toEqual(['no markup here'])
  })

  it('handles several spans in one paragraph', () => {
    const parts = renderEmphasis('**a** middle **b**')
    expect(parts.filter(isValidElement)).toHaveLength(2)
  })

  it('ignores stray or unpaired asterisks rather than mangling text', () => {
    expect(renderEmphasis('2 ** 3 exponent')).toEqual(['2 ** 3 exponent'])
    expect(renderEmphasis('****')).toEqual(['****'])
  })
})

describe('paragraphs', () => {
  it('splits on blank lines and trims', () => {
    expect(paragraphs('one\n\n  two  \n\n\n three')).toEqual(['one', 'two', 'three'])
  })

  it('keeps single newlines inside a paragraph', () => {
    expect(paragraphs('line one\nline two')).toEqual(['line one\nline two'])
  })

  it('returns nothing for empty input', () => {
    expect(paragraphs('\n\n  \n')).toEqual([])
  })
})
