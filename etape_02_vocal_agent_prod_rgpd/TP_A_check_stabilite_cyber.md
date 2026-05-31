# TP A — Stabilité & Cybersécurité : Audit des Dépendances et de l'Image Docker

**Prérequis :** TP 01 et TP 02 complétés, Docker installé, agent buildé (`docker compose build`)
**Public :** Complément aux TP 03–05 — peut se faire en autonomie après TP 03

> **Version TP :** 1.0.0
> **Mis à jour :** 2026-05-28

---

> **Cas réel — Log4Shell (décembre 2021) :** La bibliothèque Apache Log4j, présente dans des millions d'applications Java dans le monde, contenait une vulnérabilité CVSS 10.0 (le maximum). Une simple ligne dans un champ texte d'une application permettait d'exécuter du code arbitraire à distance. Des milliers d'entreprises ont découvert qu'elles étaient exposées uniquement parce qu'une *dépendance transitive* — une bibliothèque tirée par une autre bibliothèque, pas installée directement — était vulnérable. Aucun de leurs développeurs n'avait jamais entendu parler de Log4j. **Leçon directe :** votre `requirements.txt` liste ce que vous installez. Il ne liste pas ce que vos dépendances installent elles-mêmes. Seul un scanner voit l'arbre complet.

---

## Objectifs

À la fin de ce TP, vous saurez :
- Scanner une image Docker pour détecter des CVE dans les paquets OS et Python
- Auditer les dépendances Python du projet avec `pip-audit`
- Analyser statiquement le code source Python avec `bandit`
- Intégrer ces trois contrôles dans le pipeline CI/CD GitHub Actions

---

## Partie 1 — Trivy : scanner l'image Docker (1h30)

> **Cas réel — XZ Utils (mars 2024) :** Un contributeur malveillant a passé deux ans à gagner la confiance de la communauté open-source avant d'insérer une backdoor dans `liblzma` (XZ Utils), une bibliothèque de compression présente dans la quasi-totalité des distributions Linux. La backdoor ciblait le démon SSH. Elle a été découverte par hasard par un ingénieur Microsoft qui remarquait des connexions SSH 500ms plus lentes que d'habitude. **Sans scan d'image systématique**, aucune alerte n'aurait été levée avant le déploiement.

### 1.1 Installer et découvrir Trivy

```bash
# Linux / WSL
curl -sfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh | sh -s -- -b /usr/local/bin
trivy --version
```

Trivy peut scanner plusieurs types de cibles :

| Cible | Commande |
|---|---|
| Image Docker | `trivy image <nom>` |
| Répertoire de code | `trivy fs .` |
| Dépôt git | `trivy repo <url>` |
| Secrets dans les fichiers | `trivy fs --scanners secret .` |

**Questions :**
1. Quelle est la différence entre un scan d'image (`trivy image`) et un scan de fichiers (`trivy fs`) ? Lequel détecte les vulnérabilités OS ?
2. Qu'est-ce qu'un CVE ? Qui les publie et qui attribue les scores CVSS ?
3. Un score CVSS de 9.8 (CRITICAL) signifie-t-il que vous êtes forcément en danger ? Quels facteurs contextuels réduisent le risque réel ?

### 1.2 Scanner l'image de l'agent

```bash
# Scan complet
trivy image --severity CRITICAL,HIGH --no-progress \
    etape_02_vocal_agent_prod_rgpd-agent:latest

# Résumé uniquement
trivy image --severity CRITICAL,HIGH --no-progress \
    etape_02_vocal_agent_prod_rgpd-agent:latest 2>&1 | grep "^Total"
```

**Questions :**
1. Combien de vulnérabilités CRITICAL trouvez-vous ? Dans quels paquets ?
2. Les vulnérabilités CRITICAL identifiées proviennent-elles de paquets OS (Debian) ou de paquets Python (pip) ?
3. Parmi les paquets vulnérables, lesquels sont dans votre `requirements.txt` directement ? Lesquels sont des **dépendances transitives** (tirées automatiquement par d'autres paquets) ?

### 1.3 Corriger les vulnérabilités Python

Les deux CVE CRITICAL sont dans `python-multipart`, une dépendance transitive de FastAPI. Elle n'est probablement pas dans votre `requirements.txt`.

**Exercice :**

a) Vérifiez la version actuellement installée dans l'image :
```bash
docker run --rm etape_02_vocal_agent_prod_rgpd-agent:latest \
    pip show python-multipart
```

b) Ajoutez un pin explicite dans `requirements.txt` :
```
python-multipart>=0.0.27
```

c) Rebuildez l'image et relancez Trivy :
```bash
docker compose build agent
trivy image --severity CRITICAL --no-progress \
    etape_02_vocal_agent_prod_rgpd-agent:latest 2>&1 | grep "^Total"
```

**Questions :**
1. Pourquoi fixer explicitement une dépendance transitive dans `requirements.txt` est-il une bonne pratique même sans vulnérabilité connue ?
2. Après le fix, le scan retourne-t-il encore des CRITICAL ?
3. Les 15 vulnérabilités HIGH dans les paquets Debian — pourquoi sont-elles plus difficiles à corriger que les vulnérabilités Python ?

### 1.4 Scan de secrets

Trivy peut aussi détecter des secrets (clés API, tokens) accidentellement copiés dans l'image.

```bash
trivy image --scanners secret --no-progress \
    etape_02_vocal_agent_prod_rgpd-agent:latest 2>&1 | grep -A5 "Secrets"
```

**Questions :**
1. Des secrets sont-ils détectés dans l'image ? Si oui, dans quel fichier ?
2. Comment un secret peut-il se retrouver dans une image Docker sans qu'on s'en rende compte ? (hint : `COPY . .` dans un Dockerfile)
3. Quelle ligne ajouter dans `.dockerignore` pour s'assurer que `.env` n'est jamais copié dans l'image ?

---

## Partie 2 — pip-audit et Bandit : auditer le code Python (1h)

> **Cas réel — PyPI malicious packages (2023–2025) :** Des centaines de paquets malveillants sont régulièrement publiés sur PyPI avec des noms quasi-identiques à des paquets légitimes (`reqeusts` au lieu de `requests`, `coloramma` au lieu de `colorama`). Ces paquets exfiltrent des variables d'environnement — dont les clés API — au premier `pip install`. C'est le **typosquatting**. Sans audit régulier des dépendances, une faute de frappe dans un `pip install` peut compromettre toute l'infrastructure.

### 2.1 pip-audit : vulnérabilités dans les dépendances Python

`pip-audit` interroge la base de données PyPI Advisory et le NVD pour détecter les versions vulnérables installées.

```bash
pip install pip-audit

# Scanner les dépendances du projet
pip-audit -r requirements.txt

# Format JSON pour intégration CI
pip-audit -r requirements.txt --format json -o audit-report.json
```

**Questions :**
1. `pip-audit` et Trivy détectent-ils les mêmes vulnérabilités Python ? Y a-t-il des différences ? Lequel est plus exhaustif ?
2. Quelle est la différence entre `pip-audit -r requirements.txt` et `pip-audit` sans argument ?
3. Pourquoi est-il utile d'avoir les deux outils (Trivy pour l'image complète, pip-audit pour les dépendances) plutôt qu'un seul ?

### 2.2 Bandit : analyse statique de sécurité du code

`bandit` analyse le code Python source à la recherche de patterns dangereux : `eval()`, `subprocess` avec entrée utilisateur, `assert` utilisé comme contrôle de sécurité, secrets en dur, etc.

```bash
pip install bandit

# Scanner le dossier src/
bandit -r src/ -ll

# Rapport détaillé
bandit -r src/ -f txt -o bandit-report.txt
```

Les niveaux de sévérité sont `LOW`, `MEDIUM`, `HIGH` × `LOW`, `MEDIUM`, `HIGH` (confiance). `-ll` affiche uniquement HIGH severity.

**Questions :**
1. Combien de findings `HIGH severity` bandit trouve-t-il dans `src/` ?
2. Ouvrez `bandit-report.txt`. Pour chaque finding HIGH : est-ce un vrai risque dans ce contexte, ou un faux positif ?
3. Bandit signale-t-il l'utilisation de `subprocess` ou `eval` dans le code ? Si oui, dans quel fichier et quel est le risque ?
4. Quelle est la limite fondamentale de l'analyse statique (SAST) comparée à un test dynamique (DAST) ?

### 2.3 Interpréter les résultats ensemble

Remplissez ce tableau de synthèse :

| Outil | Ce qu'il détecte | Ce qu'il ne détecte pas |
|---|---|---|
| Trivy (image) | | |
| pip-audit | | |
| Bandit | | |
| Tests pytest (TP 03) | | |

**Questions :**
1. Un projet qui passe les 4 outils à zéro finding est-il sécurisé ? Justifiez.
2. Dans une équipe, à quelle fréquence lanceriez-vous chacun de ces outils ? (à chaque commit, quotidiennement, à chaque release ?)
3. Ces outils auraient-ils détecté la vulnérabilité Log4Shell si elle avait été dans une dépendance Python ? Et le backdoor XZ Utils ?

---

## Partie 3 — Intégrer dans la CI/CD (1h)

> **Cas réel — Equifax (2017) :** La violation de données d'Equifax (147 millions de personnes, numéros de sécurité sociale, dates de naissance) a été causée par une vulnérabilité dans Apache Struts (CVE-2017-5638, CVSS 10.0) connue et patchée depuis **2 mois**. Equifax n'avait pas de processus automatisé pour détecter les dépendances vulnérables. Le patch existait. Personne ne l'avait appliqué. **Un scan automatisé en CI aurait bloqué le déploiement** de l'image vulnérable dès le build.

### 3.1 Ajouter Trivy au workflow GitHub Actions

Ouvrez `.github/workflows/release.yml` et ajoutez un job de scan de sécurité **avant** le job de déploiement.

```yaml
  security-scan:
    name: Security Scan
    runs-on: ubuntu-latest
    needs: test          # s'exécute après les tests, avant le déploiement
    steps:
      - uses: actions/checkout@v4

      - name: Build image
        run: docker compose build agent

      - name: Run Trivy vulnerability scanner
        uses: aquasecurity/trivy-action@master
        with:
          image-ref: etape_02_vocal_agent_prod_rgpd-agent:latest
          format: table
          severity: CRITICAL
          exit-code: '1'        # fait échouer le pipeline si des CRITICAL sont trouvées
          ignore-unfixed: true  # ignore les CVE sans patch disponible

      - name: Run pip-audit
        run: |
          pip install pip-audit
          pip-audit -r requirements.txt
```

**Questions :**
1. Pourquoi `exit-code: '1'` est-il important ? Que se passerait-il sans ce paramètre ?
2. `ignore-unfixed: true` ignore les vulnérabilités sans correctif disponible. Est-ce une bonne ou mauvaise pratique ? Argumentez.
3. Le job `security-scan` est configuré avec `needs: test`. Pourquoi ne pas le mettre en parallèle des tests ?
4. Si une CVE CRITICAL est découverte un vendredi soir, quelle décision prenez-vous : bloquer le déploiement, déployer quand même, ou déployer avec un ticket d'urgence ouvert ? Quels facteurs influencent cette décision ?

### 3.2 Fichier `.trivyignore` — gérer les faux positifs

Certaines CVE sont inévitables (paquets OS sans patch, bibliothèques système figées) ou non exploitables dans votre contexte. Trivy permet de les ignorer explicitement.

Créez `.trivyignore` à la racine du projet :

```
# CVE sans correctif disponible dans Debian 13 à ce jour
# Paquets système — non exploitables depuis l'application Python
# À réévaluer à chaque release
```

**Exercice :** identifiez une vulnérabilité HIGH dans les paquets Debian qui n'a pas de fix disponible (`Fixed Version` vide dans le tableau Trivy). Ajoutez son CVE-ID dans `.trivyignore` avec un commentaire justifiant la décision.

**Questions :**
1. Qui dans l'équipe devrait avoir le droit de modifier `.trivyignore` ? Pourquoi versionner ce fichier dans git ?
2. Quelle est la différence entre ignorer une CVE parce qu'elle est non exploitable et l'ignorer parce qu'on n'a pas eu le temps de la corriger ?
3. Comment éviter que `.trivyignore` ne devienne un fichier "poubelle" où on enterre tous les problèmes ?

---

---

## Partie 4 — Panorama des autres outils (30min — découverte)

Le trio Trivy + pip-audit + Bandit couvre l'essentiel. Voici les outils complémentaires que vous rencontrerez en entreprise :

| Outil | Type | Ce qu'il fait de différent |
|---|---|---|
| **hadolint** | Linter Dockerfile | Détecte les mauvaises pratiques dans le `Dockerfile` lui-même (ex : `RUN apt-get` sans `--no-install-recommends`, `COPY . .` avant `pip install`, absence d'`USER` non-root) |
| **gitleaks** | Secret scanning git | Contrairement à `trivy fs --scanners secret` qui scanne les fichiers *actuels*, gitleaks scanne **tout l'historique git** — un secret commité puis supprimé reste dans l'historique |
| **semgrep** | SAST avancé | Alternative à bandit avec plus de règles, support multi-langages, règles personnalisables en YAML |
| **Safety** | Dépendances Python | Alternative à pip-audit, plus simple, utilise la Safety DB — utile en pre-commit hook |
| **docker scout** | Image Docker | Intégré à Docker Desktop, même principe que Trivy mais avec interface graphique |

**Exercice hadolint (10 min) :**
```bash
docker run --rm -i hadolint/hadolint < Dockerfile
```

**Questions :**
1. hadolint détecte-t-il des problèmes dans le `Dockerfile` de ce projet ? Lesquels ?
2. L'absence d'instruction `USER` dans un Dockerfile signifie que le container tourne en `root`. Quel est le risque si un attaquant parvient à exécuter du code dans le container ?
3. `gitleaks` est particulièrement utile lors de l'onboarding d'un nouveau projet. Pourquoi ?

---

## Rendu attendu

- [ ] `trivy image` retourne **0 CRITICAL** après correction de `requirements.txt`
- [ ] `pip-audit -r requirements.txt` retourne **0 vulnérabilité**
- [ ] `bandit -r src/ -ll` : chaque finding HIGH est documenté (vrai risque ou faux positif justifié)
- [ ] Le job `security-scan` est ajouté dans `.github/workflows/release.yml`
- [ ] `.trivyignore` existe avec au moins une entrée commentée
- [ ] *(Bonus)* `trivy fs --scanners secret .` retourne 0 secret détecté
- [ ] *(Bonus)* Ajouter `bandit` au workflow CI avec `exit-code 1` sur les findings HIGH
