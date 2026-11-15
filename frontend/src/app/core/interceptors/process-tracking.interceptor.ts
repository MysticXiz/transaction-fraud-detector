import {
  HttpEvent,
  HttpInterceptorFn,
  HttpResponse,
} from '@angular/common/http';
import { inject } from '@angular/core';
import { catchError, tap, throwError } from 'rxjs';
import { Benchmark } from '../models/benchmark.model';
import { ExecucaoAnalise } from '../models/analise.model';
import { ProcessManagerService } from '../services/process-manager.service';

export const processTrackingInterceptor: HttpInterceptorFn = (request, next) => {
  const isAnalysisRequest =
    request.method === 'POST' && isCollectionRequest(request.url, 'analises');
  const isBenchmarkRequest =
    request.method === 'POST' && isCollectionRequest(request.url, 'benchmarks');
  if (!isAnalysisRequest && !isBenchmarkRequest) return next(request);

  const processes = inject(ProcessManagerService);
  const benchmarkProcessId = isBenchmarkRequest ? processes.beginBenchmark() : null;

  return next(request).pipe(
    tap((event: HttpEvent<unknown>) => {
      if (event instanceof HttpResponse) {
        if (benchmarkProcessId) {
          if (isBenchmarkResponse(event.body)) {
            processes.startBenchmarkTracking(benchmarkProcessId, event.body);
          } else {
            processes.finishBenchmark(
              benchmarkProcessId,
              new Error('A API retornou uma resposta de benchmark inválida.')
            );
          }
        }
        if (
          isAnalysisRequest &&
          isAnalysisResponse(event.body)
        ) {
          processes.startAnalysisTracking(
            event.body.id_execucao,
            event.body
          );
        }
      }
    }),
    catchError((error: unknown) => {
      if (benchmarkProcessId) processes.finishBenchmark(benchmarkProcessId, error);
      return throwError(() => error);
    })
  );
};

function isCollectionRequest(url: string, collection: 'analises' | 'benchmarks'): boolean {
  try {
    const path = new URL(url, globalThis.location?.origin ?? 'http://localhost')
      .pathname.replace(/^\/api(?=\/)/, '');
    return path === `/${collection}`;
  } catch {
    return false;
  }
}

function isAnalysisResponse(value: unknown): value is ExecucaoAnalise {
  if (typeof value !== 'object' || value === null) return false;
  return (
    'id_execucao' in value &&
    typeof value.id_execucao === 'number' &&
    'status' in value &&
    typeof value.status === 'string' &&
    'total_analisadas' in value &&
    typeof value.total_analisadas === 'number' &&
    'total_suspeitas' in value &&
    typeof value.total_suspeitas === 'number'
  );
}

function isBenchmarkResponse(value: unknown): value is Benchmark {
  return (
    typeof value === 'object' &&
    value !== null &&
    'id_benchmark' in value &&
    typeof value.id_benchmark === 'number' &&
    'status' in value &&
    typeof value.status === 'string' &&
    'execucoes' in value &&
    Array.isArray(value.execucoes)
  );
}
