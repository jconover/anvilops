import { createRemoteJWKSet, jwtVerify } from 'jose';
import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

const PUBLIC_ROUTES = [
  '/login',
  '/api/auth/session',
  '/api/v1/health',
  '/_next/static',
  '/_next/image',
  '/favicon.ico',
  '/health',
];

function isPublicRoute(pathname: string): boolean {
  return PUBLIC_ROUTES.some((route) => pathname.startsWith(route));
}

// Cache the JWKS remote key set across requests
let jwks: ReturnType<typeof createRemoteJWKSet> | null = null;
let jwksIssuer: string | null = null;

function getJwksKeySet(
  userPoolId: string,
  region: string,
): ReturnType<typeof createRemoteJWKSet> {
  const issuer = `https://cognito-idp.${region}.amazonaws.com/${userPoolId}`;
  if (!jwks || jwksIssuer !== issuer) {
    jwks = createRemoteJWKSet(
      new URL(`${issuer}/.well-known/jwks.json`),
    );
    jwksIssuer = issuer;
  }
  return jwks;
}

async function verifyToken(token: string): Promise<boolean> {
  const userPoolId = process.env.NEXT_PUBLIC_COGNITO_USER_POOL_ID;
  const region = process.env.NEXT_PUBLIC_COGNITO_REGION ?? 'us-east-1';

  if (!userPoolId) {
    console.error('CRITICAL: NEXT_PUBLIC_COGNITO_USER_POOL_ID is not configured. Denying all requests.');
    return false;
  }

  const issuer = `https://cognito-idp.${region}.amazonaws.com/${userPoolId}`;

  try {
    const keySet = getJwksKeySet(userPoolId, region);
    const clientId = process.env.NEXT_PUBLIC_COGNITO_CLIENT_ID;
    const { payload } = await jwtVerify(token, keySet, {
      issuer,
      audience: clientId,
    });

    if (payload.token_use !== 'id') {
      return false;
    }

    return true;
  } catch {
    return false;
  }
}

function getSafeCallbackUrl(pathname: string): string {
  if (pathname.startsWith('/') && !pathname.startsWith('//')) {
    return pathname;
  }
  return '/';
}

function redirectToLogin(request: NextRequest, pathname: string): NextResponse {
  const loginUrl = new URL('/login', request.url);
  loginUrl.searchParams.set('callbackUrl', getSafeCallbackUrl(pathname));
  return NextResponse.redirect(loginUrl);
}

export async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  if (isPublicRoute(pathname)) {
    return NextResponse.next();
  }

  const tokenFromCookie = request.cookies.get('anvilops_token')?.value;
  const authHeader = request.headers.get('Authorization');
  const tokenFromHeader = authHeader?.startsWith('Bearer ') ? authHeader.slice(7) : undefined;
  const token = tokenFromCookie || tokenFromHeader;

  if (!token) {
    return redirectToLogin(request, pathname);
  }

  const valid = await verifyToken(token);
  if (!valid) {
    return redirectToLogin(request, pathname);
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    '/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)',
  ],
};
