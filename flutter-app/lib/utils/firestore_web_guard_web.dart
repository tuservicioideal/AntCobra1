import 'dart:js_interop';
import 'dart:js_interop_unsafe';

import 'package:web/web.dart' as web;

import 'firestore_web_recovery.dart';

const _reloadFlag = 'ac_fs_assertion_reload';
const _hookFlag = '_acFsConsoleHooked';

void maybeReloadForFirestoreAssertion(Object? error) {
  if (!isFirestoreInternalAssertion(error)) return;
  final already = web.window.sessionStorage.getItem(_reloadFlag) == '1';
  if (!shouldReloadAfterFirestoreAssertion(alreadyReloadedThisSession: already)) {
    return;
  }
  web.window.sessionStorage.setItem(_reloadFlag, '1');
  web.window.location.reload();
}

void installFirestoreWebGuard() {
  web.window.addEventListener(
    'unhandledrejection',
    (web.Event event) {
      final rejection = event as web.PromiseRejectionEvent;
      maybeReloadForFirestoreAssertion(
        combineErrorSources([
          rejection.reason?.toString(),
          _jsValueToProbeText(rejection.reason),
        ]),
      );
    }.toJS,
  );

  web.window.addEventListener(
    'error',
    (web.Event event) {
      final errorEvent = event as web.ErrorEvent;
      maybeReloadForFirestoreAssertion(
        combineErrorSources([
          errorEvent.message,
          _jsValueToProbeText(errorEvent.error),
        ]),
      );
    }.toJS,
  );

  _hookConsoleError();

  // After a successful recovery, allow another reload later in the session.
  web.window.setTimeout(
    () {
      web.window.sessionStorage.removeItem(_reloadFlag);
    }.toJS,
    60000.toJS,
  );
}

void _hookConsoleError() {
  final hooked = globalContext.getProperty(_hookFlag.toJS);
  if (hooked.isDefinedAndNotNull) return;
  globalContext.setProperty(_hookFlag.toJS, true.toJS);

  final console = globalContext.getProperty('console'.toJS);
  if (console == null || !console.isA<JSObject>()) return;
  final consoleObj = console as JSObject;
  final original = consoleObj.getProperty('error'.toJS);
  if (original == null || !original.isA<JSFunction>()) return;
  final originalFn = original as JSFunction;

  JSAny? hookedError(JSAny? a, [JSAny? b, JSAny? c, JSAny? d]) {
    maybeReloadForFirestoreAssertion(
      combineErrorSources([
        _jsValueToProbeText(a),
        _jsValueToProbeText(b),
        _jsValueToProbeText(c),
        _jsValueToProbeText(d),
      ]),
    );
    if (d != null) {
      return originalFn.callAsFunction(consoleObj, a, b, c, d);
    }
    if (c != null) {
      return originalFn.callAsFunction(consoleObj, a, b, c);
    }
    if (b != null) {
      return originalFn.callAsFunction(consoleObj, a, b);
    }
    return originalFn.callAsFunction(consoleObj, a);
  }

  consoleObj.setProperty('error'.toJS, hookedError.toJS);
}

String _jsValueToProbeText(JSAny? value) {
  if (value == null) return '';
  final parts = <String>[value.toString()];
  if (value.isA<JSObject>()) {
    final obj = value as JSObject;
    final name = obj.getProperty<JSAny?>('name'.toJS);
    final message = obj.getProperty<JSAny?>('message'.toJS);
    final stack = obj.getProperty<JSAny?>('stack'.toJS);
    if (name != null) parts.add(name.toString());
    if (message != null) parts.add(message.toString());
    if (stack != null) parts.add(stack.toString());
  }
  return combineErrorSources(parts);
}
