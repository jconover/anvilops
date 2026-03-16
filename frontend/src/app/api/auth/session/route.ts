import { cookies } from 'next/headers';
import { NextResponse } from 'next/server';

const COOKIE_NAME = 'anvilops_token';
const COOKIE_MAX_AGE = 3600; // 1 hour in seconds

function validateJwt(token: string): { valid: boolean; error?: string } {
  const parts = token.split('.');
  if (parts.length !== 3) {
    return { valid: false, error: 'Invalid JWT structure' };
  }

  let payload: Record<string, unknown>;
  try {
    const paddedPayload = parts[1].replace(/-/g, '+').replace(/_/g, '/');
    const decoded = Buffer.from(paddedPayload, 'base64').toString('utf-8');
    payload = JSON.parse(decoded);
  } catch {
    return { valid: false, error: 'Invalid JWT payload' };
  }

  const now = Math.floor(Date.now() / 1000);
  if (typeof payload.exp !== 'number' || payload.exp <= now) {
    return { valid: false, error: 'Token is expired' };
  }

  if (typeof payload.iss !== 'string' || !payload.iss.includes('cognito')) {
    return { valid: false, error: 'Invalid token issuer' };
  }

  if (payload.token_use !== 'id') {
    return { valid: false, error: 'Invalid token use' };
  }

  return { valid: true };
}

export async function POST(request: Request) {
  let body: { token?: unknown };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: 'Invalid request body' }, { status: 400 });
  }

  const { token } = body;
  if (typeof token !== 'string' || !token) {
    return NextResponse.json({ error: 'Missing or invalid token' }, { status: 400 });
  }

  const validation = validateJwt(token);
  if (!validation.valid) {
    return NextResponse.json({ error: validation.error }, { status: 401 });
  }

  const cookieStore = await cookies();
  cookieStore.set(COOKIE_NAME, token, {
    httpOnly: true,
    secure: true,
    sameSite: 'strict',
    path: '/',
    maxAge: COOKIE_MAX_AGE,
  });

  return NextResponse.json({ success: true });
}

export async function DELETE() {
  const cookieStore = await cookies();
  cookieStore.set(COOKIE_NAME, '', {
    httpOnly: true,
    secure: true,
    sameSite: 'strict',
    path: '/',
    maxAge: 0,
  });

  return NextResponse.json({ success: true });
}
