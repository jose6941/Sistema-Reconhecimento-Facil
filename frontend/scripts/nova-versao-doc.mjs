// Cria a próxima versão da documentação (V#### + data) copiando a mais recente.
// Uso:  npm run doc:nova-versao   e depois edite o arquivo criado.
import { promises as fs } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const pasta = path.join(path.dirname(fileURLToPath(import.meta.url)), "..", "src", "content", "documentacao");
const padrao = /^V(\d{4})_\d{4}-\d{2}-\d{2}\.md$/;

const arquivos = (await fs.readdir(pasta)).filter((a) => padrao.test(a)).sort();
if (arquivos.length === 0) {
  console.error("Nenhuma versão encontrada em", pasta);
  process.exit(1);
}

const ultimo = arquivos[arquivos.length - 1];
const proximo = Number(padrao.exec(ultimo)[1]) + 1;
const hoje = new Date();
const data = [
  hoje.getFullYear(),
  String(hoje.getMonth() + 1).padStart(2, "0"),
  String(hoje.getDate()).padStart(2, "0"),
].join("-");

const novoNome = `V${String(proximo).padStart(4, "0")}_${data}.md`;
await fs.copyFile(path.join(pasta, ultimo), path.join(pasta, novoNome), fs.constants.COPYFILE_EXCL);

console.log(`Criada ${novoNome} a partir de ${ultimo}.`);
console.log("Edite o arquivo para registrar as mudanças; o painel mostrará as diferenças na aba Log.");
