import { mkdir, open, rm, stat } from 'node:fs/promises';
import { dirname } from 'node:path';
import { pipeline } from 'node:stream/promises';

function* gerarCsv(total, atributos) {
  const lote = 4096;
  const nomes = Array.from({ length: atributos }, (_, indice) => `V${indice + 1}`);
  yield ['Time', ...nomes, 'Amount', 'Class'].join(',') + '\n';

  let semente = 42;
  function aleatorio() {
    semente = (Math.imul(semente, 1664525) + 1013904223) >>> 0;
    return semente / 2 ** 32;
  }

  for (let inicio = 0; inicio < total; inicio += lote) {
    const linhas = [];
    const fim = Math.min(inicio + lote, total);
    for (let indice = inicio; indice < fim; indice++) {
      const classe = Number(aleatorio() < 0.0017);
      const valor = (aleatorio() ** 3 * 1500 + classe * 200).toFixed(2);
      const colunas = [String(indice)];
      for (let atributo = 0; atributo < atributos; atributo++) {
        const deslocamento = atributo < 3 ? classe * 2 : 0;
        const feature = (aleatorio() + aleatorio() - 1) * 6 + deslocamento;
        colunas.push(feature.toFixed(3));
      }
      linhas.push([...colunas, valor, classe].join(','));
    }
    yield linhas.join('\n') + '\n';
  }
}

async function main() {
  const [linhasArg, arquivoArg, atributosArg = '28'] = process.argv.slice(2);
  const total = Number(linhasArg);
  const atributos = Number(atributosArg);
  const arquivo = arquivoArg ?? `storage/datasets-sinteticos/transacoes-${total}.csv`;
  if (
    !Number.isSafeInteger(total) || total < 2 || total > 2_147_483_647 ||
    !Number.isSafeInteger(atributos) || atributos < 1 || atributos > 28 ||
    !arquivo.toLowerCase().endsWith('.csv')
  ) {
    throw new Error('Uso: node scripts/gerar-dataset.mjs <linhas> [arquivo.csv] [atributos de 1 a 28]');
  }

  await mkdir(dirname(arquivo), { recursive: true });
  const destino = await open(arquivo, 'wx');
  try {
    await pipeline(gerarCsv(total, atributos), destino.createWriteStream());
  } catch (erro) {
    await rm(arquivo, { force: true });
    throw erro;
  }

  const { size } = await stat(arquivo);
  const mib = (size / (1024 * 1024)).toFixed(1);
  console.log(`${arquivo} | ${total.toLocaleString('pt-BR')} transações | ${mib} MiB`);
}

main().catch((erro) => {
  console.error(erro.code === 'EEXIST' ? 'O arquivo já existe. Informe outro caminho.' : erro.message);
  process.exitCode = 1;
});
