/**
 * User creation service — Creates Firebase Auth accounts for new users
 * using a secondary Firebase app instance so the current admin stays logged in.
 */

import { initializeApp, deleteApp } from 'firebase/app';
import { getAuth, createUserWithEmailAndPassword, updateProfile } from 'firebase/auth';

// Same config as main app — we just use a separate instance
const firebaseConfig = {
  apiKey: "AIzaSyBubpxyyN2YvcPaU6WUJkrF2IQUOzFVYWg",
  authDomain: "clase-001.firebaseapp.com",
  projectId: "clase-001",
  storageBucket: "clase-001.firebasestorage.app",
  messagingSenderId: "445584901998",
  appId: "1:445584901998:web:5c3087ceb65418619ee37f",
};

/**
 * Create a new Firebase Auth user with email + password.
 * Uses a temporary secondary Firebase app so the admin session is not affected.
 *
 * @param {string} email
 * @param {string} password
 * @param {string} displayName
 * @returns {Promise<{uid: string|null, error: string|null}>}
 */
export async function createUserWithPassword(email, password, displayName) {
  let secondaryApp = null;
  try {
    // Create a temporary Firebase app instance
    secondaryApp = initializeApp(firebaseConfig, `_temp_user_create_${Date.now()}`);
    const secondaryAuth = getAuth(secondaryApp);

    // Create the user on this secondary instance
    const credential = await createUserWithEmailAndPassword(secondaryAuth, email, password);
    const uid = credential.user.uid;

    // Set display name
    if (displayName) {
      await updateProfile(credential.user, { displayName });
    }

    // Sign out from secondary auth (cleanup)
    await secondaryAuth.signOut();

    return { uid, error: null };
  } catch (err) {
    let message = err.message;
    if (err.code === 'auth/email-already-in-use') {
      message = 'Ya existe una cuenta con este correo electrónico';
    } else if (err.code === 'auth/weak-password') {
      message = 'La contraseña es muy débil (mínimo 6 caracteres)';
    } else if (err.code === 'auth/invalid-email') {
      message = 'El correo electrónico no es válido';
    }
    return { uid: null, error: message };
  } finally {
    // Always clean up the secondary app
    if (secondaryApp) {
      try { await deleteApp(secondaryApp); } catch (_) { /* ignore */ }
    }
  }
}
