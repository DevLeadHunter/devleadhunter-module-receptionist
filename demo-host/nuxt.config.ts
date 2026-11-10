import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const currentDir: string = dirname(fileURLToPath(import.meta.url))

/**
 * Nuxt layer of the « Réceptionniste IA » module (key `ai-assistant`), extended by demo-host.
 * `~/` is the host app here: imports of the core's shared files stay `~/…`, imports between module files are relative.
 * `@dicebear/core` and `@dicebear/notionists` are in demo-host's package.json: giget never installs a layer's packages.
 */
export default defineNuxtConfig({
  $meta: {
    name: 'devleadhunter-module-receptionist',
  },

  components: [
    {
      path: join(currentDir, './app/components'),
      pathPrefix: false,
    },
  ],

  appConfig: {
    demoTracking: {
      // The chat bubbles show back what the visitor typed: the session replay masks them.
      sessionReplayMaskedTextSelectors: ['.ai-message'],
    },
  },

  routeRules: {
    // The assistant widget is an iframe on the clients' own websites: any site may frame it.
    '/embed/**': {
      cors: true,
      headers: {
        'Content-Security-Policy': 'frame-ancestors *',
      },
    },
  },
})
