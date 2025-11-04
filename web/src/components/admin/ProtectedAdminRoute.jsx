import React, { useEffect, useState } from 'react';
import { Navigate } from 'react-router-dom';
import PropTypes from 'prop-types';
import { useTranslation } from 'react-i18next';
import { isAdmin, testAdminAccess } from '../../utils/adminApi';

/**
 * ProtectedAdminRoute - US-013: Access Control
 *
 * Protects admin routes by:
 * 1. Checking JWT token exists
 * 2. Verifying is_admin flag in token
 * 3. Testing backend admin access
 * 4. Redirecting non-admin users with 403 toast
 * 5. Handling token expiration gracefully
 */
export default function ProtectedAdminRoute({ token, children, onUnauthorized }) {
  const { t } = useTranslation();
  const [checking, setChecking] = useState(true);
  const [authorized, setAuthorized] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    async function checkAccess() {
      // Step 1: Check token exists
      if (!token) {
        setError('No token - redirecting to login');
        setChecking(false);
        return;
      }

      // Step 2: Check is_admin flag in JWT (client-side check)
      if (!isAdmin(token)) {
        setError('Not admin - 403 Forbidden');
        setChecking(false);
        if (onUnauthorized) {
          onUnauthorized('Admin access required. You do not have permission to access this page.');
        }
        return;
      }

      // Step 3: Verify with backend (server-side validation)
      try {
        await testAdminAccess(token);
        setAuthorized(true);
        setError(null);
      } catch (err) {
        console.error('[ProtectedAdminRoute] Backend check failed:', err);
        setError('Backend verification failed');
        if (onUnauthorized) {
          onUnauthorized('Admin access required. You do not have permission to access this page.');
        }
      } finally {
        setChecking(false);
      }
    }

    checkAccess();
  }, [token, onUnauthorized]);

  // Loading state
  if (checking) {
    return (
      <div className="min-h-screen bg-bg flex items-center justify-center">
        <div className="text-center">
          <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-accent mb-4"></div>
          <p className="text-muted">{t('common.loading') || 'Verifying access...'}</p>
        </div>
      </div>
    );
  }

  // Not authorized - redirect to /rooms
  if (error || !authorized) {
    return <Navigate to="/rooms" replace />;
  }

  // Authorized - render children
  return <>{children}</>;
}

ProtectedAdminRoute.propTypes = {
  token: PropTypes.string.isRequired,
  children: PropTypes.node.isRequired,
  onUnauthorized: PropTypes.func,
};
