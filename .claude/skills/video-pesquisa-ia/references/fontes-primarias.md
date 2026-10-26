# Onde procurar — fontes primárias e placares para vídeos sobre IA

Mapa de **lugares**, não de fatos. Nenhuma especificação de modelo, preço ou pontuação está registrada aqui de propósito: esses números caducam em semanas e o lugar certo deles é `pesquisa/fatos.json`, com data de acesso e validade. Use este arquivo para saber **qual página abrir** quando o roteiro afirma algo.

**Verificado em 2026-10-06.** Cada endereço abaixo foi aberto nesse dia de duas formas: (1) requisição HTTP pelo `fatos.py` (`checar_url`), que dá o estado e o destino final de redirecionamentos; (2) leitura do conteúdo — **C** = conteúdo lido (WebFetch ou HTML bruto), **T** = só título, `<h1>` e descrição lidos no HTML. "Oficial" = página de quem tem autoridade sobre o dado; "terceiros" = quem mede, agrega ou relata.

Leia junto com `metodo.md` (como julgar o que a página diz). Próxima revalidação: **2027-01-06** (seção final).

## 1. Por tipo de fato: que página abrir primeiro

| o roteiro afirma… | abra primeiro (primária) | confirme ou contextualize em |
|---|---|---|
| que modelo existe, como se chama, qual o identificador | página de modelos da documentação do laboratório (§2) | changelog / notas de versão do mesmo laboratório |
| janela de contexto, saída máxima, modalidades | página de modelos ou a página do modelo (§2) | model card / system card |
| data de corte de conhecimento | tabela de modelos ou relatório de transparência (§2) | — (não pergunte ao modelo: ver `metodo.md` §8) |
| preço de API | página de preços da documentação (§2) | página de preços do provedor de nuvem, se o vídeo fala da nuvem |
| preço de assinatura (app) | página de planos do produto (§2) — **não** a de API | — |
| data de lançamento ou de desligamento | changelog, notas de versão, página de descontinuações (§2) | comunicado no blog oficial |
| pontuação em benchmark | placar mantido por quem roda o teste (§5) | artigo ou model card do fabricante (autodeclarado: diga de quem é a conta) |
| "é aberto", licença, pesos | cartão do modelo no repositório de pesos e o texto da licença (§3) | definição da OSI (§3) |
| resultado de pesquisa, "um estudo mostrou" | o artigo (§4), na versão publicada | página do evento/periódico |
| fato histórico | documento original, prêmio, arquivo institucional (§6) | segunda fonte independente |
| uso, mercado, investimento | relatório com método declarado (§5: AI Index, Epoch) | comunicado da empresa (autodeclarado) |
| lei, regulação | diário oficial / casa legislativa / órgão (§7) | — |
| "a página dizia X em tal data" | Wayback Machine (§8) | — |

## 2. Laboratórios e plataformas (oficial)

### OpenAI

A documentação de API saiu de `platform.openai.com/docs/…` para `developers.openai.com/api/docs/…` (301 observado em 2026-10-06).

| o quê | endereço | o que se encontra | conf. |
|---|---|---|---|
| modelos da API | https://developers.openai.com/api/docs/models | catálogo; por modelo em destaque: preço de entrada/saída, janela de contexto, saída máxima, corte de conhecimento; link para a página de cada modelo | C |
| preços da API | https://developers.openai.com/api/docs/pricing | preço por 1M de tokens em colunas separadas (entrada, entrada em cache, escrita de cache, saída; contexto curto × longo) e por modalidade de processamento; avisos datados de mudança | C |
| changelog | https://developers.openai.com/api/docs/changelog | entradas datadas (lançamentos, recursos) | C |
| descontinuações | https://developers.openai.com/api/docs/deprecations | modelo, data do aviso, data de desligamento, substituto recomendado | C |
| preços (página comercial) | https://openai.com/business/pricing/ | planos para empresas e resumo de API (`openai.com/api/pricing/` redireciona para cá) | T |
| planos do ChatGPT | https://chatgpt.com/pricing/ | assinaturas por usuário/mês — não é preço de API | T |
| notícias / pesquisa | https://openai.com/news/ · https://openai.com/research/index/ | comunicados e publicações | T |
| tokens (ajuda) | https://help.openai.com/en/articles/4936856-understanding-and-counting-tokens | o que conta como token de entrada, saída, cache e raciocínio. Respondeu 200 ao `fatos.py` e **403 ao WebFetch** | T |
| tokenizador | https://platform.openai.com/tokenizer | aplicativo em JavaScript: robô só vê o título | T |
| Model Spec | https://model-spec.openai.com/ | redireciona por JavaScript para a versão datada do documento de comportamento | T |
| estado do serviço | https://status.openai.com/ | incidentes | T |

### Anthropic

`docs.anthropic.com/…` redireciona (301) para `platform.claude.com/docs/…`.

| o quê | endereço | o que se encontra | conf. |
|---|---|---|---|
| modelos | https://platform.claude.com/docs/en/models/overview | tabela comparativa: identificador de API e de cada nuvem, preço, janela de contexto, saída máxima, **dois** cortes ("Reliable knowledge cutoff" e "Training data cutoff"), data mínima de aposentadoria. As notas abaixo da tabela (ex.: a conversão de tokens em palavras) **não vêm no HTML** que o robô baixa: a documentação serve a mesma página em markdown em `<endereço>.md`, e ali o `checar-links --trechos` as encontra (conferido em 2026-10-06) | C |
| preços | https://platform.claude.com/docs/en/about-claude/pricing | por milhão de tokens ("MTok"): entrada base, escrita de cache (5 min e 1 h), leitura de cache, saída; lote, modo rápido, ferramentas; nota sobre tokenizadores diferentes entre gerações | C |
| descontinuações | https://platform.claude.com/docs/en/about-claude/model-deprecations | estado de cada modelo (Active, Legacy, Deprecated, Retired), data do aviso e da aposentadoria, histórico | C |
| notas de versão | https://platform.claude.com/docs/en/release-notes/overview | entradas datadas da plataforma | C |
| janela de contexto / contagem de tokens | https://platform.claude.com/docs/en/build-with-claude/context-windows · https://platform.claude.com/docs/en/build-with-claude/token-counting | como a janela é contada; como contar tokens antes de enviar | T |
| transparência | https://www.anthropic.com/transparency | "Transparency Hub": relatório por modelo (lançamento, cortes, avaliações de segurança) | C |
| system cards | https://www.anthropic.com/system-cards | documentos de avaliação por modelo | T |
| notícias / pesquisa | https://www.anthropic.com/news · https://www.anthropic.com/research | comunicados e publicações | T |
| planos e preços (produto) | https://claude.com/pricing | planos do app e resumo da API (a documentação aponta para cá como "most current") | T |

### Google (Gemini, Gemma, DeepMind)

`ai.google.dev` entra em laço de redirecionamento por `accounts.google.com` se o cliente não guarda cookies, e traduz a página conforme o `Accept-Language` (ver SKILL.md, Armadilhas).

| o quê | endereço | o que se encontra | conf. |
|---|---|---|---|
| modelos da API Gemini | https://ai.google.dev/gemini-api/docs/models | lista com código do modelo e descrição; limites ficam na página de cada modelo; "Last updated" no rodapé | C |
| preços da API Gemini | https://ai.google.dev/gemini-api/docs/pricing | por 1M de tokens em USD; nível gratuito × pago; padrão × lote; **preços com data de vigência** ("through…", "starting…"); "Last updated" | C |
| notas de versão | https://ai.google.dev/gemini-api/docs/changelog | entradas datadas | C |
| descontinuações | https://ai.google.dev/gemini-api/docs/deprecations | calendário de desligamento | T |
| Gemma (pesos abertos) | https://ai.google.dev/gemma/docs | visão geral da família | T |
| modelos DeepMind | https://deepmind.google/models/ | famílias de modelos | T |
| model cards | https://deepmind.google/models/model-cards/ | cartões por família (PDF ou página): dados de treino, avaliações, limitações. `modelcards.withgoogle.com` redireciona para cá | C |
| blogs | https://deepmind.google/blog/ · https://blog.google/innovation-and-ai/technology/ai/ | comunicados | T |
| preços na nuvem | https://cloud.google.com/gemini-enterprise-agent-platform/generative-ai/pricing | preços de IA generativa no Google Cloud (o endereço antigo `…/vertex-ai/generative-ai/pricing` redireciona para cá) | T |
| glossário de ML | https://developers.google.com/machine-learning/glossary | definições de conceitos (serve de fonte secundária de conceito) | C |

### Outros laboratórios

| laboratório | endereço | o que se encontra | conf. |
|---|---|---|---|
| Meta — blog | https://ai.meta.com/blog/ | comunicados de IA da Meta. Respondeu **400 ao `fatos.py`** e abriu no WebFetch | C |
| Meta — desenvolvedores | https://dev.meta.ai/ | plataforma de desenvolvedor (modelos, API, documentação); `llama.com` redireciona para cá | C |
| Meta — Llama | https://github.com/meta-llama/llama-models · https://huggingface.co/meta-llama | utilitários, cartões e licenças dos modelos Llama | T |
| Mistral — modelos | https://docs.mistral.ai/models | por modelo: identificador de API, tipo de licença, descrição; seção de modelos descontinuados com datas | C |
| Mistral — preços / mudanças / notícias | https://mistral.ai/pricing · https://docs.mistral.ai/resources/changelogs · https://mistral.ai/news | preços, changelog, comunicados | T |
| xAI — modelos e preços | https://docs.x.ai/developers/models | por modelo: janela de contexto e preço por milhão de tokens (entrada, entrada em cache, saída) | C |
| xAI — notas / notícias | https://docs.x.ai/developers/release-notes · https://x.ai/news | notas de versão e comunicados (em 2026-10-06 os títulos das páginas traziam "SpaceXAI") | T |
| DeepSeek — modelos e preços | https://api-docs.deepseek.com/quick_start/pricing | modelos, contexto, saída máxima, preço por 1M de tokens (cache hit/miss, saída) | C |
| DeepSeek — mudanças | https://api-docs.deepseek.com/updates | registro datado | T |
| Alibaba (Qwen) — modelos / preços | https://www.alibabacloud.com/help/en/model-studio/models · https://www.alibabacloud.com/help/en/model-studio/model-pricing | catálogo e preços do Model Studio | T |
| Alibaba (Qwen) — blog / produto | https://qwenlm.github.io/blog/ · https://qwen.ai/ | publicações técnicas; site do produto | T |
| Cohere | https://docs.cohere.com/docs/models · https://cohere.com/pricing | catálogo e preços | T |

### Nuvens que revendem modelos (oficial para o preço **naquela** nuvem)

| nuvem | endereço | o que se encontra | conf. |
|---|---|---|---|
| Microsoft Azure — modelos | https://learn.microsoft.com/en-us/azure/foundry/foundry-models/concepts/models-sold-directly-by-azure | modelos vendidos pela Azure, capacidades, regiões; metadado `ms.date` com a data da revisão | C |
| Microsoft Azure — preços | https://azure.microsoft.com/en-us/pricing/details/azure-openai/ | preços do Azure OpenAI (lenta: estourou 15 s numa das tentativas) | T |
| Amazon Bedrock — preços | https://aws.amazon.com/bedrock/pricing/ | por 1M de tokens de entrada e de saída, organizado por fornecedor | C |
| Amazon Bedrock — modelos | https://docs.aws.amazon.com/bedrock/latest/userguide/models-supported.html | página-índice; avisa que os detalhes por modelo foram movidos para outras páginas da documentação | T |

## 3. Pesos, licenças e "aberto"

| o quê | endereço | o que se encontra | tipo | conf. |
|---|---|---|---|---|
| repositório de pesos | https://huggingface.co/models | cartão de cada modelo (README), arquivos, licença declarada | terceiros (hospeda); o cartão é do autor do modelo | T |
| o que é um model card | https://huggingface.co/docs/hub/model-cards | onde a licença é declarada (metadado `license`), dados de treino, avaliações | oficial (Hugging Face) | C |
| definição de IA de código aberto | https://opensource.org/ai/open-source-ai-definition | Open Source AI Definition 1.0: exige informação sobre os dados, código e parâmetros — pesos sozinhos não bastam | oficial (OSI) | C |
| licenças aprovadas | https://opensource.org/licenses | lista de licenças que a OSI reconhece como código aberto | oficial (OSI) | T |

## 4. Artigos científicos

| o quê | endereço | o que se encontra | conf. |
|---|---|---|---|
| arXiv | https://arxiv.org/ · https://arxiv.org/list/cs.CL/recent | pré-publicações (sem revisão por pares); a página `abs/<id>` traz autores, resumo e histórico de versões com data | C |
| ACL Anthology | https://aclanthology.org/ | artigos revisados de linguística computacional e PLN | C |
| NeurIPS | https://proceedings.neurips.cc/ | anais por ano | C |
| PMLR (ICML e outros) | https://proceedings.mlr.press/ | anais | T |
| OpenReview | https://openreview.net/ | submissões e pareceres (ICLR e outros) | T |
| Semantic Scholar | https://www.semanticscholar.org/ | busca, citações, versões de um mesmo artigo | T |
| Google Acadêmico | https://scholar.google.com/ | busca | T |
| artigos em alta | https://huggingface.co/papers/trending | artigos com links para arXiv e código. `paperswithcode.com` redireciona (302) para cá | C |
| DOI | https://www.doi.org/ | `https://doi.org/<doi>` resolve para a versão publicada | T |

## 5. Placares e índices independentes (terceiros)

Independente não quer dizer infalível: leia o método de cada um (`metodo.md` §2).

| o quê | endereço | o que mede e como | conf. |
|---|---|---|---|
| Arena | https://arena.ai/leaderboard | preferência humana em comparações às cegas; várias categorias (texto, web, visão, imagem, vídeo…). `lmarena.ai` redireciona (301) para cá | C |
| Artificial Analysis | https://artificialanalysis.ai/ | índice próprio de inteligência, velocidade, latência e custo por modelo e por provedor; método publicado | C |
| Epoch AI — benchmarks | https://epoch.ai/benchmarks | central de benchmarks: parte das avaliações é rodada pela própria Epoch, parte é coletada de fontes externas (a página distingue); dados para baixar | C |
| Epoch AI — banco de modelos | https://epoch.ai/data/ai-models | base histórica de modelos de aprendizado de máquina (datas, organizações, parâmetros quando divulgados) | T |
| SWE-bench | https://www.swebench.com/ | % de problemas reais de software resolvidos; variantes diferentes (Verified, Multimodal, Multilingual, Lite, Full) — diga qual | C |
| ARC Prize | https://arcprize.org/leaderboard | pontuação × custo por tarefa nas versões do ARC-AGI; resultados verificados pela fundação | C |
| METR | https://metr.org/time-horizons/ | "horizonte de tempo" de tarefas que modelos de fronteira completam; organização sem fins lucrativos | C |
| LiveBench | https://livebench.ai/ | placar em aplicativo JavaScript: robô só vê o título; abra no navegador | T |
| Scale Labs (SEAL) | https://labs.scale.com/leaderboard | placares com conjuntos privados e abertos. `scale.com/leaderboard` redireciona para cá | C |
| HELM | https://crfm.stanford.edu/helm/ | avaliação holística de Stanford CRFM | T |
| Aider | https://aider.chat/docs/leaderboards/ | edição de código por LLMs | T |
| Vals AI | https://www.vals.ai/home | avaliações em tarefas profissionais (finanças, software, saúde…) | T |
| MLCommons | https://mlcommons.org/benchmarks/ | benchmarks de desempenho de hardware e de segurança | T |
| Open LLM Leaderboard | https://huggingface.co/spaces/open-llm-leaderboard/open_llm_leaderboard | placar de modelos abertos; confira na própria página se segue recebendo submissões | T |
| OpenRouter — uso | https://openrouter.ai/rankings | ranking por tokens processados **naquele** roteador (não é o mercado inteiro) | T |
| OpenRouter — preços | https://openrouter.ai/models | agregador/revendedor: contexto e preço por modelo e provedor — secundária para preço | C |
| AI Index (Stanford HAI) | https://hai.stanford.edu/ai-index · https://hai.stanford.edu/ai-index/2026-ai-index-report | relatório anual com dados de investimento, adoção, desempenho; em 2026-10-06 a edição mais recente era a de 2026 | C |
| Our World in Data | https://ourworldindata.org/artificial-intelligence | séries históricas com a fonte de cada gráfico (vá à fonte citada) | T |

## 6. História e referência

| o quê | endereço | o que se encontra | tipo | conf. |
|---|---|---|---|---|
| proposta de Dartmouth (1955) | https://www-formal.stanford.edu/jmc/history/dartmouth/dartmouth.html | texto da proposta que cunhou "artificial intelligence", no arquivo de John McCarthy | primária | T |
| "Attention Is All You Need" | https://arxiv.org/abs/1706.03762 | o artigo do Transformer: autores, resumo, histórico de versões | primária | C |
| Nobel de Física 2024 | https://www.nobelprize.org/prizes/physics/2024/summary/ | laureados e motivação oficial | primária | T |
| Prêmio Turing | https://amturing.acm.org/ | laureados e citações (respondeu 200 numa tentativa e 403 em outra) | primária | T |
| Computer History Museum | https://computerhistory.org/ | acervo e linhas do tempo | secundária de qualidade | T |

## 7. Regulação

| o quê | endereço | observação | conf. |
|---|---|---|---|
| Regulamento (UE) 2024/1689 (AI Act) | https://eur-lex.europa.eu/eli/reg/2024/1689/oj | texto oficial. Responde **202 com corpo vazio** a robôs: abra no navegador | T |
| NIST AI Risk Management Framework | https://www.nist.gov/itl/ai-risk-management-framework | documento e materiais | T |
| PL 2338/2023 (Brasil) | https://www25.senado.leg.br/web/atividade/materias/-/materia/157233 | tramitação e textos no Senado Federal | T |

## 8. Ferramentas de verificação

| o quê | endereço | para que serve |
|---|---|---|
| Wayback Machine | https://web.archive.org/ | como a página estava numa data: `https://web.archive.org/web/<AAAAMMDD>/<url>` leva ao instantâneo mais próximo (testado em 2026-10-06 com a página do arXiv). Use para "o preço era X em março" e para citar página que mudou. O WebFetch **recusa** `web.archive.org`; use `curl -L` |

## 9. Endereços que mudaram (observado em 2026-10-06)

Dos endereços que escrevi de memória para montar este arquivo, pelo menos estes 11 tinham mudado de caminho ou de domínio (cada linha se reproduz: o endereço antigo responde `redirecionado` para o novo no `checar-links`):

| de memória | hoje |
|---|---|
| `platform.openai.com/docs/{models,pricing,changelog,deprecations}` | `developers.openai.com/api/docs/…` |
| `openai.com/api/pricing/` | `openai.com/business/pricing/` |
| `docs.anthropic.com/…` | `platform.claude.com/docs/…` |
| `modelcards.withgoogle.com` | `deepmind.google/models/model-cards/` |
| `cloud.google.com/vertex-ai/generative-ai/pricing` | `cloud.google.com/gemini-enterprise-agent-platform/generative-ai/pricing` |
| `www.llama.com` | `dev.meta.ai` |
| `docs.mistral.ai/getting-started/models/models_overview/` | `docs.mistral.ai/models` |
| `docs.x.ai/docs/models` | `docs.x.ai/developers/models` |
| `lmarena.ai/leaderboard` | `arena.ai/leaderboard` |
| `paperswithcode.com` | `huggingface.co/papers/trending` |
| `scale.com/leaderboard` | `labs.scale.com/leaderboard` |

Moral: endereço de memória é tão suspeito quanto número de memória. Chegue pela busca ou por este arquivo e deixe o `checar-links` dizer o destino final.

## 10. Revalidar a cada 3 meses

Este arquivo envelhece. A cada trimestre (próxima: **2027-01-06**) ou quando um link daqui falhar:

1. Rode a conferência de todos os endereços deste arquivo (uma requisição leve por URL, 4 em paralelo; cerca de 30 s):

   ```bash
   python3 "$CRIABR_SKILLS"/video-pesquisa-ia/scripts/fatos.py checar-links --arquivo "$CRIABR_SKILLS"/video-pesquisa-ia/references/fontes-primarias.md
   ```

2. Para cada `redirecionado` com 301/308: troque o endereço pelo destino e registre a mudança na §9. Para cada `quebrado`: procure a nova página oficial (busca pelo nome do laboratório + "models", "pricing", "changelog") e confirme o conteúdo antes de trocar. `bloqueado` não é defeito: confira no navegador ou com a outra ferramenta e mantenha a observação.
3. Abra uma página de modelos e uma de preços de cada laboratório da §2 e confira se a coluna "o que se encontra" ainda descreve a estrutura (colunas, unidade, datas). Mudou a unidade ou a forma de cobrar? Atualize também `metodo.md` §4.
4. Veja se surgiu laboratório, nuvem ou placar que o canal passou a citar e acrescente com o mesmo critério (aberto hoje, oficial ou terceiros, o que se encontra).
5. Troque as duas datas do topo ("Verificado em", "Próxima revalidação") e a desta seção.

Resultados das duas conferências de 2026-10-06, nenhuma com `quebrado`: de manhã (31 s) `101 URLs: 4 bloqueado, 95 ok, 2 redirecionado`; à tarde (24 s) `101 URLs: 5 bloqueado, 93 ok, 2 redirecionado, 1 sem_resposta`. Os bloqueados **mudam de uma rodada para a outra**: `ai.meta.com/blog/` (400), `amturing.acm.org` (403) e `eur-lex.europa.eu` (202 vazio) nas duas; `openai.com/research/index/` (403) só de manhã; `openai.com/business/pricing/` e `openai.com/news/` (403) só à tarde — e os dois responderam 200 um minuto depois. O `sem_resposta` foi a página de preços do Azure, que estourou os 12 s do prazo padrão e abriu com `--prazo 30`. Os dois redirecionados são os endereços-padrão das §4 e §8 (`doi.org/` e `web.archive.org/web/`), que só fazem sentido com um identificador depois da barra. Código de saída 1 nessa conferência quer dizer "há `sem_resposta` ou `quebrado`": repita só esses com prazo maior antes de mexer no arquivo.
