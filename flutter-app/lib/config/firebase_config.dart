import 'package:firebase_core/firebase_core.dart' show FirebaseOptions;
import 'package:flutter/foundation.dart'
    show defaultTargetPlatform, kIsWeb, TargetPlatform;

/// Firebase configuration for the "clase-001" project.
/// Same project as the gestor-app web and admin desktop.
class FirebaseConfig {
  static FirebaseOptions get currentPlatform {
    if (kIsWeb) {
      return web;
    }
    switch (defaultTargetPlatform) {
      case TargetPlatform.android:
        return android;
      case TargetPlatform.iOS:
        return ios;
      default:
        return web;
    }
  }

  /// Web configuration (same as gestor-app)
  static const FirebaseOptions web = FirebaseOptions(
    apiKey: 'AIzaSyBubpxyyN2YvcPaU6WUJkrF2IQUOzFVYWg',
    appId: '1:445584901998:web:5c3087ceb65418619ee37f',
    messagingSenderId: '445584901998',
    projectId: 'clase-001',
    authDomain: 'clase-001.firebaseapp.com',
    storageBucket: 'clase-001.firebasestorage.app',
    measurementId: 'G-LV7V8QBRKM',
  );

  /// Android configuration
  /// NOTE: You must download google-services.json from Firebase Console
  /// and place it in flutter-app/android/app/google-services.json
  static const FirebaseOptions android = FirebaseOptions(
    apiKey: 'AIzaSyDt9ySU5WKPc5pUuwTdvEWcXjGbA2Xi9Wk',
    appId: '1:445584901998:android:f7a6ec3a7d55f13b9ee37f',
    messagingSenderId: '445584901998',
    projectId: 'clase-001',
    storageBucket: 'clase-001.firebasestorage.app',
  );

  /// iOS configuration
  /// NOTE: You must download GoogleService-Info.plist from Firebase Console
  /// and place it in flutter-app/ios/Runner/GoogleService-Info.plist
  static const FirebaseOptions ios = FirebaseOptions(
    apiKey: 'REPLACE_WITH_IOS_API_KEY',
    appId: '1:445584901998:ios:REPLACE_WITH_IOS_APP_ID',
    messagingSenderId: '445584901998',
    projectId: 'clase-001',
    storageBucket: 'clase-001.firebasestorage.app',
    iosBundleId: 'com.fym.recaudolegal.appRecaudoLegal',
  );
}
