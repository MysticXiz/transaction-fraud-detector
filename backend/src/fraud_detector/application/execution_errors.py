ANALYSIS_FAILED = "Não foi possível concluir a análise. Consulte o suporte."
BENCHMARK_FAILED = "Não foi possível concluir o benchmark. Consulte o suporte."
MATRIX_LIMIT_EXCEEDED = (
    "A matriz de análise excede o limite de memória estimada. "
    "Reduza o número de transações ou de atributos do dataset."
)
EXECUTION_INTERRUPTED = (
    "Execução interrompida pela parada do backend. Inicie uma nova execução."
)

_PUBLIC_MESSAGES = frozenset(
    {ANALYSIS_FAILED, BENCHMARK_FAILED, MATRIX_LIMIT_EXCEEDED, EXECUTION_INTERRUPTED}
)


def public_execution_error(message: str | None, fallback: str) -> str | None:
    """Oculta diagnósticos gravados por versões anteriores da aplicação."""
    if message is None or message in _PUBLIC_MESSAGES:
        return message
    return fallback
