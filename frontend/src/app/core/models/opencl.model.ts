export interface OpenCLDevice {
  tipo: 'CPU' | 'GPU';
  plataforma: string;
  nome: string;
  max_work_group_size: number;
}

export interface OpenCLCapabilities {
  dispositivos: OpenCLDevice[];
}
