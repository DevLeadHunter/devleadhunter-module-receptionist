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
    '.dlh-sheet{position:fixed;right:max(22px,env(safe-area-inset-right,0px));bottom:max(22px,env(safe-area-inset-bottom,0px));z-index:2147483000;width:392px;max-width:calc(100vw - 28px);height:min(628px,calc(100vh - 44px));display:flex;flex-direction:column;overflow:hidden;background:#fff;border:1px solid rgba(23,19,13,.12);border-radius:22px;box-shadow:0 30px 70px -30px rgba(23,19,13,.45);font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;color:#17130d;opacity:0;transform:translate3d(0,14px,0);transition:opacity .26s cubic-bezier(.2,.7,.2,1),transform .3s cubic-bezier(.2,.7,.2,1);will-change:transform,opacity}' +
    '.dlh-sheet[hidden]{display:none}' +
    '.dlh-sheet--in{opacity:1;transform:none}' +
    '.dlh-sheet__head{display:flex;align-items:center;gap:12px;padding:14px 12px 12px 16px;border-bottom:1px solid rgba(23,19,13,.07)}' +
    '.dlh-sheet__portrait{position:relative;width:44px;height:44px;flex:none;border-radius:50%;box-shadow:0 0 0 2px var(--dlh-strong);overflow:hidden;background:var(--dlh-tint)}' +
    '.dlh-sheet__portrait img{display:block;width:100%;height:100%;object-fit:cover}' +
    '.dlh-sheet__name{flex:1;min-width:0;font-size:17px;font-weight:600;letter-spacing:-.01em;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}' +
    '.dlh-sheet__close{flex:none;width:32px;height:32px;margin:0;padding:0;border:0;border-radius:50%;background:transparent;color:#6d665b;font-size:22px;line-height:1;cursor:pointer}' +
    '.dlh-sheet__body{flex:1;padding:16px 14px;background:#faf8f3}' +
    '.dlh-sheet__dots{display:inline-flex;gap:5px;padding:12px 14px;border-radius:16px;border-bottom-left-radius:5px;background:#fff;border:1px solid rgba(23,19,13,.07);margin-left:30px}' +
    '.dlh-sheet__dots i{width:6px;height:6px;border-radius:50%;background:#6d665b;opacity:.35;animation:dlh-dot 1.1s ease-in-out infinite}' +
    '.dlh-sheet__dots i:nth-child(2){animation-delay:.15s}.dlh-sheet__dots i:nth-child(3){animation-delay:.3s}' +
    '@keyframes dlh-dot{0%,80%,100%{opacity:.35;transform:translateY(0)}40%{opacity:1;transform:translateY(-3px)}}' +
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
    '@media (max-width:559px),(max-height:639px){.dlh-launcher{transform-origin:calc(100% - 27px) calc(100% - 27px)}.dlh-launcher__say{display:none}.dlh-launcher__portrait{width:54px;height:54px}.dlh-sheet{right:0;bottom:0;width:100vw;max-width:100vw;height:100dvh;border:0;border-radius:0}.dlh-sheet__head{padding-top:max(14px,env(safe-area-inset-top,0px))}}' +
    '@media (prefers-reduced-motion:reduce){.dlh-launcher{transition:none}.dlh-launcher--pop{animation:none}.dlh-launcher__portrait{transition:none}.dlh-launcher--loading .dlh-launcher__portrait{animation:none}.dlh-sheet{transition:opacity .15s;transform:none}.dlh-sheet__dots i{animation:none}}'

  var launcher = null
  var iframe = null
  var isFrameReady = false
  var isOpen = false
  var wantsOpen = false
  // The widget said its panel is open: only then does its « closed » size mean the visitor closed it.
  var hasWidgetOpened = false
  var assistantName = ''
  var launcherHideTimer = null
  var sheet = null
  var sheetShownAt = 0
  var portraitSrc = ''
  // The part of the page really on screen: the keyboard shrinks it, and iOS pans it to keep the field in view.
  var viewport = window.visualViewport || null

  function isMobile() {
    return window.innerWidth < MOBILE_MAX_WIDTH || window.innerHeight < MOBILE_MAX_HEIGHT
  }

  function applySize() {
    if (!iframe || !isOpen) return
    var style = iframe.style
    if (isMobile()) {
      style.width = '100%'
      if (viewport) {
        // Full screen means the visible area, not the layout viewport: with the keyboard open, iOS scrolls
        // the page under a fixed frame and the site would show between the sheet and the keys.
        style.top = viewport.offsetTop + 'px'
        style.bottom = 'auto'
        style.height = viewport.height + 'px'
      } else {
        style.top = ''
        style.bottom = '0'
        style.height = '100%'
      }
    } else {
      style.top = ''
      style.bottom = '0'
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

  // `instant`: the placeholder sheet already played the opening, the widget shows its panel at once.
  function postOpen(instant) {
    if (!iframe || !iframe.contentWindow) return
    iframe.contentWindow.postMessage({ type: 'dlh-assistant-open', instant: instant === true }, origin)
  }

  // The frame was just shown at its full size: let the browser lay it out and paint once before the sheet
  // starts moving inside it, or the first frames of the animation are lost (visible on iPhone).
  function postOpenAfterPaint(instant) {
    var raf =
      window.requestAnimationFrame ||
      function (callback) {
        setTimeout(callback, 16)
      }
    raf(function () {
      raf(function () {
        postOpen(instant)
      })
    })
  }

  // Tapped before the frame is ready: a sheet with the receptionist's name opens at once, as an app would,
  // and the widget takes its place, without moving, the moment it is ready.
  function showPlaceholder() {
    if (!sheet) {
      sheet = document.createElement('div')
      sheet.className = 'dlh-sheet'
      sheet.setAttribute('role', 'dialog')
      sheet.setAttribute('aria-label', assistantName)
      var head = document.createElement('div')
      head.className = 'dlh-sheet__head'
      var portrait = document.createElement('span')
      portrait.className = 'dlh-sheet__portrait'
      if (portraitSrc) {
        var photo = document.createElement('img')
        photo.src = portraitSrc
        photo.alt = ''
        portrait.appendChild(photo)
      }
      var name = document.createElement('b')
      name.className = 'dlh-sheet__name'
      name.textContent = assistantName
      var close = document.createElement('button')
      close.type = 'button'
      close.className = 'dlh-sheet__close'
      close.setAttribute('aria-label', 'Fermer')
      close.textContent = '\u00d7'
      close.addEventListener('click', hidePlaceholder)
      head.appendChild(portrait)
      head.appendChild(name)
      head.appendChild(close)
      var body = document.createElement('div')
      body.className = 'dlh-sheet__body'
      var dots = document.createElement('span')
      dots.className = 'dlh-sheet__dots'
      dots.appendChild(document.createElement('i'))
      dots.appendChild(document.createElement('i'))
      dots.appendChild(document.createElement('i'))
      body.appendChild(dots)
      sheet.appendChild(head)
      sheet.appendChild(body)
      sheet.style.setProperty('--dlh-strong', launcher.style.getPropertyValue('--dlh-strong'))
      sheet.style.setProperty('--dlh-tint', launcher.style.getPropertyValue('--dlh-tint'))
      document.body.appendChild(sheet)
    }
    sheet.hidden = false
    sheet.classList.remove('dlh-sheet--in')
    // A reflow between the two states, so the sheet actually travels.
    void sheet.offsetWidth
    sheet.classList.add('dlh-sheet--in')
    sheetShownAt = Date.now()
    launcher.classList.remove('dlh-launcher--loading', 'dlh-launcher--pop')
    launcher.classList.add('dlh-launcher--away')
  }

  function removePlaceholder() {
    if (sheet) sheet.hidden = true
  }

  // The visitor gave up before the frame was ready (or it never came): back to the launcher.
  function hidePlaceholder() {
    wantsOpen = false
    removePlaceholder()
    launcher.classList.remove('dlh-launcher--away')
    launcher.classList.add('dlh-launcher--pop')
    launcher.focus()
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
    hasWidgetOpened = false
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
    if (viewport) {
      viewport.removeEventListener('resize', onResize)
      viewport.removeEventListener('scroll', onResize)
    }
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
        var wasPlaceholderShown = !!(sheet && !sheet.hidden)
        showFrame()
        postOpenAfterPaint(wasPlaceholderShown)
        // The widget paints its panel exactly where the sheet lands: the sheet leaves once it has landed.
        if (wasPlaceholderShown) setTimeout(removePlaceholder, Math.max(140, 340 - (Date.now() - sheetShownAt)))
      }
      return
    }
    if (event.data.type === 'dlh-assistant-persist') {
      writeStoredState(event.data.state)
      return
    }
    if (event.data.type !== 'dlh-assistant-resize') return
    if (event.data.open) {
      hasWidgetOpened = true
      if (!isOpen) showFrame()
      return
    }
    // The widget sizes itself to its launcher when it mounts, before it is asked to open: not a close.
    if (isOpen && hasWidgetOpened) hideFrame()
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
    if (viewport) {
      viewport.addEventListener('resize', onResize)
      viewport.addEventListener('scroll', onResize)
    }
    iframe.addEventListener('load', postHostViewport)
    document.body.appendChild(iframe)
  }

  function open() {
    wantsOpen = true
    if (!iframe) createFrame()
    if (isFrameReady) {
      showFrame()
      postOpenAfterPaint(false)
      return
    }
    showPlaceholder()
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
    portraitSrc = origin + config.portrait_path
    photo.src = portraitSrc
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
