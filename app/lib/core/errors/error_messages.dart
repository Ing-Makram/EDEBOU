import '../../l10n/app_localizations.dart';
import '../api/api_error.dart';
import '../api/business_code.dart';

/// Message traduit pour une erreur de l'API. Les textes viennent des fichiers .arb ;
/// le `detail` français du serveur n'est jamais affiché.
String errorMessage(AppLocalizations l, Object error) {
  switch (error) {
    case NetworkError(:final timeout):
      return timeout ? l.errorTimeout : l.errorUnreachable;
    case UnauthorizedError():
      return l.sessionExpired;
    case ForbiddenError():
      return l.errorForbidden;
    case NotFoundError():
      return l.errorNotFound;
    case ThrottledError():
      return l.errorThrottled;
    case ServerError():
      return l.errorServer;
    case ValidationError():
      return l.errorValidation;
    case BusinessError():
      return businessMessage(l, error);
    default:
      return l.errorUnknown;
  }
}

String businessMessage(AppLocalizations l, BusinessError e) {
  switch (e.code) {
    case BusinessCode.insufficientStock:
      return l.bizInsufficientStock(e.stringContext('product') ?? '?', e.intContext('available') ?? 0);
    case BusinessCode.creditLimitExceeded:
      return l.bizCreditLimitExceeded;
    case BusinessCode.consignReturnExceedsHoldings:
      return l.bizConsignReturnExceedsHoldings(e.intContext('held') ?? 0);
    case BusinessCode.consignableNeedsClient:
      return l.bizConsignableNeedsClient;
    case BusinessCode.consignReturnNeedsClient:
      return l.bizConsignReturnNeedsClient;
    case BusinessCode.creditNeedsClient:
      return l.bizCreditNeedsClient;
    case BusinessCode.paidAmountNotAllowed:
      return l.bizPaidAmountNotAllowed;
    case BusinessCode.overpaid:
      return l.bizOverpaid;
    case BusinessCode.priceMissing:
      return l.bizPriceMissing;
    case BusinessCode.unitNotFound:
      return l.bizUnitNotFound;
    case BusinessCode.productNotFound:
      return l.bizProductNotFound;
    case BusinessCode.productInactive:
      return l.bizProductInactive;
    case BusinessCode.clientNotFound:
      return l.bizClientNotFound;
    case BusinessCode.clientInactive:
      return l.bizClientInactive;
    case BusinessCode.alreadyCancelled:
      return l.bizAlreadyCancelled;
    case BusinessCode.cannotCancelReversal:
      return l.bizCannotCancelReversal;
    case BusinessCode.cancelConsignConflict:
      return l.bizCancelConsignConflict;
    case BusinessCode.saleNotFound:
      return l.bizSaleNotFound;
    case BusinessCode.saleClientMismatch:
      return l.bizSaleClientMismatch;
    case BusinessCode.saleNotCredit:
      return l.bizSaleNotCredit;
    case BusinessCode.saleCancelled:
      return l.bizSaleCancelled;
    case BusinessCode.wrongPin:
      return l.bizWrongPin;
    case BusinessCode.samePin:
      return l.bizSamePin;
    case BusinessCode.cannotDeactivateSelf:
      return l.bizCannotDeactivateSelf;
    case BusinessCode.lastManager:
      return l.bizLastManager;
    case BusinessCode.noChange:
      return l.bizNoChange(e.intContext('current') ?? 0);
    case BusinessCode.lossMustDecrease:
      return l.bizLossMustDecrease;
    case BusinessCode.adjustmentBelowZero:
      return l.bizAdjustmentBelowZero;
    case BusinessCode.unknown:
      return l.bizUnknown;
  }
}
