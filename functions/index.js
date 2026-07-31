const { initializeApp } = require("firebase-admin/app");
const { onCall } = require("firebase-functions/v2/https");
const {
  createGestorUserHandler,
  updateGestorUserHandler,
  deleteGestorUserHandler,
  ensureCanonicalUserProfileHandler,
} = require("./src/gestorUsers");

initializeApp();

exports.createGestorUser = onCall(
  { region: "us-central1" },
  createGestorUserHandler
);

exports.updateGestorUser = onCall(
  { region: "us-central1" },
  updateGestorUserHandler
);

exports.deleteGestorUser = onCall(
  { region: "us-central1" },
  deleteGestorUserHandler
);

exports.ensureCanonicalUserProfile = onCall(
  { region: "us-central1" },
  ensureCanonicalUserProfileHandler
);
