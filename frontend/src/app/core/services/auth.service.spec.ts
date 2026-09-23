import { TestBed } from '@angular/core/testing';
import { HttpClientTestingModule, HttpTestingController } from '@angular/common/http/testing';
import { RouterTestingModule } from '@angular/router/testing';
import { AuthService } from './auth.service';

describe('AuthService', () => {
  let service: AuthService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [HttpClientTestingModule, RouterTestingModule],
      providers: [AuthService],
    });

    service = TestBed.inject(AuthService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
    localStorage.clear();
  });

  it('deve autenticar e salvar o token após login', () => {
    const payload = { email: 'admin@sistema.com', senha: '12345678' };

    service.login(payload).subscribe((response) => {
      expect(response.access_token).toBe('token-123');
    });

    const req = httpMock.expectOne('http://127.0.0.1:8000/auth/login');
    expect(req.request.method).toBe('POST');
    req.flush({ access_token: 'token-123', token_type: 'bearer' });

    expect(localStorage.getItem('df_access_token')).toBe('token-123');
  });
});
