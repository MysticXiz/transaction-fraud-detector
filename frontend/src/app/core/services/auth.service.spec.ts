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

  it('deve autenticar sem persistir token em localStorage e enviar cookies', () => {
    const payload = { email: 'admin@sistema.com', senha: '12345678' };

    service.login(payload).subscribe((response) => {
      expect(response.access_token).toBe('token-123');
    });

    const req = httpMock.expectOne('http://127.0.0.1:8000/auth/login');
    expect(req.request.method).toBe('POST');
    expect(req.request.withCredentials).toBeTrue();
    req.flush({ access_token: 'token-123', token_type: 'bearer' });

    expect(localStorage.getItem('df_access_token')).toBeNull();
  });

  it('deve atualizar o perfil via PATCH usando cookies e sincronizar o usuário', () => {
    const usuario = {
      id_usuario: 1,
      nome: 'Maria Atualizada',
      email: 'maria@sistema.com',
      papel: 'ANALISTA' as never,
      ativo: true,
      criado_em: '2026-01-01T00:00:00Z',
    };

    service.atualizarPerfil({ nome: usuario.nome }).subscribe((resposta) => {
      expect(resposta).toEqual(usuario);
      expect(service.usuario()).toEqual(usuario);
    });

    const req = httpMock.expectOne('http://127.0.0.1:8000/auth/me');
    expect(req.request.method).toBe('PATCH');
    expect(req.request.withCredentials).toBeTrue();
    expect(req.request.body).toEqual({ nome: 'Maria Atualizada' });
    req.flush(usuario);
  });
});
