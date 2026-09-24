/**
 * Client-side preparation of the photos a visitor sends an assistant for a quote: a downscaled JPEG,
 * so a phone photo uploads fast and stays under the API's size limit.
 */
export class PhotoCompressionUtils {
  /** Longest side of the uploaded photo, in pixels (the API re-encodes to the same bound). */
  static readonly MAX_EDGE_PX: number = 1600
  /** JPEG quality of the upload. */
  static readonly JPEG_QUALITY: number = 0.82
  /** Largest file the API accepts. */
  static readonly MAX_BYTES: number = 8 * 1024 * 1024

  /**
   * Whether a picked file can be sent as a photo (images, HEIC included for iPhones).
   * @param file - The file the visitor picked.
   * @returns True for an image file.
   */
  static isPhoto(file: File): boolean {
    return file.type.startsWith('image/') || /\.(heic|heif)$/i.test(file.name)
  }

  /**
   * Downscale a picked photo to a JPEG no larger than MAX_EDGE_PX on its longest side (orientation kept).
   * The original file is returned when the browser cannot decode it (HEIC outside Safari): the API
   * then decides.
   * @param file - The photo the visitor picked.
   * @returns The JPEG to upload, or the original file.
   */
  static async prepare(file: File): Promise<Blob> {
    const objectUrl: string = URL.createObjectURL(file)
    try {
      const image: HTMLImageElement = new Image()
      image.src = objectUrl
      await image.decode()
      const longest: number = Math.max(image.naturalWidth, image.naturalHeight)
      if (!longest) return file
      const scale: number = Math.min(1, PhotoCompressionUtils.MAX_EDGE_PX / longest)
      const canvas: HTMLCanvasElement = document.createElement('canvas')
      canvas.width = Math.round(image.naturalWidth * scale)
      canvas.height = Math.round(image.naturalHeight * scale)
      const context: CanvasRenderingContext2D | null = canvas.getContext('2d')
      if (!context) return file
      context.drawImage(image, 0, 0, canvas.width, canvas.height)
      const blob: Blob | null = await new Promise<Blob | null>((resolve: (value: Blob | null) => void): void => {
        canvas.toBlob(resolve, 'image/jpeg', PhotoCompressionUtils.JPEG_QUALITY)
      })
      return blob ?? file
    } catch {
      return file
    } finally {
      URL.revokeObjectURL(objectUrl)
    }
  }
}
