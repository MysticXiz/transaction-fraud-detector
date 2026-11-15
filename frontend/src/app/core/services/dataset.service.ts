import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { environment } from '../../../environments/environment';
import { Dataset, DatasetDetalhe, DatasetImportJob, DatasetImportPayload, ModeloDeteccao } from '../models/dataset.model';

@Injectable({ providedIn: 'root' })
export class DatasetService {
  private http = inject(HttpClient);
  private baseUrl = `${environment.apiUrl}/datasets`;

  listar(offset = 0, limit = 50) {
    const params = new HttpParams().set('offset', offset).set('limit', limit);
    return this.http.get<Dataset[]>(this.baseUrl, { params });
  }

  obter(idDataset: number) {
    return this.http.get<DatasetDetalhe>(`${this.baseUrl}/${idDataset}`);
  }

  iniciarImportacao(payload: Omit<DatasetImportPayload, 'arquivo'> & { nome_arquivo: string }) {
    return this.http.post<DatasetImportJob>(`${this.baseUrl}/importacoes`, payload);
  }

  importar(idImportacao: number, arquivo: File) {
    const formData = new FormData();
    formData.append('arquivo', arquivo, arquivo.name);
    return this.http.post<Dataset>(
      `${this.baseUrl}/importacoes/${idImportacao}/arquivo`,
      formData,
      {
      observe: 'events',
      reportProgress: true,
      }
    );
  }

  obterImportacao(idImportacao: number) {
    return this.http.get<DatasetImportJob>(`${this.baseUrl}/importacoes/${idImportacao}`);
  }

  cancelarImportacao(idImportacao: number) {
    return this.http.post<DatasetImportJob>(
      `${this.baseUrl}/importacoes/${idImportacao}/cancelar`,
      {}
    );
  }

  remover(idDataset: number) {
    return this.http.delete<void>(`${this.baseUrl}/${idDataset}`);
  }

  listarModelos() {
    return this.http.get<ModeloDeteccao[]>(`${environment.apiUrl}/modelos`);
  }
}
