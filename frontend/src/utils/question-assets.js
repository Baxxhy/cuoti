const canPreview = (asset) =>
  /\.(png|jpe?g|webp|gif|bmp)(?:\?|$)/i.test(asset.path || asset.url || '')

export function originalQuestionImage(assets = []) {
  return (
    assets.find((asset) => asset.kind === 'uploaded_original' && canPreview(asset)) ||
    assets.find((asset) => asset.kind === 'original') ||
    assets.find((asset) => asset.kind === 'crop') ||
    null
  )
}

export function questionPreviewImages(assets = []) {
  return assets.filter((asset) => asset.kind !== 'uploaded_original' || canPreview(asset))
}
