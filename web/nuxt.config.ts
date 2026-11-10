import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

/** Receptionist layer of the dashboard: `~/` is the core here, so module files import each other relatively. */
const layerDirectory: string = dirname(fileURLToPath(import.meta.url))

export default defineNuxtConfig({
  $meta: {
    name: 'receptionist',
  },

  // Same prefixes as the core, so the components keep their names (`UiAssistantRequestDrawer`, `AssistantCard`…).
  components: [
    {
      path: join(layerDirectory, 'app/components/ui'),
      prefix: 'Ui',
    },
    {
      path: join(layerDirectory, 'app/components'),
      pathPrefix: false,
      ignore: ['**/ui/**'],
    },
  ],
})
