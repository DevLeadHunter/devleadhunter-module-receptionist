/**
 * DevLeadHunter AI assistant embed loader.
 *
 * A client drops one line on their site:
 *   <script src="https://demo.dibodev.fr/ai-assistant.js" data-slug="their-slug" defer></script>
 *
 * It mounts the assistant as a floating iframe (transparent, bottom-right) that resizes between the
 * closed bubble and the open panel from postMessage sent by the widget. No dependency, no styling of
 * the host page touched.
 */
;(function () {
  var current = document.currentScript
  if (!current) return
  var slug = current.getAttribute('data-slug')
  if (!slug) return
  if (document.getElementById('dlh-assistant-frame')) return

  var origin = new URL(current.src).origin
  var iframe = document.createElement('iframe')
  iframe.id = 'dlh-assistant-frame'
  iframe.src = origin + '/embed/' + encodeURIComponent(slug)
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

  function isMobile() {
    return window.innerWidth < 560
  }

  var isOpen = false

  function applySize() {
    if (isOpen && isMobile()) {
      style.width = '100%'
      style.height = '100%'
    } else if (isOpen) {
      style.width = '440px'
      style.height = '680px'
    } else {
      style.width = isMobile() ? '150px' : '300px'
      style.height = '112px'
    }
  }

  applySize()
  document.body.appendChild(iframe)

  window.addEventListener('message', function (event) {
    if (event.origin !== origin || !event.data || event.data.type !== 'dlh-assistant-resize') return
    isOpen = !!event.data.open
    applySize()
  })
  window.addEventListener('resize', applySize)
})()
