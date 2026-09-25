/**
 * DevLeadHunter AI receptionist embed loader.
 *
 * A client drops one line on their site:
 *   <script src="https://demo.dibodev.fr/ai-assistant.js" data-slug="their-slug" defer></script>
 *
 * The host page only pays for what it shows: the loader fetches a few hundred bytes describing the
 * receptionist (name, portrait, colours, wording in the visitor's language) and draws the launcher
 * itself, natively. The widget's iframe is created hidden once the page is idle (or on the first
 * click), so the site's own loading, its Core Web Vitals included, is never delayed by the widget.
 * Opening shows the iframe sized as the widget reports (the panel, or the whole screen on a phone);
 * closing hides it again behind the launcher. The visitor's conversation is kept in the host page's own
 * storage and handed to the widget when it starts, because Safari denies storage to a third-party iframe:
 * a visitor moving from page to page keeps their thread. An unavailable receptionist (unknown slug, demo
 * expired) draws nothing. No dependency, no styling of the host page touched.
 */
;(function () {
  var current = document.currentScript
  if (!current) return
  var slug = current.getAttribute('data-slug')
  if (!slug) return
  if (document.getElementById('dlh-assistant-launcher') || document.getElementById('dlh-assistant-frame')) return

  var MOBILE_MAX_WIDTH = 560
  // A viewport shorter than this (a phone held sideways, a small laptop window) also gets the full screen.
  var MOBILE_MAX_HEIGHT = 640
  var OPEN_WIDTH = '440px'
  var OPEN_HEIGHT = '680px'
  // The iframe is prepared this long after the page has finished loading, so a click opens at once.
  var PREFETCH_DELAY_MS = 3000

  var origin = new URL(current.src).origin
  var STORAGE_KEY = 'dlh-assistant-' + slug
  var pageParams = new URLSearchParams(window.location.search)
  var frameSrc =
    origin +
    '/embed/' +
    encodeURIComponent(slug) +
    '?embed=1' +
    '&page=' +
    encodeURIComponent(window.location.pathname) +
    '&title=' +
    encodeURIComponent((document.title || '').slice(0, 80))
  // The owner's own visits stay out of the receptionist's analytics, exactly like on the demo page.
  if (pageParams.get('internal') === '1') frameSrc += '&internal=1'

  var CSS =
    '.dlh-launcher{position:fixed;right:max(22px,env(safe-area-inset-right,0px));bottom:max(22px,env(safe-area-inset-bottom,0px));z-index:2147483000;display:flex;align-items:center;gap:12px;margin:0;padding:0;border:0;background:transparent;cursor:pointer;font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;color:#17130d;text-align:left;line-height:1.4;transform-origin:calc(100% - 25px) calc(100% - 25px);transition:opacity .16s ease,transform .16s ease}' +
    '.dlh-launcher[hidden]{display:none}' +
    '.dlh-launcher:focus{outline:none}' +
    '.dlh-launcher:focus-visible{outline:2px solid var(--dlh-strong);outline-offset:4px;border-radius:999px}' +
    '.dlh-launcher--away{opacity:0;transform:scale(.7);pointer-events:none}' +
    '.dlh-launcher--pop{animation:dlh-pop .34s cubic-bezier(.32,.72,0,1)}' +
    '@keyframes dlh-pop{from{opacity:0;transform:scale(.7)}to{opacity:1;transform:none}}' +
    '.dlh-launcher__say{background:#fff;color:#17130d;border:1px solid rgba(23,19,13,.12);border-radius:14px;padding:11px 16px;font-size:14px;max-width:300px;box-shadow:0 18px 44px -24px rgba(23,19,13,.45)}' +
    '.dlh-launcher__say strong{font-weight:600}' +
    '.dlh-launcher__portrait{position:relative;width:50px;height:50px;flex:none;border-radius:50%;box-shadow:0 0 0 3px #fff,0 0 0 4px var(--dlh-strong),0 12px 28px -12px rgba(23,19,13,.55);transition:transform .15s ease}' +
    '.dlh-launcher:hover .dlh-launcher__portrait{transform:translateY(-2px)}' +
    '.dlh-launcher__disc{display:block;width:100%;height:100%;border-radius:50%;overflow:hidden;background:var(--dlh-tint);background:radial-gradient(circle at 32% 22%,color-mix(in srgb,var(--dlh-tint) 55%,#fff),var(--dlh-tint) 72%)}' +
    '.dlh-launcher__disc img{display:block;width:100%;height:100%;object-fit:cover}' +
    '.dlh-launcher__initial{display:flex;width:100%;height:100%;align-items:center;justify-content:center;font-weight:600;font-size:20px;color:#17130d}' +
    '.dlh-launcher__dot{position:absolute;right:2px;bottom:2px;width:12px;height:12px;border-radius:50%;background:#2f9e5b;box-shadow:0 0 0 2px #fff}' +
    '.dlh-launcher--loading .dlh-launcher__portrait{animation:dlh-pulse 1s ease-in-out infinite}' +
    '@keyframes dlh-pulse{50%{opacity:.55}}' +
    '@media (max-width:559px),(max-height:639px){.dlh-launcher__say{display:none}.dlh-launcher__portrait{width:46px;height:46px}}' +
    '@media (prefers-reduced-motion:reduce){.dlh-launcher{transition:none}.dlh-launcher--pop{animation:none}.dlh-launcher__portrait{transition:none}.dlh-launcher--loading .dlh-launcher__portrait{animation:none}}'

  var launcher = null
  var iframe = null
  var isFrameReady = false
  var isOpen = false
  var wantsOpen = false
  var assistantName = ''
  var launcherHideTimer = null

  function isMobile() {
    return window.innerWidth < MOBILE_MAX_WIDTH || window.innerHeight < MOBILE_MAX_HEIGHT
  }

  function applySize() {
    if (!iframe || !isOpen) return
    var style = iframe.style
    if (isMobile()) {
      style.width = '100%'
      style.height = '100%'
    } else {
      style.width = OPEN_WIDTH
      style.height = OPEN_HEIGHT
    }
  }

  function postHostViewport() {
    if (!iframe || !iframe.contentWindow || !(window.innerWidth > 0)) return
    iframe.contentWindow.postMessage(
      { type: 'dlh-assistant-host', width: window.innerWidth, height: window.innerHeight },
      origin,
    )
  }

  function postOpen() {
    if (!iframe || !iframe.contentWindow) return
    iframe.contentWindow.postMessage({ type: 'dlh-assistant-open' }, origin)
  }

  function readStoredState() {
    try {
      return window.localStorage.getItem(STORAGE_KEY)
    } catch (error) {
      return null
    }
  }

  function writeStoredState(state) {
    try {
      if (typeof state === 'string') window.localStorage.setItem(STORAGE_KEY, state)
      else window.localStorage.removeItem(STORAGE_KEY)
    } catch (error) {
      // Storage refused (private mode, quota): the widget keeps its own copy for this page.
    }
  }

  function postStoredState() {
    if (!iframe || !iframe.contentWindow) return
    iframe.contentWindow.postMessage({ type: 'dlh-assistant-state', state: readStoredState() }, origin)
  }

  function showFrame() {
    if (!iframe) return
    isOpen = true
    iframe.style.display = 'block'
    applySize()
    // The launcher steps aside while the sheet grows out of it, then leaves the page.
    launcher.classList.remove('dlh-launcher--loading', 'dlh-launcher--pop')
    launcher.classList.add('dlh-launcher--away')
    clearTimeout(launcherHideTimer)
    launcherHideTimer = setTimeout(function () {
      if (isOpen) launcher.hidden = true
    }, 180)
    iframe.focus()
  }

  function hideFrame() {
    isOpen = false
    wantsOpen = false
    if (iframe) iframe.style.display = 'none'
    // The widget shrank its sheet back into the launcher: it pops back where the sheet went.
    clearTimeout(launcherHideTimer)
    launcher.hidden = false
    launcher.classList.remove('dlh-launcher--away')
    launcher.classList.add('dlh-launcher--pop')
    launcher.focus()
  }

  function removeAll() {
    window.removeEventListener('message', onMessage)
    window.removeEventListener('resize', onResize)
    if (iframe && iframe.parentNode) iframe.parentNode.removeChild(iframe)
    if (launcher && launcher.parentNode) launcher.parentNode.removeChild(launcher)
  }

  function onMessage(event) {
    if (event.origin !== origin || !event.data) return
    if (event.data.type === 'dlh-assistant-unavailable') {
      removeAll()
      return
    }
    if (event.data.type === 'dlh-assistant-ready') {
      isFrameReady = true
      postHostViewport()
      postStoredState()
      if (wantsOpen) {
        showFrame()
        postOpen()
      }
      return
    }
    if (event.data.type === 'dlh-assistant-persist') {
      writeStoredState(event.data.state)
      return
    }
    if (event.data.type !== 'dlh-assistant-resize') return
    if (event.data.open && !isOpen) showFrame()
    else if (!event.data.open && isOpen) hideFrame()
  }

  function onResize() {
    applySize()
    postHostViewport()
  }

  function createFrame() {
    if (iframe) return
    iframe = document.createElement('iframe')
    iframe.id = 'dlh-assistant-frame'
    iframe.src = frameSrc
    iframe.title = assistantName
    iframe.setAttribute('allow', 'clipboard-write')
    var style = iframe.style
    style.position = 'fixed'
    style.bottom = '0'
    style.right = '0'
    style.border = '0'
    style.zIndex = '2147483000'
    style.background = 'transparent'
    style.colorScheme = 'light'
    style.maxWidth = '100%'
    style.maxHeight = '100%'
    style.display = 'none'
    window.addEventListener('message', onMessage)
    window.addEventListener('resize', onResize)
    iframe.addEventListener('load', postHostViewport)
    document.body.appendChild(iframe)
  }

  function open() {
    wantsOpen = true
    if (!iframe) createFrame()
    if (isFrameReady) {
      showFrame()
      postOpen()
      return
    }
    launcher.classList.add('dlh-launcher--loading')
  }

  function schedulePrefetch() {
    var idle =
      window.requestIdleCallback ||
      function (callback) {
        setTimeout(callback, 1)
      }
    var start = function () {
      setTimeout(function () {
        idle(createFrame)
      }, PREFETCH_DELAY_MS)
    }
    if (document.readyState === 'complete') start()
    else window.addEventListener('load', start)
  }

  function injectStyle() {
    if (document.getElementById('dlh-assistant-style')) return
    var style = document.createElement('style')
    style.id = 'dlh-assistant-style'
    style.textContent = CSS
    document.head.appendChild(style)
  }

  function render(config) {
    assistantName = config.assistant_name
    injectStyle()
    launcher = document.createElement('button')
    launcher.type = 'button'
    launcher.id = 'dlh-assistant-launcher'
    launcher.className = 'dlh-launcher'
    launcher.setAttribute('aria-label', config.open_label)
    launcher.style.setProperty('--dlh-strong', config.accent_strong)
    launcher.style.setProperty('--dlh-tint', config.accent_tint)

    var say = document.createElement('span')
    say.className = 'dlh-launcher__say'
    say.appendChild(document.createTextNode(config.say_before))
    var strong = document.createElement('strong')
    strong.textContent = config.assistant_name
    say.appendChild(strong)
    say.appendChild(document.createTextNode(config.say_after))

    var portrait = document.createElement('span')
    portrait.className = 'dlh-launcher__portrait'
    portrait.setAttribute('aria-hidden', 'true')
    var disc = document.createElement('span')
    disc.className = 'dlh-launcher__disc'
    var photo = document.createElement('img')
    photo.src = origin + config.portrait_path
    photo.alt = ''
    photo.draggable = false
    photo.onerror = function () {
      disc.textContent = ''
      var initial = document.createElement('span')
      initial.className = 'dlh-launcher__initial'
      initial.textContent = config.assistant_name.charAt(0).toUpperCase()
      disc.appendChild(initial)
    }
    disc.appendChild(photo)
    var dot = document.createElement('i')
    dot.className = 'dlh-launcher__dot'
    portrait.appendChild(disc)
    portrait.appendChild(dot)

    launcher.appendChild(say)
    launcher.appendChild(portrait)
    launcher.addEventListener('click', open)
    launcher.addEventListener('animationend', function () {
      launcher.classList.remove('dlh-launcher--pop')
    })
    document.body.appendChild(launcher)
    schedulePrefetch()
  }

  fetch(origin + '/embed-launcher/' + encodeURIComponent(slug), { credentials: 'omit' })
    .then(function (response) {
      return response.ok ? response.json() : null
    })
    .then(function (config) {
      if (config && config.assistant_name) render(config)
    })
    .catch(function () {
      // The receptionist stays silent rather than breaking the host page.
    })
})()
