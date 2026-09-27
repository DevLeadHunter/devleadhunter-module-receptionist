import type { ComputedRef, Ref } from 'vue'
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import type { ClientSpaceLocation, ClientSpaceSection, ClientSpaceSettingsScreen } from '~/types/ClientSpaceNavigation'

/** The sections, as the hash names them (« #demandes »). */
const SECTION_HASHES: Record<ClientSpaceSection, string> = {
  home: 'accueil',
  requests: 'demandes',
  agenda: 'agenda',
  settings: 'reglages',
}

/** The settings screens, as the hash names them (« #reglages/alertes »). */
const SETTINGS_HASHES: Record<ClientSpaceSettingsScreen, string> = {
  assistant: 'lea',
  alerts: 'alertes',
  learned: 'reponses',
  report: 'rapport',
  subscription: 'abonnement',
  help: 'aide',
}

/** The hash of the question screen (« #question/2 »). */
const QUESTION_HASH: string = 'question'

/**
 * Where the client space is: its section, plus the request, the question or the settings screen opened on top.
 * @param location The location.
 * @returns The hash, without the leading « # ».
 */
function toHash(location: ClientSpaceLocation): string {
  if (location.questionIndex !== null) return `${QUESTION_HASH}/${location.questionIndex}`
  const base: string = SECTION_HASHES[location.section]
  if (location.section === 'requests' && location.requestId !== null) return `${base}/${location.requestId}`
  if (location.section === 'settings' && location.settingsScreen !== null) {
    return `${base}/${SETTINGS_HASHES[location.settingsScreen]}`
  }
  return base
}

/**
 * The location a hash names; the home for anything unknown.
 * @param hash The hash, with or without « # ».
 * @returns The location.
 */
function fromHash(hash: string): ClientSpaceLocation {
  const [head, tail]: string[] = hash.replace(/^#/, '').split('/')
  const home: ClientSpaceLocation = { section: 'home', requestId: null, questionIndex: null, settingsScreen: null }
  if (head === QUESTION_HASH) {
    const index: number = Number(tail)
    return Number.isInteger(index) && index >= 0 ? { ...home, section: 'requests', questionIndex: index } : home
  }
  const section: ClientSpaceSection | undefined = (Object.keys(SECTION_HASHES) as ClientSpaceSection[]).find(
    (key: ClientSpaceSection): boolean => SECTION_HASHES[key] === head,
  )
  if (!section) return home
  if (section === 'requests') {
    const id: number = Number(tail)
    return { ...home, section, requestId: Number.isInteger(id) && id > 0 ? id : null }
  }
  if (section === 'settings') {
    const screen: ClientSpaceSettingsScreen | undefined = (
      Object.keys(SETTINGS_HASHES) as ClientSpaceSettingsScreen[]
    ).find((key: ClientSpaceSettingsScreen): boolean => SETTINGS_HASHES[key] === tail)
    return { ...home, section, settingsScreen: screen ?? null }
  }
  return { ...home, section }
}

/**
 * The client space's navigation: four sections, and a request, a question or a settings screen opened on top.
 * The location lives in the URL hash, so the phone's back button and a link in an SMS both work, and the token
 * path never changes.
 * @returns The current location, what is open, and the moves.
 */
export function useClientSpaceNavigation(): {
  location: Ref<ClientSpaceLocation>
  isDetailOpen: ComputedRef<boolean>
  openSection: (section: ClientSpaceSection) => void
  openRequest: (requestId: number) => void
  openQuestion: (index: number) => void
  openSettingsScreen: (screen: ClientSpaceSettingsScreen) => void
  closeDetail: () => void
} {
  const location: Ref<ClientSpaceLocation> = ref<ClientSpaceLocation>(fromHash(''))

  /** A request, a question or a settings screen is open on top of its section. */
  const isDetailOpen: ComputedRef<boolean> = computed(
    (): boolean =>
      location.value.requestId !== null ||
      location.value.questionIndex !== null ||
      location.value.settingsScreen !== null,
  )

  /**
   * Move, and write the move in the history so the back button undoes it.
   * @param next The new location.
   */
  function go(next: ClientSpaceLocation): void {
    location.value = next
    const hash: string = `#${toHash(next)}`
    if (window.location.hash !== hash) window.history.pushState(null, '', hash)
  }

  /**
   * Show a section, closing whatever was open on top.
   * @param section The section.
   */
  function openSection(section: ClientSpaceSection): void {
    go({ section, requestId: null, questionIndex: null, settingsScreen: null })
  }

  /**
   * Open a request, in the requests section.
   * @param requestId The request.
   */
  function openRequest(requestId: number): void {
    go({ section: 'requests', requestId, questionIndex: null, settingsScreen: null })
  }

  /**
   * Open one of the receptionist's questions, in the requests section.
   * @param index The question's position in the unanswered list.
   */
  function openQuestion(index: number): void {
    go({ section: 'requests', requestId: null, questionIndex: index, settingsScreen: null })
  }

  /**
   * Open a settings screen.
   * @param screen The screen.
   */
  function openSettingsScreen(screen: ClientSpaceSettingsScreen): void {
    go({ section: 'settings', requestId: null, questionIndex: null, settingsScreen: screen })
  }

  /** Close what is open on top and show its section; goes back in history when the detail was pushed. */
  function closeDetail(): void {
    if (!isDetailOpen.value) return
    openSection(location.value.section)
  }

  /** Follow the browser's back and forward buttons. */
  function onPopState(): void {
    location.value = fromHash(window.location.hash)
  }

  onMounted((): void => {
    location.value = fromHash(window.location.hash)
    window.addEventListener('popstate', onPopState)
  })

  onBeforeUnmount((): void => {
    window.removeEventListener('popstate', onPopState)
  })

  return { location, isDetailOpen, openSection, openRequest, openQuestion, openSettingsScreen, closeDetail }
}
