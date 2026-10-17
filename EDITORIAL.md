# Editorial rules

These rules are read by the weekly drafting routine. The validator (`python3 tools/validate.py`) enforces every
rule that can be checked by machine.

1. **Mass-market and free.** Only tools a beginner can use for free on an Android phone or the web.
   - No paid-only tools.
   - No APK or sideload links.
   - No tools that need a credit card to start.
2. **Safe.**
   - No adult content, political content, medical or legal *advice*, or financial tips.
   - Every upload of a face, voice or ID needs a `privacyNote`.
   - Never suggest uploading Aadhaar, PAN, bank or OTP screenshots.
3. **True and sourced.** Every `news` item has a reputable source. Claims about features must match the tool's
   current free tier.
4. **Simple language.**
   - Write the Hindi in everyday spoken Hindi; English tech words in Devanagari are fine ("ऐप", "फ़ोटो").
   - No jargon without a one-line explanation.
5. **Each week's batch:**
   - at least 1 `safety` item if a current AI scam exists,
   - at least 2 `howto` items,
   - at most 3 `trend` items.

## Field formats

- `minutes` (optional): how long the item takes, exactly `"N min"` with 1 or 2 digits, for example `"3 min"`
  (pattern `^\d{1,2} min$`). It is shared by both languages and the app shows it localised. No ranges, words
  or Hindi digits: `"3-5 min"`, `"about 3 min"` and `"५ मिनट"` are rejected.
- `label` (per language): the short name under the item's story circle, one or two words that name the story,
  for example "Birthday song" / "जन्मदिन गाना" or "Leave letter" / "छुट्टी अर्ज़ी". At most 14 characters
  after NFC (code points: every matra, virama and nukta counts, so Hindi labels need fewer words), plain text
  with no `*`. Write the Hindi in the same everyday voice as the rest of the item; don't translate the English.
  If one language has a label, the other must too. No two items may share a label in the same language.
  Required for items with `publishAt` on or after 2026-10-20; older items may omit it, and the app then cuts
  the title at a word boundary.
- `label`, `title`, `hook` and `imageAlt` are shown as plain text, so they must not contain `*`. Inline markdown
  (`**bold**`, `*italic*`, a literal `\*`) is allowed only in the longer text fields such as `steps`, `body`
  and `whatToDo`.

## Item lifetimes

`reviewBy` is the last day an item is shown. The validator caps how long an item may live after `publishAt`:

| Type | Maximum lifetime |
|---|---|
| `trend` | 28 days |
| `news` | 14 days |
| `howto` | no cap (evergreen; default about 180 days) |
| `safety` | no cap (evergreen; default about 180 days) |

Items are left out of the feed 30 days after `reviewBy`, and their source files move to `archive/items/`.

## Each language is written natively

`hi` and `en` are two separate pieces of writing about the same item. Do not translate one into the other.
The two must still agree on facts and on structure: the same number of steps and bullets, the same tool, the
same warning.

## Voice guide (Hindi)

Talk like a patient younger relative explaining something on the phone: short sentences, "आप", everyday words.

Good:
- "अपनी फ़ोटो चुनें और नीचे वाला मैसेज चिपका दें।"
- "यह ऐप मुफ़्त है, बस Google से लॉगिन करना होगा।"
- "अगर कोई OTP माँगे, तो कभी न बताएँ। बैंक कभी OTP नहीं माँगता।"

Bad:
- "अपने छायाचित्र का चयन कर निम्नलिखित निर्देश प्रविष्ट करें।" (bookish, stiff)
- "इस LLM-आधारित जेनरेटिव मॉडल का उपयोग करके प्रॉम्प्ट इंजीनियरिंग करें।" (jargon with no explanation)
- "यह बिल्कुल सुरक्षित है, चिंता की कोई बात नहीं!" (an unproven promise; say what to check instead)

## Images

- Images are generated or self-made only. No copyrighted screenshots, and no photos of real people.
- Format: WebP, at most 40 KB, with alt text in both languages (`imageAlt`).
- If you can't produce a safe image, ship the item without one. The app then shows the type's illustration.
