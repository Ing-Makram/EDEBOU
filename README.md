# Edebou

Logiciel de gestion pour **dépôts d'eau et de boissons** en Tunisie. Il remplace le cahier et le stylo : ventes, crédit
clients, consignes (caisses et bouteilles en verre), stock, livraisons et fournisseurs.

- Licence unique, sans abonnement ni hébergement.
- Fonctionne **entièrement hors ligne**.
- Interface simple, gros boutons, **arabe (droite-à-gauche) et français**.
- Montants en **millimes** (entiers) : le dinar tunisien a 3 décimales.

## Architecture

| Partie | Technologie | Rôle |
|---|---|---|
| [`backend/`](backend) | Django + Django REST Framework + SQLite | API locale installée sur le PC du dépôt ; contient la base et **toute la logique métier** |
| [`app/`](app) | Flutter (Windows, puis Android) | Affiche et envoie ; aucune logique métier |
| [`docs/`](docs) | Markdown | [`api.md`](docs/api.md) (référence de l'API), [`decisions.md`](docs/decisions.md) (décisions, une ligne chacune) |

Principes : l'historique est en ajout seul (une annulation crée une écriture inverse) ; dette, consignes et stock sont
**calculés à partir des mouvements**, jamais stockés ; une vente met à jour stock, dette et consignes dans **une seule
transaction**. Détails dans [`CLAUDE.md`](CLAUDE.md).

## État d'avancement

**Phase 1 (cœur sur PC)**

| | Étape | État |
|---|---|---|
| ✅ | Projet Django, modèles, utilisateurs avec PIN et rôles (gérant, caissier, livreur) | fait |
| ✅ | API produits et clients | fait |
| ✅ | Ventes (comptant / crédit, prix par type de client, stock, dette, consignes en une transaction, annulation, idempotence) | fait |
| ✅ | Paiements de dettes et relevé client | fait |
| ✅ | Consignes (mouvements manuels, synthèse, retards en FIFO) | fait |
| ✅ | Stock (entrées, ajustements, alerte de seuil, historique) | fait |
| ✅ | Gestion des utilisateurs, changement de PIN, déconnexion | fait |
| 🟡 | Application Flutter Windows : connexion, paramètres, accueil par rôle, arabe/français | squelette fait |
| ⬜ | Écrans caisse, clients, consignes, stock | à faire |
| ⬜ | Impression ticket 80 mm et facture A4 · sauvegarde automatique · relance WhatsApp | à faire |

Phases suivantes : mobile Android et synchronisation Wi-Fi (2), alertes, prévisions et rapports (3), licence,
installateur Windows et notice (4).

## Démarrer

Prérequis : Python 3.12 ; pour l'application Windows, Flutter 3.47 et **Visual Studio 2022 avec la charge de travail
« Développement Desktop en C++ »**.

**1. Backend**
```powershell
cd backend
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python manage.py migrate
.venv\Scripts\python manage.py createmanager Papa --pin 2468   # premier gérant (une seule fois)
.venv\Scripts\python manage.py runserver 127.0.0.1:8000
```

**2. Application**
```powershell
cd app
flutter pub get
flutter run -d windows
```
Connexion avec le nom et le PIN du gérant. Si le serveur n'est pas à `http://127.0.0.1:8000`, régler l'adresse dans
**Paramètres** (« Tester la connexion »). Plus de détails : [`app/README.md`](app/README.md).

## Tests

```powershell
cd backend
.venv\Scripts\python manage.py test     # 282 tests : règles métier, rôles, cohérence des soldes

cd ..\app
flutter analyze
flutter test                            # 124 tests : client API, contrats docs ↔ app ↔ serveur, écrans, arabe RTL, thème
```

Chaque règle métier (dette, consigne, stock, prix par type de client, rôles) a ses tests automatiques.

## Documentation

- [`docs/api.md`](docs/api.md) : tous les endpoints (méthode, chemin, rôles, exemples de requête et de réponse, formats
  d'erreur, codes d'erreur métier).
- [`docs/decisions.md`](docs/decisions.md) : décisions importantes, une ligne chacune.
- [`CLAUDE.md`](CLAUDE.md) : contexte produit, règles de travail et plan de développement.
