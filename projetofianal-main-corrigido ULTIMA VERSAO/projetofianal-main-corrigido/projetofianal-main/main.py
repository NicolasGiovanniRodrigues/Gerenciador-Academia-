from flask import Flask, render_template, request, flash, redirect, url_for, session, abort
import fdb
from flask_bcrypt import Bcrypt
from datetime import date
from getpass import getpass
import os
import secrets


# Inicia a aplicação
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY') or secrets.token_hex(32)
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
bcrypt = Bcrypt(app)
PERFIS = {'ALUNO': 'Aluno', 'PERSONAL': 'Professor', 'ADMINISTRADOR': 'Administrador'}


# Conecta ao banco Firebird
def conectar():
    if os.getenv('FIREBIRD_CLIENT'):
        fdb.load_api(os.environ['FIREBIRD_CLIENT'])
    # Procura o banco na mesma pasta deste arquivo
    caminho = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'BANCO.FDB')
    if not os.path.isfile(caminho):
        raise fdb.ProgrammingError('BANCO.FDB não encontrado na mesma pasta de main.py.')
    # Informa os dados da conexão
    con = fdb.connect(
        host=os.getenv('DB_HOST', 'localhost') or None,
        database=caminho,
        user=os.getenv('DB_USER', 'SYSDBA'),
        password=os.getenv('DB_PASSWORD', 'sysdba'),
        charset='UTF8',
    )
    # Usa os dados mais recentes que foram salvos no banco
    con.default_tpb = fdb.ISOLATION_LEVEL_READ_COMMITED
    return con


# Explica o erro de senha do Firebird sem confundir com a senha do site.
def mensagem_firebird(erro):
    # 335544472 é o código de usuário ou senha recusados pelo Firebird.
    if 335544472 in erro.args:
        return (
            'O Firebird recusou o usuário ou a senha do banco. Pare o programa e '
            'execute main.py novamente para informar os dados no terminal. '
            'Use a senha definida na instalação do Firebird, não a senha do site.'
        )
    return (
        'Não foi possível concluir o cadastro no Firebird. Confira se BANCO.FDB '
        'está na pasta de main.py e consulte o erro no terminal.'
    )


# Testa o banco antes de abrir o site e permite corrigir a senha uma vez.
def preparar_conexao():
    for tentativa in range(2):
        try:
            con = conectar()
            con.close()
            return True
        except fdb.DatabaseError as erro:
            print('Erro na conexão com o Firebird:', erro)
            if 335544472 not in erro.args or tentativa == 1:
                print(mensagem_firebird(erro))
                return False

            print('Informe os dados usados na instalação do Firebird.')
            print('A senha não é a senha de acesso ao site e não será salva em arquivo.')
            usuario = os.getenv('DB_USER', 'SYSDBA')
            try:
                informado = input('Usuário do Firebird [' + usuario + ']: ').strip()
                if informado:
                    usuario = informado
                senha = getpass('Senha do Firebird (digitação oculta): ')
            except (EOFError, KeyboardInterrupt):
                print('Entrada cancelada. Execute python main.py em um terminal para informar os dados.')
                return False
            os.environ['DB_USER'] = usuario
            os.environ['DB_PASSWORD'] = senha

    return False


# Organiza os resultados da consulta para as páginas HTML
def consultar(con, sql, parametros=(), unico=False):
    cursor = con.cursor()
    cursor.execute(sql, parametros)
    campos = []
    for coluna in cursor.description:
        campos.append(coluna[0].lower())
    dados = []
    for registro in cursor.fetchall():
        linha = {}
        for posicao in range(len(campos)):
            linha[campos[posicao]] = registro[posicao]
        dados.append(linha)
    if unico:
        if dados:
            return dados[0]
        return None
    return dados


# Confere se a senha é forte, sem biblioteca de validação
def senha_forte(senha):
    if len(senha) < 8 or len(senha.encode('utf-8')) > 72:
        return False
    maiuscula = False
    minuscula = False
    numero = False
    especial = False
    for letra in senha:
        if letra.isupper():
            maiuscula = True
        if letra.islower():
            minuscula = True
        if letra.isdigit():
            numero = True
        if not letra.isalnum() and (not letra.isspace()):
            especial = True
    return maiuscula and minuscula and numero and especial


# Compara a senha digitada com o hash salvo no banco
def conferir_senha(hash_salvo, senha):
    if not hash_salvo or len(senha.encode('utf-8')) > 72:
        return False
    try:
        return bcrypt.check_password_hash(hash_salvo, senha)
    except (ValueError, TypeError):
        return False


# Protege a senha antes de gravar no banco
def gerar_hash(senha):
    return bcrypt.generate_password_hash(senha).decode('utf-8')


# Procura a conta da pessoa que está conectada
def usuario_logado():
    if 'id_usuario' not in session:
        return None

    con = conectar()
    try:
        usuario = consultar(
            con,
            'SELECT * FROM USUARIOS WHERE ID_USUARIO=?',
            (session['id_usuario'],),
            True,
        )
    finally:
        con.close()

    if not usuario or not usuario['ativo'] or usuario['bloqueado']:
        session.clear()
        flash('Faça login com uma conta ativa e liberada.', 'erro')
        return None
    return usuario


# Cria o código de proteção do formulário
def token_formulario():
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_hex(24)
    return session['csrf_token']


# Confere o código de proteção antes de receber o formulário
def conferir_formulario():
    if request.method == 'POST':
        recebido = request.form.get('csrf_token', '')
        esperado = session.get('csrf_token', '')
        if not recebido or not secrets.compare_digest(recebido, esperado):
            abort(400, description='Formulário expirado. Recarregue a página e tente novamente.')


# Calcula a data limite para quem já completou 18 anos
def limite_nascimento():
    hoje = date.today()
    dia = hoje.day
    if hoje.month == 2 and dia == 29:
        dia = 28
    return date(hoje.year - 18, hoje.month, dia)


# Confere os dados recebidos do formulário de usuário
def ler_pessoa(form):
    nome = form.get('nome', '').strip()
    email = form.get('email', '').strip().lower()
    telefone = form.get('telefone', '').strip()
    telefone = telefone.replace('(', '').replace(')', '').replace('-', '').replace(' ', '')
    cpf = form.get('cpf', '').strip().replace('.', '').replace('-', '')
    nascimento = form.get('data_nascimento', '')
    partes_email = email.split('@')
    if len(partes_email) != 2 or not partes_email[0] or not partes_email[1]:
        raise ValueError('Informe nome e e-mail válidos.')
    dominio = partes_email[1].split('.')
    if len(dominio) < 2 or '' in dominio:
        raise ValueError('Informe nome e e-mail válidos.')
    for letra in email:
        if letra.isspace():
            raise ValueError('O e-mail não pode conter espaços.')
    if not nome or len(nome) > 254 or len(email) > 100:
        raise ValueError('Informe nome e e-mail válidos.')
    if len(telefone) not in (10, 11) or not telefone.isascii() or not telefone.isdigit():
        raise ValueError('Informe o telefone com DDD: 10 ou 11 números.')
    if len(cpf) != 11 or not cpf.isascii() or not cpf.isdigit():
        raise ValueError('O CPF deve conter exatamente 11 números.')
    if not nascimento:
        raise ValueError('Informe a data de nascimento.')
    try:
        nascimento = date.fromisoformat(nascimento)
    except ValueError:
        raise ValueError('Data de nascimento inválida.')
    if nascimento > date.today():
        raise ValueError('A data de nascimento não pode ser futura.')
    if nascimento > limite_nascimento():
        raise ValueError('É necessário ter pelo menos 18 anos completos para se cadastrar.')
    return (nome, email, telefone, cpf, nascimento)


# Confere a força da nova senha e as três senhas anteriores
def validar_nova_senha(con, id_usuario, senha):
    if not senha_forte(senha):
        raise ValueError(
            'Use pelo menos 8 caracteres, maiúscula, minúscula, número e símbolo (até 72 bytes).'
        )
    if id_usuario:
        atual = consultar(
            con, 'SELECT SENHA FROM USUARIOS WHERE ID_USUARIO=?', (id_usuario,), True
        )
        if atual and conferir_senha(atual['senha'], senha):
            raise ValueError(
                'Você não pode repetir a senha atual ou as três últimas senhas.'
            )
        ultimas = consultar(
            con,
            '''
                SELECT FIRST 3 SENHA
                FROM HISTORICO_SENHAS
                WHERE ID_USUARIO=?
                ORDER BY ID_HISTORICO DESC
            ''',
            (id_usuario,),
        )
        for registro in ultimas:
            if conferir_senha(registro['senha'], senha):
                raise ValueError('Você não pode repetir as três últimas senhas.')
    return gerar_hash(senha)


# Guarda a senha antiga no histórico, sempre protegida
def guardar_senha(con, id_usuario, hash_senha):
    cursor = con.cursor()
    cursor.execute(
        'INSERT INTO HISTORICO_SENHAS (ID_USUARIO, SENHA) VALUES (?, ?)',
        (id_usuario, hash_senha),
    )


# Abre a página inicial do site
@app.route('/')
def index():
    return render_template(
        'landing.html',
        usuario=None,
        perfis=PERFIS,
        csrf_token=token_formulario(),
    )


# Cadastra uma nova conta de aluno
@app.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    conferir_formulario()
    if request.method == 'POST':
        try:
            # Confere os dados informados
            nome, email, telefone, cpf, nascimento = ler_pessoa(request.form)
            senha = request.form.get('senha', '')
            if senha != request.form.get('confirmar_senha'):
                raise ValueError('As senhas não coincidem.')
            con = conectar()
            try:
                if consultar(
                    con,
                    'SELECT ID_USUARIO FROM USUARIOS WHERE LOWER(TRIM(EMAIL))=?',
                    (email,),
                    True,
                ):
                    raise ValueError('Este e-mail já está cadastrado.')
                hash_senha = validar_nova_senha(con, None, senha)
                cursor = con.cursor()

                # Cadastra o usuário
                cursor.execute(
                    '''
                    INSERT INTO USUARIOS (
                        NOME, EMAIL, TELEFONE, CPF, DATA_NASCIMENTO,
                        SENHA, TIPO_USUARIO, ATIVO, BLOQUEADO, TENTATIVAS_LOGIN
                    )
                    VALUES (?, ?, ?, ?, ?, ?, 'ALUNO', 1, 0, 0)
                    ''',
                    (nome, email, telefone, cpf, nascimento, hash_senha),
                )

                con.commit()
            except Exception:
                con.rollback()
                raise
            finally:
                con.close()
            flash('Cadastro realizado com sucesso! Faça seu login.', 'sucesso')
            return redirect(url_for('login'))
        except ValueError as erro:
            flash(str(erro), 'erro')
        except fdb.IntegrityError:
            flash('Este e-mail ou CPF já está cadastrado.', 'erro')
        except fdb.DatabaseError as erro:
            print('Erro no cadastro:', erro)
            flash(mensagem_firebird(erro), 'erro')
    return render_template(
        'cadastro.html',
        nascimento_maximo=limite_nascimento().isoformat(),
        usuario=None,
        perfis=PERFIS,
        csrf_token=token_formulario(),
    )


# Faz o login e bloqueia a conta após três erros
@app.route('/login', methods=['GET', 'POST'])
def login():
    conferir_formulario()
    if request.method == 'POST':
        # Recebe o e-mail e a senha
        email = request.form.get('email', '').strip().lower()
        senha = request.form.get('senha', '')
        con = conectar()
        try:
            # Busca o usuário no banco
            usuario = consultar(
                con,
                'SELECT * FROM USUARIOS WHERE LOWER(TRIM(EMAIL))=? WITH LOCK',
                (email,),
                True,
            )
            if not usuario:
                flash('E-mail ou senha incorretos.', 'erro')
            elif not usuario['ativo']:
                flash('Usuário inativo.', 'erro')
            elif usuario['bloqueado']:
                flash('Usuário bloqueado. Procure o administrador.', 'erro')
            elif conferir_senha(usuario['senha'], senha):
                cursor = con.cursor()
                cursor.execute(
                    'UPDATE USUARIOS SET TENTATIVAS_LOGIN=0 WHERE ID_USUARIO=?',
                    (usuario['id_usuario'],),
                )
                session.clear()
                session['id_usuario'] = usuario['id_usuario']
                con.commit()
                return redirect(url_for('voltar_home'))
            else:
                tentativas = (usuario['tentativas_login'] or 0) + 1
                cursor = con.cursor()
                cursor.execute(
                    '''
                        UPDATE USUARIOS
                        SET TENTATIVAS_LOGIN=?,
                            BLOQUEADO=?
                        WHERE ID_USUARIO=?
                    ''',
                    (tentativas, int(tentativas >= 3), usuario['id_usuario']),
                )
                if tentativas >= 3:
                    flash('Usuário bloqueado após 3 tentativas erradas.', 'erro')
                else:
                    flash('E-mail ou senha incorretos. Restam ' + str(3 - tentativas) + ' tentativas.', 'erro')
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()
    return render_template(
        'login.html',
        usuario=None,
        perfis=PERFIS,
        csrf_token=token_formulario(),
    )


# Encerra a sessão da conta
@app.route('/logout', methods=['POST'])
def logout():
    # Confere quem está conectado
    usuario = usuario_logado()
    if usuario is None:
        return redirect(url_for('login'))
    conferir_formulario()

    session.clear()
    flash('Você saiu da sua conta.', 'sucesso')
    return redirect(url_for('login'))


# Abre a página inicial do perfil conectado
@app.route('/minha-home')
def voltar_home():
    # Confere quem está conectado
    usuario = usuario_logado()
    if usuario is None:
        return redirect(url_for('login'))

    if usuario['tipo_usuario'] == 'ALUNO':
        return redirect(url_for('aluno'))
    if usuario['tipo_usuario'] == 'PERSONAL':
        return redirect(url_for('personal'))
    if usuario['tipo_usuario'] == 'ADMINISTRADOR':
        return redirect(url_for('administrador'))
    session.clear()
    return redirect(url_for('login'))


# Consulta as aulas com a modalidade, o professor e as vagas
AULAS_SQL = '''
    SELECT A.*,
           M.NOME AS MODALIDADE,
           U.NOME AS PROFESSOR,
        (SELECT COUNT(*)
         FROM INSCRICOES I
         WHERE I.ID_AULA=A.ID_AULA
             AND I.ATIVA=1) AS INSCRITOS
    FROM AULAS A
    JOIN MODALIDADES M ON M.ID_MODALIDADE=A.ID_MODALIDADE
    JOIN USUARIOS U ON U.ID_USUARIO=A.ID_PROFESSOR
'''


# Mostra o início do administrador
@app.route('/administrador')
def administrador():
    # Confere quem está conectado
    usuario = usuario_logado()
    if usuario is None:
        return redirect(url_for('login'))
    if usuario['tipo_usuario'] != 'ADMINISTRADOR':
        abort(403)

    con = conectar()
    try:
        contagens = {}
        for tipo in ('ALUNO', 'PERSONAL'):
            resultado = consultar(
                con,
                'SELECT COUNT(*) AS TOTAL FROM USUARIOS WHERE TIPO_USUARIO=?',
                (tipo,),
                True,
            )
            contagens[tipo] = resultado['total']
        modalidades = consultar(
            con, 'SELECT COUNT(*) AS TOTAL FROM MODALIDADES', unico=True
        )['total']
        aulas = consultar(
            con,
            AULAS_SQL
            + " WHERE A.DATA_AULA>=CURRENT_DATE AND A.SITUACAO='AGENDADA' ORDER BY A.DATA_AULA, A.HORA_INICIO",
        )
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()
    return render_template(
        'dashboard.html',
        usuario=usuario,
        perfis=PERFIS,
        csrf_token=token_formulario(),
        contagens=contagens,
        modalidades=modalidades,
        aulas=aulas,
        hoje=date.today(),
    )


# Mostra a grade de aulas disponíveis para o aluno
@app.route('/aluno')
def aluno():
    # Confere quem está conectado
    usuario = usuario_logado()
    if usuario is None:
        return redirect(url_for('login'))
    if usuario['tipo_usuario'] != 'ALUNO':
        abort(403)

    con = conectar()
    try:
        aulas = consultar(
            con,
            AULAS_SQL
            + " WHERE A.DATA_AULA>=CURRENT_DATE AND A.SITUACAO='AGENDADA' AND M.ATIVA=1 ORDER BY A.DATA_AULA, A.HORA_INICIO",
        )
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()
    return render_template(
        'grade.html',
        usuario=usuario,
        perfis=PERFIS,
        csrf_token=token_formulario(),
        aulas=aulas,
    )


# Mostra o início do professor
@app.route('/personal')
def personal():
    # Confere quem está conectado
    usuario = usuario_logado()
    if usuario is None:
        return redirect(url_for('login'))
    if usuario['tipo_usuario'] != 'PERSONAL':
        abort(403)

    con = conectar()
    try:
        aulas = consultar(
            con,
            AULAS_SQL
            + ' WHERE A.ID_PROFESSOR=? ORDER BY A.DATA_AULA DESC, A.HORA_INICIO',
            (usuario['id_usuario'],),
        )
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()
    return render_template(
        'personal.html',
        usuario=usuario,
        perfis=PERFIS,
        csrf_token=token_formulario(),
        aulas=aulas,
        hoje=date.today(),
    )


# Lista as aulas do professor conectado
@app.route('/agenda')
def agenda():
    # Confere quem está conectado
    usuario = usuario_logado()
    if usuario is None:
        return redirect(url_for('login'))
    if usuario['tipo_usuario'] != 'PERSONAL':
        abort(403)

    con = conectar()
    try:
        aulas = consultar(
            con,
            AULAS_SQL + ' WHERE A.ID_PROFESSOR=? ORDER BY A.DATA_AULA,A.HORA_INICIO',
            (usuario['id_usuario'],),
        )
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()
    return render_template(
        'aulas.html',
        usuario=usuario,
        perfis=PERFIS,
        csrf_token=token_formulario(),
        aulas=aulas,
        titulo='Minha Agenda e Aulas',
    )


# Seleciona uma aula do professor para registrar a chamada
@app.route('/presencas')
def presencas():
    # Confere quem está conectado
    usuario = usuario_logado()
    if usuario is None:
        return redirect(url_for('login'))
    if usuario['tipo_usuario'] != 'PERSONAL':
        abort(403)

    con = conectar()
    try:
        aulas = consultar(
            con,
            AULAS_SQL
            + ' WHERE A.ID_PROFESSOR=? ORDER BY A.DATA_AULA DESC,A.HORA_INICIO',
            (usuario['id_usuario'],),
        )
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()
    return render_template(
        'aulas.html',
        usuario=usuario,
        perfis=PERFIS,
        csrf_token=token_formulario(),
        aulas=aulas,
        titulo='Selecionar aula para chamada',
    )


# Mostra os dados da própria conta
@app.route('/perfil')
def perfil():
    # Confere quem está conectado
    usuario = usuario_logado()
    if usuario is None:
        return redirect(url_for('login'))

    titulo = 'Meu Perfil'
    if usuario['tipo_usuario'] == 'ADMINISTRADOR':
        titulo = 'Minha conta'
    return render_template(
        'perfil.html',
        usuario=usuario,
        perfis=PERFIS,
        csrf_token=token_formulario(),
        titulo=titulo,
    )


# Edita os dados pessoais sem alterar o código do usuário
@app.route('/editar-dados', methods=['GET', 'POST'])
def editar_dados():
    # Confere quem está conectado
    usuario = usuario_logado()
    if usuario is None:
        return redirect(url_for('login'))
    conferir_formulario()

    if request.method == 'POST':
        try:
            # Confere os dados informados
            valores = ler_pessoa(request.form)
            con = conectar()
            try:
                if consultar(
                    con,
                    '''
                        SELECT ID_USUARIO
                        FROM USUARIOS
                        WHERE LOWER(TRIM(EMAIL))=?
                            AND ID_USUARIO<>?
                    ''',
                    (valores[1], usuario['id_usuario']),
                    True,
                ):
                    raise ValueError('Este e-mail já está cadastrado.')
                cursor = con.cursor()
                cursor.execute(
                    '''
                        UPDATE USUARIOS
                        SET NOME=?,
                            EMAIL=?,
                            TELEFONE=?,
                            CPF=?,
                            DATA_NASCIMENTO=?
                        WHERE ID_USUARIO=?
                    ''',
                    (valores[0], valores[1], valores[2], valores[3], valores[4], usuario['id_usuario']),
                )
                con.commit()
            except Exception:
                con.rollback()
                raise
            finally:
                con.close()
            flash('Dados atualizados com sucesso!', 'sucesso')
            return redirect(url_for('perfil'))
        except ValueError as erro:
            flash(str(erro), 'erro')
        except fdb.IntegrityError:
            flash('E-mail ou CPF já cadastrado.', 'erro')
    return render_template(
        'usuario_form.html',
        nascimento_maximo=limite_nascimento().isoformat(),
        usuario=usuario,
        perfis=PERFIS,
        csrf_token=token_formulario(),
        pessoa=usuario,
        proprio=True,
        titulo='Editar meus dados',
    )


# Confere a senha atual e grava a nova senha protegida
@app.route('/alterar-senha', methods=['GET', 'POST'])
def alterar_senha():
    # Confere quem está conectado
    usuario = usuario_logado()
    if usuario is None:
        return redirect(url_for('login'))
    conferir_formulario()

    if request.method == 'POST':
        try:
            if not conferir_senha(
                usuario['senha'], request.form.get('senha_atual', '')
            ):
                raise ValueError('A senha atual está incorreta.')
            nova = request.form.get('nova_senha', '')
            if nova != request.form.get('confirmar', ''):
                raise ValueError('As novas senhas não coincidem.')
            con = conectar()
            try:
                hash_senha = validar_nova_senha(con, usuario['id_usuario'], nova)
                guardar_senha(con, usuario['id_usuario'], usuario['senha'])
                cursor = con.cursor()
                cursor.execute(
                    'UPDATE USUARIOS SET SENHA=? WHERE ID_USUARIO=?',
                    (hash_senha, usuario['id_usuario']),
                )
                con.commit()
            except Exception:
                con.rollback()
                raise
            finally:
                con.close()
            flash('Senha alterada com sucesso!', 'sucesso')
            return redirect(url_for('perfil'))
        except ValueError as erro:
            flash(str(erro), 'erro')
    return render_template(
        'alterar_senha.html',
        usuario=usuario,
        perfis=PERFIS,
        csrf_token=token_formulario(),
    )


# Lista os usuários do perfil selecionado
@app.route('/usuarios')
def usuarios():
    # Confere quem está conectado
    usuario = usuario_logado()
    if usuario is None:
        return redirect(url_for('login'))
    if usuario['tipo_usuario'] != 'ADMINISTRADOR':
        abort(403)

    filtro = request.args.get('perfil', 'ALUNO')
    if filtro not in PERFIS:
        abort(400)
    con = conectar()
    try:
        pessoas = consultar(
            con, 'SELECT * FROM USUARIOS WHERE TIPO_USUARIO=? ORDER BY NOME', (filtro,)
        )
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()
    return render_template(
        'usuarios.html',
        usuario=usuario,
        perfis=PERFIS,
        csrf_token=token_formulario(),
        pessoas=pessoas,
        filtro=filtro,
        titulo={'ALUNO': 'Alunos', 'PERSONAL': 'Professores', 'ADMINISTRADOR': 'Administradores'}[filtro],
    )


# Cadastra ou edita usuários na área do administrador
@app.route('/usuarios/novo', methods=['GET', 'POST'])
@app.route('/usuarios/<int:id_usuario>/editar', methods=['GET', 'POST'])
def usuario_form(id_usuario=None):
    # Confere quem está conectado
    usuario = usuario_logado()
    if usuario is None:
        return redirect(url_for('login'))
    if usuario['tipo_usuario'] != 'ADMINISTRADOR':
        abort(403)
    conferir_formulario()

    con = conectar()
    try:
        pessoa = {}
        if id_usuario:
            pessoa = consultar(
                con, 'SELECT * FROM USUARIOS WHERE ID_USUARIO=?', (id_usuario,), True
            )
        if id_usuario and (not pessoa):
            abort(404)
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()
    if request.method == 'POST':
        try:
            # Confere os dados informados
            valores = ler_pessoa(request.form)
            tipo = request.form.get('tipo_usuario', 'ALUNO')
            if tipo not in PERFIS:
                raise ValueError('Perfil de usuário inválido.')
            ativo = int(request.form.get('ativo', '0') == '1')
            bloqueado = int(request.form.get('bloqueado', '0') == '1')
            try:
                tentativas = int(request.form.get('tentativas_login', '0'))
            except ValueError:
                raise ValueError('Tentativas de login inválidas.')
            if not 0 <= tentativas <= 2147483647:
                raise ValueError('Tentativas de login inválidas.')
            senha = request.form.get('senha', '')
            con = conectar()
            try:
                if consultar(
                    con,
                    '''
                        SELECT ID_USUARIO
                        FROM USUARIOS
                        WHERE LOWER(TRIM(EMAIL))=?
                            AND ID_USUARIO<>?
                    ''',
                    (valores[1], id_usuario or 0),
                    True,
                ):
                    raise ValueError('Este e-mail já está cadastrado.')
                if senha or not id_usuario:
                    hash_senha = validar_nova_senha(con, id_usuario, senha)
                else:
                    hash_senha = pessoa['senha']
                if id_usuario:
                    cursor = con.cursor()
                    cursor.execute(
                        '''
                            UPDATE USUARIOS
                            SET NOME=?,
                                EMAIL=?,
                                TELEFONE=?,
                                CPF=?,
                                DATA_NASCIMENTO=?,
                                TIPO_USUARIO=?,
                                ATIVO=?,
                                BLOQUEADO=?,
                                TENTATIVAS_LOGIN=?,
                                SENHA=?
                            WHERE ID_USUARIO=?
                        ''',
                        (
                            valores[0], valores[1], valores[2], valores[3], valores[4],
                            tipo,
                            ativo,
                            bloqueado,
                            tentativas,
                            hash_senha,
                            id_usuario,
                        ),
                    )
                    if senha:
                        guardar_senha(con, id_usuario, pessoa['senha'])
                else:
                    cursor = con.cursor()
                    cursor.execute(
                        '''
                            INSERT INTO USUARIOS (NOME, EMAIL, TELEFONE, CPF, DATA_NASCIMENTO, TIPO_USUARIO, ATIVO, BLOQUEADO, TENTATIVAS_LOGIN, SENHA)
                            VALUES (?,?,?,?,?,?,?,?,?,?) RETURNING ID_USUARIO
                        ''',
                        (
                            valores[0],
                            valores[1],
                            valores[2],
                            valores[3],
                            valores[4],
                            tipo,
                            ativo,
                            bloqueado,
                            tentativas,
                            hash_senha,
                        ),
                    )
                    id_usuario = cursor.fetchone()[0]
                con.commit()
            except Exception:
                con.rollback()
                raise
            finally:
                con.close()
            flash('Usuário salvo com sucesso!', 'sucesso')
            return redirect(url_for('usuarios', perfil=tipo))
        except ValueError as erro:
            flash(str(erro), 'erro')
        except fdb.IntegrityError:
            flash('Este e-mail ou CPF já está cadastrado.', 'erro')
    titulo = 'Cadastrar usuário'
    if id_usuario:
        titulo = 'Editar usuário'
    return render_template(
        'usuario_form.html',
        nascimento_maximo=limite_nascimento().isoformat(),
        usuario=usuario,
        perfis=PERFIS,
        csrf_token=token_formulario(),
        pessoa=pessoa,
        proprio=False,
        titulo=titulo,
    )


# Lista as modalidades ativas e inativas
@app.route('/modalidades')
def modalidades():
    # Confere quem está conectado
    usuario = usuario_logado()
    if usuario is None:
        return redirect(url_for('login'))
    if usuario['tipo_usuario'] != 'ADMINISTRADOR':
        abort(403)

    con = conectar()
    try:
        lista = consultar(
            con,
            '''
                SELECT M.*,
                    (SELECT COUNT(*)
                     FROM AULAS A
                     WHERE A.ID_MODALIDADE=M.ID_MODALIDADE) AS TOTAL_AULAS
                FROM MODALIDADES M
                ORDER BY M.NOME
            ''',
        )
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()
    return render_template(
        'modalidades.html',
        usuario=usuario,
        perfis=PERFIS,
        csrf_token=token_formulario(),
        modalidades=lista,
    )


# Cadastra ou edita uma modalidade sem repetir o nome
@app.route('/modalidades/nova', methods=['GET', 'POST'])
@app.route('/modalidades/<int:id_modalidade>/editar', methods=['GET', 'POST'])
def modalidade_form(id_modalidade=None):
    # Confere quem está conectado
    usuario = usuario_logado()
    if usuario is None:
        return redirect(url_for('login'))
    if usuario['tipo_usuario'] != 'ADMINISTRADOR':
        abort(403)
    conferir_formulario()

    con = conectar()
    try:
        item = {}
        if id_modalidade:
            item = consultar(
                con, 'SELECT * FROM MODALIDADES WHERE ID_MODALIDADE=?', (id_modalidade,), True
            )
        if id_modalidade and (not item):
            abort(404)
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()
    if request.method == 'POST':
        nome = request.form.get('nome', '').strip()
        descricao = request.form.get('descricao', '').strip()
        try:
            try:
                duracao = int(request.form.get('duracao', '0'))
            except ValueError:
                raise ValueError(
                    'Duração inválida. Informe um número inteiro de minutos.'
                )
            if (
                not nome
                or len(nome) > 100
                or (not descricao)
                or (len(descricao) > 500)
                or (not 0 < duracao <= 2147483647)
            ):
                raise ValueError('Preencha nome, descrição e duração maior que zero.')
            con = conectar()
            try:
                if consultar(
                    con,
                    '''
                        SELECT ID_MODALIDADE
                        FROM MODALIDADES
                        WHERE LOWER(TRIM(NOME))=?
                            AND ID_MODALIDADE<>?
                    ''',
                    (nome.lower(), id_modalidade or 0),
                    True,
                ):
                    raise ValueError('Modalidade já existe.')
                valores = (
                    nome,
                    descricao,
                    duracao,
                    int(request.form.get('ativa', '1') == '1'),
                )
                if id_modalidade:
                    cursor = con.cursor()
                    cursor.execute(
                        '''
                            UPDATE MODALIDADES
                            SET NOME=?,
                                DESCRICAO=?,
                                DURACAO=?,
                                ATIVA=?
                            WHERE ID_MODALIDADE=?
                        ''',
                        (valores[0], valores[1], valores[2], valores[3], id_modalidade),
                    )
                else:
                    cursor = con.cursor()
                    cursor.execute(
                        '''
                            INSERT INTO MODALIDADES (NOME, DESCRICAO, DURACAO, ATIVA)
                            VALUES (?,?,?,?)
                        ''',
                        valores,
                    )
                con.commit()
            except Exception:
                con.rollback()
                raise
            finally:
                con.close()
            flash('Modalidade salva com sucesso!', 'sucesso')
            return redirect(url_for('modalidades'))
        except ValueError as erro:
            flash(str(erro), 'erro')
        except fdb.IntegrityError:
            flash('Modalidade já existe.', 'erro')
    titulo = 'Nova modalidade'
    if id_modalidade:
        titulo = 'Editar Modalidade'
    return render_template(
        'modalidade_form.html',
        usuario=usuario,
        perfis=PERFIS,
        csrf_token=token_formulario(),
        item=item,
        titulo=titulo,
    )


# Exclui a modalidade somente se ela não tiver aulas vinculadas
@app.route('/modalidades/<int:id_modalidade>/excluir', methods=['GET', 'POST'])
def modalidade_excluir(id_modalidade):
    # Confere quem está conectado
    usuario = usuario_logado()
    if usuario is None:
        return redirect(url_for('login'))
    if usuario['tipo_usuario'] != 'ADMINISTRADOR':
        abort(403)
    conferir_formulario()

    con = conectar()
    try:
        item = consultar(
            con,
            'SELECT * FROM MODALIDADES WHERE ID_MODALIDADE=?',
            (id_modalidade,),
            True,
        )
        if not item:
            abort(404)
        if request.method == 'POST':
            if consultar(
                con,
                'SELECT FIRST 1 ID_AULA FROM AULAS WHERE ID_MODALIDADE=?',
                (id_modalidade,),
                True,
            ):
                con.commit()
                flash('Não é possível excluir: a modalidade possui aulas vinculadas.', 'erro')
                return redirect(url_for('modalidades'))
            cursor = con.cursor()
            cursor.execute(
                'DELETE FROM MODALIDADES WHERE ID_MODALIDADE=?', (id_modalidade,)
            )
            flash('Modalidade excluída com sucesso!', 'sucesso')
            con.commit()
            return redirect(url_for('modalidades'))
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()
    return render_template(
        'confirmar.html',
        usuario=usuario,
        perfis=PERFIS,
        csrf_token=token_formulario(),
        titulo='Excluir modalidade',
        mensagem=f"Excluir a modalidade {item['nome']}? Esta ação não pode ser desfeita.",
        voltar=url_for('modalidades'),
        botao='Excluir modalidade',
    )


# Lista as aulas cadastradas
@app.route('/aulas')
def aulas():
    # Confere quem está conectado
    usuario = usuario_logado()
    if usuario is None:
        return redirect(url_for('login'))
    if usuario['tipo_usuario'] != 'ADMINISTRADOR':
        abort(403)

    con = conectar()
    try:
        lista = consultar(con, AULAS_SQL + ' ORDER BY A.DATA_AULA DESC,A.HORA_INICIO')
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()
    return render_template(
        'aulas.html',
        usuario=usuario,
        perfis=PERFIS,
        csrf_token=token_formulario(),
        aulas=lista,
        titulo='Aulas',
    )


# Confere o horário digitado no formato HH:MM, de 00:00 a 23:59.
def ler_horario(valor):
    if len(valor) != 5 or valor[2] != ':':
        raise ValueError('Informe o horário no formato HH:MM.')
    horas = valor[:2]
    minutos = valor[3:]
    if not horas.isdigit() or not minutos.isdigit():
        raise ValueError('Informe um horário válido.')
    if int(horas) > 23 or int(minutos) > 59:
        raise ValueError('Informe um horário entre 00:00 e 23:59.')
    return valor


# Confere modalidade, professor, horário e capacidade da aula
def validar_aula(con, id_aula=None):
    try:
        nome = request.form.get('nome', '').strip()
        modalidade = int(request.form.get('id_modalidade', '0'))
        professor = int(request.form.get('id_professor', '0'))
        dia = date.fromisoformat(request.form.get('data_aula', ''))
        inicio = ler_horario(request.form.get('hora_inicio', ''))
        fim = ler_horario(request.form.get('hora_fim', ''))
        capacidade = int(request.form.get('capacidade', '0'))
        local = request.form.get('local', '').strip()
    except ValueError:
        raise ValueError('Preencha data, horários e números válidos.')
    if not 0 < modalidade <= 2147483647 or not 0 < professor <= 2147483647:
        raise ValueError('Selecione uma modalidade e um professor válidos.')
    if not nome or len(nome) > 100 or (not local) or (len(local) > 100):
        raise ValueError('Preencha nome da aula e local.')
    if not 0 < capacidade <= 2147483647:
        raise ValueError(
            'Capacidade inválida. Informe um número inteiro maior que zero.'
        )
    if fim <= inicio:
        raise ValueError('O horário de término deve ser maior que o horário de início.')
    if not consultar(
        con,
        '''
            SELECT ID_MODALIDADE
            FROM MODALIDADES
            WHERE ID_MODALIDADE=?
                AND ATIVA=1
        ''',
        (modalidade,),
        True,
    ):
        raise ValueError('Selecione uma modalidade cadastrada e ativa.')
    if not consultar(
        con,
        '''
            SELECT ID_USUARIO
            FROM USUARIOS
            WHERE ID_USUARIO=?
                AND TIPO_USUARIO='PERSONAL'
                AND ATIVO=1
        ''',
        (professor,),
        True,
    ):
        raise ValueError('Instrutor não permitido. Selecione um Professor ativo.')
    consultar(
        con,
        'SELECT ID_USUARIO FROM USUARIOS WHERE ID_USUARIO=? WITH LOCK',
        (professor,),
        True,
    )
    if consultar(
        con,
        '''
            SELECT ID_AULA
            FROM AULAS
            WHERE ID_PROFESSOR=?
                AND DATA_AULA=?
                AND HORA_INICIO<?
                AND HORA_FIM>?
                AND SITUACAO='AGENDADA'
                AND ID_AULA<>?
        ''',
        (professor, dia, fim, inicio, id_aula or 0),
        True,
    ):
        raise ValueError('O professor já possui aula nesse dia e horário.')
    if id_aula:
        total = consultar(
            con,
            '''
                SELECT COUNT(*) AS TOTAL
                FROM INSCRICOES
                WHERE ID_AULA=?
                    AND ATIVA=1
            ''',
            (id_aula,),
            True,
        )['total']
        if capacidade < total:
            raise ValueError('Capacidade inválida: inferior ao número de inscritos.')
    return (nome, modalidade, professor, dia, inicio, fim, capacidade, local)


# Cadastra ou edita os dados da aula
@app.route('/aulas/nova', methods=['GET', 'POST'])
@app.route('/aulas/<int:id_aula>/editar', methods=['GET', 'POST'])
def aula_form(id_aula=None):
    # Confere quem está conectado
    usuario = usuario_logado()
    if usuario is None:
        return redirect(url_for('login'))
    if usuario['tipo_usuario'] != 'ADMINISTRADOR':
        abort(403)
    conferir_formulario()

    con = conectar()
    try:
        item = {}
        if id_aula:
            item = consultar(con, 'SELECT * FROM AULAS WHERE ID_AULA=?', (id_aula,), True)
        if id_aula and (not item):
            abort(404)
        modalidades_ativas = consultar(con, 'SELECT * FROM MODALIDADES WHERE ATIVA=1 ORDER BY NOME')
        professores = consultar(
            con,
            '''
                SELECT ID_USUARIO,
                       NOME
                FROM USUARIOS
                WHERE TIPO_USUARIO='PERSONAL'
                    AND ATIVO=1
                ORDER BY NOME
            ''',
        )
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()
    if request.method == 'POST':
        try:
            con = conectar()
            try:
                valores = validar_aula(con, id_aula)
                if id_aula:
                    cursor = con.cursor()
                    cursor.execute(
                        '''
                            UPDATE AULAS
                            SET NOME=?,
                                ID_MODALIDADE=?,
                                ID_PROFESSOR=?,
                                DATA_AULA=?,
                                HORA_INICIO=?,
                                HORA_FIM=?,
                                CAPACIDADE=?,
                                LOCAL_AULA=?
                            WHERE ID_AULA=?
                        ''',
                        (
                            valores[0],
                            valores[1],
                            valores[2],
                            valores[3],
                            valores[4],
                            valores[5],
                            valores[6],
                            valores[7],
                            id_aula,
                        ),
                    )
                else:
                    cursor = con.cursor()
                    cursor.execute(
                        '''
                            INSERT INTO AULAS (NOME, ID_MODALIDADE, ID_PROFESSOR, DATA_AULA, HORA_INICIO, HORA_FIM, CAPACIDADE, LOCAL_AULA)
                            VALUES (?,?,?,?,?,?,?,?)
                        ''',
                        valores,
                    )
                con.commit()
            except Exception:
                con.rollback()
                raise
            finally:
                con.close()
            flash('Aula salva com sucesso!', 'sucesso')
            return redirect(url_for('aulas'))
        except ValueError as erro:
            flash(str(erro), 'erro')
        except fdb.DatabaseError as erro:
            print('Erro ao salvar aula:', erro)
            flash(
                'Não foi possível salvar: confira modalidade ativa, professor, horários e capacidade.',
                'erro',
            )
    titulo = 'Criar aula'
    if id_aula:
        titulo = 'Editar aula'
    return render_template(
        'aula_form.html',
        usuario=usuario,
        perfis=PERFIS,
        csrf_token=token_formulario(),
        item=item,
        modalidades=modalidades_ativas,
        professores=professores,
        titulo=titulo,
    )


# Busca a aula e confere se o professor pode acessá-la
def obter_aula(con, id_aula, usuario):
    aula = consultar(con, AULAS_SQL + ' WHERE A.ID_AULA=?', (id_aula,), True)
    if not aula:
        abort(404)
    if (
        usuario['tipo_usuario'] == 'PERSONAL'
        and aula['id_professor'] != usuario['id_usuario']
    ):
        abort(403)
    return aula


# Mostra os detalhes e as vagas da aula
@app.route('/aulas/<int:id_aula>')
def aula_detalhes(id_aula):
    # Confere quem está conectado
    usuario = usuario_logado()
    if usuario is None:
        return redirect(url_for('login'))

    con = conectar()
    try:
        aula = obter_aula(con, id_aula, usuario)
        inscricao = consultar(
            con,
            '''
                SELECT *
                FROM INSCRICOES
                WHERE ID_AULA=?
                    AND ID_USUARIO=?
                    AND ATIVA=1
            ''',
            (id_aula, usuario['id_usuario']),
            True,
        )
        inscritos = []
        if usuario['tipo_usuario'] != 'ALUNO':
            inscritos = consultar(
                con,
                '''
                    SELECT I.*, U.NOME
                    FROM INSCRICOES I
                    JOIN USUARIOS U ON U.ID_USUARIO=I.ID_USUARIO
                    WHERE I.ID_AULA=? AND I.ATIVA=1
                    ORDER BY U.NOME
                ''',
                (id_aula,),
            )
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()
    return render_template(
        'aula_detalhes.html',
        usuario=usuario,
        perfis=PERFIS,
        csrf_token=token_formulario(),
        aula=aula,
        inscricao=inscricao,
        inscritos=inscritos,
        hoje=date.today(),
    )


# Cancela a aula preservando os dados já registrados
@app.route('/aulas/<int:id_aula>/cancelar', methods=['GET', 'POST'])
def aula_cancelar(id_aula):
    # Confere quem está conectado
    usuario = usuario_logado()
    if usuario is None:
        return redirect(url_for('login'))
    if usuario['tipo_usuario'] != 'ADMINISTRADOR':
        abort(403)
    conferir_formulario()

    con = conectar()
    try:
        aula = obter_aula(con, id_aula, usuario)
        if request.method == 'POST':
            cursor = con.cursor()
            cursor.execute(
                "UPDATE AULAS SET SITUACAO='CANCELADA' WHERE ID_AULA=?", (id_aula,)
            )
            flash('Aula cancelada. O histórico foi preservado.', 'sucesso')
            con.commit()
            return redirect(url_for('aulas'))
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()
    return render_template(
        'confirmar.html',
        usuario=usuario,
        perfis=PERFIS,
        csrf_token=token_formulario(),
        titulo='Confirmar cancelamento da aula',
        mensagem=f"Cancelar a aula {aula['nome']}? O histórico será preservado.",
        voltar=url_for('aulas'),
        botao='Cancelar aula',
    )


# Inscreve o aluno somente quando houver vaga
@app.route('/aulas/<int:id_aula>/inscrever', methods=['POST'])
def inscrever(id_aula):
    # Confere quem está conectado
    usuario = usuario_logado()
    if usuario is None:
        return redirect(url_for('login'))
    if usuario['tipo_usuario'] != 'ALUNO':
        abort(403)
    conferir_formulario()

    try:
        con = conectar()
        try:
            consultar(
                con,
                'SELECT ID_AULA FROM AULAS WHERE ID_AULA=? WITH LOCK',
                (id_aula,),
                True,
            )
            aula = obter_aula(con, id_aula, usuario)
            if aula['situacao'] != 'AGENDADA' or aula['data_aula'] < date.today():
                raise ValueError('Inscrição indisponível para esta aula.')
            if not consultar(
                con,
                '''
                    SELECT ID_MODALIDADE
                    FROM MODALIDADES
                    WHERE ID_MODALIDADE=?
                        AND ATIVA=1
                ''',
                (aula['id_modalidade'],),
                True,
            ):
                raise ValueError('Modalidade inativa. Inscrição indisponível.')
            inscricao = consultar(
                con,
                'SELECT * FROM INSCRICOES WHERE ID_AULA=? AND ID_USUARIO=?',
                (id_aula, usuario['id_usuario']),
                True,
            )
            if inscricao and inscricao['ativa']:
                raise ValueError('Você já está inscrito nesta aula.')
            if aula['inscritos'] >= aula['capacidade']:
                raise ValueError('Aula lotada. Não há vagas disponíveis.')
            if inscricao:
                cursor = con.cursor()
                cursor.execute(
                    'UPDATE INSCRICOES SET ATIVA=1,PRESENTE=NULL WHERE ID_INSCRICAO=?',
                    (inscricao['id_inscricao'],),
                )
            else:
                cursor = con.cursor()
                cursor.execute(
                    'INSERT INTO INSCRICOES (ID_AULA,ID_USUARIO) VALUES (?,?)',
                    (id_aula, usuario['id_usuario']),
                )
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()
        flash('Inscrição realizada com sucesso!', 'sucesso')
    except ValueError as erro:
        flash(str(erro), 'erro')
    return redirect(url_for('minhas_aulas'))


# Lista as aulas em que o aluno está inscrito
@app.route('/minhas-aulas')
def minhas_aulas():
    # Confere quem está conectado
    usuario = usuario_logado()
    if usuario is None:
        return redirect(url_for('login'))
    if usuario['tipo_usuario'] != 'ALUNO':
        abort(403)

    con = conectar()
    try:
        aulas = consultar(
            con,
            AULAS_SQL
            + ' JOIN INSCRICOES IX ON IX.ID_AULA=A.ID_AULA WHERE IX.ID_USUARIO=? AND IX.ATIVA=1 ORDER BY A.DATA_AULA,A.HORA_INICIO',
            (usuario['id_usuario'],),
        )
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()
    return render_template(
        'minhas_aulas.html',
        usuario=usuario,
        perfis=PERFIS,
        csrf_token=token_formulario(),
        aulas=aulas,
    )


# Cancela a inscrição e libera a vaga
@app.route('/inscricoes/<int:id_aula>/cancelar', methods=['GET', 'POST'])
def cancelar_inscricao(id_aula):
    # Confere quem está conectado
    usuario = usuario_logado()
    if usuario is None:
        return redirect(url_for('login'))
    if usuario['tipo_usuario'] != 'ALUNO':
        abort(403)
    conferir_formulario()

    con = conectar()
    try:
        aula = obter_aula(con, id_aula, usuario)
        if not consultar(
            con,
            '''
                SELECT ID_INSCRICAO
                FROM INSCRICOES
                WHERE ID_AULA=?
                    AND ID_USUARIO=?
                    AND ATIVA=1
            ''',
            (id_aula, usuario['id_usuario']),
            True,
        ):
            abort(404)
        if request.method == 'POST':
            consultar(
                con,
                'SELECT ID_AULA FROM AULAS WHERE ID_AULA=? WITH LOCK',
                (id_aula,),
                True,
            )
            cursor = con.cursor()
            cursor.execute(
                'UPDATE INSCRICOES SET ATIVA=0 WHERE ID_AULA=? AND ID_USUARIO=?',
                (id_aula, usuario['id_usuario']),
            )
            flash('Inscrição cancelada com sucesso!', 'sucesso')
            con.commit()
            return redirect(url_for('minhas_aulas'))
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()
    return render_template(
        'confirmar.html',
        usuario=usuario,
        perfis=PERFIS,
        csrf_token=token_formulario(),
        titulo='Confirmar cancelamento da inscrição',
        mensagem=f"Cancelar sua inscrição em {aula['nome']}? A vaga será liberada.",
        voltar=url_for('minhas_aulas'),
        botao='Confirmar cancelamento',
    )


# Registra a presença dos alunos na aula
@app.route('/chamada/<int:id_aula>', methods=['GET', 'POST'])
def chamada(id_aula):
    # Confere quem está conectado
    usuario = usuario_logado()
    if usuario is None:
        return redirect(url_for('login'))
    if usuario['tipo_usuario'] not in ('ADMINISTRADOR', 'PERSONAL'):
        abort(403)
    conferir_formulario()

    con = conectar()
    try:
        aula = obter_aula(con, id_aula, usuario)
        inscritos = consultar(
            con,
            '''
                SELECT I.*,
                       U.NOME
                FROM INSCRICOES I
                JOIN USUARIOS U ON U.ID_USUARIO=I.ID_USUARIO
                WHERE I.ID_AULA=?
                    AND I.ATIVA=1
                ORDER BY U.NOME
            ''',
            (id_aula,),
        )
        if request.method == 'POST':
            for i in inscritos:
                valor = request.form.get(f"presenca_{i['id_inscricao']}", '')
                presente = None
                if valor in ('0', '1'):
                    presente = int(valor)
                cursor = con.cursor()
                cursor.execute(
                    'UPDATE INSCRICOES SET PRESENTE=? WHERE ID_INSCRICAO=?',
                    (presente, i['id_inscricao']),
                )
            flash('Chamada salva com sucesso!', 'sucesso')
            con.commit()
            return redirect(url_for('chamada', id_aula=id_aula))
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()
    return render_template(
        'chamada.html',
        usuario=usuario,
        perfis=PERFIS,
        csrf_token=token_formulario(),
        aula=aula,
        inscritos=inscritos,
    )


# Mostra uma página de erro sem abrir pop-ups
@app.errorhandler(403)
@app.errorhandler(404)
@app.errorhandler(400)
def pagina_erro(erro):
    pagina = render_template(
        'erro.html',
        usuario=None,
        perfis=PERFIS,
        csrf_token=token_formulario(),
        erro=erro,
    )
    return pagina, erro.code


# Mostra uma mensagem quando a operação no banco falha
@app.errorhandler(fdb.DatabaseError)
def erro_banco(erro):
    print('Erro no Firebird:', erro)
    codigo = 500
    descricao = 'Não foi possível concluir a operação no banco de dados. Confira o erro no terminal.'
    if 335544472 in erro.args:
        codigo = 503
        descricao = mensagem_firebird(erro)
    mensagem = {'code': codigo, 'description': descricao}
    return render_template(
        'erro.html',
        usuario=None,
        perfis=PERFIS,
        csrf_token=token_formulario(),
        erro=mensagem,
    ), codigo


# Inicia o sistema
if __name__ == '__main__':
    if preparar_conexao():
        app.run()
    else:
        raise SystemExit(1)
