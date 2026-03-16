import {
  CognitoUserPool,
  CognitoUser,
  AuthenticationDetails,
  CognitoUserSession,
} from 'amazon-cognito-identity-js';
import type { UserRole } from './roles';
import { ROLE_HIERARCHY } from './roles';

const userPoolId = process.env.NEXT_PUBLIC_COGNITO_USER_POOL_ID ?? '';
const clientId = process.env.NEXT_PUBLIC_COGNITO_CLIENT_ID ?? '';
const region = process.env.NEXT_PUBLIC_COGNITO_REGION ?? 'us-east-1';

if (!userPoolId) {
  console.warn('NEXT_PUBLIC_COGNITO_USER_POOL_ID is not set');
}
if (!clientId) {
  console.warn('NEXT_PUBLIC_COGNITO_CLIENT_ID is not set');
}

export const cognitoUserPool = new CognitoUserPool({
  UserPoolId: userPoolId || `${region}_placeholder`,
  ClientId: clientId || 'placeholder',
});

/**
 * Maps a Cognito group name to the application's UserRole type.
 */
const COGNITO_GROUP_TO_ROLE: Record<string, UserRole> = {
  Admin: 'admin',
  Approver: 'approver',
  'Builder-Prod': 'builder_prod',
  Builder: 'builder',
  Viewer: 'viewer',
};

/**
 * Authenticates a user with email and password using SRP auth flow.
 */
export function signIn(email: string, password: string): Promise<CognitoUserSession> {
  return new Promise((resolve, reject) => {
    const cognitoUser = new CognitoUser({
      Username: email,
      Pool: cognitoUserPool,
    });

    const authDetails = new AuthenticationDetails({
      Username: email,
      Password: password,
    });

    cognitoUser.authenticateUser(authDetails, {
      onSuccess: (session) => {
        resolve(session);
      },
      onFailure: (err) => {
        const message =
          err.code === 'NotAuthorizedException'
            ? 'Invalid email or password'
            : err.code === 'UserNotFoundException'
              ? 'No account found with this email'
              : err.code === 'UserNotConfirmedException'
                ? 'Account has not been confirmed. Please check your email.'
                : err.message || 'Authentication failed';
        reject(new Error(message));
      },
    });
  });
}

/**
 * Signs out the current user, clearing local session data.
 */
export function signOut(): void {
  const currentUser = cognitoUserPool.getCurrentUser();
  if (currentUser) {
    currentUser.signOut();
  }
}

/**
 * Gets the current valid session, refreshing the token if needed.
 * Returns null if no user is signed in or the session cannot be refreshed.
 */
export function getCurrentSession(): Promise<CognitoUserSession | null> {
  return new Promise((resolve) => {
    const currentUser = cognitoUserPool.getCurrentUser();
    if (!currentUser) {
      resolve(null);
      return;
    }

    currentUser.getSession(
      (err: Error | null, session: CognitoUserSession | null) => {
        if (err || !session || !session.isValid()) {
          resolve(null);
          return;
        }
        resolve(session);
      },
    );
  });
}

/**
 * Extracts user info from a Cognito session's ID token.
 * Maps Cognito groups to app roles using highest-precedence group.
 */
export function getUserFromSession(session: CognitoUserSession): {
  id: string;
  email: string;
  name: string;
  role: UserRole;
  groups: string[];
} {
  const idToken = session.getIdToken();
  const payload = idToken.decodePayload();

  const cognitoGroups: string[] = payload['cognito:groups'] ?? [];
  const groups = cognitoGroups.filter((g) => g in COGNITO_GROUP_TO_ROLE);

  const role = resolveHighestRole(groups);

  return {
    id: payload.sub as string,
    email: (payload.email as string) ?? '',
    name: (payload.name as string) ?? (payload.email as string) ?? '',
    role,
    groups: cognitoGroups,
  };
}

/**
 * Resolves the highest-precedence role from a list of Cognito group names.
 * Falls back to 'viewer' if no recognized groups are present.
 */
function resolveHighestRole(groups: string[]): UserRole {
  let highest: UserRole = 'viewer';
  let highestLevel = ROLE_HIERARCHY.viewer;

  for (const group of groups) {
    const mappedRole = COGNITO_GROUP_TO_ROLE[group];
    if (mappedRole && ROLE_HIERARCHY[mappedRole] > highestLevel) {
      highest = mappedRole;
      highestLevel = ROLE_HIERARCHY[mappedRole];
    }
  }

  return highest;
}
