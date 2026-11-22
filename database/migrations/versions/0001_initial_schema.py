"""Cria o esquema PostgreSQL e cadastra os modelos iniciais."""

from pathlib import Path

from alembic import context, op

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None

SNAPSHOT_DIR = Path(__file__).resolve().parent


def _execute_script(sql: str) -> None:
    if context.is_offline_mode():
        op.get_context().impl.static_output(sql)
    else:
        op.get_bind().exec_driver_sql(sql, execution_options={"no_parameters": True})


def upgrade() -> None:
    # Snapshots desta revisão; os scripts de inicialização do Docker podem evoluir.
    for filename in ("0001_schema.sql", "0001_seeds.sql"):
        sql = (SNAPSHOT_DIR / filename).read_text(encoding="utf-8")
        _execute_script(sql.strip())


def downgrade() -> None:
    op.execute("DROP VIEW vw_comparativo_benchmark, vw_resumo_execucao")
    op.execute(
        "DROP TABLE benchmark_execucao, dataset_import_job, benchmark, "
        "metrica_execucao, resultado_deteccao, execucao_analise, "
        "modelo_deteccao, transacao, dataset, usuario"
    )
    op.execute(
        "DROP TYPE papel_benchmark, tipo_algoritmo, status_execucao, "
        "modo_execucao, papel_usuario"
    )
