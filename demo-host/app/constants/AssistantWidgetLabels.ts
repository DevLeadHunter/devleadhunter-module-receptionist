import type {
  AiAssistantPersonaGender,
  AssistantAppointmentLabels,
  AssistantLeadLabels,
  AssistantPhotoLabels,
  AssistantWidgetLang,
} from '~/types/AiAssistant'

/** Each language's own name, on the widget's language buttons. */
export const LANGUAGE_LABELS: Record<AssistantWidgetLang, string> = {
  fr: 'Français',
  nl: 'Nederlands',
  en: 'English',
  de: 'Deutsch',
  lu: 'Lëtzebuergesch',
}

/** Each language as the « Répond en … » line under the header names it. */
export const LANGUAGE_NAMES: Record<AssistantWidgetLang, string> = {
  fr: 'français',
  nl: 'Nederlands',
  en: 'English',
  de: 'Deutsch',
  lu: 'Lëtzebuergesch',
}

/** The persona's role under its name in the header, by language and gender (« Réceptionniste IA »). */
export const ROLE_LABELS: Record<AssistantWidgetLang, Record<AiAssistantPersonaGender, string>> = {
  fr: { feminine: 'Réceptionniste IA', masculine: 'Réceptionniste IA' },
  nl: { feminine: 'AI-receptioniste', masculine: 'AI-receptionist' },
  en: { feminine: 'AI receptionist', masculine: 'AI receptionist' },
  de: { feminine: 'KI-Rezeptionistin', masculine: 'KI-Rezeptionist' },
  lu: { feminine: 'KI-Receptionistin', masculine: 'KI-Receptionist' },
}

/** The « en ligne » pill of the header. */
export const ONLINE_LABELS: Record<AssistantWidgetLang, string> = {
  fr: 'en ligne',
  nl: 'online',
  en: 'online',
  de: 'online',
  lu: 'online',
}

/**
 * The assistant's first message: it introduces itself as the business's AI receptionist, then asks. `{name}` is
 * its first name, `{business}` the business, `{of_business}` the French « de X » / « d'X ».
 */
export const GREETING_TEMPLATES: Record<AssistantWidgetLang, Record<AiAssistantPersonaGender, string>> = {
  fr: {
    feminine: 'Bonjour, je suis {name}, la réceptionniste IA {of_business}. Comment puis-je vous aider ?',
    masculine: 'Bonjour, je suis {name}, le réceptionniste IA {of_business}. Comment puis-je vous aider ?',
  },
  nl: {
    feminine: 'Hallo, ik ben {name}, de AI-receptioniste van {business}. Hoe kan ik u helpen?',
    masculine: 'Hallo, ik ben {name}, de AI-receptionist van {business}. Hoe kan ik u helpen?',
  },
  en: {
    feminine: "Hello, I'm {name}, the AI receptionist at {business}. How can I help you?",
    masculine: "Hello, I'm {name}, the AI receptionist at {business}. How can I help you?",
  },
  de: {
    feminine: 'Guten Tag, ich bin {name}, die KI-Rezeptionistin von {business}. Wie kann ich Ihnen helfen?',
    masculine: 'Guten Tag, ich bin {name}, der KI-Rezeptionist von {business}. Wie kann ich Ihnen helfen?',
  },
  lu: {
    feminine: "Moien, ech sinn d'{name}, d'KI-Receptionistin bei {business}. Wéi kann ech Iech hëllefen?",
    masculine: 'Moien, ech sinn de {name}, de KI-Receptionist bei {business}. Wéi kann ech Iech hëllefen?',
  },
}

/** The question offered as a chip before the visitor's first message, beside the photo and appointment ones. */
export const SUGGESTIONS: Record<AssistantWidgetLang, string[]> = {
  fr: ['Quels services proposez-vous ?'],
  nl: ['Welke diensten bieden jullie aan?'],
  en: ['What services do you offer?'],
  de: ['Welche Leistungen bieten Sie an?'],
  lu: ['Wéi eng Servicer bitt Dir un?'],
}

/** Placeholder of the message field. */
export const UI_PLACEHOLDER: Record<AssistantWidgetLang, string> = {
  fr: 'Votre message…',
  nl: 'Typ uw bericht…',
  en: 'Type your message…',
  de: 'Ihre Nachricht…',
  lu: 'Är Noriicht…',
}

/** The assistant's reply when the API cannot answer. */
export const FALLBACK_REPLY: Record<AssistantWidgetLang, string> = {
  fr: 'Je rencontre un souci technique. Réessayez dans un instant.',
  nl: 'Sorry, er is een technisch probleem. Probeer het zo meteen opnieuw.',
  en: 'Sorry, I hit a technical issue. Please try again in a moment.',
  de: 'Entschuldigung, es gab ein technisches Problem. Bitte versuchen Sie es gleich erneut.',
  lu: 'Pardon, et gouf e technescht Problem. Probéiert w.e.g. gläich nach eng Kéier.',
}

/** Texts of the contact form. */
export const LEAD_LABELS: Record<AssistantWidgetLang, AssistantLeadLabels> = {
  fr: {
    open: 'Être rappelé',
    title: 'Laissez vos coordonnées',
    name: 'Votre nom',
    contact: 'Email ou téléphone',
    need: 'Votre besoin (facultatif)',
    send: 'Envoyer',
    cancel: 'Annuler',
    sent: 'Merci, vos coordonnées sont transmises. On vous recontacte très vite.',
  },
  nl: {
    open: 'Word teruggebeld',
    title: 'Laat uw gegevens achter',
    name: 'Uw naam',
    contact: 'E-mail of telefoon',
    need: 'Wat u nodig heeft (optioneel)',
    send: 'Versturen',
    cancel: 'Annuleren',
    sent: 'Bedankt, uw gegevens zijn verzonden. We nemen snel contact met u op.',
  },
  en: {
    open: 'Request a callback',
    title: 'Leave your details',
    name: 'Your name',
    contact: 'Email or phone',
    need: 'What you need (optional)',
    send: 'Send',
    cancel: 'Cancel',
    sent: 'Thank you, your details have been sent. We will get back to you shortly.',
  },
  de: {
    open: 'Rückruf anfragen',
    title: 'Ihre Kontaktdaten',
    name: 'Ihr Name',
    contact: 'E-Mail oder Telefon',
    need: 'Ihr Anliegen (optional)',
    send: 'Senden',
    cancel: 'Abbrechen',
    sent: 'Danke, Ihre Daten wurden übermittelt. Wir melden uns in Kürze.',
  },
  lu: {
    open: 'Réckruff ufroen',
    title: 'Är Kontaktdaten',
    name: 'Ären Numm',
    contact: 'E-Mail oder Telefon',
    need: 'Wat Dir braucht (fakultativ)',
    send: 'Schécken',
    cancel: 'Ofbriechen',
    sent: 'Merci, Är Donnéeë sinn iwwerdroen. Mir mellen eis geschwënn.',
  },
}

/** Locales of the slot dates (Luxembourgish is « lb » in the browsers' date formats). */
export const DATE_LOCALES: Record<AssistantWidgetLang, string> = {
  fr: 'fr-FR',
  nl: 'nl-BE',
  en: 'en-GB',
  de: 'de-DE',
  lu: 'lb',
}

/** Texts of the appointment chip, button and slot panel. */
export const APPOINTMENT_LABELS: Record<AssistantWidgetLang, AssistantAppointmentLabels> = {
  fr: {
    chip: 'Prendre rendez-vous',
    button: 'Prendre rendez-vous',
    title: 'Choisissez 1 ou 2 créneaux qui vous arrangent : on vous confirme l’un des deux.',
    titleCalendar: 'Choisissez un créneau libre : il est réservé tout de suite.',
    kind: 'Pour quoi ?',
    more: 'Autres créneaux',
    appointment: 'Rendez-vous',
    booked: 'C’est réservé : {slots}.',
    bookedSms: ' Vous recevez une confirmation par SMS.',
    bookedEmail: ' Vous recevez une confirmation par email.',
    first: 'Premiers créneaux',
    taken: 'Ce créneau vient d’être pris. Choisissez-en un autre.',
    periods: { morning: 'Matin', afternoon: 'Après-midi' },
    periodsInline: { morning: 'matin', afternoon: 'après-midi' },
    next: 'Continuer',
    loading: 'Chargement des disponibilités…',
    none: 'Aucun créneau à proposer pour l’instant : laissez vos coordonnées, on vous rappelle.',
    error: 'Les créneaux ne sont pas disponibles pour le moment : laissez vos coordonnées, on vous rappelle.',
    chosen: 'Créneaux souhaités',
    unavailable: 'Ce créneau vient d’être retiré. Choisissez-en un autre.',
    sent: 'Merci ! Votre demande de rendez-vous est transmise ({slots}). On vous recontacte pour confirmer.',
  },
  nl: {
    chip: 'Afspraak maken',
    button: 'Afspraak maken',
    title: 'Kies 1 of 2 momenten die u passen: we bevestigen er één.',
    titleCalendar: 'Kies een vrij moment: het wordt meteen gereserveerd.',
    kind: 'Waarvoor?',
    more: 'Andere momenten',
    appointment: 'Afspraak',
    booked: 'Gereserveerd: {slots}.',
    bookedSms: ' U ontvangt een bevestiging per sms.',
    bookedEmail: ' U ontvangt een bevestiging per e-mail.',
    first: 'Eerste momenten',
    taken: 'Dit moment is net ingenomen. Kies een ander.',
    periods: { morning: 'Ochtend', afternoon: 'Namiddag' },
    periodsInline: { morning: 'ochtend', afternoon: 'namiddag' },
    next: 'Verder',
    loading: 'Beschikbaarheden laden…',
    none: 'Er zijn nu geen momenten beschikbaar: laat uw gegevens achter, we bellen u terug.',
    error: 'De momenten zijn nu niet beschikbaar: laat uw gegevens achter, we bellen u terug.',
    chosen: 'Gewenste momenten',
    unavailable: 'Dit moment is net weggevallen. Kies een ander.',
    sent: 'Bedankt! Uw afspraakverzoek is doorgegeven ({slots}). We nemen contact op om te bevestigen.',
  },
  en: {
    chip: 'Book an appointment',
    button: 'Book an appointment',
    title: 'Pick 1 or 2 times that suit you: we will confirm one of them.',
    titleCalendar: 'Pick a free slot: it is booked right away.',
    kind: 'What for?',
    more: 'Other times',
    appointment: 'Appointment',
    booked: 'Booked: {slots}.',
    bookedSms: ' You will get a confirmation by text message.',
    bookedEmail: ' You will get a confirmation by email.',
    first: 'Earliest times',
    taken: 'This slot was just taken. Please pick another one.',
    periods: { morning: 'Morning', afternoon: 'Afternoon' },
    periodsInline: { morning: 'morning', afternoon: 'afternoon' },
    next: 'Continue',
    loading: 'Loading availability…',
    none: 'No time to offer right now: leave your details and we will call you back.',
    error: 'Times are not available right now: leave your details and we will call you back.',
    chosen: 'Preferred times',
    unavailable: 'This time was just taken off. Please pick another one.',
    sent: 'Thank you! Your appointment request has been sent ({slots}). We will contact you to confirm.',
  },
  de: {
    chip: 'Termin vereinbaren',
    button: 'Termin vereinbaren',
    title: 'Wählen Sie 1 oder 2 passende Zeitfenster: Wir bestätigen eines davon.',
    titleCalendar: 'Wählen Sie einen freien Termin: Er wird sofort gebucht.',
    kind: 'Wofür?',
    more: 'Weitere Termine',
    appointment: 'Termin',
    booked: 'Gebucht: {slots}.',
    bookedSms: ' Sie erhalten eine Bestätigung per SMS.',
    bookedEmail: ' Sie erhalten eine Bestätigung per E-Mail.',
    first: 'Früheste Termine',
    taken: 'Dieser Termin wurde gerade vergeben. Bitte wählen Sie einen anderen.',
    periods: { morning: 'Vormittag', afternoon: 'Nachmittag' },
    periodsInline: { morning: 'Vormittag', afternoon: 'Nachmittag' },
    next: 'Weiter',
    loading: 'Verfügbarkeiten werden geladen…',
    none: 'Derzeit kein Zeitfenster frei: Hinterlassen Sie Ihre Daten, wir rufen zurück.',
    error: 'Die Zeitfenster sind gerade nicht verfügbar: Hinterlassen Sie Ihre Daten, wir rufen zurück.',
    chosen: 'Gewünschte Zeitfenster',
    unavailable: 'Dieses Zeitfenster ist gerade weggefallen. Bitte wählen Sie ein anderes.',
    sent: 'Danke! Ihre Terminanfrage wurde übermittelt ({slots}). Wir melden uns zur Bestätigung.',
  },
  lu: {
    chip: 'Rendez-vous huelen',
    button: 'Rendez-vous huelen',
    title: 'Wielt 1 oder 2 Zäitfënsteren, déi Iech passen: mir confirméieren eng dovun.',
    titleCalendar: 'Wielt eng fräi Zäit: si gëtt direkt reservéiert.',
    kind: 'Fir wat?',
    more: 'Aner Zäiten',
    appointment: 'Rendez-vous',
    booked: 'Reservéiert: {slots}.',
    bookedSms: ' Dir kritt eng Confirmatioun per SMS.',
    bookedEmail: ' Dir kritt eng Confirmatioun per E-Mail.',
    first: 'Éischt Zäiten',
    taken: 'Dës Zäit ass grad fortgaang. Wielt w.e.g. eng aner.',
    periods: { morning: 'Moies', afternoon: 'Mëttes' },
    periodsInline: { morning: 'moies', afternoon: 'mëttes' },
    next: 'Weider',
    loading: 'Disponibilitéite gi gelueden…',
    none: 'Momentan keng Zäitfënster: loosst Är Kontaktdaten do, mir ruffen Iech zréck.',
    error: 'D’Zäitfënstere sinn de Moment net disponibel: loosst Är Kontaktdaten do, mir ruffen Iech zréck.',
    chosen: 'Gewënschten Zäitfënsteren',
    unavailable: 'Dës Zäitfënster ass grad ewechgefall. Wielt w.e.g. eng aner.',
    sent: 'Merci! Är Rendez-vous-Ufro ass iwwerdroen ({slots}). Mir mellen eis fir ze confirméieren.',
  },
}

/** Texts of the photo chip, button and panel, and of its errors. */
export const PHOTO_LABELS: Record<AssistantWidgetLang, AssistantPhotoLabels> = {
  fr: {
    chip: 'Envoyer une photo pour un devis',
    button: 'Envoyer une photo',
    note: "Votre photo sert uniquement à préparer votre devis et elle est supprimée au bout de 90 jours. Évitez d'y montrer des personnes.",
    pick: 'Choisir une photo',
    sent: 'Photo envoyée',
    refused: 'Photo non envoyée',
    invalid: 'Je ne peux pas lire ce fichier. Envoyez une photo au format JPEG, PNG ou WEBP.',
    tooLarge: 'Cette photo est trop lourde (8 Mo maximum).',
    quota: "Vous avez déjà envoyé 3 photos : c'est suffisant pour préparer le devis.",
  },
  nl: {
    chip: 'Stuur een foto voor een offerte',
    button: 'Foto sturen',
    note: 'Uw foto dient alleen om uw offerte voor te bereiden en wordt na 90 dagen verwijderd. Zet er liefst geen personen op.',
    pick: 'Foto kiezen',
    sent: 'Foto verzonden',
    refused: 'Foto niet verzonden',
    invalid: 'Ik kan dit bestand niet lezen. Stuur een foto in JPEG-, PNG- of WEBP-formaat.',
    tooLarge: 'Deze foto is te groot (max. 8 MB).',
    quota: "U hebt al 3 foto's gestuurd: dat volstaat voor de offerte.",
  },
  en: {
    chip: 'Send a photo for a quote',
    button: 'Send a photo',
    note: 'Your photo is only used to prepare your quote and is deleted after 90 days. Please avoid showing people.',
    pick: 'Choose a photo',
    sent: 'Photo sent',
    refused: 'Photo not sent',
    invalid: "I can't read this file. Please send a JPEG, PNG or WEBP photo.",
    tooLarge: 'This photo is too large (8 MB max).',
    quota: "You've already sent 3 photos, that's enough to prepare the quote.",
  },
  de: {
    chip: 'Foto für ein Angebot senden',
    button: 'Foto senden',
    note: 'Ihr Foto dient nur zur Vorbereitung Ihres Angebots und wird nach 90 Tagen gelöscht. Bitte keine Personen zeigen.',
    pick: 'Foto auswählen',
    sent: 'Foto gesendet',
    refused: 'Foto nicht gesendet',
    invalid: 'Diese Datei kann ich nicht lesen. Bitte senden Sie ein JPEG-, PNG- oder WEBP-Foto.',
    tooLarge: 'Dieses Foto ist zu groß (max. 8 MB).',
    quota: 'Sie haben bereits 3 Fotos gesendet, das reicht für das Angebot.',
  },
  lu: {
    chip: 'Eng Foto fir en Devis schécken',
    button: 'Foto schécken',
    note: 'Är Foto déngt nëmme fir Ären Devis virzebereeden a gëtt no 90 Deeg geläscht. Weist w.e.g. keng Persounen drop.',
    pick: 'Foto auswielen',
    sent: 'Foto geschéckt',
    refused: 'Foto net geschéckt',
    invalid: 'Ech kann dëse Fichier net liesen. Schéckt w.e.g. eng JPEG-, PNG- oder WEBP-Foto.',
    tooLarge: 'Dës Foto ass ze grouss (max. 8 MB).',
    quota: 'Dir hutt schonn 3 Fotoe geschéckt, dat geet duer fir den Devis.',
  },
}
