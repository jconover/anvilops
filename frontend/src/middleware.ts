import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

const PUBLIC_ROUTES = [
  '/login',
  '/api/v1/health',
  '/_next',
  '/favicon.ico',
  '/health',
];

function isPublicRoute(pathname: string): boolean {
  return PUBLIC_ROUTES.some((route) => pathname.startsWith(route));
}

interface JwtPayload {
  exp?: number;
  iss?: string;
  token_use?: string;
}

function decodeJwtPayload(token: string): JwtPayload | null {
  const parts = token.split('.');
  if (parts.length !== 3) {
    return null;
  }

  try {
    const base64Url = parts[1];
    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
    const json = atob(base64);
    return JSON.parse(json) as JwtPayload;
  } catch {
    return null;
  }
}

function isTokenValid(token: string): boolean {
  const payload = decodeJwtPayload(token);
  if (!payload) {
    return false;
  }

  if (typeof payload.exp !== 'number' || payload.exp * 1000 < Date.now()) {
    return false;
  }

  if (typeof payload.iss !== 'string' || !payload.iss.includes('cognito')) {
    return false;
  }

  if (payload.token_use !== 'id') {
    return false;
  }

  return true;
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

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  if (isPublicRoute(pathname)) {
    return NextResponse.next();
  }

  const tokenFromCookie = request.cookies.get('anvilops_token')?.value;
  const tokenFromHeader = request.headers
    .get('Authorization')
    ?.replace('Bearer ', '');
  const token = tokenFromCookie || tokenFromHeader;

  if (!token) {
    return redirectToLogin(request, pathname);
  }

  if (!isTokenValid(token)) {
    return redirectToLogin(request, pathname);
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    '/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)',
  ],
};
