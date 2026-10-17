/// Codes d'erreur métier renvoyés par l'API (400 avec `code`), voir docs/api.md « Codes d'erreur métier ».
/// Un test vérifie que cette liste couvre exactement les codes documentés.
enum BusinessCode {
  insufficientStock('insufficient_stock'),
  creditLimitExceeded('credit_limit_exceeded'),
  consignReturnExceedsHoldings('consign_return_exceeds_holdings'),
  consignableNeedsClient('consignable_needs_client'),
  consignReturnNeedsClient('consign_return_needs_client'),
  creditNeedsClient('credit_needs_client'),
  paidAmountNotAllowed('paid_amount_not_allowed'),
  overpaid('overpaid'),
  priceMissing('price_missing'),
  unitNotFound('unit_not_found'),
  productNotFound('product_not_found'),
  productInactive('product_inactive'),
  clientNotFound('client_not_found'),
  clientInactive('client_inactive'),
  alreadyCancelled('already_cancelled'),
  cannotCancelReversal('cannot_cancel_reversal'),
  cancelConsignConflict('cancel_consign_conflict'),
  saleNotFound('sale_not_found'),
  saleClientMismatch('sale_client_mismatch'),
  saleNotCredit('sale_not_credit'),
  saleCancelled('sale_cancelled'),
  wrongPin('wrong_pin'),
  samePin('same_pin'),
  cannotDeactivateSelf('cannot_deactivate_self'),
  lastManager('last_manager'),
  noChange('no_change'),
  lossMustDecrease('loss_must_decrease'),
  adjustmentBelowZero('adjustment_below_zero'),

  /// Code absent de cette liste (serveur plus récent que l'app) : le code brut reste dans `BusinessError.rawCode`.
  unknown('');

  const BusinessCode(this.wire);

  /// Valeur telle qu'elle circule dans le JSON.
  final String wire;

  static BusinessCode fromWire(String code) =>
      values.firstWhere((c) => c.wire == code && c != unknown, orElse: () => unknown);
}
