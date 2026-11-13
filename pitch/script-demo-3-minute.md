# Scriptul demo: 3 minute

**Pregătire (cu 10 minute înainte):**

- `porneste.bat`, apoi deschide http://localhost:8501/?mod=prezentare pe ecranul mare. Zoom-ul browserului la 80-90%, ca
  să se vadă ambele telefoane și butoanele de timp.
- Apasă **Resetează demo**. Ține pe desktop o poză cu o chiuvetă care curge (sau folosește-o pe cea din telefon).
- Verifică internetul (hărțile, Gemini, Solana). Dacă nu e internet, totul merge pe „simulat”, iar scriptul rămâne același.
- Într-un tab separat: Solana Explorer deschis (devnet), ca să nu aștepți încărcarea.
- Cine vorbește: **A** (povestea și business), **B** (dă click-urile). Dacă ești singur, citește doar textul A.

---

### 0:00 – 0:25 · Problema

**A:** „Ți-a curs vreodată apă de sub chiuvetă la 9 seara? Suni la trei numere de pe OLX, unul nu răspunde, unul vine
peste trei zile, al treilea îți cere banii înainte. Și dacă după o săptămână curge iar, banii sunt duși.
În Timișoara, meșterii buni se găsesc din recomandări. Noi am făcut recomandarea măsurabilă.”

### 0:25 – 1:05 · Clientul cere (telefonul Anei)

**B:** Ana → **Cerere** → scrie „Curge apă de sub chiuvetă” → adaugă poza → **Analizează cu AI**.

**A:** „Ana descrie problema și pune o poză. Gemini se uită la poză și îi spune că are nevoie de un instalator,
cât de grav e și cam cât ar costa.” *(B apasă **Ascultă**)* „Și o poate și asculta, cu ElevenLabs, pentru cine
nu citește ușor de pe telefon.”

**B:** bifează **Urgent (+15%)** → trimite.

**A:** „E urgent, deci plătește cu 15% mai mult și apare primul la meșteri.”

### 1:05 – 1:40 · Meșterul ofertează (telefonul lui Ionel)

**A:** „În 2 secunde apare la Ionel, portocaliu, sus.” **B:** Ionel deschide → preț + oră din calendar → **Trimite oferta**.

**B:** Ana → ofertele. **A:** „Ana compară ofertele după **Trust Score**, un scor de la 0 la 100 din 7 factori pe care
îi poți vedea pe rând: note, dacă lucrările lui mai țin după o lună, dacă vine la oră, verificarea numărului și a SIM-ului.
Nu e o medie de stele pe care o poate umfla oricine.” **B:** deschide detaliile scorului 2 secunde, apoi **Acceptă oferta**.

### 1:40 – 2:25 · Plata blocată și sosirea

**B:** Ana confirmă ora → **Plătește**. **A:** „Banii nu ajung la Ionel. Stau blocați în SKILLIO. Și ca să nu ne
credeți pe cuvânt, blocarea e o tranzacție publică pe Solana.” *(B arată cardul **Plată verificabilă pe blockchain**.)*

**B:** Ionel → **Am ajuns**. **A:** „Rețeaua confirmă că Ionel e chiar la adresă. Dacă apăsa de acasă...”
*(B apasă **Ionel e departe de adresă**, apoi iar **Am ajuns** → apare refuzul)* „...sistemul nu-l crede.”
*(B oprește „Ionel e departe de adresă” și confirmă sosirea.)*

### 2:25 – 2:50 · Confirmare, bani, încredere în timp

**B:** Ionel → **Lucrare gata, cere confirmarea** → Ana → **Totul e în regulă**. **A:** „Abia acum Ionel primește 90%, noi 10%.
Pe Solana Explorer se vede împărțirea și amprenta lucrării, pașaportul ei.” *(B dă click pe link, 3 secunde.)*

**B:** **+6 zile**. **A:** „După o zi, o săptămână și o lună o întrebăm pe Ana: mai ține? Asta intră în scorul lui Ionel.
Un meșter bun urcă, unul care cârpește coboară, fără să depindă de cât de frumos vorbește.”

### 2:50 – 3:00 · Închidere

**A:** „SKILLIO: Find skills. Build trust. Am construit-o cu oamenii din Timișoara: [N] au răspuns la chestionar,
iar pagina «Ce e nou» arată ce am schimbat după ei. Mulțumim!”

---

**Dacă ceva nu merge:** nu te opri să depanezi. Spune „aici în mod normal...”, apasă **+1 zi** sau treci la pasul următor.
Toate ecranele arată „live” sau „simulat”, deci nu mințim niciodată juriul.

**Întrebări probabile de la juriu:**

- *De ce nu plata direct la meșter?* Pentru că blocarea banilor e chiar produsul: clientul plătește fără frică, meșterul
  știe că banii există. Comisionul de 10% plătește asta.
- *Ce e real pe blockchain?* Pe devnet, sume simbolice (1 leu = 0,0001 SOL). Pentru producție: aceeași logică, cu RON prin
  procesator de plăți și Solana doar pentru dovada publică (pașaportul lucrării).
- *Cum opriți plata pe sub mână?* Raportare din aplicație, confirmată de admin, scade Trust Score-ul. Meșterul pierde scorul
  construit, care valorează mai mult decât un comision.
- *Cine sunt primii utilizatori?* Un cartier (Elisabetin / Fabric), 10-15 meșteri recrutați direct, apoi recomandări.
