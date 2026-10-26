# Aile Bütçe Takip v10 — okunabilir grafikler ve ay kapanışı

## Yapılanlar
- Primary buttons use dark navy-blue with white high-contrast text.
- Category summary is in the Ekstre İçe Aktar page; category and merchant amounts show in visible chart labels and tables without clicking/hovering.
- Home finance chart and Harcama Analizi / Ay Karşılaştırma charts also show value labels directly.
- The separate transaction ledger is absent from Genel Bakış; detailed rows remain in import review and analysis where they are useful.
- The selected-month "Ayı kapat" button is in Ekstre İçe Aktar. A confirmation checkbox is required before closure. Closed months block uploads and budget/card-total edits; month can be reopened from the same page.
- Firebase rules remain user-scoped by ownerUid. Do not make the Firestore database public.

## Deploy
Replace GitHub files `app.py`, `requirements.txt`, and `packages.txt` with those in this package. Then publish `firestore.rules` in Firebase Console → Firestore Database → Rules. Refresh/redeploy Streamlit.

Bank statements and the processed Excel workbook are intentionally not bundled, since the GitHub repository is public. Upload the processed Excel only through the app's import module if needed.

Python syntax checked. Live Firebase/Streamlit end-to-end verification has not been performed.
