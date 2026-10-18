import { expect, it } from 'vitest'
import { originalQuestionImage, questionPreviewImages } from '../src/utils/question-assets.js'
it('opens the uploaded original instead of a crop or normalized preview', () => {
  const assets = [
    { kind: 'crop', path: 'crop.jpg' },
    { kind: 'original', path: 'original.jpg' },
    { kind: 'uploaded_original', path: 'uploaded.png' },
  ]
  expect(originalQuestionImage(assets)).toBe(assets[2])
})
it('legacy questions prefer the full preview over the crop and tolerate no photo', () => {
  const assets = [
    { kind: 'crop', path: 'crop.jpg' },
    { kind: 'original', path: 'original.jpg' },
  ]
  expect(originalQuestionImage(assets)).toBe(assets[1])
  expect(originalQuestionImage([assets[0]])).toBe(assets[0])
  expect(originalQuestionImage()).toBeNull()
})
it('keeps non-browser originals downloadable without opening them as preview images', () => {
  const assets = [
    { kind: 'uploaded_original', path: 'uploaded.bin' },
    { kind: 'original', path: 'original.jpg' },
  ]
  expect(originalQuestionImage(assets)).toBe(assets[1])
  expect(questionPreviewImages(assets)).toEqual([assets[1]])
  const signed = { kind: 'uploaded_original', url: '/uploads/uploaded.webp?signature=local' }
  expect(originalQuestionImage([signed])).toBe(signed)
})
