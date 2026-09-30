/**
 * A connection's consent page opened in a new tab, never blocked as a pop-up.
 */
export class ConsentTabUtils {
  /**
   * Open a blank tab at once, then send it to the consent page the API gives; the tab closes when the API fails.
   * @param fetchConsentUrl - Asks the API for the consent page.
   * @returns A promise resolved once the tab is on its way to the consent page.
   * @throws The API's error, once the tab is closed.
   */
  static async open(fetchConsentUrl: () => Promise<string>): Promise<void> {
    // Opened before the call: a tab opened after an await is blocked as a pop-up. It never sees this page.
    const tab: Window | null = window.open('about:blank', '_blank')
    if (tab) tab.opener = null
    try {
      const consentUrl: string = await fetchConsentUrl()
      if (tab) tab.location.href = consentUrl
      else window.location.assign(consentUrl)
    } catch (error: unknown) {
      tab?.close()
      throw error
    }
  }
}
