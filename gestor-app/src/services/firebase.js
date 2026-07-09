import { initializeApp } from "firebase/app";
import { getAuth } from "firebase/auth";
import { getStorage } from "firebase/storage";
import {
  initializeFirestore,
  persistentLocalCache,
  persistentSingleTabManager,
} from "firebase/firestore";

const firebaseConfig = {
  apiKey: "AIzaSyBubpxyyN2YvcPaU6WUJkrF2IQUOzFVYWg",
  authDomain: "clase-001.firebaseapp.com",
  projectId: "clase-001",
  storageBucket: "clase-001.firebasestorage.app",
  messagingSenderId: "445584901998",
  appId: "1:445584901998:web:5c3087ceb65418619ee37f",
  measurementId: "G-LV7V8QBRKM"
};

const app = initializeApp(firebaseConfig);
export const auth = getAuth(app);

// Enable Firestore offline persistence (IndexedDB cache)
// Allows gestors to read cached data when offline and auto-syncs when back online
export const db = initializeFirestore(app, {
  localCache: persistentLocalCache({
    tabManager: persistentSingleTabManager({}),
  }),
});
export const storage = getStorage(app);

// Safety net: if Firestore's persistent cache gets corrupted (e.g. after a
// permission-denied error on a listener), clear IndexedDB and reload once.
if (typeof window !== 'undefined') {
  window.addEventListener('unhandledrejection', (event) => {
    const msg = String(event?.reason?.message ?? '');
    if (msg.includes('INTERNAL ASSERTION FAILED') || msg.includes('Unexpected state')) {
      console.warn('[Firebase] Firestore cache corrupted. Clearing IndexedDB and reloading...');
      if (window.indexedDB?.databases) {
        window.indexedDB.databases().then((dbs) => {
          const tasks = dbs
            .filter((d) => d.name?.includes('firestore') || d.name?.includes('firebase'))
            .map((d) => window.indexedDB.deleteDatabase(d.name));
          Promise.allSettled(tasks).then(() => window.location.reload());
        }).catch(() => window.location.reload());
      } else {
        window.location.reload();
      }
    }
  });
}

export default app;
