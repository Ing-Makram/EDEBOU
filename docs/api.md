# API Edebou — référence pour l'app Flutter

API REST locale (Django + DRF + SQLite), installée sur le PC du dépôt. Tout le monde parle JSON. Les exemples ci-dessous
viennent de vraies réponses du serveur (texte des messages en français, ids d'exemple).

- [Conventions](#conventions)
- [Authentification](#authentification)
- [Format des erreurs](#format-des-erreurs)
- [Rôles et accès (tableau récapitulatif)](#rôles-et-accès)
- Endpoints : [Utilisateurs](#utilisateurs) · [Produits](#produits) · [Clients](#clients) · [Ventes](#ventes) ·
  [Paiements](#paiements) · [Consignes](#consignes) · [Stock](#stock)
- [Codes d'erreur métier](#codes-derreur-métier)
- [Conseils pour Flutter](#conseils-pour-flutter)

---

## Conventions

| Sujet | Règle |
|---|---|
| URL de base | `http://<ip-du-pc>:<port>/api/` (le slash final est obligatoire) |
| Corps | `Content-Type: application/json` |
| Montants | **entiers en millimes** (1 DT = 1000 millimes ; `4200` = 4,200 DT). Jamais de décimales. |
| Dates | ISO 8601 avec fuseau Tunis, ex. `2026-10-17T00:25:22.198615+01:00`. Filtres : `AAAA-MM-JJ` (jour de Tunis, bornes incluses). |
| Quantités de stock | toujours en **unités de base** (ex. bouteilles). Les ventes et entrées s'expriment dans une unité du produit (`unit`, `pack`, `palette`…) convertie par le serveur. |
| Listes | tableau JSON simple, **sans pagination**, trié du plus récent au plus ancien (clients et produits : par nom). |
| Prix | le client ne les envoie **jamais** : le serveur applique le tarif de l'unité selon le type du client. |
| Soldes | `debt`, `consign_holdings`, stock : **calculés** à partir des mouvements, jamais stockés. |
| Historique | on ajoute, on ne modifie pas. Une annulation crée une écriture inverse. Pas de `PUT/PATCH/DELETE` sur ventes, paiements, consignes, stock. |
| `request_id` | UUID généré par l'app **pour chaque action utilisateur** (vente, paiement, mouvement de consigne, entrée/ajustement de stock). Le renvoyer tel quel en cas de nouvel essai : le serveur renvoie l'écriture d'origine (**200** au lieu de **201**) sans rien recréer, même si le contenu envoyé diffère. |

Types de valeurs :

| Champ | Valeurs |
|---|---|
| `client.type` / prix | `retail` (détail), `cafe`, `wholesale` (grossiste) |
| `product.category` | `water`, `soda`, `juice` |
| `consign_type` | `crate` (caisse), `glass_bottle` (bouteille verre) |
| `sale.mode` | `cash` (comptant), `credit` |
| rôles | `manager` (gérant), `cashier` (caissier), `delivery` (livreur) |
| motifs de stock | `sale`, `purchase`, `inventory`, `loss` |

---

## Authentification

1. L'utilisateur choisit son nom et tape son PIN (4 à 6 chiffres).
2. `POST /api/auth/login/` renvoie un jeton.
3. Toutes les autres requêtes envoient `Authorization: Token <jeton>`.
4. Sans jeton valide : **401**. Rôle non autorisé : **403**.

Le jeton **n'expire pas** (l'expiration est prévue en phase 4) et reste le même tant que l'utilisateur ne se déconnecte
pas. `POST /api/auth/logout/` le supprime côté serveur : la connexion suivante en crée un nouveau. Un utilisateur désactivé,
ou dont le PIN a été réinitialisé par le gérant, perd sa session immédiatement (401). L'app stocke le jeton
localement (préférences de l'utilisateur Windows).

**Au démarrage de l'app** : si un jeton est enregistré, appeler `GET /api/auth/me/` ; **200** → afficher l'écran d'accueil
du rôle renvoyé ; **401** → oublier le jeton et afficher l'écran de connexion.

Le premier gérant se crée sur le PC : `python manage.py createmanager "<nom>"` (le PIN est demandé).

### POST `/api/auth/login/`  — accès : tous (sans jeton)

Limité à **10 essais par minute** (réponse **429** au-delà) : le PIN est court.

Requête :
```json
{ "name": "Papa", "pin": "2468" }
```
Réponse **200** :
```json
{ "token": "bfb0bf8a513ae05dc0920f9227aeb87f4739b111", "name": "Papa", "role": "manager" }
```
Erreur **401** (nom inconnu, PIN faux ou utilisateur désactivé) :
```json
{ "detail": "Nom ou PIN incorrect." }
```

### GET `/api/auth/me/`  — tout utilisateur connecté
Réponse **200** (le rôle est relu en base à chaque appel : une promotion se voit tout de suite) :
```json
{ "id": 1, "name": "Papa", "role": "manager" }
```
**401** si le jeton est absent, inconnu ou supprimé.

### POST `/api/auth/logout/`  — tout utilisateur connecté
Sans corps. Réponse **204** (corps vide). Le jeton utilisé est supprimé ; l'utiliser de nouveau donne 401.

### POST `/api/auth/change-pin/`  — tout utilisateur connecté
Change **son propre** PIN. La session en cours reste valable. Limité à **5 requêtes par minute** et par utilisateur (**429**
au-delà) : l'ancien PIN ne doit pas pouvoir être deviné par force brute.

Requête :
```json
{ "old_pin": "2468", "new_pin": "5555" }
```
Réponse **200** : `{ "detail": "PIN modifié." }`

Refus **400** : `wrong_pin` (ancien PIN incorrect), `same_pin` (nouveau = ancien) ; validation de format si `new_pin` n'a pas
4 à 6 chiffres :
```json
{ "code": "wrong_pin", "detail": "Ancien PIN incorrect." }
```
```json
{ "new_pin": ["Le PIN doit contenir 4 à 6 chiffres."] }
```

---

## Format des erreurs

Trois formes, à distinguer par le statut HTTP :

**1. Règle métier — 400** : toujours `code` (stable, **à utiliser pour afficher le message traduit**) et `detail`
(texte français pour les logs), plus des champs de contexte numériques (entiers) selon le code.
```json
{ "code": "insufficient_stock",
  "detail": "Stock insuffisant pour « Eau minérale 1.5L » : demandé 3000, disponible 269.",
  "product": "Eau minérale 1.5L", "requested": 3000, "available": 269 }
```
```json
{ "code": "credit_limit_exceeded",
  "detail": "Plafond de crédit dépassé : dette 13100 + reste à payer 114000 > plafond 100000.",
  "debt": 13100, "unpaid": 114000, "credit_limit": 100000 }
```
```json
{ "code": "consign_return_exceeds_holdings",
  "detail": "Retour de 9 (crate) supérieur à ce que le client détient (3).",
  "consign_type": "crate", "returned": 9, "held": 3 }
```
La liste complète des codes est [plus bas](#codes-derreur-métier).

**2. Validation de format — 400** : un objet `champ → liste de messages` (imbriqué pour les listes : `lines`, `units`…).
Pas de `code`.
```json
{ "amount": ["Assurez-vous que cette valeur est supérieure ou égale à 1."] }
```
```json
{ "units": { "0": { "prices": { "0": { "price": ["Assurez-vous que cette valeur est supérieure ou égale à 0."] } } } } }
```

**3. Accès — 401 / 403 / 404 / 405 / 429** : `{ "detail": "..." }`.
```json
{ "detail": "Vous n'avez pas la permission d'effectuer cette action." }
```

**Rejeu idempotent** (même `request_id` envoyé deux fois) : ce n'est pas une erreur. Réponse **200** avec l'objet d'origine
(les paiements n'ont alors pas de champ `warning`).

Toute erreur 4xx d'une création signifie que **rien n'a été enregistré** (transaction unique : tout ou rien).

---

## Rôles et accès

M = gérant, C = caissier, L = livreur. `—` = 403.

| Endpoint | M | C | L |
|---|:-:|:-:|:-:|
| `POST /auth/login/` | ✓ | ✓ | ✓ |
| `GET /auth/me/`, `POST /auth/logout/`, `POST /auth/change-pin/` | ✓ | ✓ | ✓ |
| `GET /users/`, `POST /users/`, `PATCH /users/{id}/`, `POST /users/{id}/reset-pin/` | ✓ | — | — |
| `GET /products/`, `GET /products/{id}/` | ✓ | ✓ | ✓ |
| `POST /products/`, `PATCH\|PUT /products/{id}/`, `POST /products/{id}/deactivate/` | ✓ | — | — |
| `GET /clients/`, `GET /clients/{id}/`, `GET /clients/{id}/statement/` | ✓ | ✓ | — |
| `POST /clients/`, `PATCH\|PUT /clients/{id}/` | ✓ | ✓ (sans toucher `credit_limit`) | — |
| `POST /clients/{id}/deactivate/` | ✓ | — | — |
| `POST /sales/`, `GET /sales/`, `GET /sales/{id}/` | ✓ | ✓ | — |
| `POST /sales/{id}/cancel/` | ✓ | — | — |
| `POST /payments/`, `GET /payments/` | ✓ | ✓ | — |
| `POST /payments/{id}/cancel/` | ✓ | — | — |
| `POST /consignments/`, `GET /consignments/`, `GET /consignments/summary/` | ✓ | ✓ | — |
| `GET /stock/` | ✓ | ✓ | ✓ (lecture seule) |
| `POST /stock/entries/`, `POST /stock/adjustments/`, `GET /stock/{product_id}/movements/` | ✓ | — | — |

Aucun `DELETE` n'existe : on désactive (`deactivate`, ou `is_active: false` pour un utilisateur) ou on annule (`cancel`).

---

## Utilisateurs

Gérant seulement. Un utilisateur a un **nom** unique (sans tenir compte des majuscules), un **rôle** et un PIN de 4 à 6
chiffres (stocké haché, jamais renvoyé). On ne supprime jamais un utilisateur : on le désactive.

Objet utilisateur :
```json
{ "id": 2, "name": "Sami", "role": "cashier", "is_active": true }
```

### GET `/api/users/`  — M
Réponse **200** : tableau, trié par nom, **désactivés inclus** (`is_active`).

### POST `/api/users/`  — M
Requête :
```json
{ "name": "Sami", "pin": "1111", "role": "cashier" }
```
Réponse **201** : l'objet utilisateur (sans PIN). Le nom est nettoyé des espaces autour. Refus **400** de validation :
nom vide, trop long (100) ou déjà pris ; rôle inconnu ; PIN qui n'a pas 4 à 6 chiffres.
```json
{ "name": ["Ce nom est déjà utilisé."], "role": ["« boss » n'est pas un choix valide."],
  "pin": ["Le PIN doit contenir 4 à 6 chiffres."] }
```

### PATCH `/api/users/{id}/`  — M
Champs optionnels : `name`, `role`, `is_active`. Le PIN ne se change pas ici (voir `reset-pin`). Pas de `PUT`, pas de
`DELETE`. Réponse **200** : l'objet utilisateur.

Règles (**400**, `code`) :

| `code` | Cas |
|---|---|
| `cannot_deactivate_self` | un gérant ne peut pas désactiver son propre compte |
| `last_manager` | le dernier gérant **actif** ne peut être ni désactivé ni rétrogradé (les gérants désactivés ne comptent pas) |

Pour passer la main : promouvoir d'abord quelqu'un d'autre gérant, puis se rétrograder. Désactiver un utilisateur ferme sa
session tout de suite ; réactiver (`"is_active": true`) lui permet de se reconnecter. Un changement de rôle s'applique à la
requête suivante.
```json
{ "code": "last_manager", "detail": "Il doit rester au moins un gérant actif." }
```

### POST `/api/users/{id}/reset-pin/`  — M
Le gérant fixe un nouveau PIN (ex. PIN oublié). Requête : `{ "pin": "4321" }` (4 à 6 chiffres). Réponse **200** :
`{ "detail": "PIN réinitialisé." }`. Les sessions de l'utilisateur sont fermées (il se reconnecte avec le nouveau PIN) ;
si le gérant réinitialise son propre PIN, sa session en cours reste ouverte. Pour changer son PIN soi-même, utiliser
`/api/auth/change-pin/`.

---

## Produits

Un produit a des **unités de vente** (`units`) : nom libre (`unit`, `pack`, `palette`), `factor` = nombre d'unités de
base, éventuelle consigne (`consign_type` + `consign_qty` = articles consignés par unité vendue) et **un prix par type de
client** (`prices`). Les unités et les prix se gèrent dans le même appel que le produit.

### GET `/api/products/`  — M, C, L
Filtre : `?is_active=true|false`. Trié par nom.

Réponse **200** : tableau d'objets produit (voir ci-dessous).

### GET `/api/products/{id}/`  — M, C, L

### POST `/api/products/`  — M
Requête :
```json
{
  "name": "Eau minérale 1.5L", "brand": "Safia", "category": "water", "consignable": true, "min_threshold": 60,
  "units": [
    { "name": "unit", "factor": 1,
      "prices": [ { "client_type": "retail", "price": 800 }, { "client_type": "cafe", "price": 750 },
                  { "client_type": "wholesale", "price": 700 } ] },
    { "name": "pack", "factor": 6, "consign_type": "crate", "consign_qty": 1,
      "prices": [ { "client_type": "retail", "price": 4500 }, { "client_type": "cafe", "price": 4200 },
                  { "client_type": "wholesale", "price": 4000 } ] },
    { "name": "palette", "factor": 60, "consign_type": "crate", "consign_qty": 10,
      "prices": [ { "client_type": "retail", "price": 40000 }, { "client_type": "cafe", "price": 38000 },
                  { "client_type": "wholesale", "price": 36000 } ] }
  ]
}
```
Réponse **201** (extrait) :
```json
{
  "id": 1, "name": "Eau minérale 1.5L", "brand": "Safia", "category": "water", "consignable": true,
  "min_threshold": 60, "is_active": true,
  "units": [
    { "id": 1, "name": "unit", "factor": 1, "consign_type": "", "consign_qty": 0,
      "prices": [ { "client_type": "retail", "price": 800 }, { "client_type": "cafe", "price": 750 },
                  { "client_type": "wholesale", "price": 700 } ] },
    { "id": 2, "name": "pack", "factor": 6, "consign_type": "crate", "consign_qty": 1, "prices": [ "..." ] },
    { "id": 3, "name": "palette", "factor": 60, "consign_type": "crate", "consign_qty": 10, "prices": [ "..." ] }
  ]
}
```
Règles (400 de validation) : prix entiers ≥ 0 (max 10¹² millimes) ; `factor` ≥ 1 ; un seul prix par type de client et par
unité ; deux unités ne peuvent pas porter le même nom ; `consign_qty` > 0 exige `consign_type` **et** `consignable: true`.
`name` et `category` obligatoires. `is_active` est en lecture seule.

### PATCH / PUT `/api/products/{id}/`  — M
Mêmes champs, tous optionnels avec `PATCH`.
- Sans `units` : les unités et prix existants ne changent pas.
- Avec `units` : la liste **remplace** l'existante. Les unités sont identifiées par leur **nom** ; une unité absente de la
  liste est supprimée, sauf si une vente ou une entrée de stock l'a déjà utilisée (400). Les `prices` d'une unité
  remplacent ses prix.

Changer un prix ne modifie jamais les ventes passées (le prix appliqué est copié sur chaque ligne de vente).

Exemple : `PATCH` `{ "min_threshold": 100 }` → **200** avec le produit complet.

### POST `/api/products/{id}/deactivate/`  — M
Sans corps. Réponse **200** : le produit avec `"is_active": false`. Un produit désactivé ne peut plus être vendu ni
recevoir d'entrée de stock ; il reste visible (historique, stock).

---

## Clients

Objet client :
```json
{ "id": 1, "name": "Café Central", "phone": "20111222", "type": "cafe", "credit_limit": 100000,
  "is_active": true, "debt": 1500, "consign_holdings": { "crate": 4, "glass_bottle": 7 } }
```
- `credit_limit` : plafond de dette en millimes ; **0 = pas de limite**.
- `debt` (lecture seule) : ventes à crédit − paiements. **Négatif = avance du client** (crédit en sa faveur), à afficher
  comme tel.
- `consign_holdings` (lecture seule) : articles consignés détenus, par type.

### GET `/api/clients/`  — M, C
Filtres : `?search=<texte>` (nom ou téléphone, contient, insensible à la casse), `?is_active=true|false`. Trié par nom.
Réponse **200** : tableau d'objets client.

### GET `/api/clients/{id}/`  — M, C

### POST `/api/clients/`  — M, C
Requête :
```json
{ "name": "Café Central", "phone": "20111222", "type": "cafe" }
```
Réponse **201** : l'objet client (`credit_limit` 0, `debt` 0).
Le gérant peut ajouter `"credit_limit": 500000`. Un caissier qui envoie un `credit_limit` différent de la valeur actuelle
(0 à la création) reçoit **403** :
```json
{ "detail": "Seul le gérant peut modifier le plafond de crédit." }
```
(renvoyer la valeur actuelle inchangée est toléré). `name` obligatoire ; `type` ∈ `retail|cafe|wholesale`.

### PATCH / PUT `/api/clients/{id}/`  — M, C
Même règle pour `credit_limit`. `debt`, `consign_holdings` et `is_active` sont ignorés. Réponse **200** : le client.

### POST `/api/clients/{id}/deactivate/`  — M
Sans corps. Réponse **200** : le client avec `"is_active": false`. Un client désactivé ne peut plus acheter ni payer
(les soldes et le relevé restent consultables).

### GET `/api/clients/{id}/statement/`  — M, C
Relevé chronologique (du plus ancien au plus récent), construit uniquement à partir des mouvements. Chaque ligne porte la
**dette courante après l'écriture** (`debt_after`) et les consignes détenues après (`consign_after`). Les ventes au comptant
ont `debt_delta: 0`. À date égale : vente, puis consigne, puis paiement.

Réponse **200** (extrait) :
```json
{
  "client": 1, "name": "Café Central", "debt": 1500,
  "consign_holdings": { "crate": 4, "glass_bottle": 0 },
  "entries": [
    { "date": "2026-10-17T00:25:22.198615+01:00", "type": "sale", "id": 1, "mode": "credit", "total": 14100,
      "reverses": null, "debt_delta": 14100, "debt_after": 14100,
      "consign_after": { "crate": 0, "glass_bottle": 0 } },
    { "date": "2026-10-17T00:25:22.206753+01:00", "type": "consign", "id": 1, "consign_type": "crate",
      "qty_out": 3, "qty_in": 0, "sale": 1, "debt_delta": 0, "debt_after": 14100,
      "consign_after": { "crate": 3, "glass_bottle": 0 } },
    { "date": "2026-10-17T00:25:22.207775+01:00", "type": "payment", "id": 1, "amount": 1000, "sale": 1,
      "reverses": null, "debt_delta": -1000, "debt_after": 13100,
      "consign_after": { "crate": 3, "glass_bottle": 0 } }
  ]
}
```
Types de lignes : `sale` (`mode`, `total`, `reverses`), `consign` (`consign_type`, `qty_out`, `qty_in`, `sale`),
`payment` (`amount`, `sale`, `reverses`). `reverses` non nul = écriture d'annulation. Le dernier `debt_after` est égal à `debt`.

---

## Ventes

Une vente met à jour **dans une seule transaction** : lignes, stock, consignes et paiement. Tout réussit ou rien.

### POST `/api/sales/`  — M, C

Requête :
```json
{
  "request_id": "00000000-0000-4000-8000-000000000005",
  "client_id": 1,
  "mode": "credit",
  "paid_amount": 1000,
  "lines": [
    { "product_id": 1, "unit": "pack", "quantity": 3 },
    { "product_id": 1, "unit": "unit", "quantity": 2 }
  ],
  "returned_consignments": [ { "consign_type": "crate", "quantity": 1 } ]
}
```
| Champ | Règle |
|---|---|
| `request_id` | obligatoire, UUID (idempotence) |
| `client_id` | optionnel. Absent = vente de passage au comptant, au **tarif détail** |
| `mode` | `cash` ou `credit` |
| `paid_amount` | optionnel, **crédit seulement** : 0 ≤ payé ≤ total ; crée un paiement lié à la vente |
| `lines` | au moins une ; `unit` = nom d'une unité du produit ; `quantity` entier 1 à 1 000 000. **Pas de prix ni de total** (ignorés s'ils sont envoyés) |
| `returned_consignments` | optionnel : consignes que le client rend pendant cette vente |

Réponse **201** :
```json
{
  "id": 1, "request_id": "00000000-0000-4000-8000-000000000005",
  "client": 1, "client_name": "Café Central", "mode": "credit",
  "total": 14100, "paid_amount": 1000,
  "user": 1, "user_name": "Sami", "created_at": "2026-10-17T00:25:22.198615+01:00",
  "reverses": null, "reversed_by": null,
  "lines": [
    { "product": 1, "product_name": "Eau minérale 1.5L", "unit": "pack", "quantity": 3,
      "unit_price": 4200, "line_total": 12600 },
    { "product": 1, "product_name": "Eau minérale 1.5L", "unit": "unit", "quantity": 2,
      "unit_price": 750, "line_total": 1500 }
  ],
  "consignments": [ { "consign_type": "crate", "qty_out": 3, "qty_in": 0 } ]
}
```
Rejeu avec le même `request_id` : **200**, même corps, aucune nouvelle écriture.

Ce que fait le serveur :
- **Prix** : tarif de l'unité pour le type du client (détail si pas de client) ; copié sur chaque ligne (`unit_price`).
- **Stock** : mouvements négatifs en unités de base (`quantity × factor`).
- **Consignes** : sortie de `consign_qty × quantity` par type pour les unités consignées ; entrées pour `returned_consignments`.
- **Crédit** : la dette du client augmente de `total − paid_amount`. Vente au comptant : ni dette ni paiement.

Refus (**400**, rien n'est enregistré) :

| `code` | Cas |
|---|---|
| `insufficient_stock` | stock insuffisant (les lignes du même produit s'additionnent) |
| `credit_limit_exceeded` | dette + reste à payer > plafond (plafond 0 = pas de limite ; égalité acceptée ; contrôle seulement s'il reste un impayé) |
| `consign_return_exceeds_holdings` | retour supérieur à ce que le client détenait **avant** cette vente |
| `consignable_needs_client` | vente de passage contenant un produit consigné |
| `consign_return_needs_client` | retour de consigne sans client |
| `credit_needs_client` | vente à crédit sans client |
| `paid_amount_not_allowed` | `paid_amount` sur une vente au comptant |
| `overpaid` | `paid_amount` > total |
| `price_missing` | pas de tarif pour ce type de client |
| `unit_not_found`, `product_not_found`, `product_inactive`, `client_not_found`, `client_inactive` | références invalides |

Exemples :
```json
{ "code": "consignable_needs_client", "detail": "« Eau minérale 1.5L » est consigné : un client est obligatoire.",
  "product": "Eau minérale 1.5L" }
```

### GET `/api/sales/`  — M, C
Filtres : `?client=<id>`, `?date_from=AAAA-MM-JJ`, `?date_to=AAAA-MM-JJ`. Du plus récent au plus ancien.
Réponse **200** : tableau d'objets vente (même forme que ci-dessus). Valeur de filtre invalide : **400**.

### GET `/api/sales/{id}/`  — M, C
Réponse **200** : l'objet vente avec ses `lines`.

### POST `/api/sales/{id}/cancel/`  — M
Sans corps. Crée une **vente d'annulation** (total négatif, `reverses` = id de l'originale, lignes en quantités négatives
au même prix) et inverse stock, consignes et le paiement fait à la vente. L'originale n'est jamais modifiée ; son champ
`reversed_by` pointe ensuite vers l'annulation. Les paiements faits **plus tard** ne sont pas annulés : si la dette devient
négative, c'est une avance du client.

Réponse **201** :
```json
{ "id": 4, "request_id": null, "client": null, "client_name": null, "mode": "cash", "total": -1500,
  "paid_amount": 0, "user": 3, "user_name": "Papa", "created_at": "2026-10-17T00:25:22.415048+01:00",
  "reverses": 2, "reversed_by": null,
  "lines": [ { "product": 2, "product_name": "Jus orange 1L", "unit": "unit", "quantity": -1,
               "unit_price": 1500, "line_total": -1500 } ],
  "consignments": [] }
```
Refus **400** : `already_cancelled` (une seule annulation par vente), `cannot_cancel_reversal` (une annulation ne
s'annule pas), `cancel_consign_conflict` (le client a déjà rendu les consignes de cette vente : annuler le laisserait avec un
solde de consignes négatif).
```json
{ "code": "already_cancelled", "detail": "Cette vente est déjà annulée." }
```
```json
{ "code": "cancel_consign_conflict",
  "detail": "Annulation impossible : le client a déjà rendu les consignes (crate) de cette vente.",
  "consign_type": "crate" }
```

---

## Paiements

### POST `/api/payments/`  — M, C
Encaisse un paiement de dette (partiel ou total). Diminue `debt`.

Requête :
```json
{ "request_id": "00000000-0000-4000-8000-000000000014", "client_id": 1, "amount": 5000, "sale_id": 5 }
```
`amount` entier ≥ 1. `sale_id` optionnel : doit être une vente **à crédit** du même client, ni annulée ni une annulation
(le montant n'est pas plafonné au reste dû de cette vente).

Réponse **201** :
```json
{ "id": 2, "request_id": "00000000-0000-4000-8000-000000000014", "client": 1, "client_name": "Café Central",
  "amount": 5000, "sale": 5, "reverses": null, "reversed_by": null,
  "user": 1, "user_name": "Sami", "created_at": "2026-10-17T00:25:22.492323+01:00",
  "warning": null }
```
**Paiement supérieur à la dette** : accepté (le surplus devient une avance), avec un avertissement à montrer au caissier :
```json
{ "id": 3, "request_id": "00000000-0000-4000-8000-000000000015", "client": 1, "client_name": "Café Central",
  "amount": 20000, "sale": null, "reverses": null, "reversed_by": null, "user": 1, "user_name": "Sami",
  "created_at": "2026-10-17T00:25:22.517644+01:00",
  "warning": { "code": "exceeds_debt", "debt_before": 16500, "credit_after": 3500 } }
```
`credit_after` = solde créditeur **total** du client après ce paiement. Le `warning` n'existe qu'à la première création
(absent d'un rejeu **200**).

Refus **400** : validation (`amount` < 1, etc.) ; codes `client_not_found`, `client_inactive`, `sale_not_found`,
`sale_client_mismatch`, `sale_not_credit`, `sale_cancelled`.

### GET `/api/payments/`  — M, C
Filtres : `?client=<id>`, `?date_from=`, `?date_to=`. Du plus récent au plus ancien. Réponse **200** : tableau d'objets
paiement (forme ci-dessus, sans `warning`).

### POST `/api/payments/{id}/cancel/`  — M
Sans corps. Crée un paiement de **montant négatif** avec `reverses` = id de l'original ; la dette remonte d'autant.

Réponse **201** :
```json
{ "id": 4, "request_id": null, "client": 1, "client_name": "Café Central", "amount": -5000, "sale": 5,
  "reverses": 2, "reversed_by": null, "user": 3, "user_name": "Papa", "created_at": "2026-10-17T00:25:22.546170+01:00" }
```
Refus **400** : `already_cancelled`, `cannot_cancel_reversal`.

---

## Consignes

Mouvements de consigne **hors vente** (le client rend des caisses plus tard, ou en emporte sans acheter). Les mouvements
créés par les ventes apparaissent dans les mêmes listes (`sale` renseigné).

### POST `/api/consignments/`  — M, C
Requête :
```json
{ "request_id": "00000000-0000-4000-8000-000000000017", "client_id": 1,
  "consign_type": "glass_bottle", "direction": "out", "quantity": 12 }
```
`direction` : `out` (le client emporte) ou `in` (le client rend). `quantity` entier ≥ 1.

Réponse **201** :
```json
{ "id": 4, "request_id": "00000000-0000-4000-8000-000000000017", "client": 1, "client_name": "Café Central",
  "consign_type": "glass_bottle", "direction": "out", "quantity": 12, "qty_out": 12, "qty_in": 0,
  "sale": null, "user": 1, "user_name": "Sami", "created_at": "2026-10-17T00:25:22.568924+01:00" }
```
Un retour supérieur au solde détenu pour ce type est refusé (**400**) :
```json
{ "code": "consign_return_exceeds_holdings",
  "detail": "Retour de 20 (glass_bottle) supérieur à ce que le client détient (12).",
  "consign_type": "glass_bottle", "returned": 20, "held": 12 }
```
Pas d'annulation : une erreur de saisie se corrige par le mouvement inverse. Autres refus : `client_not_found`, `client_inactive`.

### GET `/api/consignments/`  — M, C
Filtres : `?client=<id>`, `?type=crate|glass_bottle`, `?date_from=`, `?date_to=`. Du plus récent au plus ancien. Réponse
**200** : tableau d'objets mouvement (forme ci-dessus).

### GET `/api/consignments/summary/`  — M, C
Réponse **200** :
```json
{
  "totals": { "crate": 4, "glass_bottle": 7 },
  "overdue_days": 30,
  "overdue": [
    { "client": 1, "client_name": "Café Central", "consign_type": "crate", "held": 6, "overdue_quantity": 6,
      "oldest_since": "2026-01-01T09:00:00+01:00", "days": 34 }
  ]
}
```
- `totals` : total détenu par type, tous clients confondus.
- `overdue` : un élément par client et par type qui détient des consignes depuis **plus de 30 jours**, règle **FIFO** :
  un retour solde d'abord les sorties les plus anciennes. `held` = total détenu pour ce type, `overdue_quantity` = la part
  datant de plus de 30 jours, `oldest_since` = date de la plus ancienne sortie encore due. Trié du plus ancien au plus récent.

---

## Stock

Le stock est la somme des mouvements (unités de base). Il n'existe pas de « valeur de stock » modifiable.

### GET `/api/stock/`  — M, C, L
Réponse **200** : un élément par produit, trié par nom (produits désactivés inclus, voir `is_active`).
```json
[
  {
    "product": 1, "name": "Eau minérale 1.5L", "brand": "Safia", "category": "water", "is_active": true,
    "quantity": 256,
    "breakdown": [
      { "unit": "palette", "factor": 60, "count": 4 },
      { "unit": "pack", "factor": 6, "count": 2 },
      { "unit": "unit", "factor": 1, "count": 4 }
    ],
    "remainder": 0,
    "min_threshold": 100,
    "low_stock": false
  }
]
```
- `quantity` : unités de base.
- `breakdown` : décomposition en unités de vente, de la plus grande à la plus petite (`count × factor` + `remainder` =
  `quantity`). Données structurées : **le texte (« 4 palettes, 2 packs… ») se compose dans Flutter** avec les traductions.
- `remainder` : unités de base qui ne forment aucune unité (seulement si le produit n'a pas d'unité de facteur 1).
- `low_stock` : `true` quand `min_threshold` > 0 **et** `quantity` ≤ `min_threshold`. Seuil 0 = jamais d'alerte.

### POST `/api/stock/entries/`  — M
Achat fournisseur ou livraison reçue. Accepte n'importe quelle unité du produit ; converti en unités de base.

Requête :
```json
{ "request_id": "00000000-0000-4000-8000-000000000001", "product_id": 1, "unit": "palette", "quantity": 5,
  "unit_cost": 33000, "note": "Livraison Safia" }
```
`quantity` entier 1 à 1 000 000 (dans l'unité choisie). `unit_cost` optionnel (millimes **par unité saisie**, ici par
palette) ; `note` optionnelle (200 caractères).

Réponse **201** :
```json
{ "id": 1, "request_id": "00000000-0000-4000-8000-000000000001", "product": 1, "quantity": 300,
  "reason": "purchase", "sale": null, "unit": "palette", "unit_cost": 33000, "note": "Livraison Safia",
  "user": 3, "user_name": "Papa", "created_at": "2026-10-17T00:25:22.134315+01:00", "stock": 300 }
```
`quantity` = unités de base ajoutées ; `stock` = stock du produit après l'opération. Refus : `unit_not_found`,
`product_not_found`, `product_inactive`.

### POST `/api/stock/adjustments/`  — M
Correction d'inventaire ou perte/casse. Ajoute un mouvement, n'écrase rien. Le **motif est obligatoire**.

Requête — par quantité comptée (unités de base) :
```json
{ "request_id": "00000000-0000-4000-8000-000000000002", "product_id": 1, "reason": "inventory",
  "counted_quantity": 295, "note": "Inventaire du soir" }
```
ou par écart signé :
```json
{ "request_id": "00000000-0000-4000-8000-000000000003", "product_id": 1, "reason": "loss",
  "delta": -6, "note": "Pack cassé" }
```
- `reason` : `inventory` ou `loss` (obligatoire). `note` libre, optionnelle.
- Exactement un de `counted_quantity` (≥ 0) ou `delta` (entier non nul). Avec `counted_quantity`, le mouvement est
  l'écart avec le stock **au moment de l'appel**.
- `loss` doit diminuer le stock.

Réponse **201** (ex. comptage) :
```json
{ "id": 2, "request_id": "00000000-0000-4000-8000-000000000002", "product": 1, "quantity": -5,
  "reason": "inventory", "sale": null, "unit": null, "unit_cost": null, "note": "Inventaire du soir",
  "user": 3, "user_name": "Papa", "created_at": "2026-10-17T00:25:22.153821+01:00", "stock": 295 }
```
Refus **400** :

| `code` | Cas |
|---|---|
| `no_change` | quantité comptée = stock actuel (rien à corriger) |
| `loss_must_decrease` | perte/casse qui augmenterait le stock |
| `adjustment_below_zero` | le stock deviendrait négatif |
| `product_not_found`, `product_inactive` | produit invalide |
| *(validation)* | motif manquant ou invalide, ni `counted_quantity` ni `delta` (ou les deux), `delta` = 0 |

```json
{ "code": "no_change", "detail": "Le stock compté (289) est déjà le stock actuel.",
  "product": "Eau minérale 1.5L", "current": 289 }
```

### GET `/api/stock/{product_id}/movements/`  — M
Historique du produit, du plus récent au plus ancien, avec le stock après chaque mouvement. Les ventes annulées
apparaissent comme des mouvements positifs inverses. **404** si le produit n'existe pas.

Réponse **200** (extrait) :
```json
[
  { "id": 10, "request_id": null, "product": 1, "quantity": -12, "reason": "sale", "sale": 5, "unit": null,
    "unit_cost": null, "note": "", "user": 1, "user_name": "Sami",
    "created_at": "2026-10-17T00:25:22.464981+01:00", "balance_after": 256 }
]
```

---

## Codes d'erreur métier

Tous en **400**, avec `code` et `detail`. Champs de contexte entre parenthèses.

| `code` | Où | Sens |
|---|---|---|
| `insufficient_stock` (`product`, `requested`, `available`) | vente | stock insuffisant |
| `credit_limit_exceeded` (`debt`, `unpaid`, `credit_limit`) | vente | plafond de crédit dépassé |
| `consign_return_exceeds_holdings` (`consign_type`, `returned`, `held`) | vente, consignes | retour > consignes détenues |
| `consignable_needs_client` (`product`) | vente | produit consigné sans client |
| `consign_return_needs_client` | vente | retour de consigne sans client |
| `credit_needs_client` | vente | crédit sans client |
| `paid_amount_not_allowed` | vente | `paid_amount` sur une vente au comptant |
| `overpaid` | vente | payé > total |
| `price_missing` (`product`) | vente | pas de prix pour ce type de client |
| `unit_not_found` (`product`) | vente, entrée | unité inconnue pour ce produit |
| `product_not_found`, `product_inactive` | vente, stock | produit invalide |
| `client_not_found`, `client_inactive` | vente, paiement, consignes | client invalide |
| `already_cancelled` | annulations | déjà annulé |
| `cannot_cancel_reversal` | annulations | une annulation ne s'annule pas |
| `cancel_consign_conflict` (`consign_type`) | annulation de vente | consignes déjà rendues |
| `sale_not_found`, `sale_client_mismatch`, `sale_not_credit`, `sale_cancelled` | paiement | `sale_id` invalide |
| `wrong_pin`, `same_pin` | changement de PIN | ancien PIN faux ; nouveau PIN identique |
| `cannot_deactivate_self`, `last_manager` | utilisateurs | règles de sécurité sur les gérants |
| `no_change` (`product`, `current`) | ajustement | quantité comptée = stock |
| `loss_must_decrease` (`product`, `delta`) | ajustement | perte qui augmente le stock |
| `adjustment_below_zero` (`product`, `current`, `delta`) | ajustement | stock négatif |

`exceeds_debt` n'est pas une erreur : c'est le `warning` d'un paiement accepté.

---

## Conseils pour Flutter

- **Une action = un `request_id`.** Générer l'UUID quand l'utilisateur appuie sur « Valider », le conserver tant que
  l'écran attend la réponse, et le **renvoyer à l'identique** après une coupure réseau ou un double appui. Un nouvel UUID
  uniquement pour une nouvelle action.
- **Afficher selon `code`**, jamais selon `detail` (français, pour les logs). Les chiffres du contexte (`available`,
  `debt`…) sont des entiers prêts à formater.
- **Aucune logique métier dans l'app** : pas de calcul de prix, de total, de stock ni de dette ; afficher ce que renvoie
  le serveur (`total`, `unit_price`, `debt`, `breakdown`, `low_stock`).
- **Montants** : entiers en millimes ; formater en dinars avec 3 décimales à l'affichage seulement.
- **Dette négative** = avance du client : l'afficher comme un crédit, pas comme une erreur.
- **Après une écriture**, recharger la fiche client (`GET /clients/{id}/`) pour le nouveau `debt` et les consignes.
