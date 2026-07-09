const { getAuth } = require("firebase-admin/auth");
const { getFirestore, FieldValue } = require("firebase-admin/firestore");
const { HttpsError } = require("firebase-functions/v2/https");

const VALID_ROLES = ["gestor", "asistente", "supervisor", "admin"];
const VALID_CANALES = ["campo", "call"];

/**
 * Verify caller is an active admin or supervisor.
 * @param {import('firebase-functions/v2/https').CallableRequest} request
 */
async function assertCanManageUsers(request) {
  if (!request.auth) {
    throw new HttpsError("unauthenticated", "Debes iniciar sesión.");
  }

  const callerUid = request.auth.uid;
  const db = getFirestore();
  const callerDoc = await db.collection("usuarios").doc(callerUid).get();

  if (!callerDoc.exists) {
    throw new HttpsError("permission-denied", "Perfil no encontrado.");
  }

  const caller = callerDoc.data() || {};
  const rol = caller.rol || "";
  const activo = caller.activo !== false;

  if (!activo || !["admin", "supervisor"].includes(rol)) {
    throw new HttpsError(
      "permission-denied",
      "Solo administradores o supervisores pueden gestionar usuarios."
    );
  }
}

/**
 * Normalize role and canal (mirrors firebase_service.py).
 */
function normalizeRoleCanal(rol, canal) {
  let normalizedRol = (rol || "gestor").trim().toLowerCase();
  if (!VALID_ROLES.includes(normalizedRol)) {
    normalizedRol = "gestor";
  }

  let normalizedCanal = (canal || "campo").trim().toLowerCase();
  if (!VALID_CANALES.includes(normalizedCanal)) {
    normalizedCanal = "campo";
  }

  if (normalizedRol !== "gestor") {
    normalizedCanal = "campo";
  }

  return { rol: normalizedRol, canal: normalizedCanal };
}

/**
 * Build secciones list (mirrors firebase_service.py create_gestor_user).
 */
function buildSecciones({
  rol,
  canal,
  secciones,
  seccion,
  region,
  zona,
  uid,
}) {
  const normalizedSeccion = (seccion || "").trim().toUpperCase();
  let finalRegion = region || "";
  let finalZona = zona || "";
  let finalSeccion = normalizedSeccion;
  let finalSecciones = [];

  if (canal === "call" && rol === "gestor") {
    if (uid) {
      finalSecciones = [`_CALL_${uid}`];
    }
    return {
      secciones: finalSecciones,
      region: finalRegion,
      zona: finalZona,
      seccion: finalSeccion,
    };
  }

  if (Array.isArray(secciones) && secciones.length > 0) {
    finalSecciones = [...new Set(secciones.map((s) => String(s).trim()).filter(Boolean))].sort();
    if (finalSecciones.length > 0) {
      const parts = finalSecciones[0].split("_");
      if (parts.length === 3) {
        finalRegion = finalRegion || parts[0];
        finalZona = finalZona || parts[1];
        finalSeccion = finalSeccion || parts[2];
      }
    }
  } else if (finalRegion && finalZona && finalSeccion) {
    finalSecciones = [`${finalRegion}_${finalZona}_${finalSeccion}`];
  } else if (finalSeccion) {
    finalSecciones = [finalSeccion];
  }

  return {
    secciones: finalSecciones,
    region: finalRegion,
    zona: finalZona,
    seccion: finalSeccion,
  };
}

function emailDerivedDocId(email) {
  return email.trim().toLowerCase().replace(/\./g, "_").replace(/@/g, "_");
}

/**
 * Create Firebase Auth user + Firestore profile.
 */
async function createGestorUserHandler(request) {
  await assertCanManageUsers(request);

  const data = request.data || {};
  const email = (data.email || "").trim().toLowerCase();
  const password = data.password || "";
  const nombre = (data.nombre || "").trim();
  const telefono = (data.telefono || "").trim();
  let region = (data.region || "").trim();
  let zona = (data.zona || "").trim();
  const seccion = data.seccion || "";
  const secciones = data.secciones;
  const { rol, canal } = normalizeRoleCanal(data.rol, data.canal);

  if (!nombre) {
    throw new HttpsError("invalid-argument", "El nombre es obligatorio.");
  }
  if (!email) {
    throw new HttpsError("invalid-argument", "El correo es obligatorio.");
  }
  if (!password || password.length < 6) {
    throw new HttpsError(
      "invalid-argument",
      "La contraseña debe tener al menos 6 caracteres."
    );
  }

  const isCallGestor = rol === "gestor" && canal === "call";
  const needsSections = (rol === "gestor" && !isCallGestor) || rol === "asistente";

  const preBuild = buildSecciones({
    rol,
    canal,
    secciones,
    seccion,
    region,
    zona,
    uid: null,
  });

  if (needsSections && preBuild.secciones.length === 0) {
    throw new HttpsError(
      "invalid-argument",
      "Gestores de campo y asistentes requieren al menos una sección."
    );
  }

  const auth = getAuth();
  const db = getFirestore();

  try {
    const userRecord = await auth.createUser({
      email,
      password,
      displayName: nombre,
    });

    const built = buildSecciones({
      rol,
      canal,
      secciones,
      seccion,
      region: preBuild.region,
      zona: preBuild.zona,
      uid: userRecord.uid,
    });

    const profileData = {
      nombre,
      email,
      seccion: built.seccion,
      secciones: built.secciones,
      telefono,
      zona: built.zona,
      region: built.region,
      rol,
      canal,
      activo: true,
      uid: userRecord.uid,
      fecha_creacion: FieldValue.serverTimestamp(),
    };

    await db.collection("usuarios").doc(userRecord.uid).set(profileData);

    return { uid: userRecord.uid, success: true };
  } catch (err) {
    const code = err.code || "";
    if (code === "auth/email-already-exists") {
      throw new HttpsError(
        "already-exists",
        "Ya existe un usuario con ese correo electrónico."
      );
    }
    if (code === "auth/invalid-password" || code === "auth/weak-password") {
      throw new HttpsError(
        "invalid-argument",
        "La contraseña es demasiado débil."
      );
    }
    throw new HttpsError("internal", err.message || "Error al crear usuario.");
  }
}

/**
 * Update user Auth + Firestore profile.
 */
async function updateGestorUserHandler(request) {
  await assertCanManageUsers(request);

  const data = request.data || {};
  const uid = (data.uid || "").trim();
  if (!uid) {
    throw new HttpsError("invalid-argument", "UID obligatorio.");
  }

  const updates = { ...(data.updates || {}) };
  const password = updates.password;
  delete updates.password;

  const auth = getAuth();
  const db = getFirestore();

  const authUpdates = {};
  if (updates.nombre !== undefined) {
    authUpdates.displayName = updates.nombre;
  }
  if (password && String(password).trim().length >= 6) {
    authUpdates.password = String(password).trim();
  } else if (password && String(password).trim().length > 0) {
    throw new HttpsError(
      "invalid-argument",
      "La contraseña debe tener al menos 6 caracteres."
    );
  }

  try {
    if (Object.keys(authUpdates).length > 0) {
      await auth.updateUser(uid, authUpdates);
    }

    if (Object.keys(updates).length > 0) {
      await db.collection("usuarios").doc(uid).update(updates);

      const userDoc = await db.collection("usuarios").doc(uid).get();
      if (userDoc.exists) {
        const email = (userDoc.data() || {}).email || "";
        if (email) {
          const emailKey = emailDerivedDocId(email);
          if (emailKey !== uid) {
            const dup = await db.collection("usuarios").doc(emailKey).get();
            if (dup.exists) {
              await db.collection("usuarios").doc(emailKey).update(updates);
            }
          }
        }
      }
    }

    return { success: true };
  } catch (err) {
    throw new HttpsError("internal", err.message || "Error al actualizar usuario.");
  }
}

/**
 * Delete user from Auth + Firestore (including duplicate docs).
 */
async function deleteGestorUserHandler(request) {
  await assertCanManageUsers(request);

  const uid = (request.data?.uid || "").trim();
  if (!uid) {
    throw new HttpsError("invalid-argument", "UID obligatorio.");
  }

  const auth = getAuth();
  const db = getFirestore();

  try {
    const userDoc = await db.collection("usuarios").doc(uid).get();
    const email = userDoc.exists ? (userDoc.data() || {}).email || "" : "";

    await auth.deleteUser(uid);
    await db.collection("usuarios").doc(uid).delete();

    if (email) {
      const emailKey = emailDerivedDocId(email);
      if (emailKey !== uid) {
        try {
          await db.collection("usuarios").doc(emailKey).delete();
        } catch (_) {
          // May not exist
        }
      }

      const emailDocs = await db
        .collection("usuarios")
        .where("email", "==", email.trim().toLowerCase())
        .get();
      for (const doc of emailDocs.docs) {
        if (doc.id !== uid) {
          await doc.ref.delete();
        }
      }
    }

    return { success: true };
  } catch (err) {
    if (err.code === "auth/user-not-found") {
      // Still try to clean Firestore
      try {
        await db.collection("usuarios").doc(uid).delete();
      } catch (_) {}
      return { success: true };
    }
    throw new HttpsError("internal", err.message || "Error al eliminar usuario.");
  }
}

module.exports = {
  assertCanManageUsers,
  normalizeRoleCanal,
  buildSecciones,
  createGestorUserHandler,
  updateGestorUserHandler,
  deleteGestorUserHandler,
};
