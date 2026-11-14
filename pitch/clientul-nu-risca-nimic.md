# SKILLIO: platforma în care clientul nu riscă nimic

## Demo (3 minute, mod prezentare: `/?mod=prezentare`)
1. **Agentul Anei**: „Vreau să renovez baia” → 4 etape în ordinea corectă, cost total, câte o cerere pe etapă.
2. **Ionel trimite oferta** → Ana plătește. Banii se blochează (+5% taxă de protecție, vizibilă).
3. **Ionel ajunge și reconfirmă prețul** cu poză + motiv. AI-ul dă doar o părere (interval de preț).
4. **Ana decide**: acceptă, sau refuză și plătește doar deplasarea (40 lei). Restul se întoarce instant.
5. **Chat**: scrie un număr de telefon → SKILLIO îl ascunde. Numerele rămân private în ambele sensuri.
6. **Confirmare + 24 h**: ambii confirmă, banii mai stau blocați 24 h. Oricine (și meșterul) poate deschide dispută.
   Admin → Mediere: un **om** decide, pe baza pozelor, chatului și cronologiei. Dă ceasul +1 zi: banii pleacă.
7. **SOS 45 lei**: apel video cu un meșter (35 lei la meșter), doar instrucțiuni de siguranță, înregistrat cu acord.

## De ce nu e „încă un Meseriașul Meu”
Fiecare piesă există undeva (Urban Company: taxă de inspecție cu drept de refuz; TaskRabbit: numere ascunse;
Frontdoor: video cu experți), dar nimeni nu le pune împreună cu **prețul reconfirmat la fața locului și verificat
de AI** și cu **mediatori umani plătiți din taxa de protecție**. Meșterii nu plătesc lead-uri.

## Model de business
10% de la meșter + 5% taxă de protecție de la client = 15%. Pe o lucrare de 300 lei: 45 lei, ~6 lei procesare plată.
Chiar la 20% dispute (60 lei de om/dispută), rămân ~27 lei/lucrare. Comparație: Airtasker 10-20%, Urban Company 8,5-25%.

## Ce schimbăm pentru producție
- **Plata**: în demo, banii se blochează pe Solana devnet. În producție, escrow-ul trece printr-un procesator
  autorizat (Stripe Connect, Mangopay sau Lemonway, ca Hemea în Franța), fără licență proprie de instituție de plată.
- **Apelul SOS**: în demo, cameră video Jitsi. În producție, un serviciu WebRTC cu înregistrare (ex. Daily, Twilio Video),
  stocare în UE, ștergere automată la 30 de zile, consimțământ explicit al ambilor (GDPR).
- **Login**: Auth0 (deja integrat), cod pe SMS sau email.
- **Lansare**: un cartier din Timișoara, 2-3 meserii, apoi extindere.
