export interface OpenCLDevice {
  tipo: 'CPU' | 'GPU';
  plataforma: string;
  nome: string;
  max_workers: number;
}

export interface OpenCLCapabilities {
  dispositivos: OpenCLDevice[];
}
