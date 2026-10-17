# Edebou – Logiciel de gestion pour dépôts d'eau (Tunisie)

## Contexte
Edebou remplace le cahier et le stylo dans les dépôts d'eau et de boissons (eau minérale, boissons gazeuses, jus). Il gère les ventes, le crédit clients, les consignes (caisses et bouteilles en verre), le stock, les livraisons et les fournisseurs.

- Vendu en **licence unique de 400 DT**, sans abonnement ni hébergement.
- Doit fonctionner **entièrement hors ligne**.
- Utilisateurs : gérants peu à l'aise avec l'informatique. L'interface doit être simple, avec de gros boutons et peu de texte.
- Langues : arabe (RTL) et français.
- Projet à but de profit rapide : privilégier la **vitesse de livraison** et la simplicité, pas la perfection.

## Architecture
- **Flutter** : une seule base de code pour l'application Windows (caisse et gestion) et Android (gérant, livreurs).
- **Django + Django REST Framework + SQLite** : API locale installée sur le PC du dépôt. Elle contient la base et toute la logique métier.
- Le mobile se connecte au PC par le Wi-Fi local (QR code scanné une fois). Aucun serveur externe.
- Sauvegarde quotidienne de la base SQLite sur clé USB ou dossier choisi.
- Licence : clé d'activation liée à la machine, vérifiée hors ligne.
- Impression : ticket thermique 80 mm et facture A4.

## Structure du dépôt
```
edebou/
  backend/     # Django (API, modèles, logique métier, tests)
  app/         # Flutter (Windows + Android)
  docs/        # cahier des charges, décisions
  CLAUDE.md
```

## Règles de travail
- Travailler par **petites tâches** : un modèle, puis son API, puis son écran, puis ses tests. Ne pas mélanger plusieurs fonctions dans un même changement.
- **Toute logique métier est dans Django**, jamais dans Flutter (stock, dettes, consignes, prix). Flutter affiche et envoie.
- Écrire des **tests automatiques** pour chaque règle métier (dette, consigne, stock, prix par type de client). Lancer les tests avant de dire qu'une tâche est finie.
- **Montants en millimes** : le dinar tunisien a 3 décimales. Stocker des entiers (millimes), ne jamais utiliser de flottants pour l'argent.
- Chaque mouvement (vente, paiement, consigne, stock) est **enregistré, jamais écrasé** : on ajoute une ligne, on ne modifie pas l'historique. Une annulation crée une écriture inverse.
- Une vente met à jour **dans une seule transaction** : stock, dette client et consignes. Tout réussit ou rien.
- Toutes les chaînes de l'interface passent par les fichiers de traduction (arabe et français). Pas de texte écrit en dur.
- L'interface doit supporter l'écriture de droite à gauche (arabe).
- Utilisateurs avec code PIN et rôles : gérant (tout), caissier (vendre, encaisser), livreur (ses livraisons uniquement).
- Ne pas ajouter de fonctions non demandées. Demander avant de sortir du périmètre de la phase en cours.
- Les décisions importantes vont dans `docs/decisions.md`, en une ligne chacune.

## Modèle de données (phase 1)
- **Produit** : nom, marque, catégorie (eau, gazeux, jus), unités (palette, pack, unité) avec leurs conversions, prix par type de client, consignable (oui/non), seuil minimum.
- **Client** : nom, téléphone, type (détail, café, grossiste), plafond de crédit.
- **Vente** et **LigneVente** : client, produits, quantités, prix appliqué, mode (comptant ou crédit), utilisateur, date.
- **Paiement** : client, montant, date, vente liée (optionnelle).
- **MouvementConsigne** : client, type de consigne (caisse, bouteille verre), sorties et retours.
- **MouvementStock** : produit, quantité (positive ou négative), motif (vente, achat, inventaire, perte).
- **Utilisateur** : nom, PIN, rôle.

Le solde de dette, le solde de consignes et le stock sont **calculés à partir des mouvements**, pas stockés séparément.

## Plan de développement

### Phase 1 – Cœur sur PC (à livrer en premier)
1. Projet Django, modèles, migrations, utilisateurs avec PIN et rôles.
2. API produits et clients (création, liste, modification).
3. Vente : panier, comptant ou crédit, prix selon le type de client, mise à jour du stock, de la dette et des consignes en une transaction.
4. Paiements de dettes (partiels) et solde client.
5. Consignes : sorties, retours, solde par client.
6. Stock : entrées, sorties, inventaire, alerte de seuil.
7. Projet Flutter Windows : connexion PIN, écran caisse, liste clients, fiche client.
8. Écrans consignes et stock.
9. Impression ticket 80 mm et facture A4.
10. Sauvegarde automatique de la base.
11. Relance WhatsApp pré-remplie (lien avec message prêt).
12. Arabe et français.

**Critère de fin de phase 1** : un gérant peut vendre, noter les dettes et les consignes, voir son stock, et ne plus utiliser son cahier.

### Phase 2 – Mobile
Application Android, synchronisation Wi-Fi local avec QR code, livraisons, achats fournisseurs.

### Phase 3 – Intelligence
Alertes (stock bas, dettes en retard, caisses non rendues), prévisions de commandes, classement des clients, rapports PDF et Excel, import depuis Excel.

### Phase 4 – Commercialisation
Licence liée à la machine, installateur Windows (Django emballé avec PyInstaller), notice en arabe et en français.

## Points à tester tôt
- Imprimante thermique 80 mm sur du matériel réel.
- Emballage de Django dans l'installateur Windows.
- Synchronisation entre PC et téléphone sur le Wi-Fi d'un vrai dépôt.

## Commandes
Backend (depuis `backend/`, Python 3.12, environnement `.venv`) :
- Premier gérant : `.venv\Scripts\python manage.py createmanager <nom> --pin <PIN>`
- Lancement : `.venv\Scripts\python manage.py migrate` puis `.venv\Scripts\python manage.py runserver 127.0.0.1:8000`
- Tests : `.venv\Scripts\python manage.py test` (réglages de test automatiques, hasher rapide)

App Flutter (depuis `app/`, SDK dans `C:\src\flutter`, à mettre dans le PATH ; Visual Studio « Desktop development with C++ » requis pour compiler) :
- Lancement : `flutter run -d windows` (backend démarré)
- Vérifications : `flutter analyze` puis `flutter test`
- Référence de l'API : `docs/api.md` ; détails dans `app/README.md`

À compléter : construction de l'installateur.
