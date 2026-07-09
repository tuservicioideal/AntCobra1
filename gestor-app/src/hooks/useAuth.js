import { useState, useEffect } from 'react';
import { onAuthStateChanged, signOut } from 'firebase/auth';
import { doc, getDoc, setDoc, collection, query, where, getDocs } from 'firebase/firestore';
import { auth, db } from '../services/firebase';

/**
 * useAuth — Robust auth hook with multi-source profile resolution.
 *
 * Problem: The desktop admin creates Firestore profile docs keyed by UID,
 * while the web admin may create additional docs with email-derived IDs.
 * Emails may also differ in case between Auth (lowercase) and Firestore.
 *
 * Solution: Search by UID AND by email (case-insensitive), merge all
 * found data, then auto-sync back to the canonical UID document so that
 * subsequent logins are fast and consistent.
 */
export function useAuth() {
  const [user, setUser] = useState(null);
  const [userData, setUserData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, async (firebaseUser) => {
      if (firebaseUser) {
        setUser(firebaseUser);
        try {
          const email = (firebaseUser.email || '').trim();
          const emailLower = email.toLowerCase();

          // ────── Step 1: Collect data from every possible source ──────
          let uidData = null;
          let uidDocExists = false;
          const emailDocs = []; // { id, ...data }

          // Helper: safely execute a Firestore read (won't break the chain on permission errors)
          const safeGet = async (ref) => {
            try { return await getDoc(ref); } catch { return null; }
          };
          const safeQuery = async (q) => {
            try { return await getDocs(q); } catch { return null; }
          };

          // 1a) Direct UID lookup (fastest — desktop-app creates these)
          const byUid = await safeGet(doc(db, 'usuarios', firebaseUser.uid));
          if (byUid && byUid.exists()) {
            uidDocExists = true;
            uidData = byUid.data();
          }

          // 1b) Query by email field — exact match
          const snap1 = await safeQuery(
            query(collection(db, 'usuarios'), where('email', '==', email))
          );
          if (snap1) {
            snap1.forEach((d) => {
              if (d.id !== firebaseUser.uid) {
                emailDocs.push({ id: d.id, ...d.data() });
              }
            });
          }

          // 1c) Query by lowercase email if different (handles case mismatch)
          if (emailLower !== email) {
            const snap2 = await safeQuery(
              query(collection(db, 'usuarios'), where('email', '==', emailLower))
            );
            if (snap2) {
              snap2.forEach((d) => {
                if (d.id !== firebaseUser.uid && !emailDocs.find(e => e.id === d.id)) {
                  emailDocs.push({ id: d.id, ...d.data() });
                }
              });
            }
          }

          // 1d) Also check the common email-derived ID pattern
          const emailDerivedId = emailLower.replace(/[^a-zA-Z0-9]/g, '_');
          if (emailDerivedId !== firebaseUser.uid) {
            const byDerived = await safeGet(doc(db, 'usuarios', emailDerivedId));
            if (byDerived && byDerived.exists() && !emailDocs.find(e => e.id === emailDerivedId)) {
              emailDocs.push({ id: emailDerivedId, ...byDerived.data() });
            }
          }

          // ────── Step 2: Merge all sources, preferring most recently updated ──────
          const allProfileDocs = [];
          if (uidData) allProfileDocs.push(uidData);
          allProfileDocs.push(...emailDocs);

          // Sort by newest timestamp first
          // Firestore timestamps may be Timestamp objects, strings, or missing
          const _tsToStr = (v) => {
            if (!v) return '';
            if (typeof v === 'string') return v;
            if (v.toDate) return v.toDate().toISOString();   // Firestore Timestamp
            if (v instanceof Date) return v.toISOString();
            return String(v);
          };
          allProfileDocs.sort((a, b) => {
            const ta = _tsToStr(a.fecha_actualizacion) || _tsToStr(a.fecha_sync) || _tsToStr(a.fecha_creacion);
            const tb = _tsToStr(b.fecha_actualizacion) || _tsToStr(b.fecha_sync) || _tsToStr(b.fecha_creacion);
            return tb.localeCompare(ta);
          });

          // Build best profile: newest doc is base, fill gaps from older ones
          let best = null;
          for (const d of allProfileDocs) {
            if (!best) {
              best = { ...d };
            } else {
              const fields = ['seccion', 'secciones', 'nombre', 'telefono', 'zona', 'region', 'rol', 'activo'];
              for (const f of fields) {
                if ((best[f] === undefined || best[f] === null || best[f] === '') && d[f]) {
                  best[f] = d[f];
                }
              }
            }
          }

          // ────── Step 3: Auto-sync the canonical UID document ──────
          // If the merged profile differs from the UID doc, update it.
          // This ensures future logins are instant (single UID lookup).
          if (best && best.seccion) {
            const needsSync =
              !uidDocExists ||
              !uidData?.seccion ||
              uidData.seccion !== best.seccion ||
              uidData.nombre !== best.nombre ||
              uidData.rol !== best.rol;

            if (needsSync) {
              try {
                await setDoc(doc(db, 'usuarios', firebaseUser.uid), {
                  ...best,
                  uid: firebaseUser.uid,
                  email: emailLower,
                  fecha_sync: new Date().toISOString(),
                }, { merge: true });
                console.info('[useAuth] Synced profile to UID doc ✓');
              } catch (syncErr) {
                console.warn('[useAuth] Could not sync UID doc:', syncErr);
              }
            }
          }

          // ────── Step 4: Set user data ──────
          if (best) {
            // Ensure email is always present
            if (!best.email) best.email = emailLower;

            // Check if user is deactivated
            if (best.activo === false) {
              console.warn('[useAuth] User account is deactivated');
              await signOut(auth);
              setUser(null);
              setUserData(null);
              setLoading(false);
              return;
            }

            setUserData(best);
          } else {
            // No profile found anywhere — create minimal from Auth
            const minimal = {
              nombre: firebaseUser.displayName || email,
              email: emailLower,
              seccion: '',
              rol: 'gestor',
            };
            setUserData(minimal);
            // Auto-create the profile doc so admin can see & edit them later
            try {
              await setDoc(doc(db, 'usuarios', firebaseUser.uid), {
                ...minimal,
                uid: firebaseUser.uid,
                activo: true,
                fecha_creacion: new Date().toISOString(),
              });
            } catch (e) {
              console.warn('[useAuth] Could not create placeholder profile:', e);
            }
          }
        } catch (err) {
          console.error('[useAuth] Error fetching user data:', err);
          setUserData({
            nombre: firebaseUser.displayName || firebaseUser.email,
            email: (firebaseUser.email || '').toLowerCase(),
            seccion: '',
            rol: 'gestor',
          });
        }
      } else {
        setUser(null);
        setUserData(null);
      }
      setLoading(false);
    });

    return () => unsubscribe();
  }, []);

  return { user, userData, loading };
}
