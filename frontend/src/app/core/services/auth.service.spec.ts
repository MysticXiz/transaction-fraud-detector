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

  it('deve iniciar a sessão sem persistir um token no armazenamento local', () => {
    const payload = { email: 'admin@sistema.com', senha: '12345678' };
    localStorage.setItem('df_access_token', 'token-antigo');

    service.login(payload).subscribe();

    const req = httpMock.expectOne('/api/auth/session');
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual(payload);
    req.flush(null);

    expect(localStorage.getItem('df_access_token')).toBeNull();
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

    const req = httpMock.expectOne('/api/auth/me');
    expect(req.request.method).toBe('PATCH');
    expect(req.request.withCredentials).toBeTrue();
    expect(req.request.body).toEqual({ nome: 'Maria Atualizada' });
    req.flush(usuario);
  });

  it('deve encerrar a sessão na API e limpar o perfil', () => {
    localStorage.setItem('df_access_token', 'token-123');

    service.logout();
    const req = httpMock.expectOne('/api/auth/logout');
    expect(req.request.method).toBe('POST');
    req.flush(null);

    expect(localStorage.getItem('df_access_token')).toBeNull();
    expect(service.usuario()).toBeNull();
  });
});
