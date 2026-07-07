/**
 * On-device translation using Google ML Kit.
 * Free, offline, no API key required.
 * 
 * Usage: After installing react-native-mlkit-translate, language models
 * are downloaded on-demand (~10-30MB per language).
 */

// Language codes for Nigerian languages
export const SUPPORTED_LANGUAGES = {
  en: 'English',
  pcm: 'Pidgin', // Note: Pidgin not in ML Kit, will need custom handling
  yo: 'Yoruba',
  ha: 'Hausa',
  ig: 'Igbo',
} as const;

export type LanguageCode = keyof typeof SUPPORTED_LANGUAGES;

// ML Kit language codes mapping
const ML_KIT_CODES: Record<LanguageCode, string> = {
  en: 'en',
  pcm: 'en', // Fallback to English (Pidgin not supported by ML Kit)
  yo: 'yo',
  ha: 'ha',
  ig: 'ig',
};

let translator: any = null;

/**
 * Initialize translator (lazy load to avoid import errors if package not installed)
 */
async function getTranslator() {
  if (translator) return translator;
  
  try {
    const mlkit = await import('react-native-mlkit-translate');
    translator = mlkit.default;
    return translator;
  } catch (error) {
    console.warn('ML Kit Translate not installed. Translation disabled.');
    return null;
  }
}

/**
 * Download language model if not already downloaded.
 * This happens once per language, cached on device.
 */
export async function downloadLanguageModel(language: LanguageCode): Promise<boolean> {
  try {
    const mlkit = await getTranslator();
    if (!mlkit) return false;

    const code = ML_KIT_CODES[language];
    const isDownloaded = await mlkit.isModelDownloaded(code);
    
    if (!isDownloaded) {
      console.log(`Downloading ${language} model...`);
      await mlkit.downloadModel(code);
      console.log(`${language} model downloaded`);
    }
    
    return true;
  } catch (error) {
    console.error(`Failed to download ${language} model:`, error);
    return false;
  }
}

/**
 * Translate text from one language to another.
 * Both language models must be downloaded first.
 */
export async function translate(
  text: string,
  from: LanguageCode,
  to: LanguageCode
): Promise<string> {
  try {
    // No translation needed
    if (from === to) return text;
    
    const mlkit = await getTranslator();
    if (!mlkit) return text;

    // Ensure models are downloaded
    await downloadLanguageModel(from);
    await downloadLanguageModel(to);

    const fromCode = ML_KIT_CODES[from];
    const toCode = ML_KIT_CODES[to];

    const translated = await mlkit.translate(text, fromCode, toCode);
    return translated;
  } catch (error) {
    console.error('Translation failed:', error);
    return text; // Return original text on failure
  }
}

/**
 * Translate multiple strings at once (batch translation for efficiency)
 */
export async function translateBatch(
  texts: string[],
  from: LanguageCode,
  to: LanguageCode
): Promise<string[]> {
  if (from === to) return texts;
  
  try {
    const results = await Promise.all(
      texts.map((text) => translate(text, from, to))
    );
    return results;
  } catch (error) {
    console.error('Batch translation failed:', error);
    return texts;
  }
}

/**
 * Check if translation is available (package installed)
 */
export async function isTranslationAvailable(): Promise<boolean> {
  const mlkit = await getTranslator();
  return mlkit !== null;
}

/**
 * Delete downloaded language model to free space
 */
export async function deleteLanguageModel(language: LanguageCode): Promise<void> {
  try {
    const mlkit = await getTranslator();
    if (!mlkit) return;

    const code = ML_KIT_CODES[language];
    await mlkit.deleteModel(code);
    console.log(`${language} model deleted`);
  } catch (error) {
    console.error(`Failed to delete ${language} model:`, error);
  }
}
