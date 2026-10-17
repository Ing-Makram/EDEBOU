// ignore: unused_import
import 'package:intl/intl.dart' as intl;

import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for Arabic (`ar`).
class AppLocalizationsAr extends AppLocalizations {
  AppLocalizationsAr([String locale = 'ar']) : super(locale);

  @override
  String get appName => 'Edebou';

  @override
  String get language => 'اللغة';

  @override
  String get languageFrench => 'Français';

  @override
  String get languageArabic => 'العربية';

  @override
  String get loginTitle => 'تسجيل الدخول';

  @override
  String get loginSubtitle => 'أدخل اسمك والرمز السري';

  @override
  String get nameLabel => 'الاسم';

  @override
  String get pinLabel => 'الرمز السري';

  @override
  String get loginButton => 'دخول';

  @override
  String get nameRequired => 'أدخل اسمك.';

  @override
  String get pinFormat => 'الرمز السري من 4 إلى 6 أرقام.';

  @override
  String get pinBackspace => 'حذف';

  @override
  String get loginInvalidCredentials => 'الاسم أو الرمز السري غير صحيح.';

  @override
  String get sessionExpired => 'انتهت الجلسة. سجّل الدخول من جديد.';

  @override
  String get restoringSession => 'جارٍ فتح الجلسة…';

  @override
  String get retry => 'إعادة المحاولة';

  @override
  String get settings => 'الإعدادات';

  @override
  String get settingsTitle => 'الإعدادات';

  @override
  String get backendAddress => 'عنوان الخادم';

  @override
  String get backendAddressHelp =>
      'عنوان حاسوب المحل، مثال: http://127.0.0.1:8000';

  @override
  String get addressInvalid => 'عنوان غير صالح. مثال: http://127.0.0.1:8000';

  @override
  String get save => 'حفظ';

  @override
  String get saved => 'تم حفظ الإعدادات.';

  @override
  String get testConnection => 'اختبار الاتصال';

  @override
  String get testing => 'جارٍ الاختبار…';

  @override
  String get connectionOk => 'تم الاتصال بنجاح.';

  @override
  String get connectionNotEdebou => 'هناك خادم يستجيب لكنه ليس Edebou.';

  @override
  String get connectionUnreachable =>
      'تعذّر الوصول إلى الخادم. تحقق من العنوان ومن أن الخادم يعمل.';

  @override
  String get connectionTimeout => 'الخادم لا يستجيب (انتهت المهلة).';

  @override
  String get back => 'رجوع';

  @override
  String get homeTitle => 'الرئيسية';

  @override
  String welcomeUser(String name) {
    return 'مرحبًا، $name';
  }

  @override
  String get roleManager => 'المدير';

  @override
  String get roleCashier => 'أمين الصندوق';

  @override
  String get roleDelivery => 'عون التوصيل';

  @override
  String get moduleCashRegister => 'الصندوق';

  @override
  String get moduleClients => 'الحرفاء';

  @override
  String get moduleConsignments => 'العبوات المودعة';

  @override
  String get moduleStock => 'المخزون';

  @override
  String get comingSoon => 'قريبًا';

  @override
  String get logout => 'تسجيل الخروج';

  @override
  String get errorUnreachable => 'تعذّر الاتصال بالخادم.';

  @override
  String get errorTimeout => 'الخادم بطيء في الاستجابة.';

  @override
  String get errorForbidden => 'ليس لديك صلاحية لهذا الإجراء.';

  @override
  String get errorNotFound => 'العنصر غير موجود.';

  @override
  String get errorThrottled => 'محاولات كثيرة. انتظر دقيقة.';

  @override
  String get errorServer => 'خطأ في الخادم. أعد المحاولة.';

  @override
  String get errorUnknown => 'حدث خطأ.';

  @override
  String get errorValidation => 'بعض المعلومات غير صالحة.';

  @override
  String bizInsufficientStock(String product, int available) {
    return 'المخزون غير كافٍ لـ $product: المتوفر $available.';
  }

  @override
  String get bizCreditLimitExceeded => 'تم تجاوز سقف الدين.';

  @override
  String bizConsignReturnExceedsHoldings(int held) {
    return 'لدى الحريف $held فقط من هذا النوع.';
  }

  @override
  String get bizConsignableNeedsClient => 'هذا المنتج مودَع: اختر حريفًا.';

  @override
  String get bizConsignReturnNeedsClient => 'إرجاع العبوات يتطلب حريفًا.';

  @override
  String get bizCreditNeedsClient => 'البيع بالآجل يتطلب حريفًا.';

  @override
  String get bizPaidAmountNotAllowed => 'المبلغ المدفوع يخص البيع بالآجل فقط.';

  @override
  String get bizOverpaid => 'المبلغ المدفوع يتجاوز المجموع.';

  @override
  String get bizPriceMissing => 'لا يوجد سعر لهذا النوع من الحرفاء.';

  @override
  String get bizUnitNotFound => 'وحدة غير معروفة لهذا المنتج.';

  @override
  String get bizProductNotFound => 'المنتج غير موجود.';

  @override
  String get bizProductInactive => 'هذا المنتج معطّل.';

  @override
  String get bizClientNotFound => 'الحريف غير موجود.';

  @override
  String get bizClientInactive => 'هذا الحريف معطّل.';

  @override
  String get bizAlreadyCancelled => 'تم الإلغاء من قبل.';

  @override
  String get bizCannotCancelReversal => 'لا يمكن إلغاء عملية إلغاء.';

  @override
  String get bizCancelConsignConflict =>
      'تعذّر الإلغاء: أرجع الحريف العبوات مسبقًا.';

  @override
  String get bizSaleNotFound => 'عملية البيع غير موجودة.';

  @override
  String get bizSaleClientMismatch => 'هذا البيع لا يخص هذا الحريف.';

  @override
  String get bizSaleNotCredit => 'هذا البيع ليس بيعًا بالآجل.';

  @override
  String get bizSaleCancelled => 'هذا البيع ملغى.';

  @override
  String get bizWrongPin => 'الرمز السري القديم غير صحيح.';

  @override
  String get bizSamePin => 'يجب أن يختلف الرمز السري الجديد.';

  @override
  String get bizCannotDeactivateSelf => 'لا يمكنك تعطيل حسابك.';

  @override
  String get bizLastManager => 'يجب أن يبقى مدير واحد نشط على الأقل.';

  @override
  String bizNoChange(int current) {
    return 'المخزون المحسوب هو نفسه المخزون الحالي ($current).';
  }

  @override
  String get bizLossMustDecrease => 'الخسارة يجب أن تنقص المخزون.';

  @override
  String get bizAdjustmentBelowZero => 'لا يمكن أن يصبح المخزون سالبًا.';

  @override
  String get bizUnknown => 'رفض الخادم هذا الإجراء.';
}
