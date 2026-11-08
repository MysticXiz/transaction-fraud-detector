import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { environment } from '../../../environments/environment';
import {
  OpenCLCapabilities,
  OpenCLCalibrationResult,
} from '../models/opencl.model';

@Injectable({ providedIn: 'root' })
export class OpenClDeviceService {
  private http = inject(HttpClient);
  private baseUrl = `${environment.apiUrl}/analises/capacidades`;

  obterCapacidades() {
    return this.http.get<OpenCLCapabilities>(this.baseUrl);
  }

  calibrar(payload: {
    tipo_dispositivo: 'CPU' | 'GPU';
    tamanho_amostra?: number;
    tempo_maximo_s?: number;
  }) {
    return this.http.post<OpenCLCalibrationResult>(
      `${environment.apiUrl}/analises/calibrar-opencl`,
      payload
    );
  }
}
