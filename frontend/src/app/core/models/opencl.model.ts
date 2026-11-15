export interface OpenCLDevice {
  tipo: 'CPU' | 'GPU';
  plataforma: string;
  nome: string;
  max_work_group_size: number;
  work_group_recomendado?: number;
  chunk_recomendado?: number;
  preferred_work_group_multiple?: number;
  unidades_computacao?: number;
  local_mem_size?: number;
}

export interface OpenCLCapabilities {
  dispositivos: OpenCLDevice[];
}

export interface OpenCLCalibrationCandidate {
  work_group_size: number;
  tamanho_chunk: number;
  throughput_tps: number;
  tempo_s: number;
}

export interface OpenCLCalibrationResult {
  tipo_dispositivo: 'CPU' | 'GPU';
  work_group_size_recomendado: number;
  tamanho_chunk_recomendado: number;
  candidatos: OpenCLCalibrationCandidate[];
  explicacao: string;
}
