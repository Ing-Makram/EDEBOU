# Edebou — application Flutter (Windows)

Caisse et gestion pour dépôts d'eau. Elle affiche et envoie ; **toute la logique métier est dans le backend Django**
(`../backend`). Référence de l'API : [`../docs/api.md`](../docs/api.md).

## Prérequis (Windows)

- Flutter 3.47 (ici `C:\src\flutter`) ; ajouter `C:\src\flutter\bin` au PATH.
- Visual Studio 2022 avec la charge de travail **« Développement Desktop en C++ »** (obligatoire pour compiler
  l'application Windows ; `flutter doctor` doit afficher une coche sur « Visual Studio »).
- Python 3.12 pour le backend.

## Lancer

1. Backend (dans un premier terminal) :
   ```powershell
   cd backend
   .venv\Scripts\python manage.py migrate
   .venv\Scripts\python manage.py createmanager Papa --pin 2468   # une seule fois : premier gérant
   .venv\Scripts\python manage.py runserver 127.0.0.1:8000
   ```
2. Application (dans un second terminal) :
   ```powershell
   cd app
   flutter pub get
   flutter run -d windows
   ```
   Premier écran : connexion (nom + PIN). Si le serveur n'est pas à `http://127.0.0.1:8000`, ouvrir l'icône
   Paramètres (engrenage) et utiliser « Tester la connexion ».

## Vérifier

```powershell
cd app
flutter analyze
flutter test
```

Test contre un vrai serveur (ignoré par défaut, base jetable recommandée) :

```powershell
$env:EDEBOU_BACKEND_URL = "http://127.0.0.1:8000"
flutter test test/backend_contract_test.dart
```

## Structure

```
lib/
  core/        client API (api_client, api_error, business_code), thème, stockage local, providers, widgets communs
  features/    auth · home · sales · clients · consignments · stock · settings   (data / application / presentation)
  l10n/        app_fr.arb (modèle) et app_ar.arb → AppLocalizations (généré : flutter gen-l10n)
test/          client API, contrats (docs ↔ app ↔ serveur), thème, écrans (connexion, accueil, paramètres, session)
```

## Règles

- Aucun texte en dur : tout passe par `lib/l10n/*.arb` (français + arabe) ; un test échoue sinon.
- Les erreurs du serveur sont traduites par `core/errors/error_messages.dart` à partir du `code` (jamais du `detail`).
- Pas de calcul de prix, total, stock, dette ou consigne dans l'app.
