import { HttpRequest, HttpResponse } from '@angular/common/http';
import { TestBed } from '@angular/core/testing';
import { Router } from '@angular/router';
import { of } from 'rxjs';
import { AuthService } from '../services/auth.service';
import { authInterceptor } from './auth.interceptor';

describe('authInterceptor', () => {
  const auth = {
    clearSession: jasmine.createSpy('clearSession'),
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
    auth.clearSession.calls.reset();
    router.navigateByUrl.calls.reset();
  });

  it('envia o cabeçalho de sessão nas chamadas da API', (done) => {
    const request = new HttpRequest('GET', '/api/auth/me');

    TestBed.runInInjectionContext(() =>
      authInterceptor(request, (intercepted) => {
        expect(intercepted.headers.get('X-Requested-With')).toBe('XMLHttpRequest');
        expect(intercepted.headers.has('Authorization')).toBeFalse();
        expect(intercepted.withCredentials).toBeTrue();
        return of(new HttpResponse({ status: 200 }));
      })
    ).subscribe(() => done());
  });
});
