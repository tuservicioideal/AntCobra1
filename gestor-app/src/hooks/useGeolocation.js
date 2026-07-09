import { useState, useCallback } from 'react';

export function useGeolocation() {
  const [location, setLocation] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  const getLocation = useCallback(() => {
    if (!navigator.geolocation) {
      setError('Tu dispositivo no soporta geolocalización');
      return Promise.reject('Geolocation not supported');
    }

    setLoading(true);
    setError(null);

    return new Promise((resolve, reject) => {
      navigator.geolocation.getCurrentPosition(
        (position) => {
          const loc = {
            latitude: position.coords.latitude,
            longitude: position.coords.longitude,
            accuracy: position.coords.accuracy,
            timestamp: new Date().toISOString(),
          };
          setLocation(loc);
          setLoading(false);
          resolve(loc);
        },
        (err) => {
          let msg = 'Error al obtener ubicación';
          switch (err.code) {
            case err.PERMISSION_DENIED:
              msg = 'Permiso de ubicación denegado. Activa el GPS.';
              break;
            case err.POSITION_UNAVAILABLE:
              msg = 'Ubicación no disponible';
              break;
            case err.TIMEOUT:
              msg = 'Tiempo de espera agotado';
              break;
          }
          setError(msg);
          setLoading(false);
          reject(msg);
        },
        {
          enableHighAccuracy: true,
          timeout: 15000,
          maximumAge: 0,
        }
      );
    });
  }, []);

  return { location, error, loading, getLocation };
}
