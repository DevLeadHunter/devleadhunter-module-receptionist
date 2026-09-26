import type {
  AiAssistantPersonaGender,
  AssistantAppointmentLabels,
  AssistantExampleLabels,
  AssistantLeadLabels,
  AssistantPhotoLabels,
  AssistantUiLabels,
  AssistantWidgetLang,
} from '~/types/AiAssistant'
import type { AssistantGreetingContext } from '~/types/AssistantDemoScript'

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
 * The first sentence of the assistant's first message: it introduces itself as the business's AI receptionist.
 * `{name}` is its first name, `{business}` the business, `{of_business}` the French « de X » / « d'X ».
 */
export const GREETING_INTROS: Record<AssistantWidgetLang, Record<AiAssistantPersonaGender, string>> = {
  fr: {
    feminine: 'Bonjour, je suis {name}, la réceptionniste IA {of_business}.',
    masculine: 'Bonjour, je suis {name}, le réceptionniste IA {of_business}.',
  },
  nl: {
    feminine: 'Hallo, ik ben {name}, de AI-receptioniste van {business}.',
    masculine: 'Hallo, ik ben {name}, de AI-receptionist van {business}.',
  },
  en: {
    feminine: "Hello, I'm {name}, the AI receptionist at {business}.",
    masculine: "Hello, I'm {name}, the AI receptionist at {business}.",
  },
  de: {
    feminine: 'Guten Tag, ich bin {name}, die KI-Rezeptionistin von {business}.',
    masculine: 'Guten Tag, ich bin {name}, der KI-Rezeptionist von {business}.',
  },
  lu: {
    feminine: "Moien, ech sinn d'{name}, d'KI-Receptionistin bei {business}.",
    masculine: 'Moien, ech sinn de {name}, de KI-Receptionist bei {business}.',
  },
}

/**
 * The second sentence of the first message, by what the page the widget sits on is about: the plain question, or
 * an opening suited to a contact, quote or appointment page.
 */
export const GREETING_FOLLOW_UPS: Record<AssistantWidgetLang, Record<AssistantGreetingContext, string>> = {
  fr: {
    default: 'Comment puis-je vous aider ?',
    contact: 'Vous cherchez à nous joindre ? Dites-moi ce dont vous avez besoin, je transmets.',
    quote: 'Pour un devis, décrivez-moi votre projet ou envoyez une photo.',
    appointment: "Pour un rendez-vous, dites-moi ce qu'il vous faut, je vous propose un créneau.",
  },
  nl: {
    default: 'Hoe kan ik u helpen?',
    contact: 'Wilt u ons bereiken? Zeg me wat u nodig heeft, ik geef het door.',
    quote: 'Voor een offerte: beschrijf uw project of stuur een foto.',
    appointment: 'Voor een afspraak: zeg me wat u nodig heeft, ik stel een moment voor.',
  },
  en: {
    default: 'How can I help you?',
    contact: 'Trying to reach us? Tell me what you need and I will pass it on.',
    quote: 'For a quote, describe your project or send a photo.',
    appointment: 'For an appointment, tell me what you need and I will suggest a time.',
  },
  de: {
    default: 'Wie kann ich Ihnen helfen?',
    contact: 'Möchten Sie uns erreichen? Sagen Sie mir, was Sie brauchen, ich leite es weiter.',
    quote: 'Für ein Angebot beschreiben Sie Ihr Vorhaben oder senden Sie ein Foto.',
    appointment: 'Für einen Termin sagen Sie mir, was Sie brauchen, ich schlage eine Zeit vor.',
  },
  lu: {
    default: 'Wéi kann ech Iech hëllefen?',
    contact: 'Wëllt Dir eis erreechen? Sot mir, wat Dir braucht, ech ginn et weider.',
    quote: 'Fir en Devis: beschreift Äre Projet oder schéckt eng Foto.',
    appointment: 'Fir e Rendez-vous: sot mir, wat Dir braucht, ech proposéieren eng Zäit.',
  },
}

/** The widget's chrome: close button, launcher, typing indicator, language selector, composer. */
export const UI_LABELS: Record<AssistantWidgetLang, AssistantUiLabels> = {
  fr: {
    close: 'Fermer',
    open: 'Ouvrir la conversation avec {name}',
    launcherBefore: 'Une question\u00a0? ',
    launcherAfter: ' vous répond, 24h/24.',
    typing: 'Rédaction en cours',
    language: 'Langue',
    message: 'Votre message',
    send: 'Envoyer',
  },
  nl: {
    close: 'Sluiten',
    open: 'Gesprek met {name} openen',
    launcherBefore: 'Een vraag? ',
    launcherAfter: ' antwoordt u, dag en nacht.',
    typing: 'Aan het typen',
    language: 'Taal',
    message: 'Uw bericht',
    send: 'Versturen',
  },
  en: {
    close: 'Close',
    open: 'Open the conversation with {name}',
    launcherBefore: 'A question? ',
    launcherAfter: ' answers you, 24/7.',
    typing: 'Typing',
    language: 'Language',
    message: 'Your message',
    send: 'Send',
  },
  de: {
    close: 'Schließen',
    open: 'Gespräch mit {name} öffnen',
    launcherBefore: 'Eine Frage? ',
    launcherAfter: ' antwortet Ihnen, rund um die Uhr.',
    typing: 'Schreibt gerade',
    language: 'Sprache',
    message: 'Ihre Nachricht',
    send: 'Senden',
  },
  lu: {
    close: 'Zoumaachen',
    open: 'Gespréich mat {name} opmaachen',
    launcherBefore: 'Eng Fro? ',
    launcherAfter: " äntwert Iech, ronderëm d'Auer.",
    typing: 'Schreift grad',
    language: 'Sprooch',
    message: 'Är Noriicht',
    send: 'Schécken',
  },
}

/** The conversation the demo page plays by itself; in French the visitor's opening follows the trade instead. */
export const EXAMPLE_LABELS: Record<AssistantWidgetLang, AssistantExampleLabels> = {
  fr: {
    chip: 'Voir un exemple',
    visitor: "Bonjour, j'aurais besoin d'un devis. Vous pouvez me rappeler dans la journée ?",
    askPhoto: "Bien noté. Pouvez-vous m'envoyer une photo ? {business} pourra ainsi préparer son passage.",
    thanks:
      "Merci, c'est bien reçu. Je transmets tout de suite à {business} avec vos coordonnées : on vous rappelle dès l'ouverture. Si vous préférez un créneau, choisissez-le ci-dessous.",
  },
  nl: {
    chip: 'Bekijk een voorbeeld',
    visitor: 'Hallo, ik heb een lek onder de gootsteen. Kunt u deze week langskomen?',
    askPhoto: 'Genoteerd. Kunt u een foto sturen, zodat {business} het bezoek kan voorbereiden?',
    thanks:
      'Bedankt, goed ontvangen. Ik geef het meteen door aan {business} met uw gegevens: u wordt bij opening teruggebeld. Liever een afspraak? Kies hieronder een moment.',
  },
  en: {
    chip: 'See an example',
    visitor: 'Hello, I have a leak under the kitchen sink. Could you come this week?',
    askPhoto: 'Noted. Could you send me a photo, so {business} can prepare the visit?',
    thanks:
      'Thank you, received. I am passing it on to {business} right away with your details: they will call you back at opening time. Prefer an appointment? Pick a time below.',
  },
  de: {
    chip: 'Beispiel ansehen',
    visitor: 'Guten Tag, unter der Küchenspüle tropft es. Könnten Sie diese Woche vorbeikommen?',
    askPhoto: 'Notiert. Könnten Sie mir ein Foto schicken, damit {business} den Besuch vorbereiten kann?',
    thanks:
      'Danke, gut angekommen. Ich leite es sofort an {business} weiter, mit Ihren Kontaktdaten: Sie werden bei Öffnung zurückgerufen. Lieber ein Termin? Wählen Sie unten eine Zeit.',
  },
  lu: {
    chip: 'E Beispill kucken',
    visitor: 'Moien, ënner der Kichespull tröpfelt et. Kënnt Dir dës Woch laanschtkommen?',
    askPhoto: 'Notéiert. Kënnt Dir mir eng Foto schécken, fir datt {business} de Besuch virbereede kann?',
    thanks:
      'Merci, gutt ukomm. Ech ginn et direkt un {business} weider, mat Äre Kontaktdaten: Dir gitt bei der Ouverture zréckgeruff. Léiwer e Rendez-vous? Wielt ënnen eng Zäit.',
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
    contactHint: 'Un numéro de téléphone ou une adresse e-mail valide, pour vous joindre.',
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
    contactHint: 'Een geldig telefoonnummer of e-mailadres, om u te bereiken.',
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
    contactHint: 'A valid phone number or email address, so we can reach you.',
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
    contactHint: 'Eine gültige Telefonnummer oder E-Mail-Adresse, um Sie zu erreichen.',
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
    contactHint: 'Eng gëlteg Telefonsnummer oder E-Mail-Adress, fir Iech z’erreechen.',
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
