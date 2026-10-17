import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:intl/intl.dart' as intl;

import 'app_localizations_ar.dart';
import 'app_localizations_fr.dart';

// ignore_for_file: type=lint

/// Callers can lookup localized strings with an instance of AppLocalizations
/// returned by `AppLocalizations.of(context)`.
///
/// Applications need to include `AppLocalizations.delegate()` in their app's
/// `localizationDelegates` list, and the locales they support in the app's
/// `supportedLocales` list. For example:
///
/// ```dart
/// import 'l10n/app_localizations.dart';
///
/// return MaterialApp(
///   localizationsDelegates: AppLocalizations.localizationsDelegates,
///   supportedLocales: AppLocalizations.supportedLocales,
///   home: MyApplicationHome(),
/// );
/// ```
///
/// ## Update pubspec.yaml
///
/// Please make sure to update your pubspec.yaml to include the following
/// packages:
///
/// ```yaml
/// dependencies:
///   # Internationalization support.
///   flutter_localizations:
///     sdk: flutter
///   intl: any # Use the pinned version from flutter_localizations
///
///   # Rest of dependencies
/// ```
///
/// ## iOS Applications
///
/// iOS applications define key application metadata, including supported
/// locales, in an Info.plist file that is built into the application bundle.
/// To configure the locales supported by your app, you’ll need to edit this
/// file.
///
/// First, open your project’s ios/Runner.xcworkspace Xcode workspace file.
/// Then, in the Project Navigator, open the Info.plist file under the Runner
/// project’s Runner folder.
///
/// Next, select the Information Property List item, select Add Item from the
/// Editor menu, then select Localizations from the pop-up menu.
///
/// Select and expand the newly-created Localizations item then, for each
/// locale your application supports, add a new item and select the locale
/// you wish to add from the pop-up menu in the Value field. This list should
/// be consistent with the languages listed in the AppLocalizations.supportedLocales
/// property.
abstract class AppLocalizations {
  AppLocalizations(String locale)
    : localeName = intl.Intl.canonicalizedLocale(locale.toString());

  final String localeName;

  static AppLocalizations of(BuildContext context) {
    return Localizations.of<AppLocalizations>(context, AppLocalizations)!;
  }

  static const LocalizationsDelegate<AppLocalizations> delegate =
      _AppLocalizationsDelegate();

  /// A list of this localizations delegate along with the default localizations
  /// delegates.
  ///
  /// Returns a list of localizations delegates containing this delegate along with
  /// GlobalMaterialLocalizations.delegate, GlobalCupertinoLocalizations.delegate,
  /// and GlobalWidgetsLocalizations.delegate.
  ///
  /// Additional delegates can be added by appending to this list in
  /// MaterialApp. This list does not have to be used at all if a custom list
  /// of delegates is preferred or required.
  static const List<LocalizationsDelegate<dynamic>> localizationsDelegates =
      <LocalizationsDelegate<dynamic>>[
        delegate,
        GlobalMaterialLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
      ];

  /// A list of this localizations delegate's supported locales.
  static const List<Locale> supportedLocales = <Locale>[
    Locale('ar'),
    Locale('fr'),
  ];

  /// No description provided for @appName.
  ///
  /// In fr, this message translates to:
  /// **'Edebou'**
  String get appName;

  /// No description provided for @language.
  ///
  /// In fr, this message translates to:
  /// **'Langue'**
  String get language;

  /// No description provided for @languageFrench.
  ///
  /// In fr, this message translates to:
  /// **'Français'**
  String get languageFrench;

  /// No description provided for @languageArabic.
  ///
  /// In fr, this message translates to:
  /// **'العربية'**
  String get languageArabic;

  /// No description provided for @loginTitle.
  ///
  /// In fr, this message translates to:
  /// **'Connexion'**
  String get loginTitle;

  /// No description provided for @loginSubtitle.
  ///
  /// In fr, this message translates to:
  /// **'Entrez votre nom et votre code PIN'**
  String get loginSubtitle;

  /// No description provided for @nameLabel.
  ///
  /// In fr, this message translates to:
  /// **'Nom'**
  String get nameLabel;

  /// No description provided for @pinLabel.
  ///
  /// In fr, this message translates to:
  /// **'Code PIN'**
  String get pinLabel;

  /// No description provided for @loginButton.
  ///
  /// In fr, this message translates to:
  /// **'Se connecter'**
  String get loginButton;

  /// No description provided for @nameRequired.
  ///
  /// In fr, this message translates to:
  /// **'Entrez votre nom.'**
  String get nameRequired;

  /// No description provided for @pinFormat.
  ///
  /// In fr, this message translates to:
  /// **'Le code PIN contient 4 à 6 chiffres.'**
  String get pinFormat;

  /// No description provided for @pinBackspace.
  ///
  /// In fr, this message translates to:
  /// **'Effacer'**
  String get pinBackspace;

  /// No description provided for @loginInvalidCredentials.
  ///
  /// In fr, this message translates to:
  /// **'Nom ou code PIN incorrect.'**
  String get loginInvalidCredentials;

  /// No description provided for @sessionExpired.
  ///
  /// In fr, this message translates to:
  /// **'Votre session a expiré. Reconnectez-vous.'**
  String get sessionExpired;

  /// No description provided for @restoringSession.
  ///
  /// In fr, this message translates to:
  /// **'Ouverture de la session…'**
  String get restoringSession;

  /// No description provided for @retry.
  ///
  /// In fr, this message translates to:
  /// **'Réessayer'**
  String get retry;

  /// No description provided for @settings.
  ///
  /// In fr, this message translates to:
  /// **'Paramètres'**
  String get settings;

  /// No description provided for @settingsTitle.
  ///
  /// In fr, this message translates to:
  /// **'Paramètres'**
  String get settingsTitle;

  /// No description provided for @backendAddress.
  ///
  /// In fr, this message translates to:
  /// **'Adresse du serveur'**
  String get backendAddress;

  /// No description provided for @backendAddressHelp.
  ///
  /// In fr, this message translates to:
  /// **'Adresse du PC du dépôt, par exemple http://127.0.0.1:8000'**
  String get backendAddressHelp;

  /// No description provided for @addressInvalid.
  ///
  /// In fr, this message translates to:
  /// **'Adresse invalide. Exemple : http://127.0.0.1:8000'**
  String get addressInvalid;

  /// No description provided for @save.
  ///
  /// In fr, this message translates to:
  /// **'Enregistrer'**
  String get save;

  /// No description provided for @saved.
  ///
  /// In fr, this message translates to:
  /// **'Paramètres enregistrés.'**
  String get saved;

  /// No description provided for @testConnection.
  ///
  /// In fr, this message translates to:
  /// **'Tester la connexion'**
  String get testConnection;

  /// No description provided for @testing.
  ///
  /// In fr, this message translates to:
  /// **'Test en cours…'**
  String get testing;

  /// No description provided for @connectionOk.
  ///
  /// In fr, this message translates to:
  /// **'Connexion réussie.'**
  String get connectionOk;

  /// No description provided for @connectionNotEdebou.
  ///
  /// In fr, this message translates to:
  /// **'Un serveur répond, mais ce n\'est pas Edebou.'**
  String get connectionNotEdebou;

  /// No description provided for @connectionUnreachable.
  ///
  /// In fr, this message translates to:
  /// **'Serveur injoignable. Vérifiez l\'adresse et que le serveur est démarré.'**
  String get connectionUnreachable;

  /// No description provided for @connectionTimeout.
  ///
  /// In fr, this message translates to:
  /// **'Le serveur ne répond pas (délai dépassé).'**
  String get connectionTimeout;

  /// No description provided for @back.
  ///
  /// In fr, this message translates to:
  /// **'Retour'**
  String get back;

  /// No description provided for @homeTitle.
  ///
  /// In fr, this message translates to:
  /// **'Accueil'**
  String get homeTitle;

  /// No description provided for @welcomeUser.
  ///
  /// In fr, this message translates to:
  /// **'Bonjour, {name}'**
  String welcomeUser(String name);

  /// No description provided for @roleManager.
  ///
  /// In fr, this message translates to:
  /// **'Gérant'**
  String get roleManager;

  /// No description provided for @roleCashier.
  ///
  /// In fr, this message translates to:
  /// **'Caissier'**
  String get roleCashier;

  /// No description provided for @roleDelivery.
  ///
  /// In fr, this message translates to:
  /// **'Livreur'**
  String get roleDelivery;

  /// No description provided for @moduleCashRegister.
  ///
  /// In fr, this message translates to:
  /// **'Caisse'**
  String get moduleCashRegister;

  /// No description provided for @moduleClients.
  ///
  /// In fr, this message translates to:
  /// **'Clients'**
  String get moduleClients;

  /// No description provided for @moduleConsignments.
  ///
  /// In fr, this message translates to:
  /// **'Consignes'**
  String get moduleConsignments;

  /// No description provided for @moduleStock.
  ///
  /// In fr, this message translates to:
  /// **'Stock'**
  String get moduleStock;

  /// No description provided for @comingSoon.
  ///
  /// In fr, this message translates to:
  /// **'Bientôt disponible'**
  String get comingSoon;

  /// No description provided for @logout.
  ///
  /// In fr, this message translates to:
  /// **'Déconnexion'**
  String get logout;

  /// No description provided for @errorUnreachable.
  ///
  /// In fr, this message translates to:
  /// **'Impossible de joindre le serveur.'**
  String get errorUnreachable;

  /// No description provided for @errorTimeout.
  ///
  /// In fr, this message translates to:
  /// **'Le serveur met trop de temps à répondre.'**
  String get errorTimeout;

  /// No description provided for @errorForbidden.
  ///
  /// In fr, this message translates to:
  /// **'Vous n\'avez pas le droit de faire cette action.'**
  String get errorForbidden;

  /// No description provided for @errorNotFound.
  ///
  /// In fr, this message translates to:
  /// **'Élément introuvable.'**
  String get errorNotFound;

  /// No description provided for @errorThrottled.
  ///
  /// In fr, this message translates to:
  /// **'Trop d\'essais. Patientez une minute.'**
  String get errorThrottled;

  /// No description provided for @errorServer.
  ///
  /// In fr, this message translates to:
  /// **'Erreur du serveur. Réessayez.'**
  String get errorServer;

  /// No description provided for @errorUnknown.
  ///
  /// In fr, this message translates to:
  /// **'Une erreur est survenue.'**
  String get errorUnknown;

  /// No description provided for @errorValidation.
  ///
  /// In fr, this message translates to:
  /// **'Certaines informations sont invalides.'**
  String get errorValidation;

  /// No description provided for @bizInsufficientStock.
  ///
  /// In fr, this message translates to:
  /// **'Stock insuffisant pour {product} : {available} disponible(s).'**
  String bizInsufficientStock(String product, int available);

  /// No description provided for @bizCreditLimitExceeded.
  ///
  /// In fr, this message translates to:
  /// **'Plafond de crédit dépassé.'**
  String get bizCreditLimitExceeded;

  /// No description provided for @bizConsignReturnExceedsHoldings.
  ///
  /// In fr, this message translates to:
  /// **'Le client ne détient que {held} consigne(s) de ce type.'**
  String bizConsignReturnExceedsHoldings(int held);

  /// No description provided for @bizConsignableNeedsClient.
  ///
  /// In fr, this message translates to:
  /// **'Ce produit est consigné : choisissez un client.'**
  String get bizConsignableNeedsClient;

  /// No description provided for @bizConsignReturnNeedsClient.
  ///
  /// In fr, this message translates to:
  /// **'Un retour de consigne nécessite un client.'**
  String get bizConsignReturnNeedsClient;

  /// No description provided for @bizCreditNeedsClient.
  ///
  /// In fr, this message translates to:
  /// **'Une vente à crédit nécessite un client.'**
  String get bizCreditNeedsClient;

  /// No description provided for @bizPaidAmountNotAllowed.
  ///
  /// In fr, this message translates to:
  /// **'Le montant payé ne s\'applique qu\'aux ventes à crédit.'**
  String get bizPaidAmountNotAllowed;

  /// No description provided for @bizOverpaid.
  ///
  /// In fr, this message translates to:
  /// **'Le montant payé dépasse le total.'**
  String get bizOverpaid;

  /// No description provided for @bizPriceMissing.
  ///
  /// In fr, this message translates to:
  /// **'Aucun prix défini pour ce type de client.'**
  String get bizPriceMissing;

  /// No description provided for @bizUnitNotFound.
  ///
  /// In fr, this message translates to:
  /// **'Unité inconnue pour ce produit.'**
  String get bizUnitNotFound;

  /// No description provided for @bizProductNotFound.
  ///
  /// In fr, this message translates to:
  /// **'Produit introuvable.'**
  String get bizProductNotFound;

  /// No description provided for @bizProductInactive.
  ///
  /// In fr, this message translates to:
  /// **'Ce produit est désactivé.'**
  String get bizProductInactive;

  /// No description provided for @bizClientNotFound.
  ///
  /// In fr, this message translates to:
  /// **'Client introuvable.'**
  String get bizClientNotFound;

  /// No description provided for @bizClientInactive.
  ///
  /// In fr, this message translates to:
  /// **'Ce client est désactivé.'**
  String get bizClientInactive;

  /// No description provided for @bizAlreadyCancelled.
  ///
  /// In fr, this message translates to:
  /// **'Déjà annulé.'**
  String get bizAlreadyCancelled;

  /// No description provided for @bizCannotCancelReversal.
  ///
  /// In fr, this message translates to:
  /// **'Une annulation ne peut pas être annulée.'**
  String get bizCannotCancelReversal;

  /// No description provided for @bizCancelConsignConflict.
  ///
  /// In fr, this message translates to:
  /// **'Annulation impossible : le client a déjà rendu les consignes.'**
  String get bizCancelConsignConflict;

  /// No description provided for @bizSaleNotFound.
  ///
  /// In fr, this message translates to:
  /// **'Vente introuvable.'**
  String get bizSaleNotFound;

  /// No description provided for @bizSaleClientMismatch.
  ///
  /// In fr, this message translates to:
  /// **'Cette vente n\'appartient pas à ce client.'**
  String get bizSaleClientMismatch;

  /// No description provided for @bizSaleNotCredit.
  ///
  /// In fr, this message translates to:
  /// **'Cette vente n\'est pas une vente à crédit.'**
  String get bizSaleNotCredit;

  /// No description provided for @bizSaleCancelled.
  ///
  /// In fr, this message translates to:
  /// **'Cette vente est annulée.'**
  String get bizSaleCancelled;

  /// No description provided for @bizWrongPin.
  ///
  /// In fr, this message translates to:
  /// **'Ancien code PIN incorrect.'**
  String get bizWrongPin;

  /// No description provided for @bizSamePin.
  ///
  /// In fr, this message translates to:
  /// **'Le nouveau code PIN doit être différent.'**
  String get bizSamePin;

  /// No description provided for @bizCannotDeactivateSelf.
  ///
  /// In fr, this message translates to:
  /// **'Vous ne pouvez pas désactiver votre propre compte.'**
  String get bizCannotDeactivateSelf;

  /// No description provided for @bizLastManager.
  ///
  /// In fr, this message translates to:
  /// **'Il doit rester au moins un gérant actif.'**
  String get bizLastManager;

  /// No description provided for @bizNoChange.
  ///
  /// In fr, this message translates to:
  /// **'Le stock compté est déjà le stock actuel ({current}).'**
  String bizNoChange(int current);

  /// No description provided for @bizLossMustDecrease.
  ///
  /// In fr, this message translates to:
  /// **'Une perte doit diminuer le stock.'**
  String get bizLossMustDecrease;

  /// No description provided for @bizAdjustmentBelowZero.
  ///
  /// In fr, this message translates to:
  /// **'Le stock ne peut pas devenir négatif.'**
  String get bizAdjustmentBelowZero;

  /// No description provided for @bizUnknown.
  ///
  /// In fr, this message translates to:
  /// **'Action refusée par le serveur.'**
  String get bizUnknown;
}

class _AppLocalizationsDelegate
    extends LocalizationsDelegate<AppLocalizations> {
  const _AppLocalizationsDelegate();

  @override
  Future<AppLocalizations> load(Locale locale) {
    return SynchronousFuture<AppLocalizations>(lookupAppLocalizations(locale));
  }

  @override
  bool isSupported(Locale locale) =>
      <String>['ar', 'fr'].contains(locale.languageCode);

  @override
  bool shouldReload(_AppLocalizationsDelegate old) => false;
}

AppLocalizations lookupAppLocalizations(Locale locale) {
  // Lookup logic when only language code is specified.
  switch (locale.languageCode) {
    case 'ar':
      return AppLocalizationsAr();
    case 'fr':
      return AppLocalizationsFr();
  }

  throw FlutterError(
    'AppLocalizations.delegate failed to load unsupported locale "$locale". This is likely '
    'an issue with the localizations generation tool. Please file an issue '
    'on GitHub with a reproducible sample app and the gen-l10n configuration '
    'that was used.',
  );
}
