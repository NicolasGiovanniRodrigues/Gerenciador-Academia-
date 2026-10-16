# Contexto para continuar o projeto Automatic Fit no Codex

Este documento consolida os requisitos, decisões, alterações e problemas tratados nesta conversa até 16/10/2026. Não é uma transcrição literal. Use-o junto dos arquivos reais do projeto, que devem ser inspecionados antes de qualquer alteração. Não considere um pedido antigo como prova de que ele foi concluído.

## 1. Orientação principal para o próximo Codex

Você está dando continuidade a um projeto escolar de gerenciamento de aulas e modalidades de academia, chamado Automatic Fit / Gerenciador Academia.

O usuário quer um sistema funcional, mas com código simples, legível e próximo do modelo inicial do `main.py`. Ele precisa conseguir localizar as partes e entender o que foi escrito. Não transforme esse projeto em uma arquitetura maior nem acrescente funcionalidades por iniciativa própria.

Antes de editar:

1. Leia o `main.py`, os templates, os arquivos estáticos e a estrutura do banco disponíveis na pasta atual.
2. Verifique se essa pasta contém a versão mais recente do usuário. Não substitua alterações recentes por uma versão antiga citada neste contexto.
3. Identifique a próxima tarefa solicitada. Este documento fornece contexto; não é uma ordem para refazer o projeto, atualizar o Trello ou alterar o Figma automaticamente.
4. Preserve o banco corrigido e os dados existentes. Faça os testes de gravação em uma cópia.
5. Implemente somente o necessário, explique as mudanças em português e informe o que foi realmente verificado.

## 2. Preferências e restrições de implementação

Pedidos reiterados do usuário:

- Fazer tudo da forma mais simples possível, mas funcionando corretamente.
- Seguir a base, a organização e o estilo do `main.py` inicial.
- Manter o código limpo, organizado e separado por comentários.
- Usar construções básicas que possam ser explicadas em aula: funções, variáveis, `if`, `else`, `for`, SQL explícito e tratamento de erros compreensível.
- Evitar bibliotecas desnecessárias, abstrações excessivas e recursos que ele não estudou.
- Quando o usuário diz “artesanal” ou “feito à mão”, interpretar como lógica explícita, simples e compreensível. Não alegar autoria humana nem esconder a assistência de IA.
- Validar a força da senha manualmente, sem biblioteca de validação de senha. A proteção da senha com BCrypt foi mantida.
- Não adicionar um monte de arquivos, módulos, pastas ou ferramentas ao projeto.
- Não introduzir frameworks de frontend, ORM, migração para outro banco ou nova arquitetura sem solicitação.
- Preservar o visual aprovado e as funcionalidades existentes durante limpezas de código.
- Não remover proteções necessárias apenas para diminuir o número de importações.

O modelo inicial usava Flask, `fdb`, Flask-Bcrypt e `date`. A última versão ainda utiliza alguns mecanismos do Flask, como `g`, verificações antes da requisição e envio de contexto aos templates. Não foi fornecida uma lista completa dos assuntos estudados; não afirmar que cada construção já foi ensinada.

Estrutura de entrega adotada:

- `main.py`
- `BANCO.FDB`
- `templates/`
- `static/`

A entrega não deve incluir `.venv`, `__pycache__`, testes internos, scripts auxiliares de manutenção ou módulos extras criados apenas para organizar o backend. Este arquivo de contexto é um material de transferência, não uma nova dependência do aplicativo.

## 3. Tecnologias e execução

- Backend: Python com Flask.
- Templates: HTML com Jinja.
- Frontend: CSS e JavaScript simples.
- Banco: Firebird, arquivo `BANCO.FDB`.
- Driver: `fdb`.
- Hash de senha: Flask-Bcrypt / BCrypt.
- Ambiente do usuário: Windows, com ambiente virtual Python.
- Execução local: `python main.py`.
- Endereço usado: `http://127.0.0.1:5000`.

O caminho informado pelo usuário durante o diagnóstico foi:

```text
C:\Users\Aluno\Downloads\projetofianal-main\projetofianal-main\BANCO.FDB
```

O Python mostrado nos logs estava em:

```text
C:\Users\Aluno\Downloads\projetofianal-main\.venv\Scripts\python.exe
```

Esses são caminhos históricos daquele computador, não caminhos universais.

A conexão original apontava para `C:\AutomaticFitDados\BANCO.FDB`. Isso gerou confusão e foi alterado: na última entrega, o programa procura `BANCO.FDB` na mesma pasta do `main.py`, usando `os.path`. Não restaurar o caminho fixo antigo.

Parâmetros de desenvolvimento presentes na última versão:

- host: `localhost`;
- usuário: `SYSDBA`;
- senha configurada: `sysdba`;
- charset: `UTF8`;
- transação com isolamento de leitura confirmada.

A senha acima é uma configuração desse projeto; não assumir que seja a senha de toda instalação do Firebird.

Para reiniciar: salvar o arquivo, parar o servidor com Ctrl+C e executar `python main.py` novamente. O aviso de servidor de desenvolvimento do Flask, sozinho, não é erro de conexão.

## 4. Perfis e funcionalidades

Perfis armazenados no banco:

| Valor no banco | Nome mostrado na interface |
| --- | --- |
| `ALUNO` | Aluno |
| `PERSONAL` | Professor |
| `ADMINISTRADOR` | Administrador |

Não trocar `PERSONAL` por `PROFESSOR` no banco sem analisar todas as consultas, regras e dados vinculados.

O cadastro público cria alunos. O perfil de acesso deve vir da conta no banco; a opção de escolher perfil em um protótipo não deve permitir que qualquer pessoa se torne administrador.

Aluno:

- Cadastro e login.
- Grade de aulas disponíveis.
- Identificação de aulas lotadas e inscrições indisponíveis.
- Detalhes da aula e inscrição quando houver vaga.
- Minhas aulas e cancelamento de inscrição.
- Perfil, edição de dados e alteração de senha.

Professor:

- Página inicial do professor.
- Agenda e aulas sob sua responsabilidade.
- Consulta e registro de presença dos alunos.

Administrador:

- Página inicial com totais e próximas aulas.
- Listagem, cadastro e edição de usuários.
- Gerenciamento de modalidades.
- Gerenciamento e cancelamento de aulas.
- Consulta de detalhes e chamada conforme as permissões.

## 5. Requisitos de usuário e autenticação

A lista solicitada para o sistema e para o Trello inclui:

1. Cadastrar usuário.
2. Fazer login.
3. Proteger a senha na inserção. O usuário chamou isso de “senha criptografada”; a implementação usa hash BCrypt.
4. Validar senha forte manualmente, sem biblioteca de validação.
5. Impedir login de usuário inativo.
6. Impedir cadastro de dois e-mails iguais.
7. Proteger a senha também quando for alterada.
8. Editar todos os campos permitidos do usuário, preservando a chave primária.
9. Bloquear a conta após três tentativas de senha incorreta.
10. Proteger as páginas que exigem autenticação.
11. Fazer telas responsivas e coerentes com o Figma.
12. Impedir reutilização das três últimas senhas, além da senha atual nas verificações existentes.
13. Ter home responsiva conforme o Figma.
14. Fazer logout autenticado.
15. Redirecionar após o login para uma página segura que mostre “Olá {{ usuario }}”.
16. Conseguir explicar a rota de login.
17. Conseguir explicar a rota de cadastro.
18. Conseguir explicar o desenvolvimento do frontend.

A validação de força existente confere pelo menos oito caracteres, letra maiúscula, minúscula, número e símbolo. O código entregue também trata o limite técnico de entrada do BCrypt. Não truncar senhas silenciosamente.

E-mails são normalizados com remoção de espaços nas extremidades e conversão para minúsculas; consultas usam `LOWER(TRIM(EMAIL))`. A validação manual atual rejeita e-mails malformados e espaços internos.

CPF, telefone e data de nascimento são conferidos conforme as regras já implementadas. O cadastro público exige CPF e data de nascimento. A validação de CPF existente verifica formato de onze números; não confundir com uma validação matemática dos dígitos verificadores.

## 6. Requisitos de modalidades e aulas

Pedidos do usuário, consolidados sem repetir o item de listagem:

1. Cadastrar modalidades, como Yoga e Musculação, sem duplicidade de nome.
2. Permitir como instrutor somente um usuário com perfil de Professor.
3. Exigir horário final maior que o inicial.
4. Disponibilizar editar e excluir na listagem de modalidades.
5. Mostrar mensagens adequadas em cada operação, por exemplo “Modalidade já existe”, “Capacidade inválida” e “Instrutor não permitido”.
6. Listar modalidades com nome, descrição e situação ativa/inativa.
7. Cadastrar aula somente com modalidade já cadastrada e ativa.
8. Exigir capacidade maior que zero.
9. Impedir duas aulas da mesma modalidade, no mesmo dia e horário, com o mesmo instrutor.
10. Impedir exclusão de modalidade que possua aulas vinculadas.
11. Manter o banco correto, com chaves primárias e estrangeiras.
12. Fazer as telas conforme o desktop do Figma, com adaptação responsiva para celular.

O código também impede conflitos de horário do professor, exige professor ativo, impede reduzir a capacidade abaixo do total de inscritos e controla a disponibilidade das inscrições. Preservar esses comportamentos ao refatorar.

O registro de presença e o cancelamento de aula/inscrição já fazem parte da implementação. Cancelamentos preservam registros em vez de apagar o histórico.

## 7. Banco de dados

Tabelas existentes na versão corrigida:

| Tabela | Finalidade e principais campos |
| --- | --- |
| `USUARIOS` | `ID_USUARIO`, nome, e-mail, senha, tipo de usuário, telefone, CPF, nascimento, tentativas de login, bloqueado e ativo. |
| `HISTORICO_SENHAS` | `ID_HISTORICO`, usuário vinculado e hash de senha anterior. |
| `MODALIDADES` | `ID_MODALIDADE`, nome, descrição, duração e ativa. |
| `AULAS` | `ID_AULA`, nome, modalidade, professor, data, início, fim, capacidade, local e situação. |
| `INSCRICOES` | `ID_INSCRICAO`, aula, usuário, ativa e presença. |

Os identificadores são chaves primárias. Há vínculos por chaves estrangeiras entre as tabelas. Há índices e restrições para unicidade, capacidade, horários e estados válidos.

Regras de aplicação gravadas em triggers:

- `TR_USUARIO_NORMALIZA`
- `TR_MODALIDADE_NORMALIZA`
- `TR_AULA_VALIDA`
- `TR_INSCRICAO_VALIDA`

Há também restrições `CHECK`, índices normalizados de e-mail e nome da modalidade e a exceção `EX_REGRA`.

Não recriar o banco vazio para resolver um erro. Não apagar usuários, trocar hashes por texto puro ou eliminar vínculos existentes.

Na verificação histórica da cópia corrigida havia cinco usuários, um registro de histórico de senha e nenhum registro de modalidade, aula ou inscrição. Isso é apenas um retrato daquela entrega: conferir os dados atuais antes de assumir que continuam assim.

## 8. Erro do Firebird: causa e correção já realizada

O usuário relatou erro ao cadastrar e uma mensagem de falha de conexão na página. O log real apontava para `cursor.execute(...)` dentro de `cadastro`, com:

```text
fdb.fbcore.DatabaseError:
Error while preparing SQL statement:
- SQLCODE: -104
- invalid request BLR at offset 28
- BLR syntax error: expected valid BLR code at offset 29, encountered 64
```

Sequência relevante:

1. Inicialmente foi corrigido o caminho fixo do banco.
2. O erro persistiu porque a conexão já estava funcionando; a falha ocorria ao preparar o `INSERT` do cadastro.
3. Foi sugerido remover `RETURNING ID_USUARIO` e o `fetchone()` quando o ID não era usado. Isso simplificou o trecho, mas NÃO resolveu a causa do erro BLR.
4. O usuário enviou `projetofianal-main(1).zip` com o código e o banco realmente usados.
5. A análise reproduziu exatamente o erro usando Firebird 4.0.6 e uma cópia daquele banco.
6. A causa confirmada estava nas regras do banco compiladas no Firebird 5, incompatíveis com a execução no Firebird 4 naquele arquivo. O banco tinha ODS 13.0.
7. As quatro triggers de aplicação e as oito restrições `CHECK` foram recompiladas com Firebird 4, preservando a lógica, os vínculos e os dados.
8. Cadastro e demais operações passaram a funcionar nos testes feitos com Firebird 4 e Firebird 5.

A versão instalada no computador do usuário não foi informada explicitamente por ele. O que foi confirmado foi a reprodução no Firebird 4 e a correção testada em 4 e 5.

Também foi ajustada a mensagem genérica de erro do banco para não apresentar toda falha SQL como problema de conexão. O erro real continua disponível no terminal.

Não voltar a recompilar o banco de entrega com Firebird 5 sem conferir se a compatibilidade com Firebird 4 será mantida. Não alterar o arquivo binário diretamente. Se precisar corrigir regras novamente, use DDL apropriado no mecanismo de destino e preserve uma cópia do banco.

A correção não foi apenas no `main.py`: é necessário usar também o `BANCO.FDB` corrigido. Trocar só o Python por cima do banco antigo pode manter o problema.

## 9. Estado da última entrega desta conversa

Último arquivo entregue: `projetofianal-main-corrigido.zip`.

O usuário depois pediu outra limpeza: remover importações desnecessárias, manter organização por comentários e lógica simples. Essa revisão foi concluída sobre o projeto com o banco corrigido.

Mudanças finais:

- Removido o uso de `re` nas validações.
- Removido o uso de `time.fromisoformat` para validar os horários.
- E-mail, CPF e horário conferidos por verificações explícitas.
- Validação do horário no formato `HH:MM`, de `00:00` a `23:59`.
- Substituídos `dict(zip(...))`, compreensões e expansões de parâmetros por laços ou parâmetros explícitos onde foram revisados.
- Redirecionamento por perfil escrito com condições simples.
- SQL organizado de forma legível, mantendo parâmetros `?`.
- Seções comentadas no Python e no CSS.
- JavaScript do botão de senha reescrito com `for`, função comum e `if/else`.
- Banco corrigido preservado sem alteração dos dados.
- `BANCO.FDB` localizado junto ao `main.py`.
- Mantidas as proteções de senha, sessão, formulários e permissões.

Importações efetivamente presentes na última versão:

```python
import os
import secrets
from datetime import date
import fdb
from flask import (
    Flask, abort, flash, g, redirect, render_template,
    request, session, url_for,
)
from flask_bcrypt import Bcrypt
```

Função dessas dependências:

- Flask: páginas, formulários, redirecionamentos, sessão e controle de requisições.
- `fdb`: acesso ao Firebird.
- BCrypt: gerar e verificar hashes de senha.
- `os`: localizar o banco em relação ao `main.py`.
- `date`: datas e validação de nascimento/aula.
- `secrets`: chave de sessão e proteção dos formulários.

Todas essas importações foram conferidas como utilizadas. Não há biblioteca de validação de senha nem ORM.

A última versão cria uma chave de sessão aleatória ao iniciar. Assim, reiniciar o processo pode invalidar sessões já abertas. Isso não significa que uma conta tenha sido removida do banco.

Resultados históricos de verificação desta conversa:

- 32 testes passaram com Firebird 4.
- Os mesmos 32 passaram com Firebird 5.
- A cobertura incluiu cadastro, login, bloqueio, inatividade, acesso, modalidades, aulas, vínculos, senhas anteriores, edição, inscrição, capacidade, chamada e cancelamento.
- Foram acrescentadas verificações de horários e dados inválidos de cadastro.
- O botão de mostrar/ocultar senha foi verificado.
- A estrutura e a integridade do ZIP foram conferidas.
- Os dados do banco foram comparados e preservados durante a correção.

Esses resultados se referem à entrega daquele momento. Não são uma garantia de que alterações posteriores do usuário estejam testadas. Os testes e mecanismos auxiliares usados na análise não fazem parte da estrutura entregue.

## 10. Rotas da última versão

| Rota | Uso |
| --- | --- |
| `/` | Landing page. |
| `/cadastro` | Cadastro público de aluno, GET/POST. |
| `/login` | Login, GET/POST. |
| `/logout` | Logout por POST. |
| `/minha-home` | Redirecionamento por perfil. |
| `/administrador` | Início do administrador. |
| `/aluno` | Grade do aluno. |
| `/personal` | Início do professor. |
| `/agenda` | Agenda do professor. |
| `/presencas` | Aulas para consulta da chamada. |
| `/perfil` | Dados da conta conectada. |
| `/editar-dados` | Edição pessoal, GET/POST. |
| `/alterar-senha` | Alteração de senha, GET/POST. |
| `/usuarios` | Listagem administrativa por perfil. |
| `/usuarios/novo` | Cadastro administrativo, GET/POST. |
| `/usuarios/<id_usuario>/editar` | Edição administrativa, GET/POST. |
| `/modalidades` | Listagem de modalidades. |
| `/modalidades/nova` | Cadastro, GET/POST. |
| `/modalidades/<id_modalidade>/editar` | Edição, GET/POST. |
| `/modalidades/<id_modalidade>/excluir` | Tela de confirmação e exclusão, GET/POST. |
| `/aulas` | Listagem administrativa de aulas. |
| `/aulas/nova` | Cadastro de aula, GET/POST. |
| `/aulas/<id_aula>/editar` | Edição de aula, GET/POST. |
| `/aulas/<id_aula>` | Detalhes. |
| `/aulas/<id_aula>/cancelar` | Confirmação e cancelamento, GET/POST. |
| `/aulas/<id_aula>/inscrever` | Inscrição por POST. |
| `/minhas-aulas` | Inscrições do aluno. |
| `/inscricoes/<id_aula>/cancelar` | Confirmação e cancelamento da inscrição, GET/POST. |
| `/chamada/<id_aula>` | Presenças, GET/POST. |

Os parâmetros de ID nas rotas são inteiros. A autorização depende da sessão e do perfil; a existência da rota não significa que todos possam acessá-la.

Templates presentes: `alterar_senha.html`, `aula_detalhes.html`, `aula_form.html`, `aulas.html`, `base.html`, `cadastro.html`, `chamada.html`, `confirmar.html`, `dashboard.html`, `erro.html`, `grade.html`, `landing.html`, `login.html`, `mensagens.html`, `minhas_aulas.html`, `modalidade_form.html`, `modalidades.html`, `perfil.html`, `personal.html`, `usuario_form.html` e `usuarios.html`.

## 11. Figma, aparência e responsividade

O projeto começou também com organização de telas, protótipos e tarefas no Trello. Foram usados PDFs de telas do Gerenciador Academia, landing page, cadastro e login como referências visuais.

Um link de Figma citado no histórico associado ao projeto foi:

https://www.figma.com/file/c7q4f4s5vWmDXb9ZKEro01?locale=pt-br&type=design

Conferir se esse continua sendo o arquivo atual antes de usá-lo. Não presumir acesso ou que os anexos de outro ambiente estejam disponíveis.

Pedidos sobre o Figma:

- Coerência entre telas e tarefas.
- Não usar pop-ups, modais ou confirmações sobrepostas: transformar esses fluxos em novas telas.
- Preservar os protótipos de navegação e as conexões dos botões.
- O usuário afirmou que já havia conectado os botões; não desfazer isso ao alterar layout ou responsividade.
- Apontar problemas de desktop quando a análise for restrita a desktop.
- Os prompts destinados ao agente do Figma precisavam ter menos de 2.000 caracteres.
- Em um momento, o usuário aceitou deixar o Figma como estava, mesmo com versões mobile incorretas.

Decisão final para a implementação:

**Usar as telas de desktop do Figma como referência e torná-las responsivas para celular. Não seguir as telas mobile incorretas do arquivo.**

As primeiras telas de aluno mencionadas foram:

1. Login e cadastro.
2. Escolher perfil.
3. Grade de aulas.
4. Grade com aulas lotadas.
5. Inscrição disponível e indisponível.
6. Minhas aulas e cancelamento de inscrição.
7. Perfil do aluno.
8. Editar dados do aluno.
9. Alteração de senha.

Depois foram tratados professor/personal e administrador. O histórico disponível não permite reconstruir toda inspeção visual anterior ou afirmar que cada tela específica do Figma foi corrigida. Não inventar uma lista de problemas antigos que não esteja registrada aqui.

## 12. Trello: regras de organização solicitadas

O usuário solicitou criar e revisar tarefas do projeto no Trello, com prioridade/urgência e checklists.

Orientações consolidadas:

- Conferir o que já existe e não duplicar cartões.
- Manter o quadro coerente com o Figma e com o escopo do projeto.
- Descrição deve dizer exatamente o que fazer, com verbo e objeto, como “Desenvolver o protótipo da tela de login no Figma e conectar a navegação”.
- Diferenciar tarefa de design no Figma de implementação real em código.
- Quando for tarefa de Figma, dizer explicitamente que é no Figma e incluir o protótipo de navegação quando fizer parte do trabalho.
- Indicar desktop e mobile/responsividade conforme o escopo.
- “Landing page e footer” foi corrigido pelo usuário para uma tarefa de landing page, explicitando Figma.
- Usar a legenda/etiqueta de prioridade; não repetir urgência no título.
- Não repetir prioridade ou integrante responsável na descrição se já houver o recurso correspondente no cartão.
- Checklists devem detalhar tudo que a tarefa pede para ser feito, em etapas marcáveis.
- Não usar checklist genérico de anexar arquivos, capturas ou provas quando isso não for a tarefa.
- Revisar requisitos funcionais e não funcionais já existentes e corrigir descrições incorretas.
- O usuário pediu mover tarefas anteriores concluídas para Concluído e marcar os itens feitos.

Esses são pedidos e regras de organização, não uma confirmação do estado atual do quadro. Antes de qualquer alteração futura, ler os cartões e conferir a situação real. Não marcar uma nova tarefa como concluída só porque se parece com um pedido antigo.

## 13. Arquivos e versões: como evitar regressões

Arquivos relevantes citados nesta conversa:

- `projetofianal-main.zip`: projeto inicial e entregas anteriores.
- `projetofianal-main(1).zip`: cópia enviada pelo usuário para reproduzir o erro real.
- `projetofianal-main-corrigido.zip`: última entrega desta conversa, já com correção do banco e limpeza do código.
- `Gerenciador Academia (1).pdf`: referência de telas.
- `Landing Page.pdf`, `Página de Cadastro.pdf` e `Login — Geral.pdf`: referências visuais.

Houve várias versões intermediárias. Uma versão chamada “básica” no ambiente de trabalho chegou a usar novamente o caminho fixo antigo; ela não deve ser escolhida apenas pelo nome. A referência final desta conversa é o ZIP corrigido e organizado.

Esses nomes não garantem que os arquivos estejam na pasta em que o novo Codex vai trabalhar. O usuário pode ter feito mudanças depois. Sempre ler a cópia efetivamente fornecida e preservar os dados mais recentes.

## 14. Cuidados para continuar sem repetir os problemas

- Não diagnosticar erro de conexão apenas pelo texto genérico da página. Ler o traceback e a operação que falhou.
- Um erro no `INSERT` depois de consultas bem-sucedidas pode estar em triggers, restrições ou incompatibilidade de compilação.
- Não prometer que remover `RETURNING` resolverá o erro BLR: isso já foi tentado e não resolveu.
- Manter o `main.py` e o banco compatíveis entre si.
- Não recompilar regras no Firebird 5 e entregar para Firebird 4 sem testar a compatibilidade.
- Não usar o banco real para criar usuários de teste ou apagar dados de teste depois por suposição. Trabalhar com cópias.
- Não adicionar bibliotecas só para uma validação que um `if` ou `for` resolve.
- Manter SQL parametrizado; não concatenar entradas de formulário para montar SQL.
- Manter a proteção das senhas e o histórico de hashes.
- Preservar o controle de acesso, usuário inativo e bloqueio por tentativas.
- Manter as confirmações em páginas próprias e o visual responsivo derivado do desktop.
- Não afirmar que uma versão posterior passou nos testes históricos sem executá-los nela.
- Se a próxima tarefa depender de informação ausente, analisar primeiro o que está disponível e pedir somente o que for indispensável.

## 15. Instrução pronta para iniciar a próxima sessão

Leia este contexto e os arquivos reais do projeto antes de alterar qualquer coisa. Continue a partir da versão mais recente que estiver na pasta. Preserve o banco corrigido, os dados, a estrutura simples e os comentários por seção. Use apenas dependências necessárias e lógica que eu consiga entender e explicar. Mantenha o visual do desktop do Figma adaptado para celular e as regras de usuários, aulas, modalidades e inscrições. Ao receber minha próxima tarefa, faça a alteração específica, teste o que ela afeta e explique de forma direta o que mudou.
