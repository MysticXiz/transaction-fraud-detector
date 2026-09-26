import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { environment } from '../../../environments/environment';
import { Dataset, DatasetDetalhe, DatasetImportPayload, ModeloDeteccao } from '../models/dataset.model';

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

  importar(payload: DatasetImportPayload) {
    const formData = new FormData();
    formData.append('nome', payload.nome);
    formData.append('origem', payload.origem);
    if (payload.descricao) formData.append('descricao', payload.descricao);
    formData.append('arquivo', payload.arquivo);
    return this.http.post<Dataset>(this.baseUrl, formData);
  }

  remover(idDataset: number) {
    return this.http.delete<void>(`${this.baseUrl}/${idDataset}`);
  }

  listarModelos() {
    return this.http.get<ModeloDeteccao[]>(`${environment.apiUrl}/modelos`);
  }
}
