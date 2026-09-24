/**
 * DevLeadHunter AI assistant embed loader.
 *
 * A client drops one line on their site:
 *   <script src="https://demo.dibodev.fr/ai-assistant.js" data-slug="their-slug" defer></script>
 *
 * It mounts the assistant as a floating iframe (transparent, bottom-right) sized from what the widget
 * reports: the launcher's exact footprint when closed (no dead zone over the host page), the panel when
 * open, the whole screen on a phone. The host viewport width is posted to the widget, which cannot read
 * it from inside the iframe. An unavailable assistant (unknown slug, demo expired) removes the iframe.
 * No dependency, no styling of the host page touched.
 */
;(function () {
  var current = document.currentScript
  if (!current) return
  var slug = current.getAttribute('data-slug')
  if (!slug) return
  if (document.getElementById('dlh-assistant-frame')) return

  var MOBILE_MAX_WIDTH = 560
  var OPEN_WIDTH = '440px'
  var OPEN_HEIGHT = '680px'
  var CLOSED_FALLBACK_SIZE = { width: 300, height: 112 }

  var origin = new URL(current.src).origin
  var src = origin + '/embed/' + encodeURIComponent(slug) + '?embed=1'
  // The owner's own visits stay out of the assistant's analytics, exactly like on the demo page.
  if (new URLSearchParams(window.location.search).get('internal') === '1') src += '&internal=1'

  var iframe = document.createElement('iframe')
  iframe.id = 'dlh-assistant-frame'
  iframe.src = src
  iframe.title = 'Assistant'
  iframe.setAttribute('allow', 'clipboard-write')
  iframe.setAttribute('aria-live', 'polite')

  var style = iframe.style
  style.position = 'fixed'
  style.bottom = '0'
  style.right = '0'
  style.border = '0'
  style.zIndex = '2147483000'
  style.background = 'transparent'
  style.colorScheme = 'light'
  style.maxWidth = '100%'
  style.transition = 'width 0.18s ease, height 0.18s ease'

  var isOpen = false
  var closedSize = CLOSED_FALLBACK_SIZE

  function isMobile() {
    return window.innerWidth < MOBILE_MAX_WIDTH
  }

  function applySize() {
    if (isOpen && isMobile()) {
      style.width = '100%'
      style.height = '100%'
    } else if (isOpen) {
      style.width = OPEN_WIDTH
      style.height = OPEN_HEIGHT
    } else {
      style.width = closedSize.width + 'px'
      style.height = closedSize.height + 'px'
    }
  }

  function postHostViewport() {
    if (!iframe.contentWindow || !(window.innerWidth > 0)) return
    iframe.contentWindow.postMessage({ type: 'dlh-assistant-host', width: window.innerWidth }, origin)
  }

  function remove() {
    window.removeEventListener('message', onMessage)
    window.removeEventListener('resize', onResize)
    if (iframe.parentNode) iframe.parentNode.removeChild(iframe)
  }

  function onMessage(event) {
    if (event.origin !== origin || !event.data) return
    if (event.data.type === 'dlh-assistant-unavailable') {
      remove()
      return
    }
    if (event.data.type === 'dlh-assistant-ready') {
      postHostViewport()
      return
    }
    if (event.data.type !== 'dlh-assistant-resize') return
    isOpen = !!event.data.open
    if (!isOpen && event.data.width > 0 && event.data.height > 0) {
      closedSize = { width: Math.ceil(event.data.width), height: Math.ceil(event.data.height) }
    }
    applySize()
  }

  function onResize() {
    applySize()
    postHostViewport()
  }

  applySize()
  iframe.addEventListener('load', postHostViewport)
  window.addEventListener('message', onMessage)
  window.addEventListener('resize', onResize)
  document.body.appendChild(iframe)
})()
