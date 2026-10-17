// ignore: unused_import
import 'package:intl/intl.dart' as intl;

import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for French (`fr`).
class AppLocalizationsFr extends AppLocalizations {
  AppLocalizationsFr([String locale = 'fr']) : super(locale);

  @override
  String get appName => 'Edebou';

  @override
  String get language => 'Langue';

  @override
  String get languageFrench => 'Français';

  @override
  String get languageArabic => 'العربية';

  @override
  String get loginTitle => 'Connexion';

  @override
  String get loginSubtitle => 'Entrez votre nom et votre code PIN';

  @override
  String get nameLabel => 'Nom';

  @override
  String get pinLabel => 'Code PIN';

  @override
  String get loginButton => 'Se connecter';

  @override
  String get nameRequired => 'Entrez votre nom.';

  @override
  String get pinFormat => 'Le code PIN contient 4 à 6 chiffres.';

  @override
  String get pinBackspace => 'Effacer';

  @override
  String get loginInvalidCredentials => 'Nom ou code PIN incorrect.';

  @override
  String get sessionExpired => 'Votre session a expiré. Reconnectez-vous.';

  @override
  String get restoringSession => 'Ouverture de la session…';

  @override
  String get retry => 'Réessayer';

  @override
  String get settings => 'Paramètres';

  @override
  String get settingsTitle => 'Paramètres';

  @override
  String get backendAddress => 'Adresse du serveur';

  @override
  String get backendAddressHelp =>
      'Adresse du PC du dépôt, par exemple http://127.0.0.1:8000';

  @override
  String get addressInvalid =>
      'Adresse invalide. Exemple : http://127.0.0.1:8000';

  @override
  String get save => 'Enregistrer';

  @override
  String get saved => 'Paramètres enregistrés.';

  @override
  String get testConnection => 'Tester la connexion';

  @override
  String get testing => 'Test en cours…';

  @override
  String get connectionOk => 'Connexion réussie.';

  @override
  String get connectionNotEdebou =>
      'Un serveur répond, mais ce n\'est pas Edebou.';

  @override
  String get connectionUnreachable =>
      'Serveur injoignable. Vérifiez l\'adresse et que le serveur est démarré.';

  @override
  String get connectionTimeout => 'Le serveur ne répond pas (délai dépassé).';

  @override
  String get back => 'Retour';

  @override
  String get homeTitle => 'Accueil';

  @override
  String welcomeUser(String name) {
    return 'Bonjour, $name';
  }

  @override
  String get roleManager => 'Gérant';

  @override
  String get roleCashier => 'Caissier';

  @override
  String get roleDelivery => 'Livreur';

  @override
  String get moduleCashRegister => 'Caisse';

  @override
  String get moduleClients => 'Clients';

  @override
  String get moduleConsignments => 'Consignes';

  @override
  String get moduleStock => 'Stock';

  @override
  String get comingSoon => 'Bientôt disponible';

  @override
  String get logout => 'Déconnexion';

  @override
  String get errorUnreachable => 'Impossible de joindre le serveur.';

  @override
  String get errorTimeout => 'Le serveur met trop de temps à répondre.';

  @override
  String get errorForbidden =>
      'Vous n\'avez pas le droit de faire cette action.';

  @override
  String get errorNotFound => 'Élément introuvable.';

  @override
  String get errorThrottled => 'Trop d\'essais. Patientez une minute.';

  @override
  String get errorServer => 'Erreur du serveur. Réessayez.';

  @override
  String get errorUnknown => 'Une erreur est survenue.';

  @override
  String get errorValidation => 'Certaines informations sont invalides.';

  @override
  String bizInsufficientStock(String product, int available) {
    return 'Stock insuffisant pour $product : $available disponible(s).';
  }

  @override
  String get bizCreditLimitExceeded => 'Plafond de crédit dépassé.';

  @override
  String bizConsignReturnExceedsHoldings(int held) {
    return 'Le client ne détient que $held consigne(s) de ce type.';
  }

  @override
  String get bizConsignableNeedsClient =>
      'Ce produit est consigné : choisissez un client.';

  @override
  String get bizConsignReturnNeedsClient =>
      'Un retour de consigne nécessite un client.';

  @override
  String get bizCreditNeedsClient => 'Une vente à crédit nécessite un client.';

  @override
  String get bizPaidAmountNotAllowed =>
      'Le montant payé ne s\'applique qu\'aux ventes à crédit.';

  @override
  String get bizOverpaid => 'Le montant payé dépasse le total.';

  @override
  String get bizPriceMissing => 'Aucun prix défini pour ce type de client.';

  @override
  String get bizUnitNotFound => 'Unité inconnue pour ce produit.';

  @override
  String get bizProductNotFound => 'Produit introuvable.';

  @override
  String get bizProductInactive => 'Ce produit est désactivé.';

  @override
  String get bizClientNotFound => 'Client introuvable.';

  @override
  String get bizClientInactive => 'Ce client est désactivé.';

  @override
  String get bizAlreadyCancelled => 'Déjà annulé.';

  @override
  String get bizCannotCancelReversal =>
      'Une annulation ne peut pas être annulée.';

  @override
  String get bizCancelConsignConflict =>
      'Annulation impossible : le client a déjà rendu les consignes.';

  @override
  String get bizSaleNotFound => 'Vente introuvable.';

  @override
  String get bizSaleClientMismatch =>
      'Cette vente n\'appartient pas à ce client.';

  @override
  String get bizSaleNotCredit => 'Cette vente n\'est pas une vente à crédit.';

  @override
  String get bizSaleCancelled => 'Cette vente est annulée.';

  @override
  String get bizWrongPin => 'Ancien code PIN incorrect.';

  @override
  String get bizSamePin => 'Le nouveau code PIN doit être différent.';

  @override
  String get bizCannotDeactivateSelf =>
      'Vous ne pouvez pas désactiver votre propre compte.';

  @override
  String get bizLastManager => 'Il doit rester au moins un gérant actif.';

  @override
  String bizNoChange(int current) {
    return 'Le stock compté est déjà le stock actuel ($current).';
  }

  @override
  String get bizLossMustDecrease => 'Une perte doit diminuer le stock.';

  @override
  String get bizAdjustmentBelowZero => 'Le stock ne peut pas devenir négatif.';

  @override
  String get bizUnknown => 'Action refusée par le serveur.';
}
