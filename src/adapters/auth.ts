import type { AuthenticatedUser } from '@/types/index.js';

export interface AuthAdapter {
  requireUser(request: Request): Promise<AuthenticatedUser>;
  requireRole(request: Request, role: 'buyer' | 'creator' | 'admin'): Promise<AuthenticatedUser>;
}

export class MockAuthAdapter implements AuthAdapter {
  private defaultUser: AuthenticatedUser;

  constructor(defaultUser?: AuthenticatedUser) {
    this.defaultUser = defaultUser ?? { user_id: 'default_user', role: 'buyer' };
  }

  async requireUser(request: Request): Promise<AuthenticatedUser> {
    const userId = request.headers.get('x-user-id');
    const role = (request.headers.get('x-user-role') as AuthenticatedUser['role']) || this.defaultUser.role;
    if (userId) {
      return { user_id: userId, role };
    }
    return this.defaultUser;
  }

  async requireRole(request: Request, role: 'buyer' | 'creator' | 'admin'): Promise<AuthenticatedUser> {
    const user = await this.requireUser(request);
    if (user.role !== role) {
      throw new AuthorizationError(`Required role "${role}" but user has role "${user.role}"`);
    }
    return user;
  }
}

export class AuthorizationError extends Error {
  readonly code = 'FORBIDDEN';
  readonly status = 403;
  constructor(message: string) {
    super(message);
    this.name = 'AuthorizationError';
  }
}
