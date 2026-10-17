import {
  HttpErrorResponse,
  HttpEventType,
  HttpResponse,
} from '@angular/common/http';
import { effect, Injectable, inject, signal } from '@angular/core';
import {
  EMPTY,
  Subject,
  Subscription,
  expand,
  interval,
  switchMap,
  takeWhile,
  timer,
} from 'rxjs';
import { ExecucaoAnalise } from '../models/analise.model';
import { StatusExecucao } from '../models/enums';
import { Benchmark } from '../models/benchmark.model';
import { Dataset, DatasetImportJob, DatasetImportPayload } from '../models/dataset.model';
import { AnalysisService } from './analysis.service';
import { BenchmarkService } from './benchmark.service';
import { DatasetService } from './dataset.service';
import { AuthService } from './auth.service';

export type ProcessStatus = 'running' | 'completed' | 'failed' | 'cancelled';

export interface ManagedProcess {
  id: string;
  kind: 'benchmark' | 'analysis';
  title: string;
  description: string;
  status: ProcessStatus;
  progress: number | null;
  startedAt: number;
  elapsedSeconds: number;
  error: string | null;
  cancelling?: boolean;
  executionId?: number;
  execution?: ExecucaoAnalise;
  benchmarkId?: number;
  benchmark?: Benchmark;
}

export interface DatasetImportProcess {
  id: number;
  filename: string;
  size: number;
  status: 'starting' | 'uploading' | 'processing' | 'cancelling' | 'completed' | 'failed' | 'cancelled';
  progress: number | null;
  bytesSent: number;
  bytesPerSecond: number;
  elapsedSeconds: number;
  startedAt: number;
  dataset: Dataset | null;
  error: string | null;
  jobId: number | null;
  cancelRequested: boolean;
}

@Injectable({ providedIn: 'root' })
export class ProcessManagerService {
  private datasetService = inject(DatasetService);
  private analysisService = inject(AnalysisService);
  private benchmarkService = inject(BenchmarkService);
  private auth = inject(AuthService);
  private activeUserId: number | null = null;
  private nextProcessId = 1;
  private analysisSubscriptions = new Map<number, Subscription>();
  private benchmarkSubscriptions = new Map<string, Subscription>();
  private importStatusSubscription?: Subscription;
  private importStartSubscription?: Subscription;
  private datasetImportSubscription?: Subscription;

  readonly datasetImport = signal<DatasetImportProcess | null>(null);
  readonly datasetImportCompleted = new Subject<Dataset>();
  readonly tasks = signal<ManagedProcess[]>([]);

  constructor() {
    effect(() => {
      const userId = this.auth.usuario()?.id_usuario ?? null;
      this.resetForUser(userId);
    });
    interval(1000).subscribe(() => {
      const now = Date.now();
      this.datasetImport.update((process) =>
        process &&
        (process.status === 'starting' ||
          process.status === 'uploading' ||
          process.status === 'processing' ||
          process.status === 'cancelling')
          ? { ...process, elapsedSeconds: Math.floor((now - process.startedAt) / 1000) }
          : process
      );
      this.tasks.update((tasks) =>
        tasks.map((task) =>
          task.status === 'running'
            ? { ...task, elapsedSeconds: Math.floor((now - task.startedAt) / 1000) }
            : task
        )
      );
    });
  }

  private resetForUser(userId: number | null): void {
    if (userId === this.activeUserId) return;
    this.activeUserId = userId;
    this.analysisSubscriptions.forEach((subscription) => subscription.unsubscribe());
    this.analysisSubscriptions.clear();
    this.benchmarkSubscriptions.forEach((subscription) => subscription.unsubscribe());
    this.benchmarkSubscriptions.clear();
    this.importStartSubscription?.unsubscribe();
    this.datasetImportSubscription?.unsubscribe();
    this.importStatusSubscription?.unsubscribe();
    this.importStartSubscription = undefined;
    this.datasetImportSubscription = undefined;
    this.importStatusSubscription = undefined;
    this.datasetImport.set(null);
    this.tasks.set([]);
  }

  beginBenchmark(): string {
    const id = `benchmark-${this.nextProcessId++}`;
    this.tasks.update((tasks) =>
      this.trimProcesses([
        {
          id,
          kind: 'benchmark',
          title: 'Executando benchmark',
          description: 'Executando configurações comparativas',
          status: 'running',
          progress: null,
          startedAt: Date.now(),
          elapsedSeconds: 0,
          error: null,
        },
        ...tasks,
      ])
    );
    return id;
  }

  finishBenchmark(id: string, error?: unknown): void {
    const process = this.tasks().find((task) => task.id === id);
    if (!process || process.status !== 'running') return;
    this.tasks.update((tasks) =>
      tasks.map((task) =>
        task.id === id
          ? {
              ...task,
              status: error === undefined ? 'completed' : 'failed',
              error: error === undefined ? null : this.errorMessage(error),
              elapsedSeconds: Math.floor((Date.now() - task.startedAt) / 1000),
            }
          : task
      )
    );
    this.benchmarkSubscriptions.get(id)?.unsubscribe();
    this.benchmarkSubscriptions.delete(id);
  }

  cancelBenchmark(id: string): void {
    const process = this.tasks().find((task) => task.id === id);
    if (!process || process.status !== 'running' || process.benchmarkId === undefined) return;
    this.tasks.update((tasks) =>
      tasks.map((task) =>
        task.id === id ? { ...task, cancelling: true, error: null } : task
      )
    );
    this.benchmarkService.cancelar(process.benchmarkId).subscribe({
      next: (benchmark) => this.updateBenchmark(id, benchmark),
      error: (error: unknown) => {
        this.tasks.update((tasks) =>
          tasks.map((task) =>
            task.id === id
              ? { ...task, cancelling: false, error: this.errorMessage(error) }
              : task
          )
        );
      },
    });
  }

  startBenchmarkTracking(processId: string, initial: Benchmark): void {
    this.benchmarkSubscriptions.get(processId)?.unsubscribe();
    this.updateBenchmark(processId, initial);
    if (this.isBenchmarkTerminal(initial.status)) return;

    let delayMs = 1500;
    const subscription = timer(0)
      .pipe(
        switchMap(() => this.benchmarkService.obter(initial.id_benchmark)),
        expand((benchmark) => {
          this.updateBenchmark(processId, benchmark);
          if (this.isBenchmarkTerminal(benchmark.status)) return EMPTY;
          const delay = delayMs;
          delayMs = Math.min(Math.round(delayMs * 1.5), 8000);
          return timer(delay).pipe(
            switchMap(() => this.benchmarkService.obter(initial.id_benchmark))
          );
        }),
        takeWhile((benchmark) => !this.isBenchmarkTerminal(benchmark.status), true)
      )
      .subscribe({
        next: (benchmark) => this.updateBenchmark(processId, benchmark),
        error: (error: unknown) => this.finishBenchmark(processId, error),
        complete: () => this.benchmarkSubscriptions.delete(processId),
      });
    this.benchmarkSubscriptions.set(processId, subscription);
  }

  private updateBenchmark(processId: string, benchmark: Benchmark): void {
    const status: ProcessStatus =
      benchmark.status === 'CONCLUIDO'
        ? 'completed'
        : benchmark.status === 'FALHA'
          ? 'failed'
          : benchmark.status === 'CANCELADO'
            ? 'cancelled'
            : 'running';
    this.tasks.update((tasks) =>
      tasks.map((task) =>
        task.id === processId
          ? {
              ...task,
              benchmarkId: benchmark.id_benchmark,
              benchmark,
              status,
              cancelling: benchmark.status === 'CANCELAMENTO_SOLICITADO',
              description:
                benchmark.status === 'CANCELAMENTO_SOLICITADO'
                  ? 'Cancelamento solicitado; aguardando o backend encerrar a etapa atual.'
                  : benchmark.mensagem_erro ?? task.description,
              error: benchmark.status === 'FALHA' ? benchmark.mensagem_erro ?? 'O benchmark falhou.' : null,
            }
          : task
      )
    );
  }

  private isBenchmarkTerminal(status: Benchmark['status']): boolean {
    return status === 'CONCLUIDO' || status === 'FALHA' || status === 'CANCELADO';
  }

  startAnalysisTracking(executionId: number, initial?: ExecucaoAnalise): void {
    const existing = this.tasks().find(
      (task) => task.kind === 'analysis' && task.executionId === executionId
    );
    if (existing && existing.status !== 'failed') return;
    this.analysisSubscriptions.get(executionId)?.unsubscribe();

    const currentExecution = initial ?? existing?.execution;
    const startedAt = currentExecution?.iniciada_em
      ? new Date(currentExecution.iniciada_em).getTime()
      : Date.now();
    const processId = existing?.id ?? `analysis-${executionId}`;
    const process: ManagedProcess = {
      id: processId,
      kind: 'analysis',
      title: `Análise #${executionId}`,
      description: currentExecution?.dataset_nome ?? 'Acompanhando execução',
      status: 'running',
      progress: currentExecution?.progresso_percentual ?? 0,
      startedAt,
      elapsedSeconds: Math.max(0, Math.floor((Date.now() - startedAt) / 1000)),
      error: null,
      executionId,
      execution: currentExecution,
    };
    this.tasks.update((tasks) =>
      this.trimProcesses([process, ...tasks.filter((task) => task.id !== processId)])
    );

    let delayMs = 2000;
    const subscription = timer(0)
      .pipe(
        switchMap(() => this.analysisService.obterStatus(executionId)),
        expand((execution) => {
          this.updateAnalysis(execution);
          if (!this.isAnalysisActive(execution.status)) return EMPTY;
          const currentDelay = delayMs;
          delayMs = Math.min(Math.round(delayMs * 1.5), 8000);
          return timer(currentDelay).pipe(
            switchMap(() => this.analysisService.obterStatus(executionId))
          );
        }),
        takeWhile((execution) => this.isAnalysisActive(execution.status), true)
      )
      .subscribe({
        next: (execution) => this.updateAnalysis(execution),
        error: (error: unknown) => this.failAnalysis(executionId, error),
        complete: () => this.analysisSubscriptions.delete(executionId),
      });
    this.analysisSubscriptions.set(executionId, subscription);
  }

  getAnalysisProcess(executionId: number): ManagedProcess | undefined {
    return this.tasks().find(
      (task) => task.kind === 'analysis' && task.executionId === executionId
    );
  }

  markAnalysisCancelled(executionId: number): void {
    this.tasks.update((tasks) =>
      tasks.map((task) =>
        task.kind === 'analysis' && task.executionId === executionId
          ? {
              ...task,
              status: 'cancelled',
              execution: task.execution
                ? { ...task.execution, status: StatusExecucao.CANCELADA }
                : undefined,
            }
          : task
      )
    );
    this.analysisSubscriptions.get(executionId)?.unsubscribe();
    this.analysisSubscriptions.delete(executionId);
  }

  dismissTask(id: string): void {
    this.tasks.update((tasks) => tasks.filter((task) => task.id !== id));
  }

  cancelTask(id: string): void {
    const task = this.tasks().find((item) => item.id === id);
    if (!task || task.status !== 'running' || task.cancelling) return;
    if (task.kind === 'benchmark') {
      this.cancelBenchmark(id);
      return;
    }
    if (task.executionId === undefined) return;
    const executionId = task.executionId;

    this.tasks.update((tasks) =>
      tasks.map((item) =>
        item.id === id ? { ...item, cancelling: true, error: null } : item
      )
    );
    this.analysisService.cancelar(task.executionId).subscribe({
      next: () => this.markAnalysisCancelled(executionId),
      error: (error: unknown) => {
        this.tasks.update((tasks) =>
          tasks.map((item) =>
            item.id === id
              ? { ...item, cancelling: false, error: this.errorMessage(error) }
              : item
          )
        );
      },
    });
  }

  startDatasetImport(payload: DatasetImportPayload): boolean {
    const existing = this.datasetImport();
    if (
      existing &&
      (existing.status === 'starting' ||
        existing.status === 'uploading' ||
        existing.status === 'processing' ||
        existing.status === 'cancelling')
    ) {
      return false;
    }

    const startedAt = Date.now();
    this.datasetImport.set({
      id: this.nextProcessId++,
      filename: payload.arquivo.name,
      size: payload.arquivo.size,
      status: 'starting',
      progress: null,
      bytesSent: 0,
      bytesPerSecond: 0,
      elapsedSeconds: 0,
      startedAt,
      dataset: null,
      error: null,
      jobId: null,
      cancelRequested: false,
    });
    this.importStartSubscription = this.datasetService.iniciarImportacao({
      nome: payload.nome,
      origem: payload.origem,
      descricao: payload.descricao,
      nome_arquivo: payload.arquivo.name,
    }).subscribe({
      next: (job) => {
        this.datasetImport.update((process) =>
          process ? { ...process, jobId: job.id_importacao } : process
        );
        if (this.datasetImport()?.cancelRequested) {
          this.requestDatasetImportCancellation(job.id_importacao);
          return;
        }
        this.uploadDatasetFile(job.id_importacao, payload.arquivo);
      },
      error: (error: unknown) => this.failImport(this.errorMessage(error)),
    });
    return true;
  }

  private uploadDatasetFile(importId: number, file: File): void {
    this.datasetImport.update((process) =>
      process ? { ...process, status: 'uploading' } : process
    );
    this.datasetImportSubscription = this.datasetService.importar(importId, file).subscribe({
      next: (event) => {
        if (event.type === HttpEventType.UploadProgress) {
          this.datasetImport.update((process) => {
            if (!process) return process;
            const elapsedSeconds = Math.max((Date.now() - process.startedAt) / 1000, 0.1);
            const progress = event.total
              ? Math.min(100, Math.round((event.loaded / event.total) * 100))
              : null;
            return {
              ...process,
              status: progress === 100 || event.loaded >= process.size ? 'processing' : 'uploading',
              progress,
              bytesSent:
                progress === 100
                  ? process.size
                  : Math.min(event.loaded, process.size),
              bytesPerSecond: Math.min(event.loaded, process.size) / elapsedSeconds,
              elapsedSeconds: Math.floor(elapsedSeconds),
            };
          });
        } else if (event instanceof HttpResponse) {
          if (!event.body) {
            this.failImport(
              'O servidor concluiu a resposta sem retornar os dados do dataset.'
            );
            return;
          }
          const dataset = event.body;
          this.datasetImport.update((process) =>
            process
              ? {
                  ...process,
                  status: 'completed',
                  progress: 100,
                  bytesSent: process.size,
                  dataset,
                  elapsedSeconds: Math.floor((Date.now() - process.startedAt) / 1000),
                }
              : process
          );
          this.datasetImportCompleted.next(dataset);
          this.datasetImportSubscription = undefined;
          this.importStartSubscription = undefined;
        }
      },
      error: (error: unknown) => {
        if (this.datasetImport()?.status !== 'cancelling') {
          this.failImport(this.errorMessage(error));
        }
        this.datasetImportSubscription = undefined;
      },
    });
  }

  cancelDatasetImport(): void {
    const process = this.datasetImport();
    if (
      !process ||
      !['starting', 'uploading', 'processing'].includes(process.status)
    ) {
      return;
    }
    if (process.jobId === null) {
      this.datasetImport.update((current) =>
        current ? { ...current, status: 'cancelling', cancelRequested: true } : current
      );
      return;
    }
    this.requestDatasetImportCancellation(process.jobId);
  }

  private requestDatasetImportCancellation(jobId: number): void {
    this.datasetImport.update((current) =>
      current
        ? {
            ...current,
            status: 'cancelling',
            cancelRequested: true,
          }
        : current
    );
    this.datasetService.cancelarImportacao(jobId).subscribe({
      next: (job) => {
        this.datasetImportSubscription?.unsubscribe();
        this.datasetImportSubscription = undefined;
        this.updateImportJob(job);
        if (job.status === 'CANCELAMENTO_SOLICITADO') {
          this.watchImportCancellation(jobId);
        }
      },
      error: (error: unknown) => {
        this.datasetImport.update((current) =>
          current
            ? { ...current, status: 'uploading', cancelRequested: false, error: this.errorMessage(error) }
            : current
        );
      },
    });
  }

  private watchImportCancellation(jobId: number): void {
    this.importStatusSubscription?.unsubscribe();
    const subscription = timer(0)
      .pipe(
        switchMap(() => this.datasetService.obterImportacao(jobId)),
        expand((job) =>
          this.isImportJobTerminal(job.status)
            ? EMPTY
            : timer(1000).pipe(switchMap(() => this.datasetService.obterImportacao(jobId)))
        ),
        takeWhile((job) => !this.isImportJobTerminal(job.status), true)
      )
      .subscribe({
        next: (job) => this.updateImportJob(job),
        error: (error: unknown) => {
          this.datasetImport.update((current) =>
            current
              ? { ...current, error: `Não foi possível confirmar o cancelamento: ${this.errorMessage(error)}` }
              : current
          );
        },
        complete: () => {
          this.importStatusSubscription = undefined;
        },
      });
    this.importStatusSubscription = subscription;
  }

  private updateImportJob(job: DatasetImportJob): void {
    this.datasetImport.update((current) => {
      if (!current || current.jobId !== job.id_importacao) return current;
      if (job.status === 'CANCELADO') {
        return {
          ...current,
          status: 'cancelled',
          error: 'Importação cancelada no servidor. Nenhum dataset parcial foi mantido.',
        };
      }
      if (job.status === 'CANCELAMENTO_SOLICITADO') {
        return {
          ...current,
          status: 'cancelling',
          error: 'Cancelamento solicitado; o servidor está revertendo a importação.',
        };
      }
      if (job.status === 'FALHA') {
        return { ...current, status: 'failed', error: job.mensagem_erro };
      }
      if (job.status === 'CONCLUIDO') {
        return {
          ...current,
          status: 'completed',
          progress: 100,
          bytesSent: current.size,
          error: null,
        };
      }
      if (job.status === 'PROCESSANDO') return { ...current, status: 'processing' };
      return current;
    });
  }

  private isImportJobTerminal(status: DatasetImportJob['status']): boolean {
    return status === 'CONCLUIDO' || status === 'FALHA' || status === 'CANCELADO';
  }

  dismissDatasetImport(): void {
    const process = this.datasetImport();
    if (
      process &&
      (process.status === 'completed' ||
        process.status === 'failed' ||
        process.status === 'cancelled')
    ) {
      this.datasetImport.set(null);
    }
  }

  private failImport(message: string): void {
    this.datasetImport.update((process) =>
      process
        ? {
            ...process,
            status: 'failed',
            error: message,
            elapsedSeconds: Math.floor((Date.now() - process.startedAt) / 1000),
          }
        : process
    );
  }

  private updateAnalysis(execution: ExecucaoAnalise): void {
    const status: ProcessStatus =
      execution.status === StatusExecucao.CONCLUIDA
        ? 'completed'
        : execution.status === StatusExecucao.FALHA
          ? 'failed'
          : execution.status === StatusExecucao.CANCELADA
            ? 'cancelled'
            : 'running';
    this.tasks.update((tasks) =>
      tasks.map((task) =>
        task.kind === 'analysis' && task.executionId === execution.id_execucao
          ? {
              ...task,
              title: `Análise #${execution.id_execucao}`,
              description: execution.dataset_nome ?? task.description,
              status,
              progress: execution.progresso_percentual ?? 0,
              error: execution.mensagem_erro ?? null,
              execution,
              startedAt: execution.iniciada_em
                ? new Date(execution.iniciada_em).getTime()
                : task.startedAt,
            }
          : task
      )
    );
  }

  private failAnalysis(executionId: number, error: unknown): void {
    this.tasks.update((tasks) =>
      tasks.map((task) =>
        task.kind === 'analysis' && task.executionId === executionId
          ? {
              ...task,
              status: 'failed',
              error: this.errorMessage(error),
            }
          : task
      )
    );
    this.analysisSubscriptions.delete(executionId);
  }

  private isAnalysisActive(status: StatusExecucao): boolean {
    return (
      status === StatusExecucao.PENDENTE ||
      status === StatusExecucao.EM_ANDAMENTO
    );
  }

  private trimProcesses(tasks: ManagedProcess[]): ManagedProcess[] {
    const running = tasks.filter((task) => task.status === 'running');
    const finished = tasks.filter((task) => task.status !== 'running').slice(0, 12);
    return [...running, ...finished];
  }

  private errorMessage(error: unknown): string {
    if (!(error instanceof HttpErrorResponse)) {
      return 'Ocorreu um erro inesperado ao executar a operação.';
    }
    if (error.status === 0) {
      return 'Não foi possível conectar ao backend. Verifique se a API está em execução.';
    }
    const detail: unknown = error.error?.detail;
    if (typeof detail === 'string' && detail.trim()) return detail;
    if (Array.isArray(detail)) {
      const messages = detail
        .map((item: unknown) =>
          typeof item === 'object' && item !== null && 'msg' in item
            ? String(item.msg)
            : ''
        )
        .filter(Boolean);
      if (messages.length) return messages.join(' ');
    }
    if (error.status === 413) return 'O arquivo excede o limite máximo de upload.';
    if (error.status === 401) return 'Sua sessão expirou. Entre novamente no sistema.';
    return `A operação não foi concluída (HTTP ${error.status}).`;
  }
}
