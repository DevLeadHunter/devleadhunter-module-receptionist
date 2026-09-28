/** The API's photo quota per visit (`MAX_PHOTOS_PER_SESSION`). */
export const ASSISTANT_PHOTOS_PER_VISIT: number = 3

/** The API's largest photo (`MAX_PHOTO_BYTES`), in megabytes. */
export const ASSISTANT_PHOTO_MAX_MEGABYTES: number = 8

/** How long the API keeps a photo (its `RETENTION`), in days. */
export const ASSISTANT_PHOTO_RETENTION_DAYS: number = 90

export const ASSISTANT_STORED_MESSAGES_MAX: number = 40

/** The API's half-days a visitor wishes at most (`AiAssistantAppointmentSlots.MAX_CHOSEN`), before its offer loads. */
export const ASSISTANT_SLOTS_MAX_CHOSEN: number = 2

/** Longest wait for an answer to begin: the response of a call, or the headers of the streamed reply. */
export const ASSISTANT_FIRST_BYTE_TIMEOUT_MS: number = 20_000

/** Longest wait for the first words of a reply, above the API's 40 s for its model and the fallback one. */
export const ASSISTANT_REPLY_START_TIMEOUT_MS: number = 45_000

export const ASSISTANT_STREAM_IDLE_TIMEOUT_MS: number = 20_000

/** Longest wait for a whole reply asked without streaming. */
export const ASSISTANT_REPLY_TIMEOUT_MS: number = 45_000

/** Longest wait for a photo: its upload, then the model describing it. */
export const ASSISTANT_PHOTO_TIMEOUT_MS: number = 60_000
