import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { environment } from '../../../environments/environment';
import { OpenCLCapabilities } from '../models/opencl.model';

@Injectable({ providedIn: 'root' })
export class OpenClDeviceService {
  private http = inject(HttpClient);
  private baseUrl = `${environment.apiUrl}/analises/capacidades`;

  obterCapacidades() {
    return this.http.get<OpenCLCapabilities>(this.baseUrl);
  }
}
