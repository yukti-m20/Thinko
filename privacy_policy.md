# Privacy Policy

**Thinko — Voice STEM Learning Companion**
**Effective Date:** September 19, 2026
**Last Updated:** September 19, 2026

---

## 1. Overview

Thinko ("we," "our," or "the App") is committed to protecting the privacy of children. This Privacy Policy explains what information Thinko collects, how it is used, and the rights parents and guardians have under applicable law — including the **Children's Online Privacy Protection Act (COPPA)**, the **California Consumer Privacy Act (CCPA)**, and the **EU General Data Protection Regulation (GDPR)** where applicable.

Thinko is a voice-only STEM learning companion for students aged 8–14. There is no screen, no user account, and no persistent profile.

---

## 2. Information We Collect

### 2.1 Information We Do NOT Collect

- Full name, email address, phone number, or physical address
- Persistent user identifiers or cookies
- Voice audio recordings (audio is processed locally and never transmitted)
- Payment or financial information
- Location data

### 2.2 Information Processed During a Session

| Data | How It Is Processed | Stored by Us? |
|---|---|---|
| Voice audio | Transcribed on-device using faster-whisper (open source). Audio never leaves the device. | No |
| Text transcript of student speech | Sent over HTTPS to OpenRouter's API to generate an educational response. | No — session only |
| LLM response text | Sent over HTTPS to Deepgram's API for text-to-speech synthesis. | No — session only |
| Conversation history | Held in local memory for multi-turn context within a single session. Cleared when the session ends. | No |

We do not log, store, sell, or share any session data beyond what is required to operate the real-time pipeline described above.

---

## 3. Children's Privacy (COPPA)

Thinko is directed to children under 13 and is designed in full compliance with COPPA.

3.1 **Parental consent is required** before a child under 13 uses the App. By allowing your child to use Thinko, you provide verifiable parental consent.

3.2 We do not collect personal information from children beyond what is strictly necessary for the educational session to function.

3.3 **Parental rights under COPPA:**
- **Review:** You may request a description of the type of information collected from your child.
- **Delete:** You may request deletion of any information by contacting us at privacy@Thinko.app.
- **Withdraw consent:** You may withdraw consent at any time by discontinuing use. No account deletion is necessary since no account is created.

3.4 We do not condition a child's participation on the disclosure of more personal information than is reasonably necessary.

---

## 4. How We Use Information

The text transcript is used solely to:
- Generate an age-appropriate, educationally guided response via OpenRouter.
- Convert that response to speech via Deepgram.

We do not use any session content for:
- Advertising or marketing
- Profiling or behavioral tracking
- Training our own AI models
- Sharing with third parties beyond the two processors named above

---

## 5. Third-Party Data Processors

Thinko relies on two external services to function. These processors receive the minimum data necessary:

### 5.1 OpenRouter (openrouter.ai)
- **Data sent:** Text transcript of student query + system prompt
- **Purpose:** Generate an educational LLM response
- **Retention:** Per OpenRouter's data retention policy (see openrouter.ai/privacy)
- **Note:** We use the `openrouter/free` tier; queries may be routed to various underlying model providers

### 5.2 Deepgram (deepgram.com)
- **Data sent:** Text of the LLM response to be spoken aloud
- **Purpose:** Convert text to speech audio
- **Retention:** Per Deepgram's data retention policy (see deepgram.com/privacy)

We have no control over the internal data practices of these processors once data is transmitted. We encourage parents to review their privacy policies.

---

## 6. Data Security

- Voice audio never leaves the device.
- All API calls to OpenRouter and Deepgram are made over HTTPS with API key authentication.
- API keys are stored in environment variables and never exposed in the codebase or to the student.
- No database, cloud storage, or logging infrastructure is used by Thinko itself.

---

## 7. Data Retention

Thinko retains no data. Conversation history exists only in the local process memory and is cleared when the session ends (Ctrl+C or process termination).

---

## 8. Your Rights

Depending on your jurisdiction, you may have the right to:

- **Access** information we hold about your child (we hold none persistently)
- **Delete** any data (no account or profile exists to delete)
- **Object** to processing (discontinue use at any time)
- **Portability** (no stored data to export)

For GDPR users: our legal basis for processing is **legitimate interest** in providing the requested educational service, and for children under 13 in the EU, **parental consent**.

For CCPA users: we do not sell personal information.

---

## 9. Changes to This Policy

We may update this Privacy Policy to reflect changes in our practices or legal requirements. We will post the updated policy in the project repository. For material changes affecting children's data, we will make reasonable efforts to notify parents.

---

## 10. Contact

For privacy questions, parental data requests, COPPA consent withdrawal, or GDPR/CCPA requests:

**Privacy contact:** privacy@Thinko.app
**Project repository:** https://github.com/Chaitanya-purohit/Thinko

We will respond to verifiable parental requests within 30 days.

---

*Thinko collects the minimum necessary to teach. Nothing more.*
