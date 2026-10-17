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

  it('deve persistir o token bearer retornado pelo login', () => {
    const payload = { email: 'admin@sistema.com', senha: '12345678' };

    service.login(payload).subscribe((response) => {
      expect(response.access_token).toBe('token-123');
    });

    const req = httpMock.expectOne('http://127.0.0.1:8000/auth/login');
    expect(req.request.method).toBe('POST');
    expect(req.request.withCredentials).toBeFalse();
    req.flush({ access_token: 'token-123', token_type: 'bearer' });

    expect(localStorage.getItem('df_access_token')).toBe('token-123');
    expect(service.token()).toBe('token-123');
  });

  it('deve atualizar o perfil via PATCH e sincronizar o usuário', () => {
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
    expect(req.request.withCredentials).toBeFalse();
    expect(req.request.body).toEqual({ nome: 'Maria Atualizada' });
    req.flush(usuario);
  });

  it('deve limpar a sessão local sem chamar uma rota logout inexistente', () => {
    localStorage.setItem('df_access_token', 'token-123');

    service.logout();

    expect(localStorage.getItem('df_access_token')).toBeNull();
    expect(service.usuario()).toBeNull();
    httpMock.expectNone('http://127.0.0.1:8000/auth/logout');
  });
});
