import { HttpRequest, HttpResponse } from '@angular/common/http';
import { TestBed } from '@angular/core/testing';
import { Router } from '@angular/router';
import { of } from 'rxjs';
import { AuthService } from '../services/auth.service';
import { authInterceptor } from './auth.interceptor';

describe('authInterceptor', () => {
  const auth = {
    token: () => 'test-access-token',
    logout: jasmine.createSpy('logout'),
  };
  const router = {
    navigateByUrl: jasmine.createSpy('navigateByUrl'),
  };

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        { provide: AuthService, useValue: auth },
        { provide: Router, useValue: router },
      ],
    });
    auth.logout.calls.reset();
    router.navigateByUrl.calls.reset();
  });

  it('envia o token de acesso no header Authorization como bearer', (done) => {
    const request = new HttpRequest('GET', '/auth/me');

    TestBed.runInInjectionContext(() =>
      authInterceptor(request, (intercepted) => {
        expect(intercepted.headers.get('Authorization')).toBe(
          'Bearer test-access-token'
        );
        expect(intercepted.withCredentials).toBeTrue();
        return of(new HttpResponse({ status: 200 }));
      })
    ).subscribe(() => done());
  });
});
