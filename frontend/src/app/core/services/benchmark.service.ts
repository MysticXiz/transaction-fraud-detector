import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { environment } from '../../../environments/environment';
import { Benchmark, BenchmarkCreate } from '../models/benchmark.model';

@Injectable({ providedIn: 'root' })
export class BenchmarkService {
  private http = inject(HttpClient);
  private baseUrl = `${environment.apiUrl}/benchmarks`;

  /** Dispara a bateria completa: baseline sequencial + configurações paralelas selecionadas (RF09/PB12). */
  executarBateria(payload: BenchmarkCreate) {
    return this.http.post<Benchmark>(this.baseUrl, payload);
  }

  obter(idBenchmark: number) {
    return this.http.get<Benchmark>(`${this.baseUrl}/${idBenchmark}`);
  }

  exportarPdf(idBenchmark: number) {
    return this.http.get(`${this.baseUrl}/${idBenchmark}/exportar`, { responseType: 'blob' });
  }
}
